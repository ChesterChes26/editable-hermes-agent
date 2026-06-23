# Memory System Architecture

## Overview

Hermes has a **dual memory architecture**: a built-in file-backed `MemoryStore` and an external plugin-based `MemoryProvider` system, managed independently. The two systems are NOT unified — `MemoryStore` is not a `MemoryProvider`.

## Key Files

| File | Role |
|------|------|
| `tools/memory_tool.py` | Built-in `MemoryStore` class + `memory` tool registration (~811 lines) |
| `agent/memory_provider.py` | Abstract `MemoryProvider` base class — contract for external plugins |
| `agent/memory_manager.py` | `MemoryManager` — orchestrates at most ONE external provider (~917 lines) |
| `agent/agent_init.py` | Memory initialization: lines 1110-1200 — wires both built-in and external |
| `plugins/memory/__init__.py` | Plugin discovery: `load_memory_provider()`, `discover_memory_providers()` |

## Built-in MemoryStore (`tools/memory_tool.py`)

Two file-backed stores under `$HERMES_HOME/memories/`:

- **MEMORY.md** — agent's personal notes (environment facts, conventions, lessons)
- **USER.md** — what agent knows about the user (preferences, style, habits)

### Data format
Entries delimited by `§` (section sign — `ENTRY_DELIMITER = "\n§\n"`). Entries can be multiline. Character limits, not token counts (model-independent).

```python
class MemoryStore:
    def __init__(self, memory_char_limit=2200, user_char_limit=1375): ...
```

### Frozen snapshot pattern (core invariant)
- `load_from_disk()` creates `_system_prompt_snapshot` at session start → injected into system prompt
- Mid-session tool writes (add/replace/remove) update disk + live `memory_entries` list, but **do NOT modify the snapshot**
- This preserves the prefix cache for the entire session — the system prompt block is stable
- Tool responses reflect live state; system prompt block reflects frozen state
- **Consequence**: memory written mid-session is NOT visible to agent until next session

### Injection scanning
Each entry is scanned at snapshot-build time via `tools/threat_patterns.py` (scope: `"strict"`). Blocked entries become `[BLOCKED: ...]` placeholders in snapshot only — the raw entry stays in live state so user can inspect and remove it via the `memory` tool.

### Concurrency safety
- `.lock` file (separate from data file) — `fcntl.flock` on Unix, `msvcrt.locking` on Windows
- External drift detection: before every mutation, `_reload_target()` re-reads from disk and compares against what would round-trip. If patch tool / shell append / sister session wrote non-§-delimited content, the mutation is REFUSED and a `.bak.<ts>` snapshot is saved (issue #26045)

### Deduplication
`add()` rejects exact-duplicate entries. `load_from_disk()` deduplicates via `dict.fromkeys()`.

### Nudge mechanism
Config `memory.nudge_interval` (default 10): after N turns without a memory write, the agent gets a prompt to consider writing. Counter: `agent._turns_since_memory`.

## External MemoryProvider Plugins

Abstract base class at `agent/memory_provider.py`:

```python
class MemoryProvider(ABC):
    @abstractmethod def name(self) -> str: ...
    @abstractmethod def is_available(self) -> bool: ...
    @abstractmethod def initialize(self, session_id, **kwargs): ...
    @abstractmethod def get_tool_schemas(self) -> List[Dict]: ...
    def system_prompt_block(self) -> str: ...   # optional
    def prefetch(self, query, *, session_id) -> str: ...  # optional
    def sync_turn(self, user, asst, *, session_id, messages): ...  # optional
    def handle_tool_call(self, tool_name, args, **kwargs) -> str: ...  # optional
    # Optional hooks: on_turn_start, on_session_end, on_session_switch,
    #                 on_pre_compress, on_memory_write, on_delegation
```

### Available bundled plugins (`plugins/memory/`)
honcho, hindsight, mem0, supermemory, retaindb, byterover, holographic, openviking

### Selection
Controlled by `memory.provider` in config.yaml. Empty string = no external provider.

### MemoryManager (`agent/memory_manager.py`)
Enforces **at most ONE** external provider. Registration logic:
```python
def add_provider(self, provider):
    if provider.name == "builtin": always accept
    if self._has_external: reject with warning
    self._has_external = True
```

External provider tools are injected into agent's tool surface via `inject_memory_provider_tools()` — gated by the `"memory"` toolset.

### Built-in → External mirroring
When the built-in `memory` tool writes, `MemoryManager.on_memory_write()` forwards to all external providers (skipping `name == "builtin"`). Three metadata-passing modes detected via `inspect.signature`: keyword, positional, legacy.

### Background executor
`sync_all()` and `queue_prefetch_all()` dispatch to a single-worker `ThreadPoolExecutor` (`mem-sync` thread). Rationale: a slow/wedged provider (observed ~298s for Hindsight daemon) must never block the turn — the agent returns to user immediately while sync happens off-thread. Drain timeout on shutdown: 5 seconds.

## Initialization Flow (`agent/agent_init.py` lines 1110-1200)

```
1. Read memory config (memory_enabled, user_profile_enabled, provider, limits)
2. If built-in enabled: create MemoryStore, call load_from_disk()
3. If external provider configured: 
   a. Create MemoryManager
   b. Load provider via plugins.memory.load_memory_provider(name)
   c. If available: add_provider(), initialize_all() with session_id + kwargs
4. inject_memory_provider_tools() → appends provider tool schemas
```

## Config Keys (`memory.*`)

| Key | Default | Description |
|-----|---------|-------------|
| `memory_enabled` | true | Enable MEMORY.md |
| `user_profile_enabled` | true | Enable USER.md |
| `provider` | "" | External provider name |
| `memory_char_limit` | 2200 | MEMORY.md char cap |
| `user_char_limit` | 1375 | USER.md char cap |
| `write_approval` | false | Require user approval for writes |
| `nudge_interval` | 10 | Turns between memory-write nudges |
| `flush_min_turns` | 6 | Min turns before flush is considered |

## Token Budget: Cap Asymmetry

Built-in memory has character caps (`memory_char_limit=2200`, `user_char_limit=1375`).
Context files have a 20,000-char cap (`prompt_builder.py:86`, `CONTEXT_FILE_MAX_CHARS`).

**External memory provider `system_prompt_block()` output has NO size cap.** The
`memory_manager.py:413-430` `build_system_prompt()` method joins all provider blocks
with `\n\n` and returns them verbatim — no truncation, no limit. For agentmemory,
this is the `/agentmemory/context` endpoint which accumulates observations across
all sessions. Measured: 5,366 chars after ~12 sessions, growing linearly.

## Compression Blind Spot

Context compression (`context_compressor.py`) only compresses **messages** (conversation
history). It does NOT touch the system prompt. When compression triggers a system prompt
rebuild, external memory providers are re-queried (`system_prompt_block()` is called
again), potentially re-inflating the prompt with the same accumulated memory data.

## Multiplication Effect

The system prompt (including all memory blocks) is sent with EVERY LLM API call in a
turn — not just once per user message. A turn with 8 tool calls sends the full system
prompt 9 times. The built-in memory contribution (~3,575 chars total) is modest; the
bottleneck is the external provider's unbounded `system_prompt_block()`.
