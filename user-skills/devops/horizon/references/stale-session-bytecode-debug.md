# Stale Session Bytecode: Debugging Transcript (2026-06-26)

## The Problem

All 13 `hz_*` tools return `{"ok": false, "error": "Invalid request parameters"}` despite:
- Plugin enabled in `plugins.enabled: [agentmemory, horizon]`
- Tools appearing in agent tool list with correct schemas
- Agent log showing `Plugin discovery complete: 52 found, 44 enabled`
- `register()` confirmed called (log marker appeared in `%TEMP%/horizon_register.log`)
- Manual JSON-RPC against MCP server works perfectly

## The Diagnostic Trail

### Step 1: Eliminate MCP server as cause

```bash
cd D:/workspace/AI-research/Horizon
printf '{"jsonrpc":"2.0","id":1,"method":"initialize",...}\n{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"hz_get_metrics","arguments":{}}}\n' | timeout 15 python -m src.mcp.server
```
**Result:** SUCCESS. MCP server returns correct metrics data. Not an MCP server issue.

### Step 2: Eliminate plugin handler code as cause

Add debug logging to `_call_tool`:
```python
_debug = lambda msg: open(r"%TEMP%\horizon_plugin_debug.log", "a").write(msg + "\n")
```
**Result:** Debug file NOT created → `_call_tool` never reached. The error is above the handler.

But wait — also introduced a SyntaxError in the process. Lesson: always verify imports after patching.

### Step 3: Verify plugin loads at all

Add marker to `register()`:
```python
with open(r"%TEMP%\horizon_register.log", "a") as f:
    f.write("register() called\n")
```
**Result:** File created during gateway restart. Plugin IS discovered and `register()` IS called.

### Step 4: Check if handler is reached

Add marker to handler in `_make_handler`:
```python
def handler(args: dict, **kwargs) -> str:
    with open(r"C:\Users\chester.chen\hermes_handler_called.log", "a") as f:
        f.write(f"HANDLER CALLED: {tool_name}\n")
    return _call_tool(tool_name, args)
```
**Result:** NO file created. Handler is NEVER called by the session dispatch.

### Step 5: Bypass dispatch entirely — direct handler test in execute_code

```python
import sys
sys.path.insert(0, r"C:\Users\chester.chen\AppData\Local\hermes\plugins\horizon")
import importlib
m = importlib.import_module("__init__")
handler = m._HANDLERS["hz_get_metrics"]
result = handler({})
print(result)
```
**Result:** SUCCESS. Handler returns correct metrics data. Plugin code is correct.

## Root Cause

**Session bytecode staleness.** The execution sequence:

1. Plugin `__init__.py` was modified (several patches applied, some introducing temporary
   syntax errors)
2. `hermes gateway restart` → gateway loads new plugin, calls `register()` with new code
3. Current agent session was created BEFORE the gateway restart, or during a window when
   `__init__.py` had a SyntaxError
4. Session's tool dispatch uses the handlers loaded when the session was created
5. If the session was created while `__init__.py` had a syntax error, the handlers were
   never registered → tool calls go through dispatch but find no valid handler

**Why `register()` log appears but handler doesn't:** `register()` is called during gateway
startup (loads plugins fresh). The agent session's tool dispatch uses cached module bytecode
from session creation time.

**Why `execute_code` works:** `importlib.import_module("__init__")` always gets fresh code
from disk → reflects the latest fixes.

## Resolution

`/reset` the session to create a new agent instance that loads current plugin bytecode.

## Key Insight

Gateway restart ≠ session reload for plugin bytecode. The gateway process loads plugins
for `register()`, but agent sessions retain the bytecode they were created with. After
patching plugin files, always `/reset` (or start a new session).

## Diagnostic Pattern (Reusable)

```
Manual JSON-RPC → MCP server OK?
  └─ Execute_code handler test → handler code OK?
      └─ Handler log marker → handler reached?
          └─ If reached: check _call_tool communication
          └─ If NOT reached: session bytecode stale → /reset
```
