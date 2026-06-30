# Delegate Plugin-Toolset Recovery

## Problem

Subagents cannot use plugin-registered toolsets (e.g. `horizon`) even when the parent agent has those tools loaded. Requesting `toolsets=['horizon']` in `delegate_task` silently drops the toolset — subagent gets no `hz_*` tools.

## Root Cause

Two interacting gaps in `tools/delegate_tool.py`:

### Gap 1: TOOLSETS is static, plugins aren't in it

`toolsets.py:89` — `TOOLSETS` is a static dict of built-in toolsets. Plugin tools like `hz_*` register via `registry.register_tool(toolset="horizon")` — they never enter `TOOLSETS`.

### Gap 2: Intersection only consults TOOLSETS

`delegate_tool.py:1066-1076` — when explicit `toolsets` are provided:

```python
expanded_parent = _expand_parent_toolsets(parent_toolsets)  # only TOOLSETS
child_toolsets = [t for t in toolsets if t in expanded_parent]  # "horizon" dropped
```

`_expand_parent_toolsets` (line 561-589) iterates `TOOLSETS.items()` exclusively. Plugin toolset names like `horizon` are never in `expanded_parent`, so they're silently dropped from `child_toolsets`.

Even when parent agent has `hz_*` tools loaded (via plugin), its `enabled_toolsets` is `["hermes-cli"]` — the composite that resolves to core tools. "horizon" is not a member.

## Fix (2026-06-30)

`delegate_tool.py:1071-1083` — after the intersection, recover plugin toolsets:

```python
child_toolsets = [t for t in toolsets if t in expanded_parent]
# Recover plugin-registered toolsets dropped by the static-TOOLSETS intersection.
for t in toolsets:
    if t not in child_toolsets:
        try:
            from tools.registry import registry
            ts_tools = registry.get_tool_names_for_toolset(t)
            if ts_tools and parent_agent and hasattr(parent_agent, "valid_tool_names"):
                if set(ts_tools).issubset(parent_agent.valid_tool_names):
                    child_toolsets.append(t)
        except Exception:
            pass
```

**Safety properties:**
- Only recovers toolsets whose tools are already loaded in the parent agent
- `try/except` — registry failures are non-fatal
- Does not modify `_expand_parent_toolsets` signature or behavior
- All 152 existing delegate tests pass unchanged

## Verification

```bash
cd ~/AppData/Local/hermes/hermes-agent
uv run pytest tests/tools/test_delegate_composite_toolsets.py \
               tests/tools/test_delegate_toolset_scope.py \
               tests/tools/test_delegate.py -v
# 152 passed
```

After gateway restart, `delegate_task(toolsets=['horizon'])` passes `hz_*` tools to subagent.
