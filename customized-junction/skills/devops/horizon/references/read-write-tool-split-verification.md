# Read/Write Tool Split — Verification

## 2026-06-29: Test 1 — 24h Pipeline (PER_TOOL_TIMEOUT=300s)

### Setup

Ran a 24h pipeline via background terminal with direct plugin import.

### Results (pipeline ran 4+ min, 11 concurrent reads)

| # | Tool | Result | Blocked? |
|---|------|--------|----------|
| 1 | hz_list_runs | 3 runs listed | No |
| 2 | hz_get_metrics | 16 runs, stage counts | No |
| 3 | hz_get_run_meta | meta returned | No |
| 4 | hz_get_run_stage(raw) | "stage artifact missing" | No (error, not block) |
| 5 | hz_list_runs | New run visible | No |
| 6 | hz_get_metrics | confirmed | No |
| 7 | hz_get_run_stage(raw) | 427 items returned | No |
| 8 | hz_get_run_meta | raw_count=427 | No |
| 9 | hz_get_run_stage(scored) | "stage artifact missing" | No (error, not block) |
| 10 | hz_list_runs | confirmed | No |
| 11 | hz_list_runs | confirmed | No |

**Verdict:** All 11 read tool calls returned instantly during live 24h pipeline execution. The `_proc_lock` split is working — read tools never touch the pipe or the lock.

### Pipeline outcome: TIMEOUT at 300s

Pipeline killed at 300s. stdout silent during scoring. `_readline_with_timeout` waited 300s with no output → None → `_kill_proc()`.

**Root cause:** PER_TOOL_TIMEOUT=300s too short. Previous successful run (run-xxx-e9f125a2, 427 items, 10.5 min) must have run through a different path.

## 2026-06-29: Test 2 — 900s timeout applied

### Fix

Changed `PER_TOOL_TIMEOUT` from 300 to 900 in `plugins/horizon/__init__.py` line 21.

### Pipeline re-launched

Run `run-20260629T074255Z-9cc8366f`: 441 raw items, scoring in progress at end of session. 900s should cover full pipeline (prior: 427 items ≈ 10.5 min).
