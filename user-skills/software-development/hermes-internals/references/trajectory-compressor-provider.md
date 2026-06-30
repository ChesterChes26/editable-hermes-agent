# Trajectory Compressor: Provider Chain & Failure Paths

## Default model

```
CompressionConfig (trajectory_compressor.py:100-106)
  summarization_model = "google/gemini-3-flash-preview"
  base_url            = "https://openrouter.ai/api/v1"  (OPENROUTER_BASE_URL)
  api_key_env         = "OPENROUTER_API_KEY"
  temperature         = 0.3
```

The summarization model is **independent** of the main agent's chat model. No shared defaults.

## Provider detection

`_detect_provider()` at line 430-457 maps `base_url` hostname to provider string:

| base_url host | provider |
|---|---|
| openrouter.ai | `openrouter` |
| nousresearch.com | `nous` |
| chatgpt.com + /backend-api/codex | `codex` |
| z.ai | `zai` |
| moonshot.ai / moonshot.cn / api.kimi.com | `kimi-coding` |
| arcee.ai | `arcee` |
| minimax.com | `minimax-cn` |
| minimax.io | `minimax` |
| anything else | `""` (empty — raw client path) |

## Initialization: two paths

### Path A: Known provider (default — openrouter)

```
_init_summarizer()  line 377-391
  │
  _detect_provider() → "openrouter"
  │
  resolve_provider_client("openrouter", model="google/gemini-3-flash-preview")
  │                                              auxiliary_client.py:3697
  │
  _try_openrouter()                              auxiliary_client.py:1645
  │  1. Check credential pool → _select_pool_entry("openrouter")
  │  2. Fallback: os.getenv("OPENROUTER_API_KEY")
  │  3. If neither has key → return (None, None)
  │
  │  SUCCESS: self._use_call_llm = True
  │  FAILURE: raise RuntimeError("Provider 'openrouter' is not configured.")
```

### Path B: Unknown provider (custom base_url)

```
_init_summarizer()  line 392-409
  │
  _detect_provider() → ""
  │
  os.getenv(self.config.api_key_env)
  │  SUCCESS: OpenAI(api_key=..., base_url=...) — raw client, no routing
  │  FAILURE: raise RuntimeError("Missing API key. Set OPENROUTER_API_KEY...")
```

## API call: two paths mirroring init

### Known provider → call_llm

```
_generate_summary_async()  line 711-718
  │  self._use_call_llm == True
  │
  async_call_llm(
      provider="openrouter",
      model="google/gemini-3-flash-preview",
      messages=[{"role": "user", "content": prompt}],
      temperature=<model-adjusted>,
      max_tokens=summary_target_tokens * 2,  # 750 * 2 = 1500
  )
```

### Unknown provider → raw AsyncOpenAI

```
_generate_summary_async()  line 721-728
  │  self._use_call_llm == False
  │
  self._get_async_client().chat.completions.create(
      model=...,
      messages=[...],
      max_tokens=...,
  )
```

## Failure is hard, not graceful

Both paths raise `RuntimeError` at **init time** — the compressor never starts if it can't build its LLM client. There is no fallback chain, no silent degradation, no retry-at-init. Unlike the main agent loop which has provider health marking and credential pool failover, the compressor is a batch tool: if it can't talk to the summarization model, there's no point running.

The only retry is at the **per-summary level**: `_generate_summary_async()` retries up to 3 times with `jittered_backoff` (2s base, 30s max). If all 3 fail, it returns a placeholder summary string — the trajectory is still written, just with a degraded summary.
