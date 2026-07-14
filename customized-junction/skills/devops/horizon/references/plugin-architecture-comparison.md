# Horizon vs agentmemory — Plugin Architecture Comparison

Both plugins follow the same pattern: **thin communication bridge to an external process**. Neither injects service source code into Hermes.

## Architecture Side-by-Side

| | agentmemory | Horizon |
|---|---|---|
| Service source | `github.com/rohitg00/agentmemory` (Node.js) | `D:/workspace/AI-research/Horizon` (Python) |
| Distribution | npm → Docker image | local git clone |
| Runtime | Docker container | subprocess.Popen |
| Start trigger | Manual `npx` / watchdog cronjob | Plugin lazy-spawns on first tool call |
| Communication | HTTP → `localhost:3111` | JSON-RPC over stdio pipes |
| Plugin role | `urllib.request` HTTP client | `subprocess` MCP stdio client |
| Lifecycle | Independent — survives gateway restart | Tied to gateway process (killed on restart) |
| Cross-session | Container keeps running | Subprocess keeps running |
| Session-bound? | No | No (module-level `_proc` global) |
| Shutdown | Manual `docker stop` / watchdog timeout | `_kill_proc()` on timeout, or gateway exit |
| Plugin code weight | ~477 lines (HTTP client + hooks) | ~670 lines (MCP client + lifecycle mgmt) |

## What Both Plugins Do NOT Do

Neither plugin imports the service's source code:

```python
# agentmemory — does NOT do this
from agentmemory.iii_engine import IIIEngine  # ❌ doesn't exist

# horizon — does NOT do this  
from src.ai.client import AIClient  # ❌ doesn't import Horizon internals
```

Instead, both wrap external communication:

```python
# agentmemory (__init__.py:21,55)
from urllib.request import Request, urlopen
DEFAULT_BASE_URL = "http://localhost:3111"

# horizon (__init__.py:7,78)
import subprocess
_proc = subprocess.Popen(["python", "-m", "src.mcp.server"], stdin=PIPE, stdout=PIPE)
```

## Horizon Subprocess Lifecycle

```
gateway starts → register() called once
  → first hz_* tool call → _ensure_proc() lazy-spawns Python subprocess
  → MCP initialize handshake
  → subprocess stays alive (module-level _proc global)
  → /new session → same subprocess (no session binding)
  → gateway restart → subprocess killed (gateway owns the process)
  → tool timeout → _kill_proc(), next call re-spawns
```

Key: `_proc` is a module-level variable (`__init__.py:28`), not per-session. The plugin has no `shutdown()` or `on_session_end()` hook.

## Why Not Import Horizon Source Directly?

Technically possible (`sys.path.insert` + import), but avoided because:

1. **Dependency pollution** — Horizon's 12+ pip packages would need installing in Hermes venv, risking version conflicts
2. **Blocking risk** — pipeline runs 8-15 minutes; in-process execution would hang the gateway
3. **Crash isolation** — subprocess crash kills the child only; in-process crash kills the gateway
4. **Independent evolution** — Horizon can be updated without touching the plugin, as long as MCP interface stays stable

## What Dockerization Would Change

If Horizon were containerized (like agentmemory), the plugin would switch from stdio pipes to HTTP:

| Component | Current (subprocess) | Dockerized |
|---|---|---|
| Plugin transport | `proc.stdin.write()` + `proc.stdout.readline()` | `httpx.post()` HTTP client |
| Process mgmt | `_ensure_proc()` / `_kill_proc()` | `docker start/stop` or always-running |
| `_proc_lock` | Needed (single pipe, must serialize writes) | Not needed (HTTP is concurrent) |
| stderr logs | `%TEMP%/horizon_stderr.log` | `docker logs` |
| Dependencies | In Hermes venv or system Python | Bundled in Docker image |
| Data access | Direct filesystem | Volume mount required |

The biggest win: dependency issues disappear (no more `ModuleNotFoundError` in Hermes venv).
The biggest cost: plugin ~200 lines of pipe management rewrites to HTTP client.
