---
name: hermes-provider-setup
description: "Configure and troubleshoot third-party LLM providers in Hermes — add new providers, debug 401/403 errors, test API keys safely without secret redaction interference."
version: 1.0.0
category: devops
---

# Hermes Provider Setup

Adding a new LLM provider (DeepSeek, DashScope, xAI, etc.) to Hermes and
troubleshooting when model switching returns auth errors.

## Trigger

Load this skill when:
- Adding a new third-party LLM provider to Hermes config
- Configuring a custom OpenAI-compatible endpoint from a curl command
- Model switch returns 401 / 403 / 404
- Need to test a provider API key without secret redaction interference

## Provider Configuration Philosophy

All providers should be configured as **named sub-entries under `providers:`**.
The top-level `model.default` and `model.provider` are just the "active" routing
aliases — DO NOT scatter provider-specific `base_url`, `api_key`, or `model`
into the top-level `model:` section. When a curl command is provided, the
extracted endpoint belongs in `providers.<name>*`, NOT in `model.base_url`.

The pattern used by every Hermes-bundled provider (dashscope, deepseek, etc.):

```yaml
model:
  default: deepseek-chat     # alias for the current active model id
  provider: deepseek         # alias for the active provider name
  base_url: ''               # keep empty — providers have their own
  api_key: ''
providers:
  deepseek:
    base_url: https://api.deepseek.com
    model: deepseek-chat
  dashscope:
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    model: qwen3.6-plus
```

**CRITICAL:** The system prompt derives `Model:` from `model.default`, NOT from
`providers.<current>.model`. If you put a bare unfriendly name in
`model.default` (e.g., `deepseek-chat` when the actual routed model is
`gpt-5.4-2026-03-05`), the agent will display the wrong model name in its
identity block. Keep `model.default` matching the actual model you want.

## Rollback: Reverting to Known Clean State

When experimenting with new providers and the config gets into an inconsistent
state (wrong model.default, leftover provider segments, credential pool
corruption), revert to a known-good baseline:

1. **Visual inspection first:** `read_file config.yaml` to see the full config
2. **Restore top-level aliases** to the previous known-good values:
   ```bash
   hermes config set model.default "<previous-model>"
   hermes config set model.provider "<previous-provider>"
   ```
3. **Remove the misconfigured provider block** (via Python, NOT `hermes config`):
   ```python
   import os, yaml
   path = os.path.join(os.environ['LOCALAPPDATA'], 'hermes', 'config.yaml')
   with open(path) as f:
       cfg = yaml.safe_load(f)
   if 'providers' in cfg and '<bad-name>' in cfg['providers']:
       del cfg['providers']['<bad-name>']
   with open(path, 'w') as f:
       yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
   ```
4. **Verify the reverted state** is correct before adding the new provider back.
5. **Pitfall: remembering the right defaults.** Use session_search to find the
   earlier conversation where the config was last known-working. The CLI does not
   store config git history — session transcripts are the only rollback reference.

## Custom Endpoint: Two Patterns

Hermes supports two patterns for custom OpenAI-compatible endpoints. Use the
appropriate one based on whether the endpoint is permanent or temporary.

### Pattern A: Quick model.* (one-off / temporary)

For a one-off custom endpoint, use the top-level `model.*` keys. Fastest path —
no `.env`, no credential pool, no provider name indirection.

```bash
hermes config set model.base_url "https://gateway.example.com/<routing-key>/v1"
hermes config set model.api_key "sk-or-bearer-token"
hermes config set model.default "model-name"
```

**Downside:** `hermes model` picker won't show models (custom endpoint has no
built-in model list). Switching models requires `hermes config set model.default`
or `/model <name>` in-session — you must know model names yourself.

### Pattern B: Named provider (permanent, recommended)

For a permanent endpoint you'll keep switching models on, register it as a named
provider under `providers:` — same as `dashscope` or `deepseek`. This keeps the
top-level `model` section clean and isolates the endpoint config.

**Step 1: Clear model.*, set provider name:**

```bash
hermes config set model.base_url ""
hermes config set model.api_key ""
hermes config set model.provider "<short-name>"
hermes config set model.default "<model-name>"
```

**Step 2: Add provider block (api_key inline to bypass credential pool):**

```bash
hermes config set providers.<short-name>.base_url "https://gateway.example.com/<key>/v1"
hermes config set providers.<short-name>.api_key "<bearer-token>"
hermes config set providers.<short-name>.model "<model-name>"
```

Result in `config.yaml`:

```yaml
model:
  base_url: ''
  provider: qb
  default: gpt-5.4-2026-03-05
  api_key: ''

providers:
  qb:
    base_url: https://openai.prod.ai-gateway.quantumblack.com/<uuid>/v1
    api_key: <token>
    model: gpt-5.4-2026-03-05
```

**Why write api_key into the provider block?** See "Credential Pool Overrides"
pitfall below. Writing `api_key` directly into the provider config bypasses
credential pool resolution and prevents base_url mismatch. The pitfall about
secret redaction corrupting `hermes config set api_key` values (see next section)
applies to `.env`-based keys, not config-inline keys — when the key is already
in `config.yaml`, Hermes doesn't go through credential pool resolution.

**Switching models:** Use `hermes config set model.default <name>` or `/model <name>`.
The `hermes model` picker still won't enumerate models from a custom endpoint,
but the provider is properly registered.

### Extracting from a curl command

The user often has a `curl … /v1/chat/completions` command. Strip the trailing
`/chat/completions` from the URL to get `base_url`. The `Authorization: Bearer <token>`
value is the `api_key`. Any path segments between the host and `/v1` (e.g.,
routing keys, tenant UUIDs) stay as part of `base_url`.

### Listing available models

Most OpenAI-compatible endpoints expose `/v1/models`. Do NOT pipe curl into
python on Windows git-bash — the pipe truncates or corrupts JSON. Use a
temp-file approach:

```bash
# Write to temp file first, then parse — works cross-platform
curl -s "<base_url>/models" -H "Authorization: Bearer <key>" -o "$TEMP/qb_models.json"
python -c "
import json, os
with open(os.path.join(os.environ['TEMP'], 'qb_models.json')) as f:
    data = json.load(f)
for m in sorted(m['id'] for m in data.get('data', [])):
    print(m)
"
```

To filter out non-chat models (fine-tuned, embedding, tts, experimental):

```python
skip_prefix = ['ft:', 'text-embedding', 'tts-', 'whisper-', 'omni-moderation']
skip_contains = ['embedding', 'tts', 'whisper', 'moderation', 'sora', 'audio',
    'realtime', 'image-', 'transcribe', 'davinci', 'babbage', 'alpha',
    'crest', 'glacier', 'kepler', 'mercury', '1p-exp', 'treatment']
chat = [m for m in sorted(models)
        if not any(m.startswith(p) for p in skip_prefix)
        and not any(x in m for x in skip_contains)]
```

**Pitfall: `/v1/models` lists models the gateway may deny.** Some AI gateways
(notably QuantumBlack) return model IDs in `/v1/models` that the API key is NOT
authorized to use — aliases (`gpt-5.5`), Pro variants (`gpt-5.4-pro`), and
experimental models. Only dated version IDs (e.g., `gpt-5.4-2026-03-05`) may be
accessible. Always test candidate models individually before assuming they work.

**Pitfall: `model.default` ≠ system prompt display.** Hermes initialises
`agent.model` from `model.default` and shows it in the system prompt as
`Model: <value>`. It does NOT read `providers.<provider>.model`. This means
if `model.default` is `deepseek-chat` but the actual model routed by the provider
is `gpt-5.4-2026-03-05`, the agent will tell the user the wrong model. Keep
`model.default` reflecting the real model being used, or override via `/model`
at session start (which changes `agent.model` for that session).

### Testing model availability in batch

Test multiple candidate models sequentially with a small sleep to avoid rate
limits. Parallel (ThreadPoolExecutor) can trigger 429s on some gateways:

```python
import urllib.request, json, time

for model in candidates:
    try:
        data = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": "hi"}],
            "max_completion_tokens": 3  # USE max_completion_tokens — GPT-5.4+ rejects max_tokens
        }).encode()
        req = urllib.request.Request(url, data=data, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"OK  {model}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        reason = "denied" if "not allowed" in body else f"HTTP {e.code}"
        print(f"NO  {model} ({reason})")
    time.sleep(0.3)
```

## Provider Config Pattern

In `config.yaml`, under `providers:`, add a named entry with at minimum
`base_url` and `model`. Do NOT set `api_key` — Hermes auto-detects it
from the `.env` file via the convention `<PROVIDER>_API_KEY`.

```yaml
providers:
  deepseek:
    base_url: https://api.deepseek.com
    model: deepseek-v4-pro
  dashscope:
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    model: qwen3.6-plus
```

In `.env`:
```
DEEPSEEK_API_KEY=sk-xxx
DASHSCOPE_API_KEY=sk-xxx
```

The env var naming convention is documented in the hermes-agent skill's
provider table. Common ones:
- DeepSeek → `DEEPSEEK_API_KEY`
- DashScope / Alibaba → `DASHSCOPE_API_KEY`
- xAI / Grok → `XAI_API_KEY`
- Kimi / Moonshot → `KIMI_API_KEY`

## Critical Pitfall: Secret Redaction Corrupts `hermes config set`

**NEVER use `hermes config set` to write `api_key` values.** Hermes's
secret-redaction system (`security.redact_secrets: true`) scans all tool
output including `hermes config set` values, and will truncate or
corrupt the written value. A command like:

```
hermes config set providers.dashscope.api_key 'sk-40dbd...'
```

may write a truncated `${DASH...Y}` garbage string into config.yaml
instead of the real key — the redactor intercepts the value before
it reaches the file. This produces a 401 on next use because the
stored "key" is not a valid credential.

**Preferred approach:**
1. Put the key in `~/.hermes/.env` as `<PROVIDER>_API_KEY=sk-xxx`
2. Do NOT add an `api_key` field to the provider block in config.yaml
3. Hermes auto-maps provider name → env var at runtime

**Fallback when credential pool misbehaves:** If the credential pool
(see next pitfall) overrides your correct base_url, write `api_key`
directly into the provider block in config.yaml via Python (NEVER
via `hermes config set`). This bypasses the credential pool entirely:

```python
import os, yaml
# Read key from .env (within script, no redaction)
env_path = os.path.join(os.environ['LOCALAPPDATA'], 'hermes', '.env')
key = None
with open(env_path) as f:
    for line in f:
        if line.startswith('DASHSCOPE_API_KEY=***            key = line.split('=', 1)[1].strip()
            break
# Write to config
config_path = os.path.join(os.environ['LOCALAPPDATA'], 'hermes', 'config.yaml')
with open(config_path) as f:
    cfg = yaml.safe_load(f)
cfg['providers']['dashscope']['api_key'] = key
with open(config_path, 'w') as f:
    yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
```

## Critical Pitfall: Credential Pool Overrides Provider base_url

Hermes maintains a credential pool in `auth.json` (view with `hermes auth list`)
that maps provider names to stored credentials and base URLs. When a credential
pool entry exists for a provider, its `base_url` **takes precedence** over the
`base_url` in `config.yaml`'s `providers.<name>` block.

This causes silent 401 when:
- Your `.env` key works (verified with Python test → HTTP 200)
- Your config.yaml provider has the correct base_url
- But the credential pool entry has a **different** base_url (e.g., international
  vs China endpoint for DashScope: `dashscope-intl.aliyuncs.com` vs
  `dashscope.aliyuncs.com`)

**Detection:** The Hermes error message shows the actual endpoint being used:
```
Endpoint: https://dashscope-intl.aliyuncs.com/compatible-mode/v1
```
If this differs from your config.yaml's `base_url`, the credential pool is
overriding.

**Fixes (in order of preference):**

1. **Direct api_key in config.yaml** — write `api_key` into the provider block
   via Python (see fallback in previous pitfall). This bypasses credential pool
   resolution entirely.

2. **Reset credential pool:** `hermes auth reset alibaba` (use the pool name,
   not the config provider name — check with `hermes auth list`). Then re-test.

3. **Edit auth.json directly via Python** — update the pool entry's `base_url`.
   Note: credential pool may cache/revert edits; if changes don't stick, use
   option 1.

**How credential pool entries get created:** When Hermes first uses a provider
with credentials, it auto-creates pool entries. The base_url is snapshotted at
creation time. If you later change the provider's base_url in config.yaml, the
pool entry retains the old value.

If you accidentally wrote a corrupted `api_key` into config.yaml,
remove it:

```bash
# Replace with empty, then use Python to delete the key entirely
hermes config set providers.<name>.api_key ''
# Then edit config.yaml to remove the empty api_key: '' line
```

## Pitfall: max_tokens Rejected by Newer GPT Models (5.4+)

When testing a provider endpoint with raw curl or Python `urllib`, newer
GPT models (5.4 and above) reject the `max_tokens` parameter:

```
HTTP 400: "Unsupported parameter: 'max_tokens' is not supported with this
model. Use 'max_completion_tokens' instead."
```

Use `max_completion_tokens` instead for these models. Hermes handles this
internally for known model IDs, but manual testing scripts must use the
correct parameter name. This affects `gpt-5.4`, `gpt-5.5`, `gpt-5.6`, `o3`,
`o4-mini`, and any future models in that lineage.

## Testing a Provider Key Directly

To verify a key works without Hermes's routing layer (and without
shell-level secret redaction mangling the value), test via Python:

```python
import os, json, urllib.request

env_path = os.path.join(os.environ['LOCALAPPDATA'], 'hermes', '.env')
key = None
with open(env_path) as f:
    for line in f:
        if line.startswith('PROVIDER_API_KEY='):
            key = line.split('=', 1)[1].strip()
            break

data = json.dumps({
    "model": "model-name",
    "messages": [{"role": "user", "content": "say hi"}],
    "max_completion_tokens": 20  # GPT-5.4+ rejects max_tokens
}).encode()

req = urllib.request.Request(
    "https://api.example.com/v1/chat/completions",
    data=data,
    headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
)

try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = json.loads(resp.read())
        print(f"HTTP {resp.status}")
        print(body.get('choices', [{}])[0].get('message', {}).get('content', ''))
except urllib.error.HTTPError as e:
    body = json.loads(e.read())
    print(f"HTTP {e.code}: {body.get('error', {}).get('message', '')}")
```

This bypasses both shell redaction and Hermes's config resolution,
giving a clean yes/no on whether the key + model combination works.

## Troubleshooting 401

1. **Direct key test:** Test the key directly with Python (see above).
   If HTTP 200 but Hermes gets 401, the issue is in Hermes config resolution.

2. **Credential pool endpoint mismatch (most common):** Check the Endpoint
   in the Hermes error message. If it differs from your config.yaml
   `providers.<name>.base_url`, the credential pool is overriding. See
   "Credential Pool Overrides Provider base_url" pitfall above. Fix: write
   `api_key` into provider config via Python.

3. **`api_key` field in config.yaml?** If present, it may contain a
   redacted/corrupted value from a previous `hermes config set` attempt.
   Remove it before relying on `.env`.

4. **Provider missing `model` field?** Without an explicit `model`
   in the `providers.<name>` block, Hermes may not route correctly
   even with a valid `base_url`.

5. **Wrong env var name?** Check the provider table in the
   hermes-agent skill for the correct env var convention.

6. **Credential pool auth failure sticky state:** When a credential pool
   entry shows "auth failed" status (check with `hermes auth list`), it may
   be marked unhealthy. Reset with `hermes auth reset <pool-name>`.

## Troubleshooting 403 (Model Access Denied)

The key is valid but the model ID is wrong or not authorized for
this key. Common causes:

- **Gateway lists inaccessible aliases:** Some AI gateways return model
  IDs in `/v1/models` that the API key can't use — short aliases
  (`gpt-5.5`), Pro variants (`gpt-5.4-pro`), and experimental/internal
  models. Only dated version IDs (`gpt-5.4-2026-03-05`) may be
  accessible. Test candidates individually.

- **Wrong model name:** DashScope example: `qwen3.6-plus` works, but
  `qwen-plus-latest`, `qwen-turbo-latest`, and `qwen3-235b-a22b`
  all returned 403 on the same key. Try the exact model ID from the
  provider's console/API docs.

## Provider-Specific Notes

- **DashScope (Alibaba)**: `references/dashscope-config.md`
- **QB (QuantumBlack Gateway)**: 128-tool hard limit — see `references/tool-limit-providers.md`
- **Tool limit debugging**: full methodology in `references/tool-limit-providers.md`

## Diagnosing Tool Count Issues

Some AI gateways enforce maximum tool counts on API requests. Hermes sends
~134 tools by default (~34 built-in from enabled toolsets + ~13 plugin +
~50 agentmemory MCP + ~37 cua-driver MCP), which can exceed gateway limits
(QB: 128, others may vary). Symptoms:

```
HTTP 400: Invalid 'tools': array too long. Expected an array with maximum
length 128, but got an array with length 134 instead.
```

This is NOT a model availability issue — the gateway rejects the request
before it reaches the model. The same tool set works fine on providers
without this limit (DeepSeek, Anthropic, etc.).

**Important:** `hermes tools disable` on already-disabled toolsets (kanban,
spotify, discord, etc.) has NO effect — these are already excluded by
`platform_toolsets.cli`. The real tool count is determined by enabled
toolsets + MCP servers, NOT by the full registry.

**Quick diagnosis (what's actually sent):**

```bash
cd ~/.hermes/hermes-agent && ./venv/Scripts/python.exe -c "
from toolsets import resolve_toolset
# Replace with your actual platform_toolsets.cli
ts = ['browser','clarify','code_execution','computer_use','cronjob',
      'delegation','file','horizon','image_gen','memory','session_search',
      'skills','terminal','todo','tts','vision','web']
total = set()
for t in ts:
    total.update(resolve_toolset(t))
print(f'Built-in (enabled): {len(total)}')
# Add MCP from mcp_servers config (~50 agentmemory + ~37 cua-driver)
print(f'Estimated total with MCP: {len(total) + 87}')
"
```

Full enumeration, toolset grouping, and fix strategies:
`references/tool-limit-providers.md`.

**Fix:** disable MCP servers (remove from config) or plugin toolsets
(`hermes tools disable horizon`). Must `/reset` for changes to take effect.
**MCP tools bypass platform_toolsets entirely** — see
`references/tool-limit-providers.md` for the full mechanism distinction,
recovery commands, and `hermes tools disable` pitfalls.
