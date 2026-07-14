# Provider Model Override: How `agent.model` Gets Set

## Problem

Hermes has a two-layer model configuration:

```yaml
model:
  default: deepseek-chat    # agent.model at startup
  provider: deepseek
providers:
  qb:
    model: gpt-5.4-2026-03-05  # actual model served by QB gateway
  dashscope:
    model: qwen3.6-plus        # actual model served by DashScope
```

The system prompt (`system_prompt.py:457-460`) writes `agent.model` directly:

```python
if agent.model:
    timestamp_line += f"\nModel: {agent.model}"
```

At startup, `agent.model = model.default` (e.g. `"deepseek-chat"`). But when the user switches to a different provider via `/model` or the provider has its own model in `providers.<name>.model`, `agent.model` still shows the old value from `model.default`.

The actual API call to the provider also uses `agent.model` (passed as the `"model"` field in the HTTP body). For non-aggregator providers (anything not in `_AGGREGATOR_PROVIDERS`), the model name passes through `normalize_model_for_provider()` which for unknown providers just returns it unchanged. If `model.default` differs from `providers.<name>.model`, the API may be called with the wrong model string.

## Fix Location

**File:** `agent/agent_init.py` lines 380-392

After the `normalize_model_for_provider` path (line 376), we added a second override that reads the provider's own config:

```python
# Override agent.model from provider config if the provider has its
# own model set — what's in providers.<name>.model is the actual
# model the API will call, not the alias from model.default.
try:
    from hermes_cli.config import load_config as _load_provider_cfg

    _providers_cfg = _load_provider_cfg().get("providers", {})
    _pconfig = _providers_cfg.get(agent.provider, {})
    _pmodel = _pconfig.get("model")
    if _pmodel:
        agent.model = str(_pmodel).strip()
except Exception:
    pass
```

## Behavior By Provider

| Scenario | `model.default` | `providers.<p>.model` | `agent.model` after init |
|---|---|---|---|
| DeepSeek (no `providers.deepseek`) | `deepseek-chat` | (None) | `deepseek-chat` (unchanged) |
| QB (has `providers.qb.model`) | `deepseek-chat` | `gpt-5.4-2026-03-05` | `gpt-5.4-2026-03-05` (overridden) |
| DashScope (has `providers.dashscope.model`) | `deepseek-chat` | `qwen3.6-plus` | `qwen3.6-plus` (overridden) |

## Caution: Avoid

- Do NOT move this override into `system_prompt.py` — that file runs per-session, but the system prompt is cached at session start. Changing it mid-session breaks prefix caching.
- Do NOT remove `normalize_model_for_provider` — it handles aggregator providers (OpenRouter, Nous, etc.) that need a `vendor/model` format.
- Do NOT assume `providers.<name>.model` always exists — some setups (e.g. pure DeepSeek with no `providers.deepseek` block) don't have it.
