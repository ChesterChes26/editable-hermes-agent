# "Only one version of Outlook" Dialog — Reproduction Evidence

## Triggers

Calling `win32com.client.Dispatch("Outlook.Application")` from Python while
an `OUTLOOK.EXE` process is already running in GUI mode triggers:

> "Sorry, we're having trouble starting Outlook. Only one version of Outlook
> can run at a time. Check to see if another version of Outlook is running,
> or try restarting your computer."

## Verified instance (2026-07-10)

- **Process**: OUTLOOK.EXE (pid 71936) — *separate* from main Outlook pid 71196
- **Window**: "Microsoft Outlook", window_id=2101556, 480×188, at (728, 450)
- **Child elements**:
  - `Button "确定"` (id=2) — the only actionable button
  - `Text "Sorry, we're having trouble starting Outlook..."`
- **Root cause**: `compose.py` called `dispatch_outlook_app(use_getobject=True)`,
  which correctly does NOT fall back to Dispatch. But earlier in the session,
  a manual `win32com.client.Dispatch("Outlook.Application")` call from a
  diagnostic script spawned this orphaned process.

## Why Dispatch fallback is dangerous

1. Dispatch detects OUTLOOK.EXE is already running (GUI mode)
2. Dispatch tries to start a *second* COM server instance
3. Outlook shows modal "Only one version" dialog
4. Dialog blocks until user clicks "确定"
5. Meanwhile, *all subsequent COM calls* (GetObject, etc.) time out
   because the MAPI subsystem is in a conflicted state

## Resolution

- Click `Button "确定"` on the dialog (element_index=0)
- Kill the orphaned OUTLOOK.EXE process (`mcp_cua_driver_kill_app`)
- **Never** use `use_getobject=False` (Dispatch path) when Outlook is
  already running in GUI mode
- The `dispatch_outlook_app` function in `_shared.py` correctly does NOT
  fall back — this is by design
