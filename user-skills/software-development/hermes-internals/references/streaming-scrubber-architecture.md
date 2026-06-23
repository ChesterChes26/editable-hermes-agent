# Streaming Content Scrubber Architecture

Two stateful scrubbers run in series on every streaming delta in `run_agent.py:_fire_stream_delta` (line ~4182) to prevent internal tags from leaking to the user when split across chunk boundaries.

## Problem: Per-Delta Regex Fails

When LLMs stream content, a single XML-like tag can be split across multiple deltas:

```
delta1 = "<think>"
delta2 = "Let me check..."
delta3 = "</think>"
```

The old `_strip_think_blocks` regex ran per-delta. It would see `<think>` as an unterminated open tag and erase delta1 entirely, so the downstream state machine (CLI / gateway / TTS) never saw the open tag and leaked delta2 as regular content.

## Architecture: Two Scrubbers in Series

```
delta text
  → StreamingThinkScrubber.feed()    # Strip <think>, <thinking>, <reasoning>, <thought>, <REASONING_SCRATCHPAD>
  → StreamingContextScrubber.feed()  # Strip <memory-context>...</memory-context>
  → stream_delta_callback (CLI, gateway, ACP, API server, TTS)
```

## StreamingThinkScrubber (`agent/think_scrubber.py`)

Class: `StreamingThinkScrubber` (line 64)

### Tags handled (case-insensitive)
- `<think>`, `<thinking>`, `<reasoning>`, `<thought>`, `<REASONING_SCRATCHPAD>`

### State machine variables
| Variable | Purpose |
|----------|---------|
| `_in_block: bool` | Inside an opened reasoning block |
| `_buf: str` | Held-back partial-tag suffix crossing delta boundary |
| `_last_emitted_ended_newline: bool` | Whether last emission ended with `\n` (for block boundary detection) |

### Block boundary rule
An opening tag only opens a reasoning block when it appears:
- At position 0 AND the last emission ended with newline (or nothing emitted yet), OR
- After a newline followed only by whitespace

This prevents prose that *mentions* `<think>` (e.g. "use `<think>` tags here") from being incorrectly suppressed.

### Priority in `feed()` loop
1. **Closed pair** `<tag>X</tag>` — always stripped regardless of boundary (intentional bounded construct)
2. **Unterminated open** at a block boundary
3. Whichever appears earlier in the buffer wins

### Partial-tag hold-back
At the end of each `feed()`, if the buffer suffix could be the start of a tag (e.g. `"<thi"`), it's held in `_buf` for the next `feed()` call.

### Flush
If still in a block on flush — discard (safer: leaking partial reasoning is worse than truncated answer). Otherwise emit held-back tail.

## StreamingContextScrubber (`agent/memory_manager.py:131`)

Class: `StreamingContextScrubber` (line 131)

### Tags handled
- `<memory-context>` … `</memory-context>` (single tag pair)

### Why it exists

Hermes has **two** memory systems with different injection points:

**Built-in memory (MEMORY.md / USER.md)** — goes into the **system prompt** as plain
text blocks (no `<memory-context>` tags). Formatted by `MemoryStore._render_block()`
in `tools/memory_tool.py` with `====` headers. No scrubber needed — no XML tags to leak.

**External memory providers (Honcho, Mem0, Hindsight, etc.)** — the prefetched context
is wrapped by `build_memory_context_block()` and injected into the **current user
message** at API-call time:

```python
# agent/conversation_loop.py:717-734 — the actual injection site
if idx == current_turn_user_idx and msg.get("role") == "user":
    if _ext_prefetch_cache:
        _fenced = build_memory_context_block(_ext_prefetch_cache)  # line 724
        if _fenced:
            _injections.append(_fenced)
    # …
    api_msg["content"] = _base + "\n\n" + "\n\n".join(_injections)
```

`build_memory_context_block()` (defined at `agent/memory_manager.py:296`) wraps the
prefetched content:

```python
"<memory-context>\n"
"[System note: The following is recalled memory context, "
"NOT new user input. Treat as authoritative reference data...]\n\n"
f"{memory_content}\n"
"</memory-context>"
```

**Key design point:** the injection happens in the **user message**, not the system
prompt. This avoids rebuilding the system prompt (which would break the prefix cache),
but it means the model sees `<memory-context>` tags as if the user included them in
their message — making accidental echo-back more likely, and making the scrubber
essential.`

If the model echoes these tags in its output, `sanitize_context()` (line 123) strips them via regex — but only when both tags are in the same string. Streaming splits break this.

### State machine variables
| Variable | Purpose |
|----------|---------|
| `_in_span: bool` | Inside a memory-context span |
| `_buf: str` | Held-back partial tag suffix |
| `_at_block_boundary: bool` | Whether current position is at a block boundary |

### Key difference from ThinkScrubber: `_has_block_opener_suffix`
The context scrubber requires `<memory-context>` to be followed by `\r` or `\n` to count as a real span opener. If `<memory-context>` is at the very end of a buffer, it's held back pending the next delta's first character.

### Non-streaming fallback: `sanitize_context()` (line 123)
Three regex patterns:
```
_FENCE_TAG_RE:         </?\s*memory-context\s*>
_INTERNAL_CONTEXT_RE:  <\s*memory-context\s*>[\s\S]*?</\s*memory-context\s*>
_INTERNAL_NOTE_RE:     [System note: The following is recalled memory context, ...]
```

## Integration in `run_agent.py`

### Per-delta filtering (`_fire_stream_delta`, line ~4182)
```python
think_scrubber = getattr(self, "_stream_think_scrubber", None)
if think_scrubber is not None:
    text = think_scrubber.feed(text or "")
else:
    text = self._strip_think_blocks(text or "")  # legacy fallback

scrubber = getattr(self, "_stream_context_scrubber", None)
if scrubber is not None:
    text = scrubber.feed(text)
else:
    text = sanitize_context(text)  # legacy fallback
```

### End-of-stream flush (`_reset_stream_delivery_tracking`, line ~4095)
Think scrubber flushes first, then output is routed through context scrubber before delivery:
```python
think_tail = think_scrubber.flush()
if think_tail:
    ctx_scrubber = getattr(self, "_stream_context_scrubber", None)
    if ctx_scrubber is not None:
        think_tail = ctx_scrubber.feed(think_tail)  # cross-scrubber cascade
    # deliver think_tail to UI...
```

Then context scrubber flushes its own tail.

## Test files
| File | Covers |
|------|--------|
| `tests/agent/test_think_scrubber.py` | `StreamingThinkScrubber` state machine |
| `tests/agent/test_streaming_context_scrubber.py` | `StreamingContextScrubber` state machine |

## Key design invariants
1. **Stateful across deltas** — both scrubbers survive delta boundaries via `_buf` hold-back
2. **Block-boundary-gated open tags** — prevents false positives on prose that mentions tag names
3. **Case-insensitive** — all tag matching is lowercased
4. **Re-entrant** — `reset()` clears state for each new agent turn
5. **Safe flush** — unterminated blocks are discarded rather than leaked
