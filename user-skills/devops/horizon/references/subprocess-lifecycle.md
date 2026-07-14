# Horizon Plugin Subprocess Lifecycle

> Full analysis from 2026-06-30 session. Cross-referenced against `plugins/horizon/__init__.py` (670 lines).

## Core Mechanism

```python
# __init__.py:28-29 — module-level global, NOT session-scoped
_proc: subprocess.Popen | None = None
_proc_lock = threading.RLock()
```

The subprocess lives as long as the **gateway process** — `/new`, session switches, and agent restarts do not affect it.

## Startup: Lazy Spawn

```python
# __init__.py:63-119: _ensure_proc()
def _ensure_proc() -> subprocess.Popen:
    global _proc
    with _proc_lock:
        # Line 68: dead process → clean up
        if _proc is not None and _proc.poll() is not None:
            _proc = None

        # Line 76: only spawn if None
        if _proc is None:
            _proc = subprocess.Popen(
                [sys.executable, "-m", "src.mcp.server"],
                stdin=PIPE, stdout=PIPE, stderr=stderr_fh, ...
            )
            # Lines 89-117: MCP initialize handshake
            ...

        return _proc   # Line 119: reuse existing
```

**Timeline:**
```
gateway启动 → register() → _proc = None
第1次hz_*调用 → _ensure_proc() → spawn子进程A → MCP handshake
第2次hz_*调用 → poll()活着 → 直接用A
第N次  /new → poll()活着 → 还用A
```

At most **1 subprocess per Python process** at any time.

## Shutdown: Only Three Scenarios

### 1. Tool Call Timeout (line 203-204)

```python
# _call_tool(): _readline_with_timeout returns None after 900s
line = _readline_with_timeout(proc)
if line is None:
    _kill_proc()   # kills hung process, frees leaked daemon thread
    raise TimeoutError(...)
```

Most common trigger: pipeline runs >15 min with no stdout line.

### 2. Subprocess Crash (line 68)

```python
if _proc is not None and _proc.poll() is not None:
    # Already dead — close pipes, set to None
    # Next tool call spawns a fresh one
```

### 3. Gateway Restart / Machine Shutdown

OS reclaims all child processes when parent pythonw.exe dies.

**No** session-level shutdown: plugin has no `shutdown()` hook, no `on_session_end()`.

## Subagent Isolation

Each subagent is an **independent Python process** with its own `_proc`:

```
gateway (pythonw.exe)
  └─ _proc → Horizon子进程A    ← 1个，永不关(正常情况)

subagent-1 (python.exe)        ← delegate_task spawn
  └─ _proc → Horizon子进程B    ← subagent exit → OS回收B

subagent-2 (python.exe)
  └─ _proc → Horizon子进程C    ← subagent exit → OS回收C
```

| Scenario | Horizon子进程数 |
|----------|----------------|
| Idle | 1 (gateway) |
| 1 subagent running pipeline | 2 |
| 3 subagents concurrent | 4 |
| All subagents done | Back to 1 |

No accumulation. Only the gateway's subprocess persists.

## Contrast with agentmemory

| | agentmemory | Horizon |
|---|---|---|
| Runtime | Docker container | Local subprocess |
| Startup | Manual `npx` / watchdog cron | Plugin lazy spawn (first tool call) |
| Lifecycle owner | Completely independent | gateway (OS parent-child) |
| Cross-session | Container keeps running | Subprocess keeps running |
| Plugin role | HTTP client (`urllib.request`) | MCP stdio client (`subprocess.Popen`) |
| Plugin contains server code | No | No |

Both follow the same pattern: **plugin = thin bridge to external process**.

## Recommendation

- **Short queries** (`hz_list_runs`, `hz_get_metrics`): call from main session, reuse existing subprocess
- **Long tasks** (`hz_run_pipeline`, 8-15 min): dispatch via `delegate_task` or `cronjob` — avoids blocking main thread; subprocess auto-recycled when subagent exits
