# Office Custom Forms — cua-driver UIA Failure Evidence

## Problem

Outlook meeting invite windows (and potentially other Office custom forms with
`rctrl_renwnd32` window class) return zero elements from `get_window_state`:

```
window_id=X pid=Y elements=0
BuildUpdatedCache failed after 3 attempts: Pattern not found (0x80040201)
```

Root cause: these windows do NOT support `IUIAutomationCacheRequest`, which
cua-driver uses for batch UIA property fetching. There is no fallback to
non-cached UIA traversal.

Reproduced 4 times across 2 sessions (2026-06-30), with 1-window and 2-window
states, fresh Outlook launches — consistent every time.

## What the UIA failure blocks

- `element_index`-based clicks (`click(element=N)`) — no elements, no indices
- `set_value` on form fields — needs element access
- Reading field values via UIA
- Detecting checkbox states (checked/unchecked)

## What still works

| Operation | Method | Verified? |
|---|---|---|
| Pixel click | `click(pid, x, y, window_id)` | ✓ (UIA hit-test may still catch buttons) |
| Text input | `type_text(pid, text, window_id=...)` | ✓ (when window_id specified) |
| Tab navigation | `press_key(pid, "tab", window_id=...)` | ✓ |
| Shift+Tab | `press_key` with `modifiers=["shift"]` | ✓ |
| Ctrl+C/V/A | `hotkey(pid, ["ctrl","c"], window_id=...)` | ✓ (no Alt involved) |
| Clipboard read | `powershell -Command "Get-Clipboard"` | ✓ |
| Vision screenshots | `get_window_state(mode="vision")` | ✓ (screenshot only) |
| Zoom | `zoom(pid, window_id, x1,y1,x2,y2)` | ✓ |

## What does NOT work (and why)

| Operation | Failure mode |
|---|---|
| Alt+S (Send shortcut) | PostMessage doesn't update OS modifier state; `TranslateAccelerator` misses it |
| `bring_to_front` | Windows foreground-lock rejects non-UIAccess process swap |
| Foreground dispatch | Needs `cua-driver-uia` worker (not running on this host) |

## type_text crash root cause

**NOT caused by PostMessage incompatibility with meeting forms.** The crash
in the first attempt was caused by omitting `window_id` when 3+ Outlook
windows existed. Without `window_id`, `type_text` routes to the first
visible window of the PID, which may be a stale/dying window.

Fix: always pass explicit `window_id`:

```
# WRONG — can crash with multiple windows
type_text(pid=41364, text="hello")

# RIGHT — targets the correct window  
type_text(pid=41364, text="hello", window_id=15010582)
```

## Reminder/modal dialog interference

Outlook may pop reminder dialogs (class `#32770`, title `"N Reminder(s)"`)
that block input to other windows. Always `list_windows` after a click to
detect new dialog windows, dismiss them before continuing.

## Session verification

Session 20260630: 4 attempts to use UIA on Outlook meeting window.
All returned 0x80040201. Pixel+keyboard fallback workflow:
successfully filled Required field, set start/end time, copied Location
link via Ctrl+C, failed to pixel-click Send button after 10+ attempts.
Reminder dialog blocked mid-task; dismissed via UIA element click.
