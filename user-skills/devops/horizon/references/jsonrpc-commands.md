# JSON-RPC Command Templates

Copy-paste templates for calling Horizon MCP tools directly over stdio. All commands assume `cd D:/workspace/AI-research/Horizon` first. Use `printf` (not `echo`) to avoid newline issues with multi-line JSON.

## Run Full Pipeline

```bash
cd D:/workspace/AI-research/Horizon
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"hermes","version":"1.0"}}}\n{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"hz_run_pipeline","arguments":{}}}' | timeout 900 python -m src.mcp.server 2>/tmp/horizon_stderr.log > /tmp/horizon_stdout.txt; echo "EXIT=$?"
```

**Expected duration:** 8–15 minutes for 500+ items. `timeout 600` is not enough — use `timeout 900`.
**Output:** summaries in `data/mcp-runs/<run-id>/summary-{lang}.md`. With `save_to_horizon_data: true` also in `data/summaries/`.

## Generate Single-Language Summary (Resume Partial Run)

```bash
cd D:/workspace/AI-research/Horizon
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"hermes","version":"1.0"}}}\n{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"hz_generate_summary","arguments":{"run_id":"<run-id>","language":"en","save_to_horizon_data":true}}}' | timeout 300 python -m src.mcp.server
```

**Duration:** ~1–3 minutes (LLM-only, no fetching/scoring). Each language is a separate call.

## Validate Config (Fast)

```bash
cd D:/workspace/AI-research/Horizon
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}\n{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"hz_validate_config","arguments":{"check_env":false}}}' | timeout 20 python -m src.mcp.server 2>&1 | grep '"jsonrpc"'
```

## List Recent Runs

```bash
cd D:/workspace/AI-research/Horizon
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}\n{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"hz_list_runs","arguments":{"limit":5}}}' | python -m src.mcp.server 2>&1 | grep '"jsonrpc"'
```

## Read Run Metadata

```bash
cd D:/workspace/AI-research/Horizon
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}\n{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"hz_get_run_meta","arguments":{"run_id":"<run-id>"}}}' | python -m src.mcp.server 2>&1 | grep '"jsonrpc"'
```

## Read Summary from Run

```bash
cd D:/workspace/AI-research/Horizon
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}\n{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"hz_get_run_summary","arguments":{"run_id":"<run-id>","language":"zh"}}}' | python -m src.mcp.server 2>&1 | grep '"jsonrpc"'
```

## Pipeline with Custom Arguments

```bash
cd D:/workspace/AI-research/Horizon
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"hermes","version":"1.0"}}}\n{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"hz_run_pipeline","arguments":{"hours":48,"languages":["en"],"threshold":6.0,"enrich":true,"topic_dedup":true,"save_to_horizon_data":true}}}' | timeout 900 python -m src.mcp.server
```

## Notes

- **Don't use `grep '"jsonrpc"'` for pipeline output** — the `hz_run_pipeline` response is multi-line with progress text before the JSON-RPC result. Capture full stdout.
- **`printf` vs `echo`**: Use `printf` with explicit `\n` for multi-line JSON. `echo` may interpret escape sequences differently across shells.
- **stderr**: The MCP server logs all INFO messages (stages, HTTP requests, dedup decisions) to stderr. Redirect with `2>/tmp/stderr.log` to keep them separate from stdout.
- **Exit codes**: `0` = success, `124` = killed by `timeout`, `1` = pipeline error. Even with exit 1, intermediate stage files may be usable for recovery.
