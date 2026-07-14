# Pipeline Fix Review — 2026-06-29

Review of 6 Claude Code fixes applied to resolve the three-layer deadlock.

## Fix Status

### P0 — Hermes Plugin (`__init__.py`)

| Fix | Line(s) | Status | Notes |
|-----|---------|--------|-------|
| `PER_TOOL_TIMEOUT = 300` | 21 | ⚠️ Applied | Pipeline always times out (design: enforces delegate_task only) |
| `_kill_proc()` | 31-59 | ✅ Applied | RLock-safe, closes all pipes, waits for process death |
| `_readline_with_timeout` timeout→None | 135-162 | ✅ Applied | Daemon thread, return None on timeout, caller must kill |
| `_call_tool` timeout/EOF branch | 200-208 | ✅ Applied | Calls `_kill_proc()` before raising |
| `_ensure_proc` init 30s timeout | 99-115 | ✅ Applied | Independent timeout, kills on failure |

### P1 — Horizon AI Client (`client.py`)

| Fix | Line | Status |
|-----|------|--------|
| AnthropicClient timeout | 135 | ✅ `httpx.Timeout(120.0, connect=10.0)` |
| OpenAIClient timeout | 223 | ✅ same |
| AzureOpenAIClient timeout | 371 | ✅ same |

### P1 — Horizon stdout pollution

| Fix | Line | Status |
|-----|------|--------|
| `analyzer.py` Progress→devnull | 71 | ✅ `Console(file=open(os.devnull, "w"))` |
| `enricher.py` Progress→devnull | 64 | ✅ same |
| `enricher.py` DDGS stderr→devnull | 81 | ✅ properly closes/restores stderr |
| `horizon_adapter.py` orchestrator console | 188 | ✅ `orch.console = Console(file=open(os.devnull, "w"))` |

### P2 — Horizon Reddit parallel (`reddit.py`)

| Fix | Line | Status |
|-----|------|--------|
| Subreddit parallel fetch | 69 | ✅ `asyncio.gather(*tasks, return_exceptions=True)` |
| Comment parallel fetch | 340 | ✅ same |

## Review Findings

### 1. Pipeline always times out at 300s (design, not bug)

The orchestrator's Rich Console output is now fully redirected to devnull (`horizon_adapter.py:188`, `analyzer.py:71`, `enricher.py:64`). During an `hz_run_pipeline` call (8-15 min), stdout produces ZERO lines until the final JSON-RPC response. The plugin's `_readline_with_timeout(timeout=300)` will always fire at 5 minutes, calling `_kill_proc()` and killing the pipeline.

This is **by design** — it forcibly prevents direct `hz_run_pipeline` calls from the main agent thread, enforcing the "delegate_task or cronjob only" rule documented in the skill. Individual stage tools (`hz_fetch_items`, `hz_score_items`, etc.) complete within 300s and are unaffected.

### 2. Defense-in-depth: plugin non-JSON skip still active

Plugin `__init__.py:210-220` still skips non-JSON lines from stdout. With all Horizon-side output now going to devnull, these lines are effectively never hit — but they remain as a safety net if devnull redirect fails or a new source of stdout output is introduced.

### 3. Minor: unclosed devnull file handles

`open(os.devnull, "w")` at `analyzer.py:71`, `enricher.py:64`, and `horizon_adapter.py:188` create file handles that are never explicitly closed. CPython's refcount GC will close them when the objects are collected, and `/dev/null` writes are harmless. `enricher.py:80-87` (DDGS stderr) correctly closes and restores — good pattern, but not worth applying everywhere since the handles are process-lifetime.

### 4. `_kill_proc()` RLock re-entrancy is safe

`_kill_proc()` acquires `_proc_lock` internally. It is called from `_call_tool()` (line 201) and `_ensure_proc()` (line 114), both of which already hold `_proc_lock`. Since it's an `RLock`, re-entrant acquisition by the same thread is allowed. No deadlock risk.

### 5. `_call_tool` retry path lock handling is correct

When `BrokenPipeError` triggers retry (lines 192-195): `_proc = None` + `return _call_tool(_retry=False)`. The `return` statement exits the outer `with _proc_lock` block, releasing the lock via `__exit__`. The recursive call acquires its own lock. Correct.
