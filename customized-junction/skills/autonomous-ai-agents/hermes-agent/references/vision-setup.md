---
name: hermes-vision-setup
description: Configure Hermes to analyze images when the main model lacks vision — auxiliary vision providers, domestic Chinese options, and architecture clarification.
category: hermes
platforms: [linux, macos, windows]
---

# Hermes Vision Setup

When the main model (e.g. DeepSeek V4 Pro) doesn't support vision, Hermes can
route image analysis to a separate **auxiliary vision provider**. This is a
separate LLM provider — NOT MCP, NOT an external tool server.

## Architecture

```
WeChat/QQ/Messenger receives image
    │
    ▼
Gateway downloads image to local temp file
    │
    ▼
Hermes detects image → routes to auxiliary.vision.provider
  (NOT the main model — e.g. DeepSeek)
    │
    ▼
Vision provider returns text description
    │
    ▼
Text injected into main model's context → main model "sees" the image
```

The key config lives in `config.yaml` under `auxiliary.vision`:

```yaml
auxiliary:
  vision:
    provider: auto       # or explicit provider name
    model: ''            # model name
    base_url: ''         # custom endpoint (for proxies)
    api_key: ''          # override API key
    timeout: 120
    download_timeout: 30
```

When `provider: auto`, Hermes tries to find ANY configured provider with a
vision-capable model. If none found, vision tasks fail SILENTLY — no error
shown, image is just skipped. This is the most common pitfall.

## Configuration

### Option 1: DashScope (Alibaba Qwen-VL) — recommended for China

```bash
hermes config set auxiliary.vision.provider dashscope
hermes config set auxiliary.vision.model qwen-vl-max
# Requires DASHSCOPE_API_KEY in .env or via hermes auth
```

### Option 2: Zhipu (GLM-4V)

```bash
hermes config set auxiliary.vision.provider zhipu
hermes config set auxiliary.vision.model glm-4v
# Requires GLM_API_KEY
```

### Option 3: Custom proxy (OpenAI-compatible)

For GPT-4o / GPT-4-vision via a domestic proxy server:

```bash
hermes config set auxiliary.vision.provider "custom:my-proxy"
hermes config set auxiliary.vision.model gpt-4o
hermes config set auxiliary.vision.base_url "https://your-proxy.example.com/v1"
hermes config set auxiliary.vision.api_key "your-proxy-key"
```

The `custom:` prefix is mandatory for custom providers.

### Option 4: OpenRouter (if accessible)

```bash
hermes config set auxiliary.vision.provider openrouter
hermes config set auxiliary.vision.model google/gemini-2.5-flash
```

### Option 5: Google Gemini (direct, if not blocked)

```bash
hermes config set auxiliary.vision.provider google
hermes config set auxiliary.vision.model gemini-2.5-flash
```

## After Configuring

Restart the gateway for changes to take effect:

```bash
hermes gateway restart
```

Then test by sending an image through WeChat/QQ. The agent should now
describe the image content in its response.

## Pitfalls

- **`provider: auto` with no valid provider can CRASH the gateway.** Not just
  silent failure — the auto-provider cycles through all available providers
  (OpenRouter, Nous, etc.), marks each unhealthy on credential/payment errors,
  and the error spam can crash the gateway process. Always set an explicit
  provider or disable auxiliary vision entirely.
- **Disabling auxiliary vision:** set `provider` to empty string to prevent
  the auto-cycling crash:
  ```bash
  hermes config set auxiliary.vision.provider ""
  ```
  The gateway will run stably; images will be saved but not analyzed.
- **Auxiliary vision is NOT MCP**: it's a regular LLM provider slot. No MCP
  server config needed. Confusing the two is common.
- **`image_input_mode: auto`** in `agent` section must be left at default —
  this controls whether Hermes attempts image analysis at all.
- **Gateway restart required**: config changes to auxiliary.vision don't
  take effect until gateway restarts.
- **API key check**: ensure the provider's API key exists in `.env` or via
  `hermes auth`. Use `hermes auth list` to verify.

## Verification

1. Check config: `hermes config get auxiliary.vision`
2. Check auth: `hermes auth list`
3. Restart: `hermes gateway restart`
4. Send a test image through WeChat/QQ and verify the bot describes it
