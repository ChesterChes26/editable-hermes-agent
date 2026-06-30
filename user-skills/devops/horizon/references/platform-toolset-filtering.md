# Platform Toolset Filtering — Why MCP Tools Disappear in API Server Sessions

Source-level trace of the 2026-06-26 investigation.

## The Problem

Horizon MCP server connected and registered 17 tools at gateway startup:
```
agent.log: 12:23:11 INFO MCP server 'horizon' (stdio): registered 17 tool(s): 
  mcp_horizon_hz_validate_config, mcp_horizon_hz_fetch_items, ...
```

But `mcp_horizon_hz_*` tools were absent from the Hermes-A (WeChat/QQ) chatbot session.

## Root Cause Chain

### 1. API Server agent creation (`api_server.py:1103`)

```python
enabled_toolsets = sorted(_get_platform_tools(user_config, "api_server"))
```

### 2. Default toolset resolution (`tools_config.py:1386-1390`)

```python
plat_info = PLATFORMS.get(platform)  # → "hermes-api-server"
default_ts = plat_info["default_toolset"]
toolset_names = [default_ts]
```

### 3. Composite → individual resolution (`tools_config.py:1444-1457`)

```python
all_tool_names = set()
for ts_name in toolset_names:
    all_tool_names.update(resolve_toolset(ts_name))  # resolve "hermes-api-server"

enabled_toolsets = set()
for ts_key, _, _ in CONFIGURABLE_TOOLSETS:  # ← only STATIC toolsets!
    if ts_tools and ts_tools.issubset(all_tool_names):
        enabled_toolsets.add(ts_key)
```

`CONFIGURABLE_TOOLSETS` only contains built-in toolset keys like `web`, `terminal`, `file`, `browser`, etc. MCP toolsets are NOT in this list.

### 4. Recovery loop also misses MCP toolsets (`tools_config.py:1518-1534`)

```python
for ts_key, ts_def in TOOLSETS.items():  # ← static TOOLSETS dict
    ...
```

MCP toolsets are registered via `registry.register_toolset_alias()` at `mcp_tool.py:3991` — they are NEVER added to the static `TOOLSETS` dict. The recovery loop can't see them.

### 5. Per-turn refresh also blocked (`turn_context.py:181`)

```python
if has_registered_mcp_tools():
    refresh_agent_mcp_tools(agent, quiet_mode=True)
```

`refresh_agent_mcp_tools()` calls `get_tool_definitions(enabled_toolsets=agent.enabled_toolsets)`. Since `mcp-horizon` is not in `enabled_toolsets`, Horizon tools are filtered out.

### 6. Result

`mcp-horizon` never enters the agent's `enabled_toolsets` → `get_tool_definitions()` filters all Horizon tools → session has no `mcp_horizon_hz_*` tools.

## Why agentmemory MCP tools work (unresolved)

Agentmemory has TWO separate channels:
1. **Hermes MemoryProvider plugin** (`user-plugins/agentmemory/__init__.py`) → provides `memory_recall`, `memory_save`, `memory_search` via `_reinject_post_build_tools()`, bypassing toolset filtering entirely
2. **MCP server** (`npx @agentmemory/mcp`) → provides `mcp_agentmemory_memory_*` tools via the SAME `register_toolset_alias()` path as Horizon

The MCP tools from channel (2) go through the identical code path as `mcp_horizon_hz_*`:
`_register_server_tools()` → `_convert_mcp_schema()` → `registry.register()` → `register_toolset_alias("agentmemory", "mcp-agentmemory")`

Both then appear in `plugin_ts_keys` via `_get_plugin_toolset_keys()` → `_get_plugin_toolset_names()`. Both should be auto-enabled by `tools_config.py:1553-1555`:
```python
elif pts not in known_for_platform:
    enabled_toolsets.add(pts)  # new plugin → default enabled
```

Neither is in `_DEFAULT_OFF_TOOLSETS`, neither in `known_for_platform` (for api_server). **Theoretically both should work.** But empirically `mcp_agentmemory_memory_*` tools are available in the Hermes-A session while `mcp_horizon_hz_*` are not.

Possible unresolved cause: timing — `_get_platform_tools("api_server")` may be called before Horizon's `register_toolset_alias()` completes (agentmemory MCP server may connect faster via npx/Node.js than Horizon's Python startup). This hypothesis has not been verified with log timestamps.

## Fix

Add `mcp-horizon` to the API Server platform toolset config:

```yaml
# ~/.hermes/config.yaml
platform_toolsets:
  api_server:
    - hermes-api-server
    - mcp-horizon
```

Restart gateway after change. No code modification needed.

## Verification

```bash
# Confirm gateway-side registration succeeded
grep "MCP server 'horizon'.*registered" ~/AppData/Local/hermes/logs/agent.log | tail -3

# After config fix: confirm tools are in session tool list
grep "mcp_horizon" ~/AppData/Local/hermes/logs/agent.log | tail -5
```

## Key Source Files

| File | Line(s) | Role |
|------|---------|------|
| `tools/mcp_tool.py` | 3669 | Tool naming: `mcp_{server}_{tool}` |
| `tools/mcp_tool.py` | 3991 | `registry.register_toolset_alias(name, toolset_name)` |
| `tools/mcp_tool.py` | 4014-4019 | Registration INFO log |
| `gateway/platforms/api_server.py` | 1103 | `_get_platform_tools(config, "api_server")` |
| `hermes_cli/tools_config.py` | 1386 | Platform default toolset lookup |
| `hermes_cli/tools_config.py` | 1444-1498 | Composite → individual resolution |
| `hermes_cli/tools_config.py` | 1518-1534 | Recovery loop (misses MCP) |
| `agent/turn_context.py` | 181-183 | Per-turn MCP tool refresh |
| `hermes_cli/platforms.py` | 42 | `api_server` → `"hermes-api-server"` |
| `toolsets.py` | 390-421 | `hermes-api-server` tool list |
