# Plugin Tool Registration: Source-Level Architecture

## Overview

Hermes plugins register tools through a synchronous, static path — unlike MCP, which
uses asynchronous dynamic discovery. This document traces the exact code path and
explains why plugin tools survive `/reset` and `/new` while MCP tools may not.

## Source Path

### Step 1: Discovery trigger — `model_tools.py:199-204`

```python
# Plugin tool discovery (user/project/pip plugins)
try:
    from hermes_cli.plugins import discover_plugins
    discover_plugins()
except Exception as e:
    logger.debug("Plugin discovery failed: %s", e)
```

This runs at module import time — every time the agent initializes (startup, `/reset`,
`/new`). It scans `~/.hermes/plugins/` for directories with `plugin.yaml` + `__init__.py`,
loads each, and calls `register(ctx)`.

### Step 2: Tool registration — `hermes_cli/plugins.py:367-401`

```python
class PluginContext:
    def register_tool(
        self,
        name: str,
        toolset: str,
        schema: dict,
        handler: Callable,
        check_fn: Callable | None = None,
        requires_env: list | None = None,
        is_async: bool = False,
        description: str = "",
        emoji: str = "",
        override: bool = False,
    ) -> None:
        from tools.registry import registry
        registry.register(
            name=name,
            toolset=toolset,
            schema=schema,
            handler=handler,
            check_fn=check_fn,
            requires_env=requires_env,
            is_async=is_async,
            description=description,
            emoji=emoji,
            override=override,
        )
        self._manager._plugin_tool_names.add(name)
```

Writes directly into the global `registry`. No async discovery, no `tools/list` polling.

### Step 3: Toolset exposure — automatic

Plugin toolsets are discovered automatically (AGENTS.md:506). The toolset name
passed to `ctx.register_tool(toolset="horizon", ...)` becomes a first-class toolset,
just like `web` or `terminal`. It appears in `toolsets.py` at runtime without manual
registration.

### Step 4: Cache invalidation — `model_tools.py:254-256`

```python
# Invalidation happens transparently via the registry's _generation counter,
# which bumps on register() / deregister() / register_toolset_alias().
```

Every `register_tool()` call bumps a generation counter, invalidating the tool
definitions cache. Next `get_tool_definitions()` call picks up the new tools.

## Plugin vs MCP: Architectural Comparison

| Aspect | MCP | Plugin |
|--------|-----|--------|
| Tool discovery | Async `tools/list` (dynamic) | Static code in `__init__.py` |
| Registration timing | After MCP server starts | Synchronous at Hermes startup |
| Toolset assignment | Requires `register_toolset_alias()` | `toolset="..."` in `register()` call |
| Naming | `mcp_<server>_<tool>` (auto-prefixed) | Whatever you pass as `name` |
| After `/reset` | Race condition — tools may miss startup | Reloaded synchronously, always present |
| Filtering | `toolsets.py` enabled/disabled sets | Same toolset mechanism, but no intermediate layer |
| Opt-in | Auto-enabled when `mcp_servers` config present | **Standalone plugins require `plugins.enabled`** |

## Standalone Plugin Opt-In: Source Evidence

`hermes_cli/plugins.py:1322-1348`:

```python
# Bundled platform plugins (gateway adapters like IRC) auto-load
# for the same reason: every platform Hermes ships must be
# available out of the box without the user having to opt in.
if manifest.source == "bundled" and manifest.kind in {"backend", "platform"}:
    self._load_plugin(manifest)
    continue

# Everything else (standalone, user-installed backends,
# entry-point plugins) is opt-in via plugins.enabled.
# Accept both the path-derived key and the legacy bare name
# so existing configs keep working.
is_enabled = (
    enabled is not None
    and (lookup_key in enabled or manifest.name in enabled)
)
if not is_enabled:
    loaded = LoadedPlugin(manifest=manifest, enabled=False)
    loaded.error = (
        "not enabled in config (run `hermes plugins enable {}` to activate)"
        .format(lookup_key)
    )
    self._plugins[lookup_key] = loaded
    logger.debug(
        "Skipping '%s' (not in plugins.enabled)", lookup_key
    )
    continue
self._load_plugin(manifest)
```

**Summary**: Bundled `backend`/`platform` plugins auto-load. Everything else — including
`kind: standalone` user-installed plugins — must be explicitly listed in
`plugins.enabled` in config.yaml, otherwise they are discovered but skipped
with a DEBUG-level log message (invisible at default INFO log level).

**To enable**: `hermes plugins enable <name>` or add the plugin name to
`plugins.enabled` in config.yaml, then restart the gateway.

## Why Plugin Tools Survive `/reset` and `/new`

1. `discover_plugins()` in `model_tools.py:199` runs every time the agent initializes
2. Plugin's `register(ctx)` is called synchronously
3. `ctx.register_tool()` writes directly to the global registry
4. No timing dependency on external process readiness
5. No intermediate `register_toolset_alias()` that can be missed

The entire MCP path (`mcp_tool.py` → `tools/list` → `register_toolset_alias`) has
three additional indirections between discovery and registration. The plugin path
has zero.

## Plugin Structure Reference

```
~/.hermes/plugins/<name>/
  plugin.yaml    # name, version, description, kind: standalone
  __init__.py    # def register(ctx): ctx.register_tool(...)
```

### plugin.yaml (minimal)

```yaml
name: horizon
version: 1.0.0
description: Horizon AI news pipeline tools
kind: standalone
provides_tools:
  - hz_run_pipeline
  - hz_fetch_sources
  # ...
```

### __init__.py (skeleton)

```python
def register(ctx):
    ctx.register_tool(
        name="hz_run_pipeline",
        toolset="horizon",
        schema={
            "name": "hz_run_pipeline",
            "description": "...",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
        handler=_hz_run_pipeline_handler,
    )
```

## Known Plugin Types

| Kind | Use case | Example |
|------|----------|---------|
| `standalone` | General tool plugins | Horizon, custom tools |
| `exclusive` | Memory/category providers | agentmemory |
| `backend` | Pluggable backend for core tools | image_gen backends |
| `platform` | Gateway messaging adapters | IRC, custom platforms |

## Pitfalls

1. **Standalone plugins MUST be explicitly enabled.** `hermes_cli/plugins.py:1329-1348`:
   standalone plugins are opt-in via `plugins.enabled` in config.yaml. They are
   *discovered* (filesystem scan finds them) but *skipped* if not listed. The skip
   is logged at DEBUG level, invisible at default INFO. Diagnosis: check
   `gateway-stdio.log` for `"Plugin discovery complete: %d found, %d enabled"` —
   the gap between found and enabled counts includes disabled standalone plugins.
   Fix: `hermes plugins enable <name>` then restart gateway.

2. **Plugin must live in `$HERMES_HOME/plugins/`** — on Windows, this is typically
   `~/AppData/Local/hermes/plugins/`, NOT `~/.hermes/plugins/`. Check with
   `hermes config path`.

3. **`register()` function is the entry point** — the function MUST be named `register`,
   accepting a single `ctx` argument. Other function names are ignored.

4. **Toolset must be a string** — the `toolset` parameter in `register_tool()` is a
   plain string. Multiple tools sharing the same toolset string become one toolset.

5. **Handler signature** — handler receives `(args: dict, **kwargs)`. The `task_id`
   is in `kwargs`. Return value must be a string (JSON-serialized typically).
