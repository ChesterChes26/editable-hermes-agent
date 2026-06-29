"""Horizon data pipeline plugin for Hermes Agent."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HORIZON_CWD = "D:/workspace/AI-research/Horizon"
HORIZON_CMD = [sys.executable or "python", "-m", "src.mcp.server"]
HORIZON_ENV = {
    **os.environ,
    "PYTHONUTF8": "1",
}
PER_TOOL_TIMEOUT = 900  # 15 min without a single stdout line → assume hung
STDERR_LOG = os.path.expandvars(r"%TEMP%\horizon_stderr.log")

# ---------------------------------------------------------------------------
# Subprocess management (lazy start, restart on death)
# ---------------------------------------------------------------------------

_proc: subprocess.Popen | None = None
_proc_lock = threading.RLock()


def _kill_proc() -> None:
    """Kill the Horizon subprocess and clear the global reference.

    This is the ONLY safe way to recover from a hung subprocess.  After
    ``proc.stdout.readline()`` times out, a leaked daemon thread is still
    blocking on the pipe.  Killing the process forces that thread to unblock
    (``readline()`` returns ``""`` on EOF), so the pipe is clean for the
    next call.
    """
    global _proc
    with _proc_lock:
        p = _proc
        _proc = None
        if p is None:
            return
        try:
            p.kill()
        except OSError:
            pass
        try:
            p.wait(timeout=5)
        except Exception:
            pass
        for stream in (p.stdout, p.stdin, p.stderr):
            try:
                if stream is not None:
                    stream.close()
            except OSError:
                pass


def _ensure_proc() -> subprocess.Popen:
    """Return the running Horizon subprocess, (re)starting it if needed."""
    global _proc

    with _proc_lock:
        if _proc is not None and _proc.poll() is not None:
            try:
                _proc.stdout.close()
                _proc.stdin.close()
            except OSError:
                pass
            _proc = None

        if _proc is None:
            _stderr_fh = open(STDERR_LOG, "a", encoding="utf-8", errors="replace")
            _proc = subprocess.Popen(
                HORIZON_CMD,
                cwd=HORIZON_CWD,
                env=HORIZON_ENV,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=_stderr_fh,
                text=True,
                encoding="utf-8",
            )

            init_req_id = _next_id()
            init_request = json.dumps({
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "hermes-horizon-plugin", "version": "1.0.0"},
                },
                "id": init_req_id,
            })
            try:
                _proc.stdin.write(init_request + "\n")
                _proc.stdin.flush()
                line = _readline_with_timeout(_proc, timeout=30)
                if line is None:
                    raise TimeoutError(
                        "Horizon subprocess did not respond to initialize "
                        "within 30s"
                    )
                if not line:
                    raise EOFError("MCP subprocess closed stdout during initialize")
                resp = json.loads(line)
                if "error" in resp:
                    err_msg = resp["error"].get("message", str(resp["error"]))
                    raise RuntimeError(f"MCP initialize failed: {err_msg}")
            except Exception:
                _kill_proc()
                raise

        return _proc


# ---------------------------------------------------------------------------
# JSON-RPC helpers
# ---------------------------------------------------------------------------

_RPC_ID = 0
_RPC_ID_LOCK = threading.Lock()


def _next_id() -> int:
    global _RPC_ID
    with _RPC_ID_LOCK:
        _RPC_ID += 1
        return _RPC_ID


def _readline_with_timeout(proc: subprocess.Popen, timeout: int = PER_TOOL_TIMEOUT) -> str | None:
    """Read a line from proc.stdout with a timeout via a daemon thread.

    On Windows, pipe reads are not interruptible by signals and select() is
    incompatible with pipes, so the only reliable timeout mechanism is a
    separate thread.  If the read does not complete within *timeout* seconds,
    ``None`` is returned.  The caller MUST call ``_kill_proc()`` to clean up
    the hung subprocess and the leaked daemon thread.
    """
    result: dict = {"line": None, "error": None}

    def _read() -> None:
        try:
            result["line"] = proc.stdout.readline()
        except Exception as exc:
            result["error"] = str(exc)

    t = threading.Thread(target=_read, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        # Thread still blocked on readline — caller must kill proc to
        # unblock it.  We cannot close the pipe from here because
        # proc.stdout belongs to the parent; only kill() will force EOF.
        return None
    if result["error"]:
        raise RuntimeError(f"readline thread failed: {result['error']}")
    return result["line"]


def _call_tool(tool_name: str, arguments: dict, _retry: bool = True) -> str:
    """Send a tools/call JSON-RPC request and return the result text string.

    The Horizon MCP server writes Rich Console progress lines to stdout
    (e.g. "🔍 Fetching from GitHub...") intermixed with JSON-RPC responses.
    We loop until we find a valid JSON line whose id matches our request.
    """
    try:
        proc = _ensure_proc()
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    req_id = _next_id()
    request = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
        "id": req_id,
    }
    payload = json.dumps(request, ensure_ascii=False)

    progress_lines: list[str] = []
    try:
        with _proc_lock:
            try:
                proc.stdin.write(payload + "\n")
                proc.stdin.flush()
            except (BrokenPipeError, OSError):
                if _retry:
                    global _proc
                    _proc = None
                    return _call_tool(tool_name, arguments, _retry=False)
                raise

            while True:
                line = _readline_with_timeout(proc)
                if line is None:
                    _kill_proc()  # kill hung process → frees leaked daemon thread
                    raise TimeoutError(
                        f"Horizon subprocess did not respond within "
                        f"{PER_TOOL_TIMEOUT}s for tool '{tool_name}'"
                    )
                if line == "":
                    _kill_proc()
                    raise EOFError("Horizon subprocess closed stdout unexpectedly")

                # Try to parse as JSON.  Non-JSON lines are console progress
                # output from the orchestrator's Rich Console; skip them.
                stripped = line.strip()
                if not stripped:
                    continue

                try:
                    response = json.loads(stripped)
                except json.JSONDecodeError:
                    progress_lines.append(stripped[:200])
                    continue

                # Check if this response matches our request id.
                if response.get("id") != req_id:
                    # Stale response from a previous request — skip.
                    continue

                break  # Found our response — exit loop

    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})

    if "error" in response:
        err = response["error"]
        return json.dumps({"ok": False, "error": err.get("message", str(err))})

    try:
        content_list = response.get("result", {}).get("content", [])
        if content_list and isinstance(content_list[0], dict):
            text = content_list[0].get("text", json.dumps({"ok": False, "error": "Empty content"}))
            # Attach progress lines as metadata so the caller can see them.
            if progress_lines:
                try:
                    result = json.loads(text)
                    if isinstance(result, dict) and result.get("ok"):
                        result["_progress"] = progress_lines
                        text = json.dumps(result, ensure_ascii=False)
                except json.JSONDecodeError:
                    pass
            return text
        return json.dumps({"ok": False, "error": "No content in JSON-RPC response"})
    except (IndexError, KeyError, TypeError):
        return json.dumps({"ok": False, "error": "Malformed JSON-RPC response"})


# ---------------------------------------------------------------------------
# Direct filesystem access for read-only queries
# ---------------------------------------------------------------------------
# hz_list_runs, hz_get_run_meta, hz_get_run_stage, hz_get_run_summary, and
# hz_get_metrics read data that Horizon persists to disk via RunStore.
# They do NOT need the subprocess pipe — they can read the JSON files
# directly.  This lets the main agent inspect pipeline progress while the
# subprocess pipe is busy running hz_run_pipeline (which holds _proc_lock).

import glob as _glob
from datetime import datetime as _dt, timezone as _tz
from pathlib import Path as _Path
from uuid import uuid4 as _uuid4

_RUNS_ROOT = _Path(HORIZON_CWD) / "data" / "mcp-runs"

_STAGE_FILES = {
    "raw": "raw_items.json",
    "scored": "scored_items.json",
    "filtered": "filtered_items.json",
    "enriched": "enriched_items.json",
}


def _utc_now() -> str:
    return _dt.now(_tz.utc).isoformat()


def _read_runs_root() -> _Path:
    """Return the resolved runs root directory, creating it if absent."""
    root = _RUNS_ROOT.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _list_run_dirs() -> list[_Path]:
    """Yield existing run directories sorted by name descending."""
    root = _read_runs_root()
    dirs = sorted(
        [d for d in root.iterdir() if d.is_dir()],
        key=lambda d: d.name,
        reverse=True,
    )
    return dirs


def _read_json(path: _Path) -> dict | list:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _read_json_safe(path: _Path) -> dict | list | None:
    try:
        return _read_json(path)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _hz_list_runs_direct(args: dict) -> str:
    limit = max(1, min(args.get("limit", 20), 200))
    items = []
    for run_dir in _list_run_dirs():
        meta = _read_json_safe(run_dir / "meta.json")
        if meta is None:
            continue
        if not isinstance(meta, dict):
            continue
        stages = {}
        for stage, fname in _STAGE_FILES.items():
            stages[stage] = (run_dir / fname).exists()
        items.append({
            "run_id": meta.get("run_id", run_dir.name),
            "created_at": meta.get("created_at", ""),
            "updated_at": meta.get("updated_at", ""),
            "stages": stages,
            "meta": meta,
        })
        if len(items) >= limit:
            break
    return json.dumps({"ok": True, "tool": "hz_list_runs", "data": {"count": len(items), "items": items}, "meta": {"timestamp": _utc_now()}})


def _hz_get_run_meta_direct(args: dict) -> str:
    run_id = args.get("run_id", "")
    if not run_id:
        return json.dumps({"ok": False, "error": "run_id is required"})
    run_dir = _read_runs_root() / run_id
    if not run_dir.is_dir():
        return json.dumps({"ok": False, "error": f"run not found: {run_id}"})
    meta = _read_json_safe(run_dir / "meta.json")
    if meta is None:
        return json.dumps({"ok": False, "error": f"meta.json missing for run: {run_id}"})
    return json.dumps({"ok": True, "tool": "hz_get_run_meta", "data": {"run_id": run_id, "meta": meta}, "meta": {"timestamp": _utc_now()}})


def _hz_get_run_stage_direct(args: dict) -> str:
    run_id = args.get("run_id", "")
    stage = args.get("stage", "")
    max_items = max(1, args.get("max_items", 200))
    if not run_id or not stage:
        return json.dumps({"ok": False, "error": "run_id and stage are required"})
    if stage not in _STAGE_FILES:
        return json.dumps({"ok": False, "error": f"invalid stage: {stage}"})
    run_dir = _read_runs_root() / run_id
    if not run_dir.is_dir():
        return json.dumps({"ok": False, "error": f"run not found: {run_id}"})
    items = _read_json_safe(run_dir / _STAGE_FILES[stage])
    if items is None:
        return json.dumps({"ok": False, "error": f"stage artifact missing: {run_id}/{stage}"})
    if not isinstance(items, list):
        return json.dumps({"ok": False, "error": f"malformed stage artifact: {run_id}/{stage}"})
    truncated = len(items) > max_items
    return json.dumps({
        "ok": True,
        "tool": "hz_get_run_stage",
        "data": {
            "run_id": run_id,
            "stage": stage,
            "count": len(items),
            "items": items[:max_items],
            "truncated": truncated,
        },
        "meta": {"timestamp": _utc_now()},
    })


def _hz_get_run_summary_direct(args: dict) -> str:
    run_id = args.get("run_id", "")
    language = args.get("language", "zh")
    if not run_id:
        return json.dumps({"ok": False, "error": "run_id is required"})
    run_dir = _read_runs_root() / run_id
    if not run_dir.is_dir():
        return json.dumps({"ok": False, "error": f"run not found: {run_id}"})
    summary_path = run_dir / f"summary-{language}.md"
    try:
        markdown = summary_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return json.dumps({"ok": False, "error": f"summary not found: {run_id}/{language}"})
    return json.dumps({"ok": True, "tool": "hz_get_run_summary", "data": {"run_id": run_id, "language": language, "summary": markdown}, "meta": {"timestamp": _utc_now()}})


def _hz_get_metrics_direct(args: dict) -> str:
    """Read aggregate stats from the filesystem (no pipe needed)."""
    runs = _list_run_dirs()
    total_runs = len(runs)
    stage_counts = {"raw": 0, "scored": 0, "filtered": 0, "enriched": 0}
    for run_dir in runs:
        for stage, fname in _STAGE_FILES.items():
            if (run_dir / fname).exists():
                stage_counts[stage] += 1
    return json.dumps({
        "ok": True,
        "tool": "hz_get_metrics",
        "data": {
            "total_runs": total_runs,
            "stages_present": stage_counts,
            "runs_root": str(_read_runs_root()),
        },
        "meta": {"timestamp": _utc_now(), "note": "filesystem stats (not server in-memory metrics)"},
    })


# ---------------------------------------------------------------------------
# Tool handlers  (write tools → pipe;  read tools → direct fs)
# ---------------------------------------------------------------------------


def _make_handler(tool_name: str):
    """Factory: return a handler(args, **kwargs) -> str for the given tool."""
    def handler(args: dict, **kwargs) -> str:
        with open(os.path.expandvars(r"%TEMP%\horizon_handler.log"), "a") as f:
            f.write(f"handler called: tool={tool_name}\n")
        return _call_tool(tool_name, args)
    return handler


# Write / mutating tools — must go through the subprocess pipe
hz_validate_config_handler = _make_handler("hz_validate_config")
hz_fetch_items_handler = _make_handler("hz_fetch_items")
hz_score_items_handler = _make_handler("hz_score_items")
hz_filter_items_handler = _make_handler("hz_filter_items")
hz_enrich_items_handler = _make_handler("hz_enrich_items")
hz_generate_summary_handler = _make_handler("hz_generate_summary")
hz_run_pipeline_handler = _make_handler("hz_run_pipeline")
hz_send_webhook_handler = _make_handler("hz_send_webhook")

# Read-only tools — bypass the pipe, read files directly
hz_list_runs_handler = lambda args, **kw: _hz_list_runs_direct(args)
hz_get_run_meta_handler = lambda args, **kw: _hz_get_run_meta_direct(args)
hz_get_run_stage_handler = lambda args, **kw: _hz_get_run_stage_direct(args)
hz_get_run_summary_handler = lambda args, **kw: _hz_get_run_summary_direct(args)
hz_get_metrics_handler = lambda args, **kw: _hz_get_metrics_direct(args)


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "name": "hz_validate_config",
        "description": "Validate Horizon config and required environment variables.",
        "parameters": {
            "type": "object",
            "properties": {
                "horizon_path": {"type": "string", "description": "Path to Horizon project directory."},
                "config_path": {"type": "string", "description": "Path to Horizon config file."},
                "sources": {"type": "array", "items": {"type": "string"}, "description": "List of source names to validate."},
                "check_env": {"type": "boolean", "description": "Whether to check required environment variables.", "default": True},
            },
            "required": [],
        },
    },
    {
        "name": "hz_fetch_items",
        "description": "Fetch and deduplicate content into the raw stage.",
        "parameters": {
            "type": "object",
            "properties": {
                "hours": {"type": "integer", "description": "How many hours back to fetch.", "default": 24},
                "run_id": {"type": "string", "description": "Optional run ID to continue."},
                "horizon_path": {"type": "string", "description": "Path to Horizon project directory."},
                "config_path": {"type": "string", "description": "Path to Horizon config file."},
                "sources": {"type": "array", "items": {"type": "string"}, "description": "Source names to fetch from."},
            },
            "required": [],
        },
    },
    {
        "name": "hz_score_items",
        "description": "Score a stage into the scored stage.",
        "parameters": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "Target run ID."},
                "source_stage": {"type": "string", "description": "Stage to read from.", "default": "raw"},
                "horizon_path": {"type": "string", "description": "Path to Horizon project directory."},
                "config_path": {"type": "string", "description": "Path to Horizon config file."},
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "hz_filter_items",
        "description": "Filter scored items into the filtered stage.",
        "parameters": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "Target run ID."},
                "threshold": {"type": "number", "description": "Minimum score threshold (0-100)."},
                "source_stage": {"type": "string", "description": "Stage to read from.", "default": "scored"},
                "topic_dedup": {"type": "boolean", "description": "Deduplicate by topic similarity.", "default": True},
                "horizon_path": {"type": "string", "description": "Path to Horizon project directory."},
                "config_path": {"type": "string", "description": "Path to Horizon config file."},
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "hz_enrich_items",
        "description": "Enrich filtered items into the enriched stage.",
        "parameters": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "Target run ID."},
                "source_stage": {"type": "string", "description": "Stage to read from.", "default": "filtered"},
                "horizon_path": {"type": "string", "description": "Path to Horizon project directory."},
                "config_path": {"type": "string", "description": "Path to Horizon config file."},
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "hz_generate_summary",
        "description": "Generate a markdown summary from a stage.",
        "parameters": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "Target run ID."},
                "language": {"type": "string", "description": "Summary language code (e.g. zh, en).", "default": "zh"},
                "source_stage": {"type": "string", "description": "Stage to summarize."},
                "horizon_path": {"type": "string", "description": "Path to Horizon project directory."},
                "config_path": {"type": "string", "description": "Path to Horizon config file."},
                "save_to_horizon_data": {"type": "boolean", "description": "Whether to persist the summary to Horizon data directory.", "default": False},
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "hz_run_pipeline",
        "description": "Run fetch -> score -> filter -> enrich -> summarize in one call.",
        "parameters": {
            "type": "object",
            "properties": {
                "hours": {"type": "integer", "description": "How many hours back to fetch.", "default": 24},
                "languages": {"type": "array", "items": {"type": "string"}, "description": "Languages for summary generation."},
                "threshold": {"type": "number", "description": "Filter threshold (0-100)."},
                "horizon_path": {"type": "string", "description": "Path to Horizon project directory."},
                "config_path": {"type": "string", "description": "Path to Horizon config file."},
                "sources": {"type": "array", "items": {"type": "string"}, "description": "Source names to fetch from."},
                "enrich": {"type": "boolean", "description": "Whether to run the enrichment step.", "default": True},
                "topic_dedup": {"type": "boolean", "description": "Deduplicate by topic similarity.", "default": True},
                "save_to_horizon_data": {"type": "boolean", "description": "Whether to persist the summary to Horizon data directory.", "default": False},
            },
            "required": [],
        },
    },
    {
        "name": "hz_list_runs",
        "description": "List recent runs and stage states.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Maximum number of runs to return.", "default": 20},
            },
            "required": [],
        },
    },
    {
        "name": "hz_get_run_meta",
        "description": "Read run metadata.",
        "parameters": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "Run ID to query."},
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "hz_get_run_stage",
        "description": "Read items from a run stage.",
        "parameters": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "Run ID to query."},
                "stage": {"type": "string", "description": "Stage name (raw, scored, filtered, enriched)."},
                "max_items": {"type": "integer", "description": "Maximum items to return.", "default": 200},
            },
            "required": ["run_id", "stage"],
        },
    },
    {
        "name": "hz_get_run_summary",
        "description": "Read a generated run summary.",
        "parameters": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "Run ID to query."},
                "language": {"type": "string", "description": "Summary language to retrieve.", "default": "zh"},
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "hz_get_metrics",
        "description": "Read in-memory server metrics.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "hz_send_webhook",
        "description": "Send a webhook notification with the given variables.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date string for the notification."},
                "language": {"type": "string", "description": "Summary language.", "default": "zh"},
                "important_items": {"type": "integer", "description": "Number of important items to report.", "default": 0},
                "all_items": {"type": "integer", "description": "Total number of items to report.", "default": 0},
                "result": {"type": "string", "description": "Pipeline result status.", "default": "success"},
                "summary": {"type": "string", "description": "Summary text to include.", "default": ""},
                "horizon_path": {"type": "string", "description": "Path to Horizon project directory."},
                "config_path": {"type": "string", "description": "Path to Horizon config file."},
            },
            "required": ["date"],
        },
    },
]

_HANDLERS = {
    "hz_validate_config": hz_validate_config_handler,
    "hz_fetch_items": hz_fetch_items_handler,
    "hz_score_items": hz_score_items_handler,
    "hz_filter_items": hz_filter_items_handler,
    "hz_enrich_items": hz_enrich_items_handler,
    "hz_generate_summary": hz_generate_summary_handler,
    "hz_run_pipeline": hz_run_pipeline_handler,
    "hz_list_runs": hz_list_runs_handler,
    "hz_get_run_meta": hz_get_run_meta_handler,
    "hz_get_run_stage": hz_get_run_stage_handler,
    "hz_get_run_summary": hz_get_run_summary_handler,
    "hz_get_metrics": hz_get_metrics_handler,
    "hz_send_webhook": hz_send_webhook_handler,
}


def register(ctx: object) -> None:
    """Register all Horizon tools directly via ctx.register_tool()."""
    with open(os.path.expandvars(r"%TEMP%\horizon_register.log"), "a") as f:
        f.write("register() called\n")
    for schema in TOOL_SCHEMAS:
        tool_name = schema["name"]
        handler = _HANDLERS[tool_name]
        ctx.register_tool(
            name=tool_name,
            toolset="horizon",
            schema=schema,
            handler=handler,
        )
