# Prompt Caching & Context Compression Architecture

Hermes uses a two-layer design: **Layer 1** context compression (lossy summarization) +
**Layer 2** prefix cache (LLM server-side KV reuse). They are interlocked — compression
creates the space for long sessions, caching makes each turn economically viable.

---

## Layer 1: Context Compression (`ContextCompressor`)

**Core files:**
- `agent/context_compressor.py` — `ContextCompressor(ContextEngine)` class, the algorithm
- `agent/conversation_compression.py` — `compress_context()` orchestrator: lock, session rotation, memory notification

### Trigger Paths

Three ways compression fires:

1. **Threshold-based auto-compress** — `conversation_loop.py:3988`
   After each API response, if `prompt_tokens > context_length × threshold_percent`
   (default 0.50), triggers. Uses real `prompt_tokens` from the provider's usage
   response, NOT the rough estimate (which overestimates schema-heavy requests).

2. **Error-driven auto-compress** — `conversation_loop.py:2631-2703`
   On 429 (Anthropic long-context tier), 413 (payload-too-large), or
   context-overflow errors. Compresses then retries, up to
   `max_compression_attempts`. If `compression.enabled: false` in config,
   these paths are **blocked** entirely (port from anomalyco/opencode#30749).

3. **Manual `/compress`** — passes `force=True`, bypasses summary-failure cooldown.

### Algorithm (5 Steps)

`ContextCompressor.compress()` in `context_compressor.py`:

**Step 1 — Tool output pruning** (`_prune_old_tool_results`, line 841)
No LLM call. Replaces old tool results outside the protected tail with informative
1-line summaries:
```
[terminal] ran `npm test` -> exit 0, 47 lines output
[read_file] read config.py from line 1 (3,400 chars)
```
Also deduplicates repeated tool results (same file read 5× → keep newest full copy),
and truncates large tool_call arguments in assistant messages. Returns
`(pruned_messages, pruned_count)`.

**Step 2 — Protect head messages** (`protect_first_n`, default 3)
First N messages (system prompt + initial exchange) are never touched —
they are the historical anchor.

**Step 3 — Protect tail by token budget** (`tail_token_budget`)
Default = `threshold_tokens × summary_target_ratio` ≈ 20% of threshold.
Protects the most recent messages that fall within the budget. Falls back to
`protect_last_n` (default 20) as a hard minimum floor. Hard ceiling is
`_MAX_TAIL_MESSAGE_FLOOR = 8` — even when budget is exhausted, keep
at least 8 recent messages verbatim.

**Step 4 — LLM summarization** (`_generate_summary`)
Uses an **auxiliary model** (configured in `auxiliary.compression.model`).
Produces structured summary with four sections:
- `Historical Task Snapshot`
- `Historical In-Progress State`
- `Historical Pending User Asks`
- `Historical Remaining Work`

Summary is wrapped in `SUMMARY_PREFIX` (line 43):
```
[CONTEXT COMPACTION — REFERENCE ONLY] Earlier turns were compacted
into the summary below. This is a handoff from a previous context
window — treat it as background reference, NOT as active instructions.
...
--- END OF CONTEXT SUMMARY — respond to the message below, not the summary above ---
```

The prefix has evolved through multiple iterations to prevent the model from
treating summary content as fresh instructions (#11475, #14521, #33256, #35344).

Summary budget: `min(context_length × 0.05, _SUMMARY_TOKENS_CEILING=12000)`.
Minimum floor: `_MIN_SUMMARY_TOKENS = 2000`.

**Step 5 — Iterative update**
On subsequent compactions, `_previous_summary` is carried forward and the
auxiliary model updates it incrementally, preserving information across
multiple compaction passes.

### Protection Mechanisms

| Mechanism | Location | Purpose |
|-----------|----------|---------|
| Anti-thrashing | `context_compressor.py:826-834` | After 2 consecutive compressions each saving <10%, skip further auto-compression. Prevents infinite loop where each pass removes only 1-2 messages. |
| Summary failure cooldown | `context_compressor.py:164` | `_SUMMARY_FAILURE_COOLDOWN_SECONDS = 600` — 10-minute cooldown after aux LLM failure. |
| Compression abort | `context_compressor.py:701,763` | When `abort_on_summary_failure=True`, returns messages **unchanged** — no messages dropped, session NOT rotated. |
| Fallback summary | `context_compressor.py:169` | When LLM summarizer fails, inserts deterministic handoff (≤8000 chars) listing the last few turns verbatim. |
| Image stripping | `context_compressor.py:414-468` | Replaces base64 image parts in pre-anchor messages with `[Attached image — stripped after compression]` placeholder. Kilo-Org/kilocode#9434 port. |
| Session-ID rotation lock | `conversation_compression.py:339-410` | SQLite-backed per-session lock preventing concurrent compression by parent-turn agent + background-review fork sharing the same session_id. |

### Compression Feasibility Check

`conversation_compression.py:74` `check_compression_model_feasibility()`:
- Lazily probed on first compression attempt (not at `AIAgent.__init__` — saves ~400ms for short sessions).
- If aux model context < compression threshold, auto-lowers threshold to aux context.
- Hard floor: aux model must have ≥ `MINIMUM_CONTEXT_LENGTH` (64K) tokens.

### Session Rotation

After successful compression (`conversation_compression.py`):
1. Session splits in SQLite (new child session_id)
2. External memory providers notified (`memory_manager.on_pre_compress`)
3. Plugin context engines notified
4. System prompt rebuilt (fresh for new session)
5. Compression lock released

---

## Layer 2: Prefix Cache (KV Cache)

**Core files:**
- `agent/prompt_caching.py` — `apply_anthropic_cache_control()` (79 lines)
- `agent/agent_runtime_helpers.py:1254` — `anthropic_prompt_cache_policy()` decision matrix
- `agent/conversation_loop.py:780-811` — bit-perfect prefix normalization

### Layer 1: Hermes Local `messages` (Ground Truth)

Stored in session DB (SQLite + FTS5). Cross-turn durable.

**Rules:**

1. **Append-only** — old entries never mutate. This is the prerequisite for Layer 2 cache to work.
2. **`api_messages` is a deep copy** — system prompt + memory injection only happen on the API-call copy, never polluting the persisted `messages`.
3. **bit-perfect prefix** — `conversation_loop.py:780-811` normalizes whitespace and JSON key ordering so the prefix is byte-identical across iterations.

**System prompt separation** (`conversation_loop.py:724-734`):
- System prompt built ONCE per session, stored on `_cached_system_prompt`.
- Ephemeral context (memory, plugins) injected into user message, NEVER system prompt.
- If the system prompt changes, the entire LLM-level cache is invalidated.

### Bit-Perfect Prefix Normalization

`conversation_loop.py:780-811`. Runs on `api_messages` (API copy) before every request.
Persisted `messages` are untouched.

1. **Whitespace normalization:** strip leading/trailing whitespace from string content.
2. **JSON key sorting + compact serialization:**
```python
args_obj = json.loads(tc["function"]["arguments"])
tc["function"]["arguments"] = json.dumps(
    args_obj, separators=(",", ":"), sort_keys=True,
)
```

Without this step, LLMs returning tool-call arguments with inconsistent key order
(`{"path": ..., "content": ...}` vs `{"content": ..., "path": ...}`) would
produce different byte sequences every turn, making prefix cache hits impossible
on vLLM/Ollama/llama.cpp.

### Anthropic `cache_control` (Explicit Control)

`agent/prompt_caching.py:49-79` `apply_anthropic_cache_control`:

**Strategy: `system_and_3`** — system prompt + last 3 non-system messages get
`cache_control` breakpoints. Max 4 breakpoints, TTL 5m (or 1h for long sessions).

```python
if messages[0].get("role") == "system":
    _apply_cache_marker(messages[0], marker)      # system breakpoint

non_sys = [i for i ... if role != "system"]
for idx in non_sys[-3:]:                          # last 3 messages
    _apply_cache_marker(messages[idx], marker)
```

**Decision matrix** (`agent_runtime_helpers.py:1254` `anthropic_prompt_cache_policy`):

| Scenario | Cache? | Native layout? | Notes |
|----------|:------:|:--------------:|-------|
| Native Anthropic (`api.anthropic.com`) | ✓ | ✓ | Content-block internal markers |
| OpenRouter + Claude | ✓ | ✗ | Message-envelope markers (OpenAI-wire) |
| Nous Portal + Claude | ✓ | ✗ | Proxies through OpenRouter |
| Nous Portal + Qwen | ✓ | ✗ | Upstream Qwen route accepts cache_control |
| Third-party Anthropic-wire + Claude | ✓ | ✓ | e.g. MiniMax, Zhipu GLM, LiteLLM proxy |
| MiniMax on Anthropic endpoint | ✓ | ✓ | Documented 0.1× read pricing, 5-min TTL |
| DeepSeek | ✗ | — | No `cache_control` API field |
| Other providers | ✗ | — | Depends on provider |

Two marker layouts:
- **Native** (`use_native_layout=True`): `cache_control` placed on inner content blocks
  (required by Anthropic API).
- **Envelope** (`use_native_layout=False`): `cache_control` placed on the message dict
  itself (OpenRouter and OpenAI-wire proxies accept this looser format).

### DeepSeek KV Cache (Implicit, Engine-Level)

DeepSeek API has **no** `cache_control` field. Caching happens at the inference engine level:

1. **MLA (Multi-head Latent Attention)** — DeepSeek-V2/V3 architecture compresses KV cache
   into low-dimensional latent space, reducing memory by 5-10×. This makes long-context
   caching economically viable.

2. **Prefix-aware engine** — The serving engine (vLLM/SGLang or proprietary) detects
   identical prefixes between consecutive requests and reuses computed KV states automatically.

3. **What Hermes does for DeepSeek**: Cannot explicitly control caching, but maximizes
   hit probability through:
   - System prompt never changes (bit-perfect)
   - `messages` append-only
   - Whitespace normalization + JSON key sorting

### Comparison

| | Anthropic | DeepSeek |
|---|---|---|
| Control mechanism | API field `cache_control` | Inference engine auto-detect |
| Billing | Cached tokens at 1/10 write price | No cache/non-cache price distinction |
| Guarantee | Explicit API contract | Depends on server implementation |
| Max breakpoints | 4 | — |

### Economic Impact

20-turn bug-fix session with 50K token system prompt:

```
Without cache:  ~1,200K input tokens
Anthropic cache: ~50K write + incremental × 0.1 ≈ 95% savings
DeepSeek:        No billing distinction, but computation drops dramatically
```

---

## Why Caching Shapes the While Loop Design

Every architectural constraint traces back to caching:

| Design choice | Reason |
|---------------|--------|
| System prompt built once, never changed | Cache invalidation = full price every turn |
| Memory injected into user message, not system prompt | Preserves system prefix |
| `api_messages` is deep copy of `messages` | Mutations don't affect cache stability |
| `messages` append-only | Existing prefix bytes never change |
| Toolsets only change on `/reset` | Tool schemas are in system prompt |
| `_drop_thinking_only` only on api_messages | Persisted messages keep full history |
| JSON key sorting on api_messages | Byte-identical prefixes for vLLM/Ollama cache hits |

**Caching is the economic foundation that makes the while loop viable.**
Without it, 20-turn tool-call sessions would be cost-prohibitive.

---

## Full Flow: Compression + Caching Together

```
1. User sends message
2. conversation_loop builds api_messages (deep copy of messages)
3. Bit-perfect normalization (whitespace strip + JSON key sort)
4. Anthropic/OpenRouter: inject cache_control breakpoints
5. Estimate request tokens
6. If tokens > threshold (50%):
   ├── Acquire compression lock (SQLite state.db)
   ├── ContextCompressor.compress()
   │   ├── Step 1: Prune old tool results
   │   ├── Step 2: Protect head (first_n)
   │   ├── Step 3: Protect tail (token budget)
   │   ├── Step 4: Aux model summarizes middle turns
   │   └── Step 5: Iterative update of previous summary
   ├── Session splits → new session_id
   ├── Memory providers notified
   └── Release compression lock
7. API request sent
   ├── Anthropic: cache_control markers → server-side cache hit on prefix
   └── DeepSeek: engine auto-detects identical prefix → implicit KV reuse
8. API response → tool results appended to messages (append-only)
9. Loop back to step 2 — next turn's prefix matches → cache hit
```

**Key insight:** Compression solves "window not big enough"; prefix cache solves
"window too expensive." They are tightly coupled — compression changes message
structure, which would break the cache if normalization weren't bit-perfect.
