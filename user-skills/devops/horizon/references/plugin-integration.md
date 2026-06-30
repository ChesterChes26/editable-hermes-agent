# Horizon Plugin Integration (Alternative to MCP)

## Architecture

The Horizon plugin lives under Hermes' home directory: `~/AppData/Local/hermes/plugins/horizon/`
on Windows, `~/.hermes/plugins/horizon/` on macOS/Linux (determined by `get_hermes_home()` at
`hermes_constants.py:46-49`). It is a **standalone Hermes plugin** that replaces the generic
MCP-based integration with a direct subprocess + JSON-RPC pipe approach. Key difference from MCP:

| Aspect | MCP (old) | Plugin (new) |
|--------|-----------|--------------|
| Transport | Generic MCP client (`mcp_tool.py`) | Direct subprocess + JSON-RPC |
| Tool naming | `mcp_horizon_hz_*` (prefixed) | `hz_*` (native) |
| Registration | Async server negotiation → race-prone | Sync `register()` at gateway startup |
| Toolset filtering | Dynamic `register_toolset_alias()` → invisible to `_get_platform_tools()` | Static `toolset="horizon"` → always visible |
| Concurrency | MCP client-level | `threading.RLock` in plugin handlers |

## Plugin Structure

```
$(hermes_home)/plugins/horizon/     # ~/AppData/Local/hermes/... on Windows
  plugin.yaml          # metadata: name, kind=standalone, provides_tools list
  __init__.py          # register(ctx), tool handlers, subprocess management
```

**`plugin.yaml` key fields:**
```yaml
name: horizon
kind: standalone          # ← standalone = opt-in (see pitfall below)
provides_tools:
  - hz_validate_config
  - hz_fetch_items
  # ... all 13 tools
```

**`__init__.py` key functions:**
- `_ensure_proc()` — lazy-start Horizon subprocess, restart on death
- `_call_tool(name, arguments)` — JSON-RPC to Horizon via stdin/stdout
- `register(ctx)` — registers all 13 tools via `ctx.register_tool()` with `toolset="horizon"`

## Registration Flow

```
Gateway startup
  → discover_plugins() [hermes_cli/plugins.py]
    → scan $(hermes_home)/plugins/   # AppData/Local/hermes/plugins/ on Windows
      → find horizon/plugin.yaml, parse manifest
        → check: is "horizon" in plugins.enabled? [plugins.py:1329-1348]
          → YES: load plugin, call register(ctx)
            → ctx.register_tool(name="hz_*", toolset="horizon", handler=...)
          → NO: skip, mark as not-enabled
```

## Critical Pitfall: Standalone Plugins Are Opt-In

**Source:** `hermes_cli/plugins.py:1329-1348`

```python
# Everything else (standalone, user-installed backends,
# entry-point plugins) is opt-in via plugins.enabled.
is_enabled = (
    enabled is not None
    and (lookup_key in enabled or manifest.name in enabled)
)
if not is_enabled:
    loaded = LoadedPlugin(manifest=manifest, enabled=False)
    loaded.error = (
        "not enabled in config (run `hermes plugins enable {}` to activate)"
    )
```

Unlike `kind: backend` or `kind: platform` plugins (which auto-load), **standalone plugins require explicit opt-in**. The plugin scanner discovers them but skips loading if they're not in `plugins.enabled`.

### Symptoms of Not-Enabled Plugin

1. Plugin files exist at `$(hermes_home)/plugins/horizon/` ✓
2. Gateway log shows `Plugin discovery complete: N found, M enabled` — horizon is among the (N-M) skipped
3. No `hz_*` tools in the session tool list
4. `/reset` and `/new` don't help — the plugin is never loaded

### Fix

```bash
# Option A: CLI command (writes to config.yaml)
hermes plugins enable horizon

# Option B: Direct config edit
# Add "horizon" to plugins.enabled in ~/.hermes/config.yaml:
#   plugins:
#     enabled:
#       - agentmemory
#       - horizon

# Then restart gateway
hermes gateway restart

# Then /reset in the CLI session to pick up tools
```

### Verification After Fix

```bash
# Check plugin is enabled
hermes plugins list | grep horizon

# Check gateway-stdio.log for plugin load message
grep "horizon" ~/AppData/Local/hermes/logs/gateway-stdio.log

# After /reset, hz_* tools should appear in the session
```

## MCP Config Must Be Disabled

When using the plugin approach, the old MCP config MUST be disabled to avoid
double-registration and conflict:

```yaml
# In ~/AppData/Local/hermes/config.yaml:
mcp_servers:
  agentmemory:
    command: npx
    args: [...]
  # horizon: DISABLED - replaced by plugin at ~/.hermes/plugins/horizon/
```

If both MCP and plugin try to register horizon tools, you get duplicate tool names
and unpredictable behavior.
