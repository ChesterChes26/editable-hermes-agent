# Replacing MCP with Direct Plugin: Hermes ↔ External Server Pattern

When an external tool server speaks JSON-RPC over stdin/stdout (MCP protocol), Hermes can connect via either:

| Approach | Transport | Registration | Reliability on /reset |
|----------|-----------|-------------|----------------------|
| MCP (`mcp_tool.py`) | Generic MCP client → stdin/stdout pipe | Dynamic `tools/list` + `register_toolset_alias` | Race condition — toolset alias may miss static toolset list |
| Direct plugin | Custom handler → stdin/stdout pipe | Static `ctx.register_tool(toolset="...")` at plugin import | Always — no discovery phase |

## When to use plugin over MCP

- The external server is **your own project** (control both sides)
- You need **stable tool names** without `mcp_<server>_` prefix
- You hit **toolset filtering race conditions** after `/reset`
- You want tools to appear in a **specific named toolset** (e.g. `horizon`)

## Pattern: JSON-RPC pipe plugin

### Architecture

```
Hermes Agent
  → plugin __init__.py (register(ctx))
    → ctx.register_tool(name, toolset, schema, handler)
      → handler(args) → _call_tool(tool_name, args)
        → subprocess.Popen → stdin.write(JSON-RPC) / stdout.readline()
          → External MCP Server process
```

### Subprocess management

```python
import subprocess, threading, json, os

_proc: subprocess.Popen | None = None
_proc_lock = threading.RLock()  # MUST be RLock: retry path calls _ensure_proc()

def _ensure_proc() -> subprocess.Popen:
    global _proc
    with _proc_lock:
        if _proc is not None and _proc.poll() is not None:
            _proc = None
        if _proc is None:
            _proc = subprocess.Popen(
                ["python", "-m", "src.mcp.server"],
                cwd=PROJECT_DIR,
                env={**os.environ, "PYTHONUTF8": "1"},
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8",
            )
        return _proc
```

### JSON-RPC call with retry

```python
_RPC_ID = 0
_RPC_ID_LOCK = threading.Lock()

def _next_id() -> int:
    global _RPC_ID
    with _RPC_ID_LOCK:
        _RPC_ID += 1
        return _RPC_ID

def _call_tool(tool_name: str, arguments: dict) -> str:
    proc = _ensure_proc()
    req_id = _next_id()
    request = {"jsonrpc": "2.0", "method": "tools/call",
               "params": {"name": tool_name, "arguments": arguments}, "id": req_id}
    payload = json.dumps(request, ensure_ascii=False)

    try:
        with _proc_lock:
            try:
                proc.stdin.write(payload + "\n")
                proc.stdin.flush()
            except (BrokenPipeError, OSError):
                # Process died — restart and retry once
                global _proc
                _proc = None
                proc = _ensure_proc()   # ⚠ this acquires _proc_lock again → needs RLock!
                proc.stdin.write(payload + "\n")
                proc.stdin.flush()

            line = proc.stdout.readline()
            if not line:
                raise EOFError("Subprocess closed stdout unexpectedly")
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})

    try:
        response = json.loads(line)
    except json.JSONDecodeError:
        return json.dumps({"ok": False, "error": f"Invalid response: {line[:200]}"})

    if "error" in response:
        return json.dumps({"ok": False, "error": response["error"].get("message", "")})

    content_list = response.get("result", {}).get("content", [])
    if content_list and isinstance(content_list[0], dict):
        return content_list[0].get("text", "")
    return json.dumps({"ok": False, "error": "No content in response"})
```

### Tool registration

```python
TOOL_SCHEMAS = [
    {"name": "hz_validate_config", "description": "...", "parameters": {...}},
    # ... more tools
]

_HANDLERS = {
    "hz_validate_config": lambda args: _call_tool("hz_validate_config", args),
    # ... more handlers
}

def register(ctx):
    for schema in TOOL_SCHEMAS:
        ctx.register_tool(
            name=schema["name"],
            toolset="horizon",
            schema=schema,
            handler=_HANDLERS[schema["name"]],
        )
```

### plugin.yaml

```yaml
name: horizon
version: "1.0.0"
description: "Horizon data pipeline tools"
kind: standalone
provides_tools:
  - hz_validate_config
  - hz_fetch_items
  # ... all tools
```

## Pitfall: Lock → RLock

If `_call_tool` holds `_proc_lock` and its retry path calls `_ensure_proc()` which also does `with _proc_lock:`, Python's `threading.Lock` (non-reentrant) deadlocks. Use `threading.RLock` instead.

Concrete example from Horizon plugin (2026-06-26): Claude Code used `threading.Lock()`. The retry path at line 110 called `_ensure_proc()` which also acquires the lock. Fixed by switching to `threading.RLock()`.

## Pitfall: Two clients on same stdin/stdout

If both the MCP config (in config.yaml) and the plugin start the same external process, two subprocess.Popen instances compete for stdin/stdout. Disable the MCP config block before enabling the plugin.

## Verification

After deploying:
1. `hermes gateway restart`
2. Check `agent.log`: should show MCP registered from 1 server(s) (agentmemory only, not 2)
3. In session, `/reset` then test: `hz_get_metrics` should return server metrics
