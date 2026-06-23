# Context Compression Architecture

How Hermes compresses conversation context when it approaches the model's context window limit.

## Key Files

| File | Role |
|------|------|
| `agent/context_compressor.py` | `ContextCompressor` class — algorithm implementation |
| `agent/conversation_compression.py` | `compress_context()` — scheduling, locking, session splitting |
| `agent/conversation_loop.py` | Three trigger paths for compression |
| `agent/model_metadata.py` | `estimate_messages_tokens_rough()` — rough token estimation |

## Trigger Paths

### 1. Proactive threshold (post-response)
`conversation_loop.py:3960-3988` — after each API call:
- Uses `last_prompt_tokens` from API response (prompt only, no completion)
- Fallback: `estimate_request_tokens_rough(messages, tools=...)` when no real tokens available
- Threshold: `max(int(context_length * 0.50), MINIMUM_CONTEXT_LENGTH)` (default 50%, floor 64K)

### 2. Provider error trigger
`conversation_loop.py:2626-2721` — on overflow errors:
- `FailoverReason.long_context_tier` — Anthropic 429 "Extra usage required" (downgrades to 200K first)
- `FailoverReason.payload_too_large` — HTTP 413
- `FailoverReason.context_overflow`
- Respects `compression.enabled: false` — won't compress even on error (port from opencode#30749)

### 3. Manual `/compress`
Passes `force=True`, bypasses cooldown and all `should_compress` checks.

## prompt_tokens Composition

`prompt_tokens` = the token count of the entire API request body, not just "system prompt + history":

```
prompt_tokens = system_prompt + messages + tool_schemas
```

- **system_prompt**: Full system prompt built by `prompt_builder.py` — persona, environment hints, skills index, memory, tool-use enforcement blocks. Stored in `_cached_system_prompt`, built once per session.
- **messages**: `api_messages`, deep copy of persisted `messages` + bit-perfect normalization.
- **tool_schemas**: JSON Schema for every enabled tool. 50+ tools = 20-30K tokens alone.

Stored via `context_compressor.py:771-783` `update_from_response()` → `last_prompt_tokens`.

**Compression only uses prompt_tokens, NOT completion_tokens** (`conversation_loop.py:3967-3973`). Reasoning tokens from thinking models (GLM-5.1, QwQ, DeepSeek R1) inflate completion_tokens but don't consume context window — including them would cause premature compression.

## Compression Algorithm (5 Steps)

`ContextCompressor.compress()`:

1. **Tool result pruning** (`_prune_old_tool_results`) — cheap pre-pass, no LLM call. Replaces old tool outputs with 1-line summaries:
   ```
   [terminal] ran `npm test` -> exit 0, 47 lines output
   [read_file] read config.py from line 1 (3,400 chars)
   ```
   Also deduplicates identical results and truncates large tool-call arguments while preserving JSON validity (`_truncate_tool_call_args_json`).

2. **Head protection** — `protect_first_n` (default 3). System prompt + first exchange never touched.

3. **Tail protection** — `tail_token_budget` (default = threshold × 20% = 10% of total context). Protects most recent messages by token budget.

4. **LLM summarization of middle turns** — auxiliary model (`auxiliary.compression.model`) generates structured summary with four sections: Historical Task Snapshot, In-Progress State, Pending User Asks, Remaining Work. Wrapped in `SUMMARY_PREFIX` that explicitly marks it as reference-only (not active instructions). Falls back to static deterministic summary if aux model unavailable.

5. **Iterative update** — subsequent compactions incrementally update `_previous_summary` rather than re-summarizing the entire history.

## 10% Savings Threshold (Anti-Thrashing)

`context_compressor.py:2405-2414`:

```python
new_estimate = estimate_messages_tokens_rough(compressed)
saved_estimate = display_tokens - new_estimate
savings_pct = (saved_estimate / display_tokens * 100) if display_tokens > 0 else 0

if savings_pct < 10:
    self._ineffective_compression_count += 1  # increment
else:
    self._ineffective_compression_count = 0   # reset
```

After 2 consecutive ineffective compressions, `should_compress()` returns False — skipping all future auto-compression. Reset by: effective compression, `/new`, or manual `/compress`.

`estimate_messages_tokens_rough` is NOT simple `chars/4`. It has three optimizations:
- Images count as flat **1500 tokens each** (otherwise 1MB base64 screenshot ≈ 250K tokens)
- `_anthropic_content_blocks` internal fields are excluded (otherwise double-counted)
- Multimodal tool results use `text_summary` instead of full data

## Protection Layers

| Layer | Location | What |
|-------|----------|------|
| SQLite compression lock | `conversation_compression.py:339-410` | Prevents two agent instances compressing same session simultaneously |
| Failure cooldown | `context_compressor.py:164` — 600 seconds | No retry for 10 minutes after aux model failure |
| Abort mode | `context_compressor.py:701,763` | Returns original messages unchanged on summary failure, session NOT rotated |
| Anti-thrashing | `context_compressor.py:826-834` | Skip after 2 consecutive <10% savings |
| Image stripping | `context_compressor.py:414-468` | Replace old base64 images with placeholder text |

## Session Splitting

Compression creates a CHILD session, not just dropping messages:

1. Acquire SQLite compression lock (keyed on OLD session_id)
2. Parent session marked `parent.metadata.compressed: true`
3. New `session_id` generated
4. Parent's `child_session_id` points to child
5. Compressed messages appended to new session
6. `_cached_system_prompt = None` — rebuilt next round

Why split: compression is irreversible information loss. Old session preserves full history (FTS search, export, rollback). New session carries compressed working context.

## Bit-Perfect Prefix Normalization (Cache Foundation)

`conversation_loop.py:780-811` — runs before EVERY API call:

```python
# 1. Strip whitespace from message content
for am in api_messages:
    if isinstance(am.get("content"), str):
        am["content"] = am["content"].strip()

# 2. JSON key sort + compact serialization
for tc in am.get("tool_calls") or []:
    args_obj = json.loads(tc["function"]["arguments"])
    tc["function"]["arguments"] = json.dumps(
        args_obj, separators=(",", ":"), sort_keys=True,
    )
```

Ensures byte-identical prefixes even when LLM returns tool-call arguments with varying JSON key order. Without this, vLLM/Ollama/llama.cpp prefix cache would never hit.

See also: `references/prompt-caching-architecture.md` for the full two-layer cache design.
