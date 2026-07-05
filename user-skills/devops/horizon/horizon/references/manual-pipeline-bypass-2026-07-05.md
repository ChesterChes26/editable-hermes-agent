# Manual Pipeline Bypass — 2026-07-05 Session

## Context

`hz_run_pipeline(hours=24, languages=['zh'], enrich=true, save_to_horizon_data=true)` was requested. The Horizon plugin's MCP subprocess was broken because the gateway's Python (uv-managed) lacked `mcp`. This session documents the bypass approach and the stdin-closure pitfall discovered.

## Diagnostic Chain

### 1. Plugin tools failing — `MCP subprocess closed stdout during initialize`

All pipe tools (`hz_validate_config`, `hz_run_pipeline`, etc.) returned the same error. Read tools (`hz_get_metrics`, `hz_list_runs`) worked because they read disk directly.

### 2. Stderr log showed old path — stale file

`%TEMP%\horizon_stderr.log` contained errors from a previous session with path `D:\workspace\AI-research\Horizon`. The file is opened in append mode (`"a"`), so old errors persist. **Lesson:** clear the stderr log before diagnosis:
```bash
cmd.exe /c "del %TEMP%\horizon_stderr.log"
```

### 3. Root cause: Gateway Python ≠ Hermes venv Python

```bash
# Gateway process uses uv-managed Python:
wmic process where "name='pythonw.exe'" get ExecutablePath
# → $HOME\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\pythonw.exe

# This Python lacks mcp:
/c/Users/admin/AppData/Roaming/uv/python/cpython-3.11-windows-x86_64-none/python.exe -c "import mcp"
# → ModuleNotFoundError

# Hermes venv Python has mcp:
~/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe -c "import mcp.server.fastmcp; print('OK')"
# → OK
```

The plugin's `HORIZON_CMD = [sys.executable, ...]` resolves to the gateway Python at plugin load time.

### 4. Plugin patch + gateway restart didn't take effect

Patched `HORIZON_CMD` to hardcode the venv Python path, restarted gateway — tools still failed. Likely session bytecode staleness (see `stale-session-bytecode-debug.md`). Bypassed by going directly to manual JSON-RPC.

### 5. First manual attempt: stdin closure killed pipeline

```bash
cd $HORIZON_HOME
printf '{init}\n{tools/call hz_run_pipeline...}\n' | \
  timeout 1200 ~/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe -m src.mcp.server
```

Result: Pipeline fetched 8 items (HN + Telegram), then crashed during scoring with:
```
anyio.ClosedResourceError
ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)
```

The `stdio_server()` async context manager cleans up when stdin closes. Since `printf` closes stdin immediately after writing, the server's async task group shuts down before the long-running pipeline can produce its response.

### 6. Fix: keep stdin open with sleep

```bash
cd $HORIZON_HOME
(printf '{init}\n{tools/call hz_run_pipeline...}\n'; sleep 1200) | \
  ~/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe -m src.mcp.server \
  2>/tmp/horizon_stderr.txt | tee /tmp/horizon_output.txt
```

`sleep 1200` (20 min) holds stdin open for the entire pipeline duration. The MCP server stays alive, completes fetch → score → filter → enrich → summarize, then writes the JSON-RPC response to stdout.

### 7. Second manual attempt: DEEPSEEK_API_KEY missing

The pipeline completed fetch (8 items, `raw_items.json` written) but failed at scoring:
```
Missing API key environment variable configured by ai.api_key_env.
Set DEEPSEEK_API_KEY=your_api_key in .env or your shell.
```

The API key exists in Hermes' credential pool (`auth.json`) as `source: "env:DEEPSEEK_API_KEY"` but is not set as an actual environment variable. The MCP subprocess needs it exported.

### 8. Partial run preserved on disk

The failed run is recoverable:
- `$HORIZON_HOME\data\mcp-runs\run-20260705T100735Z-356ae7f1\`
- `raw_items.json` (19KB) — fetch completed
- `meta.json` — run metadata (8 items, sources: hackernews, telegram)

To resume: set `DEEPSEEK_API_KEY`, then call `hz_score_items(run_id="run-20260705T100735Z-356ae7f1")`.

## Key Takeaways

1. **Always check which Python the gateway uses** — `wmic process where "name='pythonw.exe'" get ExecutablePath`
2. **Clear `%TEMP%\horizon_stderr.log` before diagnosis** — appended mode preserves stale errors
3. **For manual JSON-RPC with long-running tools, keep stdin open** — use `(printf ...; sleep N) |`
4. **Monitor runs via disk during manual pipelines** — plugin read tools see a different subprocess
5. **DEEPSEEK_API_KEY must be an actual env var** — Hermes credential pool references aren't enough for subprocesses
