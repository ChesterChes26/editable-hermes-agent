# Horizon Diagnosis — 2026-06-26

Full diagnosis session transcript and findings from two consecutive sessions.

## Session 1: Initial Fix ("Horizen状态检查")

### Trigger

User asked "检查Horizen是否正常工作" (check if Horizon is working).

### Initial State

- Horizon MCP tools not visible in Hermes session (no `hz_*` tools in tool list)
- No running Horizon process (`tasklist | grep horizon` → empty)
- Config present in `~/.hermes/config.yaml` under `mcp_servers.horizon`

### Phase 1: MCP Server Binary Validation

1. **Locate MCP server**: `D:/workspace/AI-research/Horizon`, server module: `src/mcp/server.py`
2. **Manual smoke test**: Server responds, `horizon-mcp v1.26.0`, 13 tools discovered
3. **First tool call fails**: `hz_validate_config` → `HZ_IMPORT_FAILED: No module named 'feedparser'`
4. **Install feedparser**: Only to find next dep missing: `No module named 'anthropic'`
5. **Install all deps**: `pip install -e .` installs 12 packages
6. **Retry succeeds**: `hz_validate_config(check_env=false)` → `ok: true`, 5 sources, valid config
7. **check_env=true hangs**: LLM client init over stdio times out — use `check_env=false` for fast validation
8. **hz_list_runs**: count=0, never run

### Phase 2: Gateway Integration Debugging

9. **Root cause**: Gateway spawns MCP server using Hermes venv Python (`~/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe`). Dependencies were installed to system Python, not the venv.
10. **Fix**: Install deps into Hermes venv via `pip install -e .` from within the venv context.
11. **Gateway restart**: `hermes gateway restart` → PID 83768
12. **mcp-stderr verification**: `ListToolsRequest` processed at 10:04:38

### Key Findings (Session 1)

| Finding | Impact | Fix |
|---------|--------|-----|
| Missing pip deps in Hermes venv | MCP server import failures | Install deps in venv |
| check_env=true hangs | LLM init over stdio times out | Use check_env=false |
| Gateway-stdio.log retains old entries | False diagnosis | Cross-reference with errors.log timestamps |
| Windows Job Object warning | Non-fatal noise | Ignore |

## Session 2: Reliability Testing ("查看前1个session会话结果")

### Trigger

User `/reset` and finds no `hz_*` tools. Follows up with "我已经reset了，为什么没有hz工具".

### Discovery: Gateway MCP Connection Failed Silently

Examined gateway-stdio.log for the 10:04 restart (PID 83768):
```
WARNING tools.mcp_tool: MCP server 'horizon' initial connection failed (attempt 1/3)
WARNING tools.mcp_tool: MCP server 'horizon' initial connection failed (attempt 2/3)
WARNING tools.mcp_tool: MCP server 'horizon' initial connection failed (attempt 3/3)
WARNING tools.mcp_tool: MCP server 'horizon' failed initial connection after 3 attempts, giving up
WARNING tools.mcp_tool: Failed to connect to MCP server 'horizon' (command=python): Connection closed
```

Error: `unhandled errors in a TaskGroup (1 sub-exception)` → `Connection closed`

Despite the MCP server process starting and processing `ListToolsRequest` (visible in mcp-stderr.log), the gateway's MCPServerTask.run() exhausted its 3 retries and permanently abandoned the connection. The gateway never retries — only a full gateway restart re-runs `discover_mcp_tools()`.

### Source Code Confirmation

`tools/mcp_tool.py` lines 2313-2322:
```python
_MAX_INITIAL_CONNECT_RETRIES = 3  # line 280

if initial_retries > _MAX_INITIAL_CONNECT_RETRIES:  # line 2314
    self._error = exc
    self._ready.set()
    return  # PERMANENT ABANDON
```

The gateway never adds the server to `_servers` dict. `/reset` only creates a new CLI agent session — it does NOT restart the gateway or re-run MCP discovery.

### Reliability Test: 3 Consecutive Gateway Restarts

| Restart | PID | gateway-stdio warnings | mcp-stderr PingRequest | Result |
|---------|-----|----------------------|----------------------|--------|
| 10:04 | 83768 | 5 WARNINGs | None | **FAIL** |
| 10:27 | 116280 | 0 | 10:30:16 | SUCCESS |
| 10:32 | 84740 | 0 | 10:35:02 | SUCCESS |

**Pattern**: First restart after dependency fix failed (1/3). Two subsequent restarts succeeded (2/2). The first post-fix restart appears more prone to failure — possibly due to stale Python bytecode or venv state.

### PingRequest: Definitive Success Signal

After a successful gateway restart, the gateway sends keepalive pings every 180s (the `_DEFAULT_KEEPALIVE_INTERVAL`). Finding `PingRequest` entries in mcp-stderr.log AFTER the restart timestamp is the gold-standard proof of a healthy connection:

```bash
grep "PingRequest" ~/AppData/Local/hermes/logs/mcp-stderr.log | tail -3
```

Example healthy timeline:
```
===== [10:27:15] starting MCP server 'horizon' =====
[10:27:16] Processing request of type ListToolsRequest   ← initial discovery
[10:30:16] Processing request of type PingRequest        ← 3 min later = SUCCESS
[10:33:16] Processing request of type PingRequest        ← alive and well
```

### Gateway Log File Behavior

`gateway.log` and `gateway-stdio.log` are written by the `hermes gateway restart` CLI command process, NOT by the running gateway daemon (pythonw.exe). Once the restart command exits, these files freeze. `errors.log` and `mcp-stderr.log` continue updating as long as the gateway and MCP server are alive.

### hermes mcp list / test Timeout

Both `hermes mcp list` and `hermes mcp test horizon` timed out (>10s, no output) during diagnosis. Fall through to manual JSON-RPC testing or log analysis when these commands are unresponsive.

### Horizon Has No Web Dashboard

User asked about "URL login". Horizon is purely CLI + MCP server — no local web interface exists. The README links to `horizon1123.top` and `thysrael.github.io/Horizon/` are documentation sites on GitHub Pages, not a management UI.

## Resolution

1. Dependencies installed in Hermes venv ✓
2. Config validated ✓
3. MCP server binary confirmed working ✓
4. Gateway restarted x2, second restart succeeded ✓
5. PingRequest heartbeat confirmed ✓
6. **Remaining**: User needs `/reset` after the SUCCESSFUL gateway restart (10:32, PID 84740) to load hz_* tools. The earlier `/reset` at 10:13 was against the FAILED gateway (10:04, PID 83768).

## Key JSON-RPC Testing Pattern

```bash
cd D:/workspace/AI-research/Horizon
(echo 'REQ1'; echo 'REQ2'; echo 'REQ3') | timeout 8 python -m src.mcp.server 2>/dev/null
```

- Each line is a complete JSON-RPC call
- No `notifications/initialized` needed (causes validation warnings but doesn't block)
- For long-running tests, use `timeout` to avoid hangs on `check_env=true`
- Response lines are interleaved with server stderr; filter with `grep '"jsonrpc"'`

## Log File Reference

| Log | Path | Updated by | Key signal |
|-----|------|-----------|-----------|
| errors.log | `~/AppData/Local/hermes/logs/errors.log` | gateway daemon | Timestamped WARNING/ERROR — cross-reference with restart time |
| mcp-stderr.log | `~/AppData/Local/hermes/logs/mcp-stderr.log` | MCP subprocess | `ListToolsRequest` + `PingRequest` = connection health |
| gateway-stdio.log | `~/AppData/Local/hermes/logs/gateway-stdio.log` | restart CLI command | Retains ALL historical entries; FREEZES after restart exits |
| gateway.log | `~/AppData/Local/hermes/logs/gateway.log` | restart CLI command | Platform connection logs; FREEZES after restart exits |

## Current Config Snapshot

```yaml
mcp_servers:
  horizon:
    command: python
    args:
    - -m
    - src.mcp.server
    cwd: D:/workspace/AI-research/Horizon
    env:
      DEEPSEEK_API_KEY: sk-ff4...44a6
      PYTHONUTF8: "1"
```

Category groups: academic-papers (15), ai-news (15), ai-news-zh (10), ai-tools (10). Default: other (20).
Enabled sources: github, hackernews, rss, reddit, telegram.
