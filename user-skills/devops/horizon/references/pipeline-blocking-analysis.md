# Pipeline Blocking Analysis — 2026-06-26

Full root cause analysis of why `hz_run_pipeline` blocks the Hermes agent's main thread,
producing zombie runs and cascading tool deadlocks.

## Timeline

### Session chain (4 sessions, same day)

```
Session 1 (15:42) — MCP initialize handshake fix
  → _ensure_proc() patched to send initialize after Popen
  → Gateway restart → tools verified working

Session 2 (16:32) — stdout protocol pollution fix
  → _call_tool() rewritten: while True loop skips non-JSON lines
  → orchestrator Console() writes progress to stdout mixed with JSON-RPC
  → Gateway restart again

Session 3 (16:57) — First pipeline attempt → HUNG
  08:57:21 UTC  hz_get_metrics → ok (uptime 0.04s, fresh server)
  08:57:22 UTC  hz_list_runs → 5 zombie runs from earlier session
  08:57:31 UTC  hz_validate_config → ok
  08:57:35 UTC  hz_run_pipeline(hours=1, threshold=0, sources=["hackernews"])
      → agent blocks for ~13 minutes
  09:10:xx UTC  agent wakes up, processes out-of-band messages
      → hz_get_metrics → uptime ~1s (SERVER WAS KILLED AND RESTARTED)
      → hz_list_runs → 9 total zombie runs (4 new ones from this session)

Session 4 (17:18) — Second pipeline attempt → HUNG AGAIN
  Same pattern: fresh server, same deadlock

Session 5 (17:20) — Delegated to subagent
  → delegate_task("Execute Horizon pipeline...") → deleg_f0bdd443
  → Subagent called hz_run_pipeline
  → MCP server died mid-pipeline → another zombie run at 09:22:48 UTC
```

## Three-Layer Blocking Mechanism

### Layer 1: Plugin readline with NO timeout

**File:** `~/AppData/Local/hermes/plugins/horizon/__init__.py:136-158`

```python
while True:
    line = proc.stdout.readline()  # ← BLOCKS INDEFINITELY
    if not line:
        raise EOFError("Horizon subprocess closed stdout unexpectedly")
    stripped = line.strip()
    if not stripped:
        continue
    try:
        response = json.loads(stripped)
    except json.JSONDecodeError:
        progress_lines.append(stripped[:200])
        continue
    if response.get("id") != req_id:
        continue
    break  # Found our response
```

The `readline()` on `proc.stdout` has **zero timeout**. No `threading.Thread` + `join(timeout)`,
no `select.select` (incompatible with Windows pipes — raises `OSError: [WinError 10093]`).

Previously identified by Claude Code review but never fixed — the review noted it was
a pre-existing pattern and deferred to "test first."

**Impact:** If the MCP subprocess crashes mid-pipeline, stdout closes but the plugin thread
is still blocked on `readline()`. The `except Exception` at line 160 catches `EOFError` but
only AFTER `readline()` returns — which may never happen if the process is killed by Windows
Job Object cleanup rather than a clean exit.

### Layer 2: Pipeline exceeds Hermes tool-call timeout

**File:** `D:/workspace/AI-research/Horizon/src/mcp/service.py:487-559`

```python
async def run_pipeline(self, hours, languages, threshold, ...):
    fetch_result = await self.fetch_items(...)     # line 499
    run_id = fetch_result["run_id"]
    score_result = await self.score_items(...)      # line 507
    filter_result = await self.filter_items(...)    # line 513
    enrich_result = await self.enrich_items(...)    # line 524
    for lang in final_languages:
        summary_result = await self.generate_summary(...)  # line 541
```

Each step involves LLM API calls (DeepSeek) with throttling at 3 concurrency for scoring,
2 for enrichment. The orchestrator's `fetch_all_sources()` at `orchestrator.py:87` fetches
from 5+ sources (GitHub, HN, RSS, Reddit, Telegram) sequentially or concurrently.

**Timing evidence:** From Session 3 — `hz_run_pipeline(hours=1, threshold=0, sources=["hackernews"])` —
even with just 1 source and 1 hour window, the agent was blocked for ~13 minutes before
the framework timeout recovered the session.

### Layer 3: _proc_lock cascading deadlock

**File:** `~/AppData/Local/hermes/plugins/horizon/__init__.py:125-158`

```python
def _call_tool(tool_name, arguments, _retry=True):
    proc = _ensure_proc()
    req_id = _next_id()
    ...
    with _proc_lock:                    # ← ACQUIRES LOCK
        proc.stdin.write(payload + "\n")
        proc.stdin.flush()
        while True:
            line = proc.stdout.readline()  # ← BLOCKS WHILE HOLDING LOCK
```

And `_ensure_proc()` also needs the lock:

```python
def _ensure_proc():
    global _proc
    with _proc_lock:                    # ← ALSO NEEDS LOCK
        if _proc is not None and _proc.poll() is not None:
            ...
        if _proc is None:
            _proc = subprocess.Popen(...)
```

**Result:** One hung pipeline call holds `_proc_lock` during the entire blocking `readline()`.
Any subsequent `hz_*` call enters `_ensure_proc()` → tries to `acquire _proc_lock` → **blocked forever**
until the Gateway process is restarted, killing the subprocess and releasing the lock.

This is why the user saw ALL Horizon tools become unresponsive, not just the pipeline.

## Zombie Run Mechanism

**File:** `D:/workspace/AI-research/Horizon/src/mcp/service.py:242-248`

```python
run_id = self.run_store.create_run(run_id)             # line 242: IMMEDIATE
...
raw_items = await orchestrator.fetch_all_sources(since)  # line 245: ACTUAL WORK
merged_items = orchestrator.merge_cross_source_duplicates(raw_items)
self.run_store.save_items(run_id, "raw", ...)           # line 248: SAVE RESULTS
```

`create_run()` at line 242 persists the run_id to disk BEFORE any actual work.
If the MCP process is killed between lines 242 and 248, the run survives as a
zombie — all stages `false`, no data.

**Kill triggers:**
1. Hermes Gateway restart → kills all plugin subprocesses
2. User opens new session after previous hung → Gateway restart → orphans killed
3. Windows Job Object cleanup on process exit

**Evidence from this session:**
```
run-20260626T092248Z-af99903d  created 09:22:48  all stages: false  ← subagent's run
run-20260626T091847Z-87eb8b1c  created 09:18:47  all stages: false  ← session 4
run-20260626T085734Z-ee11fec0  created 08:57:34  all stages: false  ← session 3
run-20260626T085611Z-4a502fb4  created 08:56:11  all stages: false  ← session 2
run-20260626T085610Z-09bb99ae  created 08:56:10  all stages: false
run-20260626T085610Z-f004c632  created 08:56:10  all stages: false
run-20260626T085610Z-25b4e4c3  created 08:56:10  all stages: false
run-20260626T084655Z-08dd49fa  created 08:46:55  all stages: false
run-20260626T084337Z-98067886  created 08:43:37  all stages: false
run-20260626T083402Z-29d8d132  created 08:34:02  all stages: false
```

All 10 most recent runs are zombies. Only `run-20260626T045402Z-a94f6a28` (04:54 UTC)
completed successfully — this was the cronjob-triggered run.

## Orchestrator Console stdout pollution

**File:** `D:/workspace/AI-research/Horizon/src/orchestrator.py:55`

```python
class HorizonOrchestrator:
    def __init__(self, config, storage):
        self.console = Console()  # ← writes to sys.stdout by default
```

**File:** `D:/workspace/AI-research/Horizon/src/mcp/horizon_adapter.py:178-181`

```python
def make_orchestrator(runtime, config, storage):
    return runtime.HorizonOrchestrator(config, storage)  # ← NO devnull redirect
```

The orchestrator uses `rich.Console()` which defaults to `sys.stdout`. In MCP stdio mode,
stdout IS the JSON-RPC protocol channel. All Rich progress lines
("🔍 Fetching from GitHub...", "📥 Fetched N items") are written to `proc.stdout`.

The plugin's `_call_tool()` handles this correctly (skips non-JSON lines at line 149-150),
so this is NOT the direct cause of blocking. But it means `readline()` keeps getting
data during pipeline execution — so it never hits an empty-pipe timeout, and the plugin
can't distinguish "pipeline in progress" from "MCP server crashed."

**Fix:** Redirect orchestrator console to `devnull`:
```python
def make_orchestrator(runtime, config, storage):
    import os
    console = Console(file=open(os.devnull, 'w'))
    return runtime.HorizonOrchestrator(config, storage)
    # then set orchestrator.console = console after init
```

## Correct Approach: Never call hz_run_pipeline directly

**Use `delegate_task` to spawn a subagent:**
- Subagent runs in isolated context — its blocking does not lock the main session
- Subagent's tool calls time out independently
- Main session remains responsive for monitoring (`hz_list_runs`, `hz_get_metrics`)

**Or use `cronjob` for recurring pipeline:**
- Cron jobs run in separate sessions with no main-thread dependency
- The existing successful run at 04:54 UTC was cron-triggered
- Long-running pipeline is the expected cron use case

## Permanent Fix Checklist

1. `plugins/horizon/__init__.py:137` — add `readline` timeout:
   ```python
   import threading
   def _readline_with_timeout(proc, timeout_seconds=900):
       result = [None]; exc = [None]
       def target():
           try: result[0] = proc.stdout.readline()
           except Exception as e: exc[0] = e
       t = threading.Thread(target=target, daemon=True)
       t.start(); t.join(timeout_seconds)
       if t.is_alive():
           raise TimeoutError(f"No response from MCP server after {timeout_seconds}s")
       if exc[0]: raise exc[0]
       return result[0]
   ```

2. `src/mcp/horizon_adapter.py:178-181` — redirect orchestrator console to devnull

3. Consider splitting `_call_tool()` to NOT hold `_proc_lock` during read:
   - Write + flush under lock
   - Release lock before readline loop
   - Re-acquire only to check/kill _proc on error
