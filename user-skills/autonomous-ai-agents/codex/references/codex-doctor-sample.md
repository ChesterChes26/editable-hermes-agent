# Codex Doctor Sample Output (v0.142.0, Windows, API key auth)

Real output from a working Codex installation with OpenAI Official provider,
empty config.toml, and API key auth. Corporate network blocks api.openai.com
so connectivity checks fail, but auth and config are correct.

```
Codex Doctor v0.142.0 · windows-x86_64

Notes
   websocket    Responses WebSocket timed out; HTTPS fallback may still work
   git          Git executable was found on PATH but did not return a version
   reachability one or more required provider endpoints are unreachable over HTTP

Environment
  system       zh-CN
      os                       Windows 10.0.26200 (Windows 11 Professional) [64-bit]
  runtime      npm
      version                  0.142.0
      install method           npm
  install      consistent
  search       file exists (bundled rg.exe)
  git          Git executable was found on PATH but did not return a version
  terminal     Windows Terminal
  title        default · project <name>
  state        databases healthy
      default model provider   openai
      rollout DB model providers custom=7
      rollout DB sources       cli=7

Configuration
  config       loaded
      model                    <default> · openai
      cwd                      current directory
      config.toml              ~/.codex/config.toml
      config.toml parse        ok
      feature flags            31 enabled · 0 overridden
  auth         auth is configured
      auth storage mode        File
      auth file                ~/.codex/auth.json
      stored auth mode         api_key
      stored API key           true
      stored ChatGPT tokens    false
      stored agent identity    false
  mcp          no MCP servers configured
  sandbox      restricted fs + restricted network · approval OnRequest

Updates
  updates      update configuration is locally consistent
      latest version           0.142.0
      latest version status    current version is not older

Connectivity
  network      no proxy env vars
  websocket    Responses WebSocket timed out
      model provider           openai
      provider name            OpenAI
      wire API                 responses
      auth mode                api_key
      endpoint                 wss://api.openai.com/v1/<redacted>
  reachability one or more required provider endpoints are unreachable over HTTP
      reachability mode        API key auth
      openai API base URL      https://api.openai.com/v1 request timed out (required)

Background Server
  app-server   not running (ephemeral mode)

14 ok · 1 idle · 3 notes · 2 warn · 1 fail failed
```

## Key Diagnostic Fields

| Field | Meaning |
|-------|---------|
| `default model provider   openai` | Provider is OpenAI Official (not ccswitch/third-party) |
| `model   <default> · openai` | No model override in config.toml |
| `stored API key   true` | API key present in auth.json |
| `stored ChatGPT tokens   false` | Not using ChatGPT OAuth |
| `rollout DB model providers custom=N` | Past third-party tool history count (N=7 in this case, from ccswitch) |
| `config.toml parse   ok` | Config file is valid (empty is valid) |
| `feature flags   31 enabled · 0 overridden` | No manual feature flag changes |

## Known Network Issue Pattern

When `openai API base URL   https://api.openai.com/v1 request timed out (required)`
appears alongside correct auth and config, the cause is a network/firewall/VPN
block — not a configuration error. The same install works elsewhere.
