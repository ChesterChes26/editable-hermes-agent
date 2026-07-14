# Plugin Toolset Recovery in Subagent Delegation

## Problem

Subagent dispatched with `toolsets=['horizon']` silently loses the `horizon` toolset. Subagent gets no `hz_*` tools.

## Root Cause (source-level)

### 1. Plugin toolsets are not in static TOOLSETS dict

`toolsets.py:89` — `TOOLSETS` is a static dict of built-in toolsets only:
```python
TOOLSETS = {
    "web": {...}, "terminal": {...}, ..., "hermes-cli": {...}
}
```

Horizon plugin registers tools via `ctx.register_tool(toolset="horizon")` → goes to the tool **registry**, not `TOOLSETS`.

### 2. Subagent toolset intersection drops plugins

`tools/delegate_tool.py:1066-1071` — `_build_child_agent()`:

```python
if toolsets:  # ['horizon']
    expanded_parent = _expand_parent_toolsets(parent_toolsets)  # {"hermes-cli", "web", ...}
    child_toolsets = [t for t in toolsets if t in expanded_parent]  # "horizon" NOT in expanded → DROPPED
```

### 3. _expand_parent_toolsets only sees static TOOLSETS

`tools/delegate_tool.py:561-589`:

```python
def _expand_parent_toolsets(parent_toolsets: set) -> set:
    parent_tool_names: set = set()
    for ts_name in parent_toolsets:
        ts_def = TOOLSETS.get(ts_name)  # TOOLSETS.get("hermes-cli") = OK
        # ... collects tools from static TOOLSETS only

    expanded = set(parent_toolsets)
    for ts_name, ts_def in TOOLSETS.items():  # iterates TOOLSETS — "horizon" not there
        # ...
    return expanded  # no "horizon"
```

## Fix (2026-06-30)

`tools/delegate_tool.py` line 1071 — after intersection, recover dropped plugin toolsets:

```python
child_toolsets = [t for t in toolsets if t in expanded_parent]
# NEW: recover plugin-registered toolsets dropped by static-TOOLSETS intersection
for t in toolsets:
    if t not in child_toolsets:
        try:
            from tools.registry import registry
            ts_tools = registry.get_tool_names_for_toolset(t)
            if ts_tools and parent_agent and hasattr(parent_agent, "valid_tool_names"):
                if set(ts_tools).issubset(parent_agent.valid_tool_names):
                    child_toolsets.append(t)  # recovered
        except Exception:
            pass
```

### Safety

- Only recovers toolset if parent agent actually has ALL those tools loaded (`valid_tool_names` check)
- `try/except` — any registry error doesn't affect normal flow
- Works for ANY plugin toolset, not just `horizon`

## Verification

- 152 tests (test_delegate.py, test_delegate_composite_toolsets.py, test_delegate_toolset_scope.py) — all pass
- Live test: `delegate_task(goal="hz_run_pipeline(...)", toolsets=["horizon"])` — completed in 17m18s, 2 API calls, full pipeline success

## Commit

`ChesterChes26/editable-hermes-agent`, branch `chester`, commit `03c3905c`
