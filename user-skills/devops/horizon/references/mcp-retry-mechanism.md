# MCPServerTask Retry-and-Abandon Mechanism

Source: `tools/mcp_tool.py` in Hermes Agent codebase.

## Connection Flow

```
discover_mcp_tools()            # line 4134 - entry point
  → _load_mcp_config()          # line 3055 - reads mcp_servers from config.yaml
  → register_mcp_servers()      # line 4027 - connects to new servers
    → _discover_and_register_server()  # line 3996 - per-server
      → _connect_server()       # line 3098
        → MCPServerTask(name)   # creates task object
        → server.start(config)  # line 3110
          → self._task = ensure_future(run(config))  # async task
          → await self._ready.wait()
          → if self._error: raise  # line 2376
```

## The Run Loop (line 2260+)

`MCPServerTask.run()` enters an infinite loop:

1. Calls `_connect()` to establish MCP session via stdio
2. On first failure: checks if still in "initial" phase (`not self._ready.is_set()`)
3. Increments `initial_retries`, checks against `_MAX_INITIAL_CONNECT_RETRIES` (3)
4. If <= 3: logs WARNING, sleeps with exponential backoff (1s, 2s, 4s), retries
5. If > 3: sets `self._error = exc`, `self._ready.set()`, **returns permanently**

```python
# Line 2313-2322
initial_retries += 1
if initial_retries > _MAX_INITIAL_CONNECT_RETRIES:
    logger.warning(
        "MCP server '%s' failed initial connection after "
        "%d attempts, giving up: %s",
        self.name, _MAX_INITIAL_CONNECT_RETRIES, exc,
    )
    self._error = exc
    self._ready.set()
    return
```

## Error Propagation

1. `run()` returns → `start()` sees `self._error` → raises to `_connect_server()`
2. `_connect_server()` propagates → `_discover_and_register_server()` fails
3. `_discover_one()` in `register_mcp_servers()` catches as `BaseException`
4. Server is logged as failed, **NOT added to `_servers` dict** (line 4009)

```python
# Line 4083-4095
if isinstance(result, BaseException):
    command = new_servers.get(name, {}).get("command")
    message = _format_connect_error(result)
    with _lock:
        _server_connecting.discard(name)
        _server_connect_errors[name] = message
    logger.warning(
        "Failed to connect to MCP server '%s'%s: %s",
        name,
        f" (command={command})" if command else "",
        message,
    )
```

## Idempotency Gate

`discover_mcp_tools()` only retries servers where `name not in _servers`:

```python
# Line 4156-4160
new_server_names = [
    name
    for name, cfg in servers.items()
    if name not in _servers and _parse_boolish(cfg.get("enabled", True), default=True)
]
```

Since failed servers are never added to `_servers`, they WILL be retried on the NEXT call to `discover_mcp_tools()`. But `discover_mcp_tools()` is only called at process startup — the gateway only calls it once. A CLI `/reset` does NOT call it.

## Practical Implications

1. **After a connection failure, only a gateway process restart triggers retry.** The gateway never re-runs `discover_mcp_tools()`.
2. **Dependency fixes require gateway restart, not just `/reset`.** Even if you `pip install` missing deps in the Hermes venv, the gateway process has already given up on Horizon. Restart the gateway, then `/reset`.
3. **The MCP server subprocess may stay alive after gateway gives up.** mcp-stderr.log will show PingRequests and ListToolsRequests even though the gateway considers the connection failed — these are from the MCP server's own lifecycle, not the gateway's tool registration.
4. **Verifying success:** Two checks, in order:
   - **errors.log**: no new horizon entries after restart timestamp = absence of failure.
   - **mcp-stderr.log PingRequests**: the definitive proof. After a successful restart, the gateway sends keepalive pings every 180s (`_DEFAULT_KEEPALIVE_INTERVAL`). Seeing `PingRequest` in mcp-stderr 3+ minutes after restart means the stdio transport is alive, the session is maintained, and Horizon is connected. ListToolsRequest alone is NOT enough — it can appear even when the handshake eventually fails.
   
   Gateway-stdio.log is unreliable for current-state verification: it retains WARNING entries from EVERY gateway instance that ever ran. 5 horizon warnings from last week will still show up today. Use errors.log (timestamped, per-process) and mcp-stderr PingRequests instead.
   
5. **First restart after dependency fix may fail transiently.** Observed on Windows: 1 failure in 3 consecutive restarts, exclusively on the first restart after `pip install -e .` into the Hermes venv. Suspected cause: stale Python bytecode cache or incomplete venv module resolution. If the first restart fails (5 WARNINGs), restart again — subsequent restarts have been reliable (2/2 successes observed).
