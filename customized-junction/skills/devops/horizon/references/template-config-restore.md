# Template Config Restore — 2026-06-26 Diagnosis Session

## Session Summary

**User's Claude Code session** identified and fixed a root cause where Horizon plugin
disappeared after Hermes restart. The existing fix (runtime `config.yaml` with
`plugins.enabled: [agentmemory, horizon]`) was insufficient — Hermes may restore config
from a template on restart.

## Root Cause

Hermes may restore configuration from `user-config/config.yaml` on restart.
If this **template** file only has `agentmemory` in `plugins.enabled` (no `horizon`),
the restored runtime config loses `horizon`, and the plugin is skipped on next
gateway load.

The template lives at:
```
Windows: %LOCALAPPDATA%/hermes/hermes-agent/user-config/config.yaml
```

## All 4 Fix Locations

| # | File | Fix | Status (post-session) |
|---|------|-----|------------------------|
| 1 | Runtime config `config.yaml` | `plugins.enabled` includes `horizon` | ✅ |
| 2 | Template `user-config/config.yaml` | `plugins.enabled` includes `horizon` | ✅ |
| 3 | Runtime config `config.yaml` | `mcp_servers.horizon` removed | ✅ |
| 4 | Template `user-config/config.yaml` | `mcp_servers.horizon` removed | ✅ |

## Extra: Redundant Plugin Directory

`~/.hermes/plugins/horizon/` is a redundant copy — on Windows, Hermes scans
`%LOCALAPPDATA%/hermes/plugins/` (per `hermes_constants.py:46-49`). The `~/.hermes`
copy is never read and causes confusion when external tools (Claude Code) write
fixes there. **Deleted.**

## Verification Commands

```bash
# Check template has horizon in plugins.enabled
python -c "
import yaml
cfg = yaml.safe_load(open(r'$LOCALAPPDATA\hermes\hermes-agent\user-config\config.yaml'))
print('plugins.enabled:', cfg['plugins']['enabled'])
print('mcp_servers keys:', list(cfg.get('mcp_servers', {}).keys()))
"

# Verify no redundant ~/.hermes/plugins/horizon/ exists
ls ~/.hermes/plugins/  # should show only agentmemory

# Verify AppData copy exists (the one Hermes actually scans)
ls $LOCALAPPDATA/hermes/plugins/  # should show agentmemory and horizon
```

## Lesson

When fixing a plugin that "disappears after restart", check **both** configs:
- Runtime: `%LOCALAPPDATA%/hermes/config.yaml`
- Template: `%LOCALAPPDATA%/hermes/hermes-agent/user-config/config.yaml`

Fix both, or the next restart will undo the fix.
