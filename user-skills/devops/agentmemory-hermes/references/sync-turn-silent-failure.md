## sync_turn Silent Failure Chain

### When sync_turn fires

`run_agent.py:3076` — after every agent reply completes:

```
Agent reply done
  → _sync_turn_memory() (run_agent.py:3060)
    → check interrupted? → skip
    → memory_manager.sync_all(user_text, response_text)
      → _submit_background(_run)  ← background thread pool
        → for provider in _providers:
            provider.sync_turn()
              → agentmemory: _api_bg("observe", {...})
                → daemon thread → HTTP POST /agentmemory/observe
```

Key: `sync_turn` fires every turn, unconditionally (unless interrupted). This makes it the ideal place for self-healing — if `session/start` failed silently during init, `sync_turn` can fix it before `observe`.

### Root cause: session/start silent failure

When `initialize()` or `on_session_switch` calls `_api("session/start", ...)` and the HTTP call fails (container TCP-stuck, transient timeout, worker not registered), `_api()` returns None silently. The caller discards the return value. Hermes believes the session is registered; agentmemory has never heard of it. Every subsequent `observe` fails because the session doesn't exist server-side.

The symptom: repeatedly `/new` and still 0 observations. The session list shows no entries for today.

### Permanent fix: self-healing in sync_turn (IMPLEMENTED 2026-06-23)

Add a synchronous `session/start` call at the top of agentmemory's `sync_turn()`, before the `observe` call. `session/start` is idempotent — calling it on an already-registered session is a no-op. This turns `sync_turn` into a self-healing hook.

**Implementation status:** Applied to `plugins/agentmemory/__init__.py`. Uses `logger.info` to emit diagnostic output on every turn. Requires `import logging` + `logger = logging.getLogger(__name__)` — without this, the code crashes (see "NameError pitfall" below).

```python
def sync_turn(self, user: str, assistant: str, **kwargs: Any) -> None:
    # Self-healing: if initialize()/on_session_switch silently failed to
    # register this session, fix it now. Idempotent — no-op for existing sessions.
    sid = kwargs.get("session_id", self._session_id)
    _api(self._base, "session/start", {
        "sessionId": sid,
        "project": self._project,
        "cwd": self._project,
    })
    _api_bg(self._base, "observe", {
        "hookType": "post_tool_use",
        "sessionId": sid,
        ...
    })
```

Why in `sync_turn` and not in `on_session_switch`:
- `sync_turn` fires every turn, `on_session_switch` only on `/new`
- If the first `/new` silently fails, `sync_turn` catches it next turn
- No retry logic needed — it just tries every turn until it works once

### NameError pitfall: logger missing

When adding diagnostic logging to the agentmemory plugin `__init__.py`, ensure:
```python
import logging
logger = logging.getLogger(__name__)
```
Without this, any `logger.warning(...)` / `logger.info(...)` call raises `NameError`, which propagates to `memory_manager`'s `except Exception: logger.debug(...)` and is silently swallowed. The diagnostic code itself becomes the silent crash it was trying to debug.

### When agentmemory worker is not running during session initialization:

```
session/start → 404 → _api() returns None → provider._base 仍设为默认值
↓
每轮 sync_turn → _api_bg(self._base, "observe", {...})
  → daemon thread → _api() → HTTP POST observe → 404 → return None
  → no exception raised → memory_manager._run() 的 try/except 没触发
  → no warning logged
  → Docker 日志无 "Observation captured"
```

Even after worker is manually started, the provider's `_session_id` was never properly registered server-side (session/start failed), but observe calls should still work since they include the sessionId in the payload.

### Five layers of silent exception swallowing (plus a NameError):

1. `run_agent.py:3085` — `except Exception: pass` after sync_all
2. `memory_manager.py:591` — `except Exception: logger.debug(...)` — debug level, not persisted
3. `memory_manager.py:595` — `executor.submit(fn)` returns a Future; nobody calls `.result()`, so if the `_run` lambda itself throws (e.g. `self._providers` mutated during iteration), the exception is silently captured by the Future and never surfaced. The outer `except Exception: pass` at layer 1 never sees it.
4. `memory_manager.py:772` — `on_session_switch() → except Exception: logger.debug(...)` — **debug 不落盘**。与 `initialize_all()` 的 `logger.warning`（line 945）形成关键对比——后者会落盘。
5. `plugins/agentmemory/__init__.py:168` — `except (URLError, TimeoutError, json.JSONDecodeError): return None`
6. `plugins/agentmemory/__init__.py:172` — `_api_bg` spawns daemon thread, no result tracking
7. `plugins/agentmemory/__init__.py:200,390` — `logger.warning(...)` → **NameError**（`logger` 未 import）。诊断代码自身崩溃，掩盖了 `session/start` 的返回值。

**关键区分：** `memory_manager.initialize_all()` 的异常处理用 `logger.warning`（**会落盘**），而 `memory_manager.on_session_switch()` 用 `logger.debug`（**不落盘**）。排查时优先看 agent.log 里的 "Memory provider initialize failed"——如果连这个都没有，说明 `initialize_all` 可能根本没被调用（gateway agent 初始化路径可能跳过了 memory init block）。

Net effect: the agent loop continues normally while sync_turn silently drops all writes. No log, no warning, no observable symptom except missing data in agentmemory.

### Best diagnostic: end-to-end verification script

```bash
python skills/devops/agentmemory-hermes/scripts/verify-ingestion.py
```

This is faster and more reliable than grepping logs — it tests the full chain (session/start → observe → smart-search) in one shot and gives a definitive PASS/FAIL.

### Fix: restart session

If endpoint works (200) but Docker shows no observe requests, the fix is to manually register the current session:

```bash
# 1. Get current session ID
python -c "import sqlite3; db=sqlite3.connect('~/AppData/Local/hermes/state.db'); print(db.execute('SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1').fetchone()[0])"

# 2. Register it with agentmemory
curl -s -X POST http://localhost:3111/agentmemory/session/start \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"<id>","project":"hermes","cwd":"C:/Users/<user>"}'

# 3. Verify
curl -s http://localhost:3111/agentmemory/sessions | grep <id>
```

Once registered, subsequent sync_turn calls will write observations normally.

**Why `/new` alone may not fix this:** `/new` triggers `on_session_switch` which calls `_api("session/start", ...)` — but this goes through the SAME `_api()` that returns None on failure (layer 5 above). If the HTTP call fails transiently, the miss is silent. After `/new`, always verify the session exists in agentmemory.

### Diagnostic workflow: Docker zero-request evidence

When `session/start` is truly called, Docker logs a POST request. Absence of POST requests means the call never reached the server. In the 2026-06-23 session, `docker logs --since/--until` showed zero requests between 10:30-11:00 despite a CLI restart at 10:39:52 creating a new session. Meanwhile, `agent.log` had no "Memory provider activated" entry — suggesting the `agent_init` memory init block may be skipped in some gateway agent creation paths. The self-healing `sync_turn` bypasses this entirely: even if initialize never runs, the first turn's sync_turn registers the session.
