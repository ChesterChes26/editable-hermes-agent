# Gateway & Cron Process Lifecycle

How Hermes gateway stays alive after terminal close, why cron is a thread
not a process, and the distinction between "process" and "Agent instance."

## The Core Question

"Closing the CLI kills my `hermes` session — why doesn't it kill the gateway?"

Answer: the CLI is a foreground process attached to the terminal. The gateway
uses Win32 creation flags to **detach from the parent console and process group**
at spawn time. These are OS-level mechanisms, not Hermes-specific magic.

## Gateway Detach Mechanism

### Windows: `DETACHED_PROCESS` et al.

`hermes_cli/gateway.py:622-703` — `launch_detached_profile_gateway_restart()`.

When `hermes gateway start` is invoked, it spawns a **watcher** subprocess.
The watcher then spawns the actual gateway process with these creation flags
(line 678-702):

```python
_CREATE_NEW_PROCESS_GROUP     = 0x00000200  # escape parent's process group
_DETACHED_PROCESS             = 0x00000008  # no console attachment
_CREATE_NO_WINDOW             = 0x08000000  # suppress any GUI window
_CREATE_BREAKAWAY_FROM_JOB    = 0x01000000  # escape parent's Job Object
```

What each flag does:

- **`DETACHED_PROCESS`** — the critical one. Normally child processes inherit
  the parent's console. When the console closes, Windows sends `CTRL_CLOSE_EVENT`
  to every attached process. This flag severs that attachment. The gateway
  process has no console — closing the terminal does nothing to it.

- **`CREATE_NEW_PROCESS_GROUP`** — prevents `Ctrl+C` from propagating from the
  parent's process group. Without this, a Ctrl+C in the terminal (even to an
  unrelated process) could reach the gateway.

- **`CREATE_BREAKAWAY_FROM_JOB`** — Windows Terminal, Electron apps, and other
  terminal emulators often place child processes in a Job Object. When the
  parent exits, the Job Object is destroyed, killing all its children. This
  flag requests the kernel to remove the new process from the parent's job.
  Has a fallback (line 692-699): if the kernel rejects breakaway (parent
  Job Object has `JOB_OBJECT_LIMIT_BREAKAWAY_OK` not set), retries without it.

### Linux: `start_new_session=True`

Line 700-702: the POSIX path just sets `start_new_session=True`, which calls
`os.setsid()` in the child process. The new process becomes its own session
leader, detached from the terminal's session. Closing the terminal sends
`SIGHUP` to the session leader — but the gateway is the leader of its own
session, so it never receives it.

### Watcher Process

The watcher (line 649-703, a Python script passed as `-c` string) does:

1. Polls the old gateway PID with `_pid_exists()` every 0.2s
2. 120-second deadline — gives up if old process won't die
3. Once old PID is gone → spawns new gateway with the same detach flags

The watcher ITSELF is also spawned detached (line 714-742, same
`windows_detach_popen_kwargs()`). So closing the terminal kills neither the
watcher nor the gateway.

### Actual Launch Arguments

`hermes_cli/gateway.py:614-619`:

```python
def _gateway_run_args_for_profile(profile: str) -> list[str]:
    args = [get_python_path(), "-m", "hermes_cli.main"]
    if profile != "default":
        args.extend(["--profile", profile])
    args.extend(["gateway", "run", "--replace"])
    return args
```

The gateway process is literally just `python -m hermes_cli.main gateway run`.
Same Python, same codebase as CLI — different entry path.

## Cron: Thread, Not Process

`cron/scheduler.py:1-9` — the module docstring:

```
Cron job scheduler - executes due jobs.
The gateway calls this every 60 seconds from a background thread.
```

Cron does not have its own PID. It's a **daemon thread** inside the gateway
process.

`gateway/run.py:16442-16469` — `_start_cron_ticker()`:

```python
def _start_cron_ticker(stop_event, adapters=None, loop=None, interval=60):
    from cron.scheduler import tick as cron_tick
    while not stop_event.is_set():
        cron_tick(verbose=False, adapters=adapters, loop=loop, sync=False)
        stop_event.wait(60)
```

`gateway/run.py:16930-16938` — started inside gateway `main()`:

```python
threading.Thread(
    target=_start_cron_ticker,
    daemon=True,
    name="cron-ticker",
).start()
```

Implications:
- Gateway alive → cron alive. Gateway dead → cron dead.
- No separate install, no separate service management.
- `stop_event` cleanly shuts down the ticker on gateway exit.
- Daemon thread: if the main gateway thread exits unexpectedly, the cron
  thread is killed by the Python runtime (daemon threads don't block exit).

Each tick runs jobs in a fresh Agent instance. The cron thread is a pure
scheduler — it creates `AIAgent`, runs the session, discards it. No
persistent cron agent.

## Process vs Agent Instance

This is the most commonly misunderstood distinction:

**Process** = OS entity. One `python.exe` running `hermes_cli.main`.
You see it in `tasklist` / `ps aux`. Has a PID.

**Agent instance** = an `AIAgent` object in memory. Has a session, a
conversation loop, tool access. Created when needed, destroyed after
the task completes.

They are NOT 1:1. One gateway process creates many agent instances over
its lifetime. The CLI process creates exactly one. Cron ticks create
one per job run.

### What's actually running on a typical Hermes setup

| Process | PID count | Agent instances |
|---------|-----------|----------------|
| CLI (`hermes`) | 1 | 1 (your current conversation) |
| Gateway (`hermes gateway run`) | 1 | 0-N (per-platform, per-message — created on demand, destroyed after reply) |
| Cron ticker | 0 (thread in gateway) | 0-N (per job run — spawned, run, discarded) |

The gateway process is the only long-lived OS entity. Everything else is
ephemeral Agent instances that come and go.

## Why This Matters

1. **Memory isolation**: each agent instance has its own conversation,
   tools, and session state. They don't share context windows.

2. **No "zombie agents"**: when a message is handled or a cron job finishes,
   the agent instance is garbage collected. No persistent memory leak.

3. **Gateway restart = cron restart**: restarting the gateway process also
   restarts the cron ticker. There's no independent cron lifecycle.

4. **Platform adapters live in the gateway**: WeChat long-poll, QQ WebSocket,
   etc. all run as components inside the gateway process. When gateway dies,
   all messaging stops.

5. **CLI is completely independent**: you can have gateway running while using
   CLI, or vice versa. They share only the filesystem (config, state.db,
   skills) — no runtime coupling.
