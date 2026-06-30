---
name: horizon
description: "Manage and diagnose the Horizon MCP server (AI-driven info aggregation: fetch → score → filter → enrich → summarize → webhook). Manual JSON-RPC testing, dependency install, pipeline operation, gateway integration."
version: 1.0.0
tags: [horizon, mcp, information-aggregation, deepseek, pipeline, webhook, windows]
category: devops
---

# Horizon MCP Server

Horizon is an AI-driven information aggregation system that tracks academic and social trends. It sources from GitHub, HackerNews, RSS, Reddit, and Telegram, scores items with an LLM (DeepSeek), filters, enriches, and summarizes — all exposed as a 13-tool MCP server called `horizon-mcp`.

**Location:** `D:/workspace/AI-research/Horizon`
**MCP Server:** `python -m src.mcp.server` (stdio transport)
**Version:** 1.26.0
**Config:** `data/config.json`

## Quick Health Check

**Horizon has NO local web dashboard.** It is a CLI tool + MCP server with no built-in HTTP interface. The README links to a project website (`horizon1123.top`) and demo page (`thysrael.github.io/Horizon/`), but these are documentation sites hosted on GitHub Pages, not a local management UI. All interaction is through the MCP tools via Hermes, CLI commands, or webhook push notifications.

MCP server tools are only available in Hermes when the gateway is running with the server connected. Use this diagnostic escalation ladder — start at the top and only go deeper if the previous step fails:

### Step 1: Hermes built-in MCP status (may time out on Windows)

```bash
# Check both MCP servers' status at a glance
hermes mcp list

# Direct connection test (connects, lists tools, reports timing)
hermes mcp test horizon
```

`hermes mcp list` shows transport type, tool count, and enabled/disabled status for all configured MCP servers. `hermes mcp test horizon` does a full initialize + tools/list handshake and reports connection time.

**Pitfall:** Both commands have been observed to time out (>10s, no output) on Windows, likely due to contention with the running gateway's MCP loop. When this happens, fall through to Step 2 (manual JSON-RPC) or Step 4 (log-based diagnosis) — both are reliable regardless of CLI tool state.

### Step 2: Manual JSON-RPC smoke test (when CLI commands aren't available or you need deeper inspection)

```bash
cd D:/workspace/AI-research/Horizon

# Smoke test: server starts and responds
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | python -m src.mcp.server

# Check config (fast — check_env=false avoids LLM client init)
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"hz_validate_config","arguments":{"check_env":false}}}' | timeout 20 python -m src.mcp.server 2>&1 | grep '"jsonrpc"'

# List past pipeline runs
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"hz_list_runs","arguments":{"limit":5}}}' | python -m src.mcp.server 2>&1 | grep '"jsonrpc"'
```

The key pattern: pipe JSON-RPC requests (one per line, no newline between them) to `python -m src.mcp.server`. Each request is a complete JSON-RPC call. Extract results with `grep '"jsonrpc"'`.

## Dependency Installation

Dependencies are listed in `pyproject.toml`. Install all at once:

```bash
cd D:/workspace/AI-research/Horizon
pip install -e .
```

Key deps: `feedparser`, `anthropic`, `openai`, `google-genai`, `httpx`, `ddgs`, `beautifulsoup4`, `rich`, `tenacity`, `mcp`.

If tools return `HZ_IMPORT_FAILED`, a dependency is missing — install it (or all of them with `-e .`).

## Tool Inventory (13 tools)

Pipeline stages (read-only, idempotent — no side effects until webhook):

| Stage | Tool | Transport | Description |
|-------|------|-----------|-------------|
| Validate | `hz_validate_config` | pipe | Check config + env vars |
| Fetch | `hz_fetch_items` | pipe | Fetch + deduplicate → raw stage |
| Score | `hz_score_items` | pipe | LLM score raw → scored stage |
| Filter | `hz_filter_items` | pipe | Threshold + topic dedup → filtered |
| Enrich | `hz_enrich_items` | pipe | Enrich filtered → enriched stage |
| Summarize | `hz_generate_summary` | pipe | Markdown summary from any stage |
| Pipeline | `hz_run_pipeline` | pipe | fetch→score→filter→enrich→summarize in one call |
| Inspect | `hz_list_runs` | direct fs | List recent runs + stage states |
| Inspect | `hz_get_run_meta` | direct fs | Read run metadata |
| Inspect | `hz_get_run_stage` | direct fs | Read items from a stage |
| Inspect | `hz_get_run_summary` | direct fs | Read generated summary |
| Metrics | `hz_get_metrics` | direct fs | Filesystem-based run stats |
| Notify | `hz_send_webhook` | pipe | Send webhook notification |

**Pipe** tools go through `_call_tool` → JSON-RPC subprocess (hold `_proc_lock`). **Direct fs** tools read `data/mcp-runs/` JSON/MD files — no lock, concurrent with pipe operations. See `references/read-write-tool-split.md`.

Full tool schemas with input/output shapes are in `references/tool-schemas.md`.

## Hermes Integration — Two Approaches

### Approach A: Plugin-Based (Recommended)

The Horizon plugin lives under Hermes' home directory — `~/AppData/Local/hermes/plugins/horizon/`
on Windows, `~/.hermes/plugins/horizon/` on macOS/Linux. It spawns Horizon as a subprocess and
registers tools directly via `ctx.register_tool(toolset="horizon")`. This bypasses MCP
client issues (race conditions, toolset filtering, naming prefixes).

**Critical — Windows path:** `get_hermes_home()` on Windows returns `%LOCALAPPDATA%/hermes`
(`hermes_constants.py:46-49`), which resolves to `~/AppData/Local/hermes/`, NOT `~/.hermes/`.
These are two separate directories. Plugin files MUST be in `~/AppData/Local/hermes/plugins/horizon/`
or the gateway will never discover them. See pitfall "Plugin at wrong path" below.

**Setup:**
```bash
hermes plugins enable horizon   # standalone plugins are opt-in
hermes gateway restart
# /reset in CLI session to pick up tools
```

Tools appear as `hz_*` (native names), registered under the `horizon` toolset.
No `mcp_` prefix, no dynamic toolset alias registration.

**Critical pitfall:** Standalone plugins (`kind: standalone`) are NOT auto-enabled.
They must be explicitly opted in via `plugins.enabled` in config.yaml, or they are
discovered but skipped (`hermes_cli/plugins.py:1329-1348`). See full details in
`references/plugin-integration.md`.

### Approach B: MCP-Based (Legacy)

Config in `~/.hermes/config.yaml` under `mcp_servers`:

```yaml
mcp_servers:
  horizon:
    command: python
    args:
    - -m
    - src.mcp.server
    cwd: D:/workspace/AI-research/Horizon
    env:
      DEEPSEEK_API_KEY: sk-...
      PYTHONUTF8: "1"
```

Tools appear as `mcp_horizon_hz_*` in Hermes (e.g. `mcp_horizon_hz_run_pipeline`). The prefix follows the standard MCP convention `mcp_{server}_{tool}` — source at `mcp_tool.py:3669`.

**Critical:** Adding/modifying MCP servers requires gateway restart. Tools are discovered at startup only — no hot-reload. After config change:

```bash
hermes gateway restart   # kill old gateway
hermes gateway run &     # start new (Windows: restart only kills, doesn't start)
```

Then `/reset` in the current session to pick up new tools.

**Do NOT use both approaches simultaneously.** If the plugin is enabled, ensure
`mcp_servers.horizon` is commented out (or removed) to avoid double-registration.

## Pitfalls

### `check_env=true` hangs

`hz_validate_config` with `check_env=true` initializes the LLM client (DeepSeek), which can time out over stdio. Use `check_env=false` for fast config validation — it still checks config structure, sources, and category groups. Only use `check_env=true` when you specifically need to verify API key connectivity.

### Standalone plugin discovered but not enabled — tools never load

The Horizon plugin (`kind: standalone`) is discovered by the plugin scanner at gateway
startup but **never loaded** unless explicitly enabled. Cause: `hermes_cli/plugins.py:1329-1348`
— standalone plugins are opt-in via `plugins.enabled`.

**Symptoms:**
- Plugin files exist at `~/.hermes/plugins/horizon/` with valid `plugin.yaml` and `register(ctx)`
- Gateway log shows `Plugin discovery complete: N found, M enabled` — horizon is in the (N-M) skipped
- No `hz_*` tools appear in any session, even after `/reset` or `/new`
- Debug-level log (not visible at INFO): `Skipping 'horizon' (not in plugins.enabled)`
- Config at `~/.hermes/config.yaml` shows `plugins.enabled: [agentmemory]` — horizon missing

**Fix:**
```bash
hermes plugins enable horizon   # adds to plugins.enabled
hermes gateway restart          # loads the plugin
# /reset in CLI to pick up hz_* tools
```

**Why it's not auto-enabled:** Unlike `kind: backend` and `kind: platform` plugins
(which auto-load because they're critical infrastructure), standalone plugins require
user opt-in to avoid surprise tool proliferation. The scanner discovers them so
`hermes plugins list` shows them, but loading requires `plugins.enabled`.

Full architecture details: `references/plugin-integration.md`.

### Plugin at wrong path — Windows `~/.hermes` ≠ `AppData/Local/hermes`

On Windows, `get_hermes_home()` returns `%LOCALAPPDATA%/hermes` (e.g. `C:\\Users\\<user>\\AppData\\Local\\hermes`)
— NOT `~/.hermes`. These are two physically separate directories (`hermes_constants.py:46-49`).
Plugin discovery scans `$(hermes_home)/plugins/` (`hermes_cli/plugins.py:1192-1193`), so plugin files
must be at `AppData/Local/hermes/plugins/horizon/`, not `~/.hermes/plugins/horizon/`.

**How this happens:** External tools (e.g. Claude Code) or agents may write files to `~/.hermes/`
because that's the conventional path on macOS/Linux. On Windows this silently creates a parallel
directory that Hermes never reads.

**Symptoms:**
- Plugin files exist at `~/.hermes/plugins/horizon/` with valid `plugin.yaml` and `__init__.py`
- Config has `plugins.enabled: [agentmemory, horizon]` ✓
- Gateway restart shows MCP only (53 agentmemory tools, no horizon) but no errors
- `Plugin discovery complete` log still shows the old count (plugin not found)
- No `hz_*` tools in any session

**Diagnosis:**
```bash
# Compare both directories
ls ~/.hermes/plugins/horizon/        # files exist here ✓
ls ~/AppData/Local/hermes/plugins/   # only agentmemory, horizon missing ✗

# Verify Hermes home path
grep -n "def get_hermes_home\\|win32\\|LOCALAPPDATA" $(which hermes)/../hermes_constants.py | head -5
```

**Fix:**
```bash
cp -r ~/.hermes/plugins/horizon/ ~/AppData/Local/hermes/plugins/
hermes gateway restart
# Then /reset to pick up hz_* tools
```

**Extra:** Once the AppData copy is confirmed working, delete the `~/.hermes/plugins/horizon/`
redundant copy to avoid future confusion:
```bash
rm -rf ~/.hermes/plugins/horizon
```

### Plugin disappears after restart — template config restore

**Root cause:** Hermes may restore configuration from a **template** file
`user-config/config.yaml` on restart. If this template only has `agentmemory` in
`plugins.enabled` (missing `horizon`), the restored runtime config loses `horizon`,
and the plugin is skipped on the next gateway load — even though you previously
fixed the runtime `config.yaml`.

This means fixing ONLY the runtime `config.yaml` is **insufficient** — the fix
survives until the next restart, then gets silently undone.

**Symptoms:**
- Horizon tools worked in a previous session after running `hermes plugins enable horizon`
- After a Hermes restart (or machine reboot), `hz_*` tools disappear
- Runtime `config.yaml` shows `horizon` in `plugins.enabled` — but `user-config/config.yaml` does NOT
- Re-running `hermes plugins enable horizon` fixes it — but only until the next restart

**Locations:**
- Runtime config: `%LOCALAPPDATA%/hermes/config.yaml`
- Template config: `%LOCALAPPDATA%/hermes/hermes-agent/user-config/config.yaml`

**Fix — update BOTH files:**
```bash
# 1. Ensure runtime config has horizon
hermes plugins enable horizon

# 2. Manually verify and fix the template too
python -c "
import yaml, os
path = os.path.expandvars(r'%LOCALAPPDATA%\hermes\hermes-agent\user-config\config.yaml')
cfg = yaml.safe_load(open(path))
if 'horizon' not in cfg['plugins']['enabled']:
    cfg['plugins']['enabled'].append('horizon')
    yaml.dump(cfg, open(path, 'w'), default_flow_style=False)
    print('Fixed: added horizon to template')
else:
    print('Template already has horizon')
"
```

**Also check:** If using the plugin approach, remove `mcp_servers.horizon` from BOTH
configs to avoid double-registration risk:
```bash
# Check template for stray mcp_servers.horizon
grep -A8 'mcp_servers:' ~/AppData/Local/hermes/hermes-agent/user-config/config.yaml
```

Full diagnosis session details: `references/template-config-restore.md`.

### Handler signature: MUST accept **kwargs

Plugin tool handlers are dispatched via `tools/registry.py:404`: `entry.handler(args, **kwargs)`. Hermes passes extra keyword arguments (`task_id`, `session_id`, `tool_call_id`, `turn_id`, `api_request_id`). Handlers that only accept `(args: dict)` will fail with `TypeError: handler() got an unexpected keyword argument 'task_id'`.

**Symptoms:**
- Tools appear in the agent's available tool list (registration succeeded)
- Every tool call fails with `TypeError: ... got an unexpected keyword argument 'task_id'`
- Plugin `.pyc` cache may mask the fix even after gateway restart — clear `__pycache__/`

**Fix:**
```python
# WRONG — fails at runtime
def hz_get_metrics_handler(args: dict) -> str:
    return _call_tool("hz_get_metrics", args)

# CORRECT — swallows Hermes kwargs
def hz_get_metrics_handler(args: dict, **kwargs) -> str:
    return _call_tool("hz_get_metrics", args)
```

After fixing, clear `__pycache__/`, restart gateway, and `/reset` the session.

**Source:** `hermes-internals` skill `references/plugin-tool-registration.md` pitfall #5.

### Plugin discovery log swallowed by concurrent_log_handler lock contention

### Dependencies missing in Hermes venv (NOT system Python)

The Hermes gateway spawns MCP servers using its own venv Python at `~/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe`, NOT the system Python. Dependencies MUST be installed in that venv for the gateway to connect.

Two ways to install:

```bash
# Option A: Use the venv pip directly (preferred — unambiguous)
~/AppData/Local/hermes/hermes-agent/venv/Scripts/pip.exe install -e D:/workspace/AI-research/Horizon

# Option B: Install from the venv shell
~/AppData/Local/hermes/hermes-agent/venv/Scripts/pip.exe install feedparser anthropic google-genai ddgs
```

After installing, verify:
```bash
~/AppData/Local/hermes/hermes-agent/venv/Scripts/pip.exe list | grep horizon
# should show: horizon  0.1.0  D:\workspace\AI-research\Horizon
```

Common symptom: Manual `python -m src.mcp.server` works fine from your terminal (system python with deps), but gateway logs show `ModuleNotFoundError: No module named 'src'` (Hermes venv python without deps).

### Dependencies missing after fresh clone

Horizon has 12+ pip dependencies. If `hz_*` tools return `HZ_IMPORT_FAILED`, ensure deps are in the Hermes venv (see above). The error message names the missing module — install it individually or all at once.

### Tools not in API Server / chatbot session (Hermes-A, WeChat, QQ)

**This is the most common "connected but no tools" scenario for non-CLI platforms.** The API Server gateway platform (`Hermes-A`, WeChat, QQ bot) builds agents with `enabled_toolsets` from `_get_platform_tools(config, "api_server")` at `api_server.py:1103`. This function resolves the `hermes-api-server` composite toolset to individual configurable toolsets — but **only** iterates `CONFIGURABLE_TOOLSETS` (static: `web`, `terminal`, `file`, etc.). MCP toolsets like `mcp-horizon` are dynamically registered via `registry.register_toolset_alias()` at `mcp_tool.py:3991` and are invisible to this resolution path.

The recovery loop at `tools_config.py:1518-1534` iterates the static `TOOLSETS` dict — MCP toolsets are absent from this dict (they only exist in the registry). Result: `mcp-horizon` is never in the agent's `enabled_toolsets`, and `get_tool_definitions()` filters all Horizon tools out.

**Symptoms:** (a) mcp-stderr shows ListToolsRequest + PingRequest (gateway connected), (b) `agent.log` shows `"MCP server 'horizon' (stdio): registered 17 tool(s): mcp_horizon_hz_*"` (tools registered), (c) but `mcp_horizon_hz_*` tools are absent from the Hermes-A/chatbot session.

**Why CLI sessions work:** The CLI uses `hermes-cli` toolset which includes `_HERMES_CORE_TOOLS` — all core tools. The API Server uses `hermes-api-server` which is a curated subset without MCP.

**Fix — add to `~/.hermes/config.yaml`:**

```yaml
platform_toolsets:
  api_server:
    - hermes-api-server
    - mcp-horizon
```

After adding, restart gateway (`hermes gateway restart`). The `mcp-horizon` toolset will be included in `enabled_toolsets` and Horizon tools become available. No code changes needed.

**Why agentmemory MCP tools work but Horizon doesn't:** agentmemory registers through Hermes' plugin system which has its own toolset activation path (`tools_config.py:1536` plugin toolsets logic). Horizon is a pure external MCP server with no Hermes plugin component — it relies solely on the dynamic `register_toolset_alias()` path which platform toolset resolution doesn't see.

**Verification:** Check `agent.log` (not gateway-stdio.log — it freezes after gateway restart) for the registration log:
```bash
grep "MCP server 'horizon'.*registered" ~/AppData/Local/hermes/logs/agent.log | tail -3
```
If you see `"registered 17 tool(s): mcp_horizon_hz_*"`, the gateway side is correct — the issue is platform toolset filtering.

### MCPServerTask retry-and-abandon (source-level)

When the gateway starts, `_connect_server()` at `tools/mcp_tool.py:3098` calls `MCPServerTask.start()` which runs `MCPServerTask.run()`. The run loop tries connection up to `_MAX_INITIAL_CONNECT_RETRIES` (3) with exponential backoff (1s, 2s, 4s). If all fail, it sets `self._error`, marks `_ready`, and **permanently gives up** — the server is never added to `_servers` dict. The gateway will show `Failed to connect to MCP server 'horizon': Connection closed` in logs with zero subsequent retry until the next gateway process restart.

Key code path (`tools/mcp_tool.py`):
- Line 2313-2322: retry counter check, sets `_error`, returns
- Line 2372-2377: `start()` sees `_error`, raises to caller
- Line 3098-3111: `_connect_server()` propagates exception
- Line 4083-4095: `_discover_all()` catches as `BaseException`, logs warning, server NOT added to `_servers`

After a connection failure, the gateway process will never retry Horizon. Only a full gateway restart triggers `discover_mcp_tools()` again. The CLI `/reset` command does NOT restart the gateway or re-run MCP discovery — it only creates a new agent session within the existing gateway process.

**Failure rate observation (Windows):** 1 failure in 3 consecutive restarts (the first post-dependency-fix restart at 10:04 failed; two subsequent restarts at 10:27 and 10:32 succeeded). The first restart after installing dependencies may have a higher failure rate due to Python bytecode cache or venv state — be prepared for this. If the first restart shows 5 WARNINGs in errors.log, restart again. A failure at the first restart after dep fix does NOT indicate a persistent problem.

### PingRequest: the definitive success signal

Besides checking for absence of WARNINGs, there is one **irrefutable** signal that Horizon is connected: `PingRequest` entries in mcp-stderr.log, appearing every 180s (the `_DEFAULT_KEEPALIVE_INTERVAL`) after a successful gateway restart.

```bash
# After gateway restart, wait ~3 minutes and check:
grep "PingRequest" ~/AppData/Local/hermes/logs/mcp-stderr.log | tail -3
```

A PingRequest after the gateway restart timestamp means the MCP server is alive, the stdio transport is working, and the gateway is successfully maintaining the session. If you see `ListToolsRequest` but no subsequent `PingRequest`, the initial handshake may have been processed but the session was not established — restart gateway and check again after 3 minutes.

Example of a healthy timeline:
```
===== [2026-06-26 10:27:15] starting MCP server 'horizon' =====
[06/26/26 10:27:16] Processing request of type ListToolsRequest   ← initial discovery
[06/26/26 10:30:16] Processing request of type PingRequest        ← 3 min later = success
[06/26/26 10:33:16] Processing request of type PingRequest        ← 6 min later = alive
```

### Plugin missing MCP initialize handshake (all tools return "Invalid request parameters")

**Root cause (MCP SDK >= 1.26.0):** The `FastMCP` server's `ClientRequest` union type requires
proper `initialize` handshake before accepting `tools/call`. The Hermes Horizon plugin's
`_ensure_proc()` starts the subprocess but **never calls `initialize`** — it goes straight to
`tools/call`, which MCP 1.26.0 rejects with `-32602 Invalid request parameters`.

**Symptoms:** All 13 `hz_*` tools return `{"ok": false, "error": "Invalid request parameters"}`.
The plugin is enabled, tools appear in the agent's tool list, but every call fails identically.

**Fix applied (2026-06-26):** `_ensure_proc()` now sends `initialize` with
`clientInfo: {name: "hermes-horizon-plugin", version: "1.0.0"}` after `Popen`, reads the
response, and only returns the process on success. On failure it kills the process and
re-raises, allowing retry. Requires `/reset` (or gateway restart + `/reset`) to pick up
the new plugin bytecode.

**Key detail:** `clientInfo.version` is **required** — without it the initialize itself fails.

**Note:** "Invalid request parameters" can also be caused by **stale session bytecode**
(see pitfall below) — the MCP server never receives the `tools/call` because the handler
function was never registered or was broken by a syntax error. Distinguish the two by:
(1) manual JSON-RPC test (works → MCP server fine, issue is plugin side), (2) `execute_code`
handler test (works → handler code fine, issue is session bytecode staleness).

### Session stale bytecode after patching plugin — handler never called (all tools return "Invalid request parameters")

**Root cause:** When you patch `__init__.py` and run `hermes gateway restart`, the gateway
reloads plugins and calls `register()` with the new code — but the **current agent session
still holds the old bytecode** from when the session was created. `register()` runs during
gateway startup (independent of any session), but tool dispatch within a session uses the
handler functions loaded when that session was created.

**Symptoms:**
- `register()` debug marker appears in log → gateway loaded new plugin
- `hz_*` tools present in agent tool list with correct schemas
- Every tool call returns `{"ok": false, "error": "Invalid request parameters"}`
- Handler debug marker (added to the handler function) does NOT appear — handler never reached
- `execute_code` directly importing and calling the handler **works** — gets fresh code
- Manual JSON-RPC test against MCP server **works** — MCP server is fine

**This specific failure chain played out on 2026-06-26:** a syntax error was introduced
into `__init__.py` during debugging (unterminated string literal at line 23). The plugin
failed to import during that session's creation. After fixing the syntax error and restarting
the gateway, `register()` ran with the fixed code (tools appeared in tool list), but the
current session still had no valid handlers from the broken-import session. `/reset` was
needed to reload the plugin bytecode.

**Diagnostic escalation:**
```bash
# 1. Verify MCP server is healthy (bypass plugin entirely)
cd D:/workspace/AI-research/Horizon
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}\n{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"hz_get_metrics","arguments":{}}}\n' | timeout 15 python -m src.mcp.server 2>&1 | grep '"jsonrpc"'
# → If this returns success, MCP server is fine → issue is on the plugin side

# 2. Verify plugin module imports cleanly and handlers work
python -c "
import sys
sys.path.insert(0, r'C:\Users\chester.chen\AppData\Local\hermes\plugins\horizon')
import __init__ as m
print(f'Handlers: {len(m._HANDLERS)}')
result = m._HANDLERS['hz_get_metrics']({})
print(result[:200])
"
# → If this returns success, plugin code is correct → issue is session bytecode

# 3. CHECK: Is the handler actually reached? Add a marker to handler() in __init__.py:
#    def handler(args: dict, **kwargs) -> str:
#        with open(r"C:\Users\chester.chen\hermes_handler_called.log", "a") as f:
#            f.write("HANDLER CALLED\n")
#        return _call_tool(tool_name, args)
# → After gateway restart, call tool. If log file missing → handler never invoked.
```

**Fix:**
```bash
# /reset the session to reload plugins with current bytecode
# Or start a new session if /reset isn't available
```

**Prevention:** Always `/reset` after patching plugin files. Gateway restart alone is
insufficient — it reloads `register()` but the agent session keeps its old handlers.

Full debugging transcript: `references/stale-session-bytecode-debug.md`.

### Use execute_code to test plugin handlers bypassing dispatch framework

When debugging plugin tool failures, use `execute_code` to directly import and call the
handler function. This bypasses the entire Hermes dispatch chain (handle_function_call →
run_tool_execution_middleware → registry.dispatch → entry.handler) and isolates whether
the problem is in the plugin code or in the framework dispatch layer.

```python
# In execute_code or a Python terminal:
import sys
sys.path.insert(0, r"C:\Users\chester.chen\AppData\Local\hermes\plugins\horizon")
import importlib
m = importlib.import_module("__init__")
handler = m._HANDLERS["hz_get_metrics"]  # or any tool name
result = handler({})                      # pass the tool arguments dict
print(result[:500])
```

If this succeeds but the in-session tool call fails, the issue is in the dispatch layer or
session bytecode staleness (see pitfall above). If this also fails, the issue is in the
plugin code itself — check for syntax errors, `_ensure_proc` failures, or MCP communication
errors.

```python
# Required format (in _ensure_proc after Popen):
init_request = json.dumps({
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "hermes-horizon-plugin", "version": "1.0.0"},
    },
    "id": req_id,
})
_proc.stdin.write(init_request + "\n")
_proc.stdin.flush()
line = _proc.stdout.readline()
resp = json.loads(line)
if "error" in resp:
    raise RuntimeError(f"MCP initialize failed: {resp['error']['message']}")
```

### Manual testing: notification/initialized not needed

The `notifications/initialized` message often causes validation warnings but doesn't block tool calls. Skip it — just send `initialize` then directly call tools.

### JSON-RPC over stdio: one-shot per process

Each `echo ... | python -m src.mcp.server` starts a fresh process. The server exits after stdin closes. For multiple tool calls in one test, pipe all requests at once (one JSON object per line).

### Pipeline blocks main agent thread — three-layer deadlock (CRITICAL)

**Never call `hz_run_pipeline` directly from the agent's main thread.** The pipeline takes 8–15 minutes and the plugin's blocking implementation will hang the session. Always use `delegate_task` (subagent) or `cronjob` for pipeline execution.
The blocking happens at THREE layers simultaneously:

**Layer 1 — plugin `_call_tool()` readline timeout (FIXED 2026-06-29, UPDATED 2026-06-29):**
`plugins/horizon/__init__.py:135-162` — `_readline_with_timeout()` wraps the blocking `proc.stdout.readline()` in a daemon thread with `join(timeout=PER_TOOL_TIMEOUT)` (900s, line 21). Returns `None` on timeout → `_call_tool` calls `_kill_proc()` (line 201) then raises `TimeoutError` → `_proc_lock` released.

**Pipeline interaction:** Because orchestrator Rich Console output is now redirected to devnull (`horizon_adapter.py:188`), stdout produces ZERO lines during the 8–17 minute pipeline run until the final JSON-RPC response. At 900s (15 min), the timeout covers most pipeline runs (observed: 445 items ≈ 9m44s scoring + 6m51s enrich = 16m35s, see `references/pipeline-timing-baseline.md`). **Always use delegate_task or cronjob for pipeline runs** — the 900s timeout is a safety net against genuine hangs, not a license to run pipelines on the main agent thread. Individual stage tools (`hz_fetch_items`, `hz_score_items`, etc.) complete well within 300s and are unaffected.

**Historical note (root cause of 2026-06-29 session hangs):** The original 300s timeout was too short — pipeline stdout is silent during scoring (10+ min), so `_readline_with_timeout` always fired before completion, killing the MCP subprocess mid-pipeline. This produced the "session接连2次卡死" symptoms: `_proc_lock` was held by the killed tool call, and subsequent calls hit a dead/restarting subprocess. Raising to 900s allows the full pipeline to complete through `_call_tool`, but delegate_task remains the recommended approach to avoid blocking the main agent thread.

**Layer 2 — pipeline duration exceeds Hermes tool-call framework timeout:**
The pipeline (`service.py:487-559` `run_pipeline()`) executes fetch→score→filter→enrich→summarize synchronously — 8–15 minutes end-to-end. Hermes' tool-call framework has a ~10–13 minute timeout. When it fires, the session becomes responsive again. With the Layer 1 fix, `_call_tool()` will also time out within 600s, releasing `_proc_lock`.

**Layer 3 — `_proc_lock` cascading deadlock (mitigated by Layer 1 fix):**
`plugins/horizon/__init__.py:~155` — `_call_tool()` holds `_proc_lock` (RLock) during the entire read. With the timeout, the lock is released after 10 minutes at worst. After a timeout, `_ensure_proc()` (line 34) will kill the hung subprocess on the next call (poll detects dead process → spawn new one).

**Read tools now bypass `_proc_lock` (fixed 2026-06-29):** `hz_list_runs`, `hz_get_run_meta`, `hz_get_run_stage`, `hz_get_run_summary`, and `hz_get_metrics` no longer go through `_call_tool` → they read JSON/MD files directly from `data/mcp-runs/` on disk (no pipe, no lock). During a subagent's `hz_run_pipeline` (holding `_proc_lock` for the pipe), the main agent can freely call these read tools to monitor pipeline progress — see `references/read-write-tool-split.md` for architecture details. Live-verified 2026-06-29: 24h pipeline, 11 concurrent reads, 0 blocking (`references/read-write-tool-split-verification.md`).

**Orchestrator stdout pollution (FIXED 2026-06-29):**
`src/mcp/horizon_adapter.py:179-189` — `make_orchestrator()` now replaces `orch.console` with `Console(file=open(os.devnull, "w"))`. The orchestrator's Rich progress-bar output no longer writes to stdout, keeping the JSON-RPC channel clean. The plugin-side non-JSON line skip (`__init__.py:177-179`) remains as defense-in-depth.

**stderr pipe deadlock → file logging (FIXED 2026-06-29):**
The MCP subprocess stderr went through three stages:
1. Original: `stderr=subprocess.PIPE` — 4KB Windows pipe buffer filled by Rich Console output → subprocess blocked before writing anything to stdout → "8 minutes zero output" symptom
2. Interim: `stderr=subprocess.DEVNULL` — no blocking, but ALL progress/error output lost, making debugging impossible
3. Current: `stderr=open(STDERR_LOG, "a")` where `STDERR_LOG = %TEMP%\horizon_stderr.log` (`__init__.py:77,84`) — unlimited buffer, all stderr preserved for diagnosis. Check `%TEMP%\horizon_stderr.log` after any pipeline run for full error/progress output.

**Root cause trace (source-level):**
```
hz_run_pipeline handler → _call_tool() ──[_proc_lock held]──→ proc.stdin.write(request)
  → MCP server: service.run_pipeline() [8-15 min]
    → orchestrator.fetch_all_sources()  ← Console → devnull (no stdout pollution)
    → score_items()  → filter_items()  → enrich_items()  → generate_summary()
  → plugin: while True: _readline_with_timeout(proc, timeout=900)
    → 900s covers full pipeline (observed: 427 items ≈ 10.5 min)
    → returns final JSON-RPC response → _proc_lock released
```

**How to detect:**
- Session hangs for 10+ minutes after `hz_run_pipeline` call
- `hz_get_metrics` shows `uptime_seconds` reset to ~1 (MCP server was killed and restarted between sessions)
- `hz_list_runs` shows runs with ALL stages `false` (see "Zombie runs" pitfall below)

**Workaround — delegate to subagent:**
```python
delegate_task(
    goal="Execute Horizon pipeline...",
    context="...params here... pipeline takes 8-15 min"
)
```
Subagent runs in isolated context — its blocking does not affect the main session.

Full timeline and evidence: `references/pipeline-blocking-analysis.md`.

### Zombie runs — all stages `false`, run_id created but fetch never completed

**Root cause:** `service.py:242` — `run_store.create_run(run_id)` is called BEFORE the actual fetch (line 245: `orchestrator.fetch_all_sources()`). If the MCP process is killed between these two lines, the run_id persists but no stage data is written.

**Why MCP process gets killed:**
- Hermes Gateway restart (between sessions) kills all plugin subprocesses
- Previous session's pipeline was hung → user opens new session → Gateway restarts → MCP process terminated
- The zombie runs survive in RunStore (disk) across MCP server restarts

**How to detect:**
```bash
# All stages false = zombie
hz_list_runs → items where stages: {raw:false, scored:false, filtered:false, enriched:false}
```

**Cleanup:**
```bash
rm -rf D:/workspace/AI-research/Horizon/data/mcp-runs/<zombie-run-id>
```

### Pipeline runs >10 minutes — use 900s timeout (CLI/JSON-RPC only)

The full pipeline takes 8–15 minutes. When calling via manual JSON-RPC (not through Hermes plugin), use `timeout 900` (15 min) minimum.

Observed: 555 raw → 538 above threshold → 37 filtered → enriched → summarized. Two attempts with `timeout 600` killed during enrich/summarize phase (exit 124).

The pipeline writes intermediate stage files to `data/mcp-runs/run-<timestamp>-<id>/` progressively. See "Recovering from Partial Pipeline Run" below.

### JSON-RPC response capture: don't grep for multi-line JSON

When capturing pipeline output, `grep '"jsonrpc"'` only matches single-line JSON objects. The `hz_run_pipeline` result is multi-line (progress text + JSON-RPC response). For debugging, capture the full stdout without filtering (`> /tmp/out.txt`). For production use, the summaries are written to `data/summaries/` and `data/mcp-runs/<id>/` regardless of whether the JSON-RPC response was captured — the files are the deliverable, not the stdout.

## Gateway MCP Connection Debugging

When Horizon tools are absent from Hermes but the config looks correct, the issue is at the gateway MCP transport layer. Use this diagnostic sequence:

### Log files (in order of usefulness)

| Log | Path | What it tells you |
|-----|------|-------------------|
| **agent.log** | `~/AppData/Local/hermes/logs/agent.log` | MCP registration INFO — `"MCP server 'horizon' (stdio): registered 17 tool(s): mcp_horizon_hz_*"` proves tools were registered. This is the **only log** that captures the registration success message from `mcp_tool.py:4014-4019`. |
| **errors.log** | `~/AppData/Local/hermes/logs/errors.log` | WARNING/ERROR with timestamps — authoritative for current connection state |
| **mcp-stderr.log** | `~/AppData/Local/hermes/logs/mcp-stderr.log` | Raw stderr from MCP server processes — shows actual startup and request processing (ListToolsRequest, PingRequest) |
| **horizon_stderr.log** | `%TEMP%\\horizon_stderr.log` | Plugin-side MCP subprocess stderr (all Rich Console progress and errors — unlimited buffer, no pipe deadlock) |
| **gateway-stdio.log** | `~/AppData/Local/hermes/logs/gateway-stdio.log` | Gateway stdout — BUT freezes after `hermes gateway restart` exits; NOT reliable for current state |

### Diagnostic workflow

0. **Check agent.log for MCP registration confirmation (fastest check):**
   ```bash
   grep "MCP server 'horizon'.*registered" ~/AppData/Local/hermes/logs/agent.log | tail -3
   ```
   A line like `"MCP server 'horizon' (stdio): registered 17 tool(s): mcp_horizon_hz_*"` proves the gateway successfully registered Horizon tools. If this line exists but tools are still missing, the issue is platform toolset filtering — see "Tools not in API Server / chatbot session" pitfall above.

1. **Check errors.log for current failures:**
   ```bash
   grep "horizon" ~/AppData/Local/hermes/logs/errors.log | tail -5
   ```
   If the last horizon errors are from BEFORE the most recent gateway restart, the connection likely succeeded this time. Errors.log is append-only per gateway process and shows real-time WARNING/ERROR.

2. **Check mcp-stderr.log for server startup AND liveness proof:**
   ```bash
   grep -A3 "starting MCP server 'horizon'" ~/AppData/Local/hermes/logs/mcp-stderr.log | tail -10
   ```
   A successful connection shows `Processing request of type ListToolsRequest` immediately after the start line. This proves the MCP server process started and responded to tools/list.

   **Definitive success signal — PingRequest:** After a successful gateway restart, the gateway sends keepalive pings every 180s. If you see `PingRequest` entries in mcp-stderr.log AFTER the most recent gateway restart timestamp, the connection is alive and healthy:
   ```bash
   grep "PingRequest" ~/AppData/Local/hermes/logs/mcp-stderr.log | tail -3
   ```
   PingRequest is the gold-standard success indicator — more reliable than "absence of WARNINGs" alone. If you see ListToolsRequest but no PingRequest 3+ minutes later, the initial handshake completed but the session didn't establish — restart gateway again.

3. **Don't trust gateway-stdio.log alone — it retains entries across every gateway restart.** `grep "horizon" gateway-stdio.log` returns WARNING entries from every gateway instance that has ever run, including ones from days ago. A current grep showing 5 horizon warnings does NOT mean the current gateway has 5 failures.

   **Verification pattern:**
   ```bash
   # BAD — shows all historical failures, not current state
   grep "horizon" ~/AppData/Local/hermes/logs/gateway-stdio.log

   # GOOD — shows only current-session errors with timestamps
   grep "horizon" ~/AppData/Local/hermes/logs/errors.log | tail -5
   ```

   **Why gateway-stdio.log stops updating:** `hermes gateway restart` spawns the gateway as a background process and exits. The gateway-stdio.log and gateway.log files are written only by the CLI command process — once the restart command returns, these files freeze at startup-complete. The running gateway process (pythonw.exe) continues operating but does not append to these logs. In contrast, errors.log and mcp-stderr.log are written by the gateway's Python logging system and MCP subprocess respectively, and continue updating as long as the gateway is alive. Always cross-reference with errors.log timestamps — if errors.log has no horizon entries after the most recent restart, the connection succeeded regardless of what gateway-stdio.log shows.

4. **Windows-specific: Job Object warning is non-fatal.** You may see `Failed to assign process <PID> to Job Object: (5, '拒绝访问')` in errors.log. This is the MCP SDK's win32 subprocess handler failing to assign the child to a Windows Job Object. It does NOT block MCP functionality — the server still processes requests normally.

### After fixing: verify

```bash
hermes gateway restart
sleep 5
# Confirm NO new horizon errors since restart
grep "horizon" ~/AppData/Local/hermes/logs/errors.log | tail -3
```

## Pipeline Output

After a successful pipeline run (`hz_run_pipeline` or `horizon` CLI), summaries are written to:

```
data/summaries/horizon-YYYY-MM-DD-{lang}.md
```

Example: `data/summaries/horizon-2026-06-26-en.md` (72KB, 851 lines, 37 items selected from 776 fetched).

**Format**: Markdown with anchor-based TOC (e.g. `#item-1`), each item containing:
- Title + link + ⭐ score (7.0-10.0)
- AI-generated summary paragraph
- Source attribution (hackernews/rss/reddit with date, discussion link)
- **Background** section — web-researched context for unfamiliar concepts
- **References** — collapsible `<details>` block with cited URLs
- **Discussion** — community conversation summary (HN/Reddit)
- **Tags** — hashtag-style category labels

No local web dashboard exists to browse these — open the `.md` files directly in Obsidian/VS Code/browser.

## Recovering from Partial Pipeline Run

If `hz_run_pipeline` is killed mid-run (timeout, crash), the pipeline persists intermediate stages to `data/mcp-runs/run-<timestamp>-<id>/`. Each stage file is written atomically when that stage completes:

```
data/mcp-runs/<run-id>/
  raw_items.json       → fetch complete
  scored_items.json    → scoring complete
  filtered_items.json  → filtering + dedup complete
  enriched_items.json  → enrichment complete
  summary-{lang}.md    → per-language summary generated
  meta.json            → run metadata (includes summary_language field)
```

To resume from the last completed stage, call the next step individually via JSON-RPC using the `run_id`:

```bash
cd D:/workspace/AI-research/Horizon

# Resume: generate missing language summary from existing enriched data
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"hermes","version":"1.0"}}}\n{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"hz_generate_summary","arguments":{"run_id":"<run-id>","language":"en","save_to_horizon_data":true}}}' | timeout 300 python -m src.mcp.server
```

Set `save_to_horizon_data: true` to also copy the result to `data/summaries/horizon-YYYY-MM-DD-{lang}.md`. Each language requires a separate `hz_generate_summary` call — they are independent.

**Config-driven bilingual output:** When `config.json` has `"languages": ["en", "zh"]`, `hz_run_pipeline` generates summaries for all listed languages sequentially. If the process is killed between languages, the completed language files survive in the run directory — only the missing language needs regeneration.

**Cleanup:** Failed/partial runs leave directories in `data/mcp-runs/`. After verifying the final run is complete, remove incomplete runs:
```bash
ls D:/workspace/AI-research/Horizon/data/mcp-runs/
# Remove any run missing enriched_items.json or both summary files
rm -rf D:/workspace/AI-research/Horizon/data/mcp-runs/<incomplete-run-id>
```

## References

- `references/tool-schemas.md` — complete input/output schemas for all 13 tools (captured from live server)
- `references/diagnosis-session.md` — full transcript of the 2026-06-26 diagnosis session
- `references/mcp-retry-mechanism.md` — source-level analysis of MCPServerTask retry-and-abandon (mcp_tool.py lines 2260-4095)
- `references/jsonrpc-commands.md` — copy-paste JSON-RPC templates for common pipeline operations
- `references/platform-toolset-filtering.md` — why `mcp_horizon_hz_*` tools are absent from API Server sessions despite successful gateway registration (source-level trace of `_get_platform_tools` → `CONFIGURABLE_TOOLSETS` gap)
- `references/plugin-integration.md` — plugin-based integration architecture, standalone-plugin opt-in mechanics, setup, and pitfalls
- `references/stale-session-bytecode-debug.md` — 2026-06-26: session bytecode staleness after plugin patch — handler never called, diagnostic escalation (manual JSON-RPC → execute_code handler test → handler marker)
- `references/template-config-restore.md` — 2026-06-26 diagnosis: template config restore as root cause for plugin disappearing after restart
- `references/pipeline-blocking-analysis.md` — 2026-06-26: three-layer deadlock when calling `hz_run_pipeline` from main thread — session timeline, zombie run mechanism, orchestrator stdout pollution, permanent fixes
- `references/pipeline-fix-review-2026-06-29.md` — 2026-06-29: review of 6 Claude Code fixes — PER_TOOL_TIMEOUT pipeline impact, defense-in-depth analysis, lock safety audit
- `references/read-write-tool-split.md` — plugin architecture: write tools go through pipe with `_proc_lock`; read tools bypass pipe entirely, reading JSON/MD directly from `data/mcp-runs/`. Enables main agent to monitor pipeline progress (via `hz_list_runs`/`hz_get_run_stage`) while subagent holds `_proc_lock` running `hz_run_pipeline`.
- `references/read-write-tool-split-verification.md` — 2026-06-29 live verification: 24h pipeline running, 11 concurrent read tool calls, 0 blocking.
- `references/daily-ai-news-workflow.md` — 2026-06-29: daily AI news workflow: subagent dispatch with `toolsets=['horizon']` → read-tool monitoring → copy summary. Primary path uses subagent + monitor; fallback uses individual stage tools from main thread. See `references/delegate-plugin-toolset-recovery.md` for the code fix enabling plugin toolset delegation.
- `references/delegate-plugin-toolset-recovery.md` — 2026-06-30: code fix in `tools/delegate_tool.py` — `_expand_parent_toolsets` only sees static `TOOLSETS`, drops plugin toolsets like `horizon` from subagent intersection. Recovery loop after intersection checks registry + parent `valid_tool_names`.
- `references/pipeline-timing-baseline.md` — 2026-06-30: actual stage timing from 3 complete runs: fetch 6s, score 9m44s (445 items), filter 27s, enrich 6m51s–8m51s (38 items), total 17-21min.
