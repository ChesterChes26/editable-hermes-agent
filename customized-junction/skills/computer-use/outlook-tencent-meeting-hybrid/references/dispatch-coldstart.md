# Dispatch Cold-Start Verification

## Problem

On this machine, Outlook does NOT register in the COM Running Object Table (ROT),
regardless of launch method. Three methods tested: `launch_app(path=OUTLOOK.EXE)`,
manual EXE launch, and `Dispatch("Outlook.Application")` cold-start.
ROT always has 3 system-level GUIDs — never Outlook.

## Discovery

`Explorers.Add(inbox, 0)` creates the `rctrl_renwnd32` window but WITHOUT `WS_VISIBLE`
style bit (`WS=0x6cf0000`). Window exists at the correct screen position with the
correct title, but `IsWindowVisible()` returns 0.

Claude Code's main process has a COM message pump that makes Explorer windows visible
automatically. Hermes subprocesses (`terminal`, `execute_code`) do not have message
pumps. Calling `explorer.Display()` in a Hermes subprocess blocks indefinitely (timeout).

## Fix

`_shared.py::launch_outlook_gui()`:
1. `Dispatch("Outlook.Application")` → COM handle
2. `Explorers.Add(ns.GetDefaultFolder(6), 0)` → creates hidden window
3. `EnumWindows` by PID + class name `rctrl_renwnd32` → find HWND
4. `ShowWindow(hwnd, SW_SHOWNOACTIVATE)` → sets WS_VISIBLE
5. `ShowWindow(hwnd, SW_MAXIMIZE)` → maximizes
6. Returns `(outlook_app, pid, hwnd)` — COM handle passed to compose.py

## Verification

5-round cold-start loop on 2026-07-10:

```
Round 1: PASS — VIS=1 Title='收件箱 - Leon88726@hotmail.com - Outlook'
Round 2: PASS — VIS=1 Title='收件箱 - Leon88726@hotmail.com - Outlook'
Round 3: PASS — VIS=1 Title='收件箱 - Leon88726@hotmail.com - Outlook'
Round 4: PASS — VIS=1 Title='收件箱 - Leon88726@hotmail.com - Outlook'
Round 5: PASS — VIS=1 Title='收件箱 - Leon88726@hotmail.com - Outlook'
```

5/5 passes. Runtime verification confirmed: Dispatch → WS_VISIBLE set → COM MAPI
access OK → Quit clean. `compose_meeting(outlook_app=handle)` passes COM handle
correctly (prints "Using pre-existing COM handle (launch_outlook_gui)").
