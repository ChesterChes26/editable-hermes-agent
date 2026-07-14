# DeepSeek Providers for Codex CLI

Codex uses OpenAI Responses API protocol (`wire_api = "responses"`). DeepSeek only provides Chat Completions API. A protocol translation layer is required — you cannot point `base_url` at DeepSeek's endpoint directly.

## Three bridging approaches (researched 2026-07-08)

### 1. ccswitch-deepseek (liuzhengming/ccswitch-deepseek, ★287)

Pure Node.js local proxy. Translates Responses ↔ Chat Completions bidirectionally.

- **Strengths:** Lightweight (npm install + .env + npm start), focused on protocol translation, covers reasoning_content cross-turn recovery, tool_calls mapping, SSE event translation
- **Weaknesses:** Last code push 2026-05-26 (stale), 7 open issues, no GUI
- **License:** ISC
- **When suitable:** Quick one-off sessions where you just need DeepSeek to answer Codex queries

### 2. CodeSeeX (TasteSteak/CodeSeeX, ★84)

Desktop app (Electron) with full agent runtime layer, not just protocol translation.

- **Strengths:** Actively maintained (last push 2026-07-07), 0 open issues, handles tool lifecycle, context hygiene (prevents tool results from polluting later turns), usage tracking by task, GUI dashboard
- **Weaknesses:** Heavier (Electron), AGPL-3.0 license, smaller community
- **Version:** 0.5.4
- **When suitable:** Real Codex agent work — long sessions, tool loops, large repos

#### Known bugs (all 15 issues closed as of 2026-07-08)

Real bugs encountered and resolved:
- #15: Cache miss rate zero when launching Codex from CodeSeeX
- #14: Tool call repeated 3x on long-running tasks → SSE stream disconnect
- #11: Sub-agent (delegate) tool not working
- #7: apply_patch broken after update
- #6: Model catalog schema error
- #5: Codex MCP tools not discoverable
- #1: model-catalog.json generation failure

Startup issues resolved: #10/#12 proxy startup failure, #13 update errors

### 3. cc-switch (farion1231/cc-switch, ★114k)

All-in-one GUI manager for Claude Code / Codex / Gemini CLI / Hermes Agent. Built-in provider switching with routing configuration. If you already use cc-switch, its routing UI may handle DeepSeek natively.

## CodeSeeX Installation & Configuration

### Download (when git clone is blocked)

The release binary (~6 MB NSIS installer) is on GitHub Releases. If `git clone` or direct `github.com` HTTPS fails but `api.github.com` works:

```bash
# Download release asset via API (bypasses github.com CDN)
ASSET_ID=$(curl -s "https://api.github.com/repos/TasteSteak/CodeSeeX/releases/tags/v0.5.4" | python -c "import sys,json; [print(a['id']) for a in json.load(sys.stdin)['assets'] if 'Windows' in a['name']]")
curl -sL -H "Accept: application/octet-stream" "https://api.github.com/repos/TasteSteak/CodeSeeX/releases/assets/$ASSET_ID" -o installer.exe
```

For source code download when git is blocked:
```bash
curl -sL "https://api.github.com/repos/TasteSteak/CodeSeeX/zipball/main" -o repo.zip
```

### Silent install gotcha

NSIS `/S` flag from bash may fail silently. Use interactive install via cua-driver or run from cmd.exe:
```cmd
cmd.exe /c "installer.exe /S /D=C:\Path\To\Install"
```

### Post-install

- Binary: `C:\Program Files\CodeSeeX\codeseex-desktop.exe`
- Data dir: `~/.codeseex/` (config.toml, model-catalog.json, logs/, secrets/)
- Proxy: `http://127.0.0.1:8787/v1` (default)
- Exposed models: `deepseek-v4-flash`, `deepseek-v4-pro`
- Verify: `curl http://127.0.0.1:8787/v1/models`

### API Key configuration trap

CodeSeeX picks up API keys from Codex auth cache or `DEEPSEEK_API_KEY` env var. If you previously used a third-party relay (e.g. right.codes), CodeSeeX may use THAT key against DeepSeek's endpoint — and fail with auth error. Fix:

1. Set `DEEPSEEK_API_KEY=sk-your-deepseek-key` env var and restart CodeSeeX, OR
2. Configure via GUI: Settings → Proxy → set DeepSeek base URL + API key

### Codex config.toml after setup

```toml
model_provider = "custom"
model = "deepseek-v4-pro"
disable_response_storage = true
model_reasoning_effort = "xhigh"

[model_providers.custom]
name = "DeepSeek"
wire_api = "responses"
requires_openai_auth = true
base_url = "http://127.0.0.1:8787/v1"
```

For faster model: `model = "deepseek-v4-flash"`

### Commit analysis (2026-07-08 main branch audit)

All 7 real bugs from closed issues have corresponding fix commits — not just closed and ignored:

| Issue | Title | Commit(s) | Date |
|-------|-------|-----------|------|
| #14 | Stream disconnect after 3x tool repeat | `de512a5`, `343a5e0`, `94219f2` (0.5.4 hotfix) | 6/20–7/7 |
| #15 | Zero cache hit rate | `46d24d4` | 7/6 |
| #7 | apply_patch broken | `3b52555`, `f2b1fe5` | 6/2–6/4 |
| #11 | Sub-agent tool not working | `de512a5`, `9716a85`, `dac5bbe` | 6/16–6/20 |
| #5 | MCP tools not discoverable | `8a27768`, `dac5bbe` | 6/16 |
| #6 | Model catalog schema error | Early fixes in 0.5.0 | 5/21–5/24 |

Pattern: issues are closed optimistically (close date before fix-in-main date), but commits follow within 1-4 weeks. Latest release (0.5.4, July 7) is a dedicated "agent stability hotfix".

### Common config.toml pitfalls when switching providers

#### Missing model_catalog_json — can't switch models

After switching to a custom provider with `model_catalog_json`, if you omit this field, Codex can only use the single `model = "..."` you set — the model picker in Codex Desktop won't show other models from the catalog.

**Fix:** ensure `model_catalog_json` points to a valid catalog file:
```toml
model_catalog_json = "C:\\Users\\<user>\\.codeseex\\model-catalog.json"
```
Path must use TOML-escaped backslashes (`\\`) or forward slashes. Restart Codex after adding.

#### Plugin/marketplace config silently lost

When users regenerate `config.toml` for a new provider (often by copying from a tool like CodeSeeX or cc-switch), the `[marketplaces.*]` and `[plugins.*]` sections are NOT included — they're specific to the old config. After restart, all previously enabled plugins (superpowers, etc.) silently fail to load.

**Fix:** after switching providers, manually merge the marketplace/plugin stanzas from a backup of the old config. Example:
```toml
[marketplaces.superpowers-dev]
source = "https://github.com/obra/superpowers.git"

[plugins."superpowers@superpowers-dev"]
enabled = true
```

**Verification:** `codex plugin list` shows `installed, enabled` for expected plugins. A `codex exec "list loaded skills"` confirms they appear in the system prompt.

#### Compatibility confirmed

As of 2026-07-08: Codex 0.142.5 + CodeSeeX 0.5.4 + DeepSeek V4 Pro + superpowers v6.1.1 — all 14 superpowers skills load correctly. `model_reasoning_effort = "xhigh"` is the recommended value for DeepSeek V4 Pro (matches the Flash→medium, Pro→xhigh convention).

## Recommendation (as of 2026-07)

CodeSeeX over ccswitch-deepseek. ccswitch-deepseek's last code push was May 2026 and has 7 unresolved issues. CodeSeeX is actively maintained and designed specifically for Codex agent sessions (tool lifecycle, context management), not just chat-level protocol translation. The tradeoff is AGPL-3.0 + Electron weight.

### Unresolved testing (not yet verified)

- #11 sub-agent delegate path — fix commits exist but not field-tested
- #7 apply_patch — fix commits exist but not field-tested
- Long-session stability under real agent workload — 0.5.4 hotfix is new
