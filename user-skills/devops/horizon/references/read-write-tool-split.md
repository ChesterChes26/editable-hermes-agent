# Read/Write Tool Split — `_proc_lock` Architecture

## Source

`~/AppData/Local/hermes/plugins/horizon/__init__.py` (Windows)

## Architecture

The plugin splits 13 Horizon tools into two categories based on how they access data:

### Write Tools (pipe → `_proc_lock` held)

These go through `_call_tool()` which wraps the entire JSON-RPC pipe write+read loop in `with _proc_lock:` (L187). Lock held for 5s–15min depending on the tool.

```
_make_handler(tool_name) → handler(args, **kw) → _call_tool(tool_name, args)
```

Lines 433-440:
```python
hz_validate_config_handler = _make_handler("hz_validate_config")
hz_fetch_items_handler     = _make_handler("hz_fetch_items")
hz_score_items_handler     = _make_handler("hz_score_items")
hz_filter_items_handler    = _make_handler("hz_filter_items")
hz_enrich_items_handler    = _make_handler("hz_enrich_items")
hz_generate_summary_handler = _make_handler("hz_generate_summary")
hz_run_pipeline_handler    = _make_handler("hz_run_pipeline")
hz_send_webhook_handler    = _make_handler("hz_send_webhook")
```

### Read Tools (direct filesystem → no lock)

These bypass the subprocess pipe entirely. They read JSON/MD files directly from `data/mcp-runs/` on disk. No `_proc_lock` acquired — instant return.

```
lambda args, **kw → _hz_*_direct(args)
```

Lines 443-447:
```python
hz_list_runs_handler       = lambda args, **kw: _hz_list_runs_direct(args)
hz_get_run_meta_handler    = lambda args, **kw: _hz_get_run_meta_direct(args)
hz_get_run_stage_handler   = lambda args, **kw: _hz_get_run_stage_direct(args)
hz_get_run_summary_handler = lambda args, **kw: _hz_get_run_summary_direct(args)
hz_get_metrics_handler     = lambda args, **kw: _hz_get_metrics_direct(args)
```

## Direct filesystem implementations (L256-415)

Each `_hz_*_direct()` function reads from `D:/workspace/AI-research/Horizon/data/mcp-runs/<run_id>/`:

| Function | Reads | L |
|---|---|---|
| `_hz_list_runs_direct` | `*/meta.json` (list dirs) | 313 |
| `_hz_get_run_meta_direct` | `<id>/meta.json` | 337 |
| `_hz_get_run_stage_direct` | `<id>/<stage>_items.json` | 350 |
| `_hz_get_run_summary_direct` | `<id>/summary-{lang}.md` | 381 |
| `_hz_get_metrics_direct` | counts stage files across all runs | 397 |

## Why this matters

**Before this split:** ALL 13 tools went through `_call_tool` → `_proc_lock`. During `hz_run_pipeline` (8-15 min), the lock was held, blocking even read-only queries. The main agent couldn't check pipeline progress.

**After this split:** While a subagent runs `hz_run_pipeline` (holding `_proc_lock` for the pipe), the main agent can freely call `hz_list_runs`, `hz_get_run_stage`, `hz_get_run_meta`, `hz_get_run_summary`, and `hz_get_metrics` — they read directly from disk without touching the pipe or the lock.

## Lock safety

- `_proc_lock` = `threading.RLock()` (L28) — re-entrant, safe for same-thread reacquisition
- `_kill_proc()` acquires `_proc_lock` internally (L41) — safe because RLock allows re-entry
- `_call_tool` retry path: `_proc = None` → `return _call_tool(_retry=False)` → `__exit__` releases lock, recursive call acquires fresh lock
- Read tools never touch `_proc_lock` — no contention possible
