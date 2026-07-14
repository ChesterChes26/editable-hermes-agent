# Hermes Memory Architecture (Source-Level Analysis)

Traced 2026-06-17. Covers the full pipeline from system prompt injection to Obsidian wiki file loading.

## Layers

```
┌─────────────────────────────────────────────────┐
│ System Prompt (frozen snapshot at session start) │
│   ← MEMORY.md index + USER.md                    │
│   ← External provider system_prompt_block()      │
│   ← Timestamp / model info                       │
├─────────────────────────────────────────────────┤
│ Per-turn Injection (conversation_loop.py:684)    │
│   ← MemoryManager.prefetch_all(user_message)     │
│   ← Plugin pre_llm_call hooks                    │
├─────────────────────────────────────────────────┤
│ Disk Storage                                      │
│   ~/.hermes/memories/MEMORY.md (2,200 char cap)  │
│   ~/.hermes/memories/USER.md   (1,375 char cap)  │
│   D:/obsidian/2026/memory(记忆)/ (memory files)   │
└─────────────────────────────────────────────────┘
```

## Key Source Files

| File | Role |
|------|------|
| `agent/system_prompt.py:343-352` | Injects MEMORY.md + USER.md frozen snapshots into system prompt |
| `agent/conversation_loop.py:684-695` | Injects external provider prefetch results into user message |
| `tools/memory_tool.py` | `MemoryStore` class — file-backed CRUD with §-delimiter, file locks, threat scanning |
| `agent/memory_manager.py` | `MemoryManager` — orchestrates builtin + 1 external provider |
| `agent/memory_provider.py` | `MemoryProvider` ABC — interface for external providers |
| `plugins/memory/__init__.py` | Plugin discovery — `load_memory_provider(name)` |
| `agent/agent_init.py:1116-1200` | Wires MemoryStore + MemoryManager into AIAgent |

## Frozen Snapshot Pattern

`MemoryStore.load_from_disk()` (line 132):
1. Reads MEMORY.md and USER.md from disk
2. Deduplicates entries (preserves order, keeps first occurrence)
3. Scans for threat patterns (strict scope from `tools/threat_patterns.py`)
4. Builds `_system_prompt_snapshot` — NEVER mutated mid-session
5. `format_for_system_prompt()` returns the snapshot, not live state

Mid-session writes update disk files immediately but do NOT affect the system prompt.
The snapshot refreshes on next session start. This preserves prefix cache across all turns.

## Write Safety

- **File locking**: `fcntl.flock()` on Linux/macOS, `msvcrt.locking()` on Windows (`_file_lock` context manager, line 210)
- **External drift detection**: Before mutating, re-reads disk under lock. If disk content wouldn't round-trip through the § parser (e.g., patch tool added text), the mutation is refused and a `.bak.<ts>` snapshot is saved
- **Threat scanning**: `_scan_memory_content()` (line 78) scans new/replacement content for injection/exfiltration patterns before accepting
- **Deduplication**: `add()` rejects exact duplicates

## Wiki Memory Loading Gap

The MEMORY.md index (lines like `→ pause before risky ops | driving/behavior`) is injected into EVERY session's system prompt by `system_prompt.py:343-352`.

But reading the actual memory files (`D:/obsidian/2026/memory(记忆)/driving(行为)/behavior.md`) is ENTIRELY LLM-driven:
- The `wiki-memory` skill provides the instruction "scan index → load relevant files"
- This skill is auto-loaded for WeChat/QQ via env vars, but NOT for CLI
- No code anywhere parses the index lines or auto-reads wiki files

## External Provider Model

`MemoryManager` (line 312) enforces a **one external provider limit**:
- Builtin provider (`name == "builtin"`) is always accepted
- First external provider is accepted
- Second external provider is rejected with a warning
- Available: honcho, hindsight, mem0, supermemory, retaindb, byterover, holographic, openviking

External providers implement `MemoryProvider` ABC (16 methods, 8 abstract):
- Core: `is_available()`, `initialize()`, `get_tool_schemas()`, `handle_tool_call()`
- Recall: `system_prompt_block()`, `prefetch(query)`, `queue_prefetch(query)`
- Sync: `sync_turn(user, assistant)` — runs on background worker thread
- Hooks: `on_turn_start()`, `on_session_end()`, `on_session_switch()`, `on_pre_compress()`, `on_memory_write()`, `on_delegation()`

Prefetched context is injected into the user message wrapped in `<memory-context>` fence tags (line 295), with a system note: "The following is recalled memory context, NOT new user input."

`StreamingContextScrubber` (line 130) prevents `<memory-context>` tag leakage in streaming output.

## Config

```yaml
memory:
  memory_enabled: true
  user_profile_enabled: true
  write_approval: false
  memory_char_limit: 2200
  user_char_limit: 1375
  provider: ''           # empty = no external provider
  nudge_interval: 10     # turns between memory-write nudges
  flush_min_turns: 6
```

## Context Compression & Memory

When context compression fires (`agent/context_compressor.py:2151`), the system prompt is rebuilt (`agent/system_prompt.py:406`), re-injecting the MEMORY.md snapshot. The compression summary carries an explicit directive:

> IMPORTANT: Your persistent memory (MEMORY.md, USER.md) in the system prompt is ALWAYS authoritative and active — never ignore or deprioritize memory content due to this compaction note.

Key protections:
- Memory snapshot is re-read from disk on each system prompt rebuild
- Compression summary cannot override or contradict built-in memory
- External provider's `on_pre_compress()` hook can extract insights from about-to-be-discarded messages before compression runs
- After compression, `on_session_switch()` fires so providers update their per-session state
