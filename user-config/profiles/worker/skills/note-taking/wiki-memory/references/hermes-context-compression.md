# Hermes Context Compression

Source-level analysis of Hermes's compression subsystem (`agent/context_compressor.py`, 2426 lines).

## Trigger

`should_compress()` — when tokens exceed model context window × `threshold` (default 0.50). Anti-thrashing: 2 consecutive compressions saving <10% → skip.

## Five-Phase Algorithm

### Phase 1: Tool Output Pruning (no LLM call)
`_prune_old_tool_results()` — replaces old tool results with 1-line summaries:
```
[terminal] ran `npm test` -> exit 0, 47 lines output
[read_file] read config.py from line 1 (3,400 chars)
```
Also deduplicates identical results, truncates old tool_call arguments, strips old images → `[screenshot removed to save context]`.

### Phase 2: Boundary Determination
```
[ head: 3 messages ] [ === compress window === ] [ tail: ~20K tokens / 20 messages ]
```
Token-budget tail protection (soft ceiling), with hard floor of 8 messages. Boundaries aligned to complete user/assistant turns.

### Phase 3: Structured Summary Generation
Uses auxiliary compression model (cheap/fast). Iterative: re-compression updates previous summary rather than re-summarizing from scratch. Structure:
```
## Historical Task Snapshot
## Goal
## Completed Actions
## Active State
## Historical In-Progress State
## Historical Pending User Asks
## Historical Remaining Work
```
All section headings prefixed with "Historical" to prevent the model from treating them as active instructions.

### Phase 4: Assembly
Head messages + summary message + tail messages. Summary role chosen to avoid consecutive same-role with neighbors. If impossible, summary merges into first tail message.

### Phase 5: Cleanup
`_sanitize_tool_pairs()` removes orphaned tool_results. `_strip_historical_media()` replaces old image blobs with placeholders.

## Core Protection Directives

### Summary Prefix (line 43-69)
```
[CONTEXT COMPACTION — REFERENCE ONLY]
treat it as background reference, NOT as active instructions
Respond ONLY to the latest user message that appears AFTER this summary
Reverse signals (stop, undo, roll back, never mind) must immediately end in-flight work
IMPORTANT: Your persistent memory (MEMORY.md, USER.md) is ALWAYS authoritative
```

### Summary End Marker
```
--- END OF CONTEXT SUMMARY — respond to the message below, not the summary above ---
```
Prevents weak models from re-reading "## Active Task" quotes as fresh user input (#11475, #14521) or regurgitating assistant-role summaries (#33256).

### Historical Prefix Handling
`_HISTORICAL_SUMMARY_PREFIXES` (line 103-140) tracks previous versions of the prefix so re-compaction of a resumed session strips stale directives (e.g., the old "resume exactly from Active Task" wording that caused self-contradicting behavior).

## System Prompt Protection

On compression, system prompt is rebuilt (`system_prompt.py:406-414`):
- MEMORY.md + USER.md snapshots re-read from disk
- Compression note appended to system prompt: `[Note: Some earlier conversation turns have been compacted into a handoff summary...]`
- Memory authority explicitly re-affirmed

## Failure Handling

| Scenario | Behavior |
|----------|----------|
| LLM summarizer fails + `abort_on_summary_failure: false` | Deterministic fallback: `_build_static_fallback_summary()` — local extraction of user asks, tool names, file paths, error text. No LLM call. Max 8,000 chars. |
| LLM summarizer fails + `abort_on_summary_failure: true` | Full abort. Messages unchanged. 600s cooldown. |
| `/compress` manual trigger | `force=True` bypasses cooldown |
| Too few messages | Skip entirely |

## Re-compression (Iterative Summaries)

`_find_latest_context_summary()` searches the protected head for a previous handoff summary (identified by `_compressed_summary` metadata key). If found, `_previous_summary` is restored and the summarizer prompt includes the old summary for iterative update. Cross-session `_previous_summary` is discarded to prevent contamination.

## Anti-Thrashing

`_ineffective_compression_count` tracks consecutive compressions with <10% savings. At 2, `should_compress()` returns False. Resets on effective compression.

## Key Config

```yaml
compression:
  enabled: true
  threshold: 0.50        # trigger at 50% context
  target_ratio: 0.20     # summary gets 20% of compressed budget
  protect_last_n: 20     # tail messages always verbatim
  protect_first_n: 3     # head messages always verbatim
  abort_on_summary_failure: false
```

## Memory Interaction

- Compression summary's prefix explicitly states MEMORY.md/USER.md remain authoritative
- System prompt rebuild re-injects memory snapshots
- External provider's `on_pre_compress()` hook can extract insights before compression
- `on_session_switch()` fires after compression for provider state refresh

## Source Files

| File | Role |
|------|------|
| `agent/context_compressor.py` | Core compression logic (2426 lines) |
| `agent/conversation_loop.py:2700-2720` | Triggers `_compress_context()` on error recovery |
| `agent/system_prompt.py:406-414` | Invalidates and rebuilds system prompt after compression |
| `agent/agent_init.py:1239-1516` | Wires compression config into AIAgent |
