# Memory vs Context File Injection: Cross-System Analysis

How external memory providers (e.g. agentmemory) and project context files
(AGENTS.md/CLAUDE.md/.cursorrules) share the same context window without
overriding each other — and where the real risk lives.

## Two Subsystems, Four Injection Points

```
                    System Prompt (built once per session)
                    ============
stable tier:    identity + tools + skills + env hints
context tier:   AGENTS.md / .hermes.md / .cursorrules   ← context files (1)
volatile tier:  memory system_prompt_block               ← memory (2)
                    ============

                    Per-Turn Injection (every API call)
                    ============
user message:   ...original user text...
                <memory-context>                         ← memory prefetch (3)
                  recalled observations (top 5, ≤200 chars each)
                </memory-context>
                    ============
```

### Injection Point 1: Context Files (context tier)

`agent/prompt_builder.py:1647-1686` — `build_context_files_prompt()`

- Priority chain: .hermes.md → AGENTS.md → CLAUDE.md → .cursorrules (first match wins)
- Security scan via `threat_patterns.py(scope="context")`
- **HARD CAP: 20,000 chars** (`CONTEXT_FILE_MAX_CHARS`), configurable via `context_file_max_chars`
- Truncation: head 70% + tail 20%, marker in middle

### Injection Point 2: Memory system_prompt_block (volatile tier)

`agent/system_prompt.py:344-352` → `agent/memory_manager.py:413-430` →
`provider.system_prompt_block()`

- agentmemory: calls `GET /context?sessionId=X&project=Y`
- **NO SIZE LIMIT** — whatever the provider returns goes straight into the system prompt
- agentmemory's observations accumulate per session; the `/context` endpoint has no built-in truncation

### Injection Point 3: Memory per-turn prefetch

`agent/turn_context.py:370-374` → `agent/memory_manager.py:452-472` →
`provider.prefetch(query)`

- agentmemory: calls `POST /smart-search` with `limit: 5`
- Each result: `narrative[:200]` (capped at 200 chars)
- Wrapped in `<memory-context>` tags via `build_memory_context_block()` (line 296)
- Appended to user message at API-call time (`conversation_loop.py:721-732`)
- Only affects the current turn — NOT persisted to session store
- NOTE: `queue_prefetch_all()` uses `limit: 3` (background path, line 249)

### Injection Point 4: Built-in memory (MemoryStore)

`agent/system_prompt.py:344-352` — `agent._memory_store.format_for_system_prompt("memory")`

- File-backed, reads from `~/.hermes/memories/memory/`
- Also in volatile tier alongside external provider block
- Simple file read, no size limit

## They Don't Override Each Other

Context files are in the **context tier** (middle layer of system prompt).
Memory is in the **volatile tier** (bottom layer) + user message (per-turn).
They occupy different positions in the prompt structure — no direct
override is possible.

But this doesn't mean they're harmless together.

## The Real Problem: Context Window Budget Competition

```
DeepSeek V4 Pro: 128K tokens total context window

  system prompt
    ├── stable:      ~15-25K tokens (identity, tools, skills, env hints)
    ├── context:     ~0-5K tokens  (AGENTS.md, capped at 20K chars)
    └── volatile:    ~1-50K tokens (memory, NO CAP)
  
  messages
    └── conversation history: variable
  
  tool schemas
    └── function definitions: ~2-5K tokens
  
  thinking tokens
    └── reasoning: not counted toward context window (separate budget)
```

The AGENTS.md cap (20K chars ≈ 5K tokens) is a known quantity.
Memory (point 2 above) has no cap — agentmemory's `/context` endpoint
can grow unboundedly as observations accumulate.

**Compression doesn't help the memory block.** Context compression
(`context_compressor.py`) only compresses `messages` (the conversation
history). The system prompt is **rebuilt from scratch** after compression,
which means it re-fetches memory — if memory is huge, the rebuilt prompt
is still huge. Compression might free up 20K tokens from messages, only
for memory to eat 15K of them back.

## Three Failure Modes

### 1. Silent context window exhaustion

Memory grows → system prompt grows → less room for messages →
compression triggers earlier → rebuild inflates prompt again → loop.

No error is thrown. The model just has less working memory for the
current conversation, leading to degraded reasoning quality.

### 2. Attention dilution

AGENTS.md says "use pytest." Memory says "last time you said unittest
is better for this project." Both are in the same API call. The model
sees conflicting signals and may follow either — or split the difference
in an incoherent way.

### 3. Memory pollution loop

Prefetch injects old conclusions → model references them in new reply →
agentmemory compresses the new reply → old conclusion is now reinforced
in the store → next prefetch surfaces it again. Without a "forgetting"
mechanism, stale facts self-perpetuate.

## Mitigation Checklist

- [ ] Check agentmemory's `/context` endpoint response size periodically
- [ ] Consider adding a `CONTEXT_MAX_CHARS` equivalent for
      `system_prompt_block()` — currently no such limit exists in
      `memory_manager.py` or the agentmemory plugin
- [ ] If using agentmemory, watch the `agentmemory-context` block in the
      system prompt for growth over sessions
- [ ] Prefer agentmemory's per-turn prefetch (bounded: 5 × 200 chars)
      over unbounded system_prompt_block for critical data
- [ ] The built-in `memory` tool (MemoryStore) has the same unbounded
      risk — both paths need attention

## Key Source Locations

| What | Where |
|------|-------|
| Context file injection | `agent/prompt_builder.py:1647-1686` |
| Context file cap | `agent/prompt_builder.py:86` (`CONTEXT_FILE_MAX_CHARS = 20_000`) |
| Memory system_prompt_block | `agent/memory_manager.py:413-430` |
| Memory per-turn prefetch | `agent/memory_manager.py:452-472` + `agent/turn_context.py:370-374` |
| Memory-context fence | `agent/memory_manager.py:296-310` (`build_memory_context_block`) |
| Prefetch injection into user msg | `agent/conversation_loop.py:721-732` |
| System prompt tiers | `agent/system_prompt.py:323-353` |
| agentmemory prefetch impl | `plugins/agentmemory/__init__.py:231-246` |
| agentmemory context impl | `plugins/agentmemory/__init__.py:222-229` |
| Context compression (messages only) | `agent/context_compressor.py` |

## Related References

- `references/context-file-injection.md` — context file pipeline (priority chain, security scan, truncation)
- `references/memory-architecture.md` — dual built-in + external memory design
- `references/context-compression-architecture.md` — compression algorithm and system prompt rebuild
