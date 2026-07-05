# Gateway Restart Fixes Plugin — 2026-07-05 Session

## Context

User asked about why restarting the gateway resolved Horizon issues in the previous session. Investigation traced through two sessions:

1. **"Runtime路径区分与插件验证"** (20260705_181952_bdd036) — After machine reboot, Horizon MCP server had no `.venv` at `$HORIZON_HOME\.venv\`. The plugin's `HORIZON_CMD` used `sys.executable` (gateway Python), which lacked Horizon dependencies. Multiple diagnostic dead-ends: checking PYTHONPATH shadowing, gateway env simulation, path resolution issues.

2. **"Horizon连通性确认与修复"** (20260705_184854_4ab98a) — Built Horizon's own venv: `editable-hermes-agent\.venv\Scripts\python.exe -m venv $HORIZON_HOME\.venv`, installed all deps with `pip install -e .`. Then `hermes gateway restart` → `hz_validate_config` returned `ok: true` immediately. Session was interrupted while cleaning zombie processes.

## Root Cause Chain

```
Plugin HORIZON_CMD = [sys.executable, ...]  ← broken (gateway Python lacks mcp)
  ↓
'hermes gateway restart' still uses old bytecode (plugin loaded once at startup)
  ↓
Fix: rebuild Horizon venv + update HORIZON_CMD → gateway restart → new process loads fixed plugin
```

## Key Insight: Plugin Hot-Reload Does Not Exist

The Hermes gateway imports plugin modules once at startup and caches them in `sys.modules`. File changes on disk are invisible until the gateway process exits and a new one starts. This is a general Hermes plugin architecture property — not Horizon-specific.

## Resolution Steps (in order)

1. **Build Horizon venv:**
   ```bash
   $EDITABLE_HERMES\.venv\Scripts\python.exe -m venv $HORIZON_HOME\.venv
   $HORIZON_HOME\.venv\Scripts\pip.exe install -e $HORIZON_HOME
   ```

2. **Update plugin `HORIZON_CMD`** to point to Horizon's own venv Python (done in plugin `__init__.py`).

3. **Clean zombie processes:**
   ```bash
   wmic process where "name='python.exe'" get ProcessId,CommandLine | grep "src.mcp.server"
   taskkill /F /PID <pid>
   ```

4. **Restart gateway:**
   ```bash
   hermes gateway restart
   ```

5. **Verify pipe connectivity:**
   ```
   hz_validate_config(check_env=false) → ok: true
   ```

## Current State (post-fix)

Horizon MCP server runs from `$HORIZON_HOME\.venv\Scripts\python.exe` (own isolated venv). Process tree:

```
gateway (system python, PID 11064)
  └─ Horizon MCP server (Horizon .venv python, PID 14772)
```

Gateway restart tested again in 2026-07-05 follow-up session: gateway was down, `hermes gateway restart` → PID 7124 → `hz_validate_config` ok, full pipeline completed successfully (9 items → 8 filtered → enriched → zh summary, 5m38s).

## Diagnostic Escalation (when pipe tools fail but disk reads work)

1. `hz_get_metrics` works → disk read path fine, plugin loaded
2. `hz_validate_config` fails → pipe path broken
3. Check `%TEMP%\horizon_stderr.log` for actual error
4. Check which Python the MCP subprocess is using:
   ```bash
   wmic process where "name='python.exe'" get ProcessId,ExecutablePath,CommandLine | grep "src.mcp.server"
   ```
5. Fix root cause → `hermes gateway restart` → re-verify
