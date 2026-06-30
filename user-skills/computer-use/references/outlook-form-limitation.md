# Outlook Meeting Form — cua-driver Limitation & Hybrid Workaround

## Problem

Outlook meeting windows (class `rctrl_renwnd32`, e.g. "chuckGen预定的会议 - Meeting")
consistently fail UIA tree traversal:

```
BuildUpdatedCache failed after 3 attempts: Pattern not found (0x80040201)
```

This is **not** caused by multiple windows. Verified in clean single-window state.
Root cause: `rctrl_renwnd32` does not support `IUIAutomationCacheRequest`.

## Cascading failures without UIA tree

| Failure | Root Cause |
|---|---|
| Can't get element_index for form fields | No UIA tree |
| PostMessage Tab doesn't switch focus | Custom form ignores WM_CHAR Tab |
| PostMessage Alt+S doesn't send | Win32 TranslateAccelerator needs system modifier state |
| Pixel blind-clicking Send | LLM can't see screenshots; 0/12 hit rate |
| bring_to_front fails | Needs UIAccess (cua-driver-uia.exe) |

## Verified workaround: Hybrid CUA + COM

```
CUA UIA:  click Schedule Meeting → Waiting Room → OK      ✓
COM:      Dispatch → Inspectors → AppointmentItem          ✓
          item.RequiredAttendees = "..."                     ✓
          item.Start / item.End = "2026-07-01 08:30/11:30"  ✓
          item.Send()                                        ✓
CUA UIA:  verify in Calendar                                ✓
```

Tool: `outlook_com.py` (131 lines) at `C:/Users/chester.chen/outlook_com.py`

### COM gotchas

- `GetActiveObject("Outlook.Application")` hangs → use `Dispatch()` instead
- `Dispatch()` connects to existing Outlook GUI instance reliably
- Traverse `outlook.Inspectors` to find `AppointmentItem` (Class == 26)
- COM is **Windows-only**; Mac needs AppleScript or Graph API

## What works with CUA UIA

| Window type | UIA tree |
|---|---|
| Outlook main window | ✓ 115-131 elements |
| Tencent Meeting dialog | ✓ 15 elements |
| Activation nag ("Keep using Outlook") | ✓ 9 elements |
| Reminder dialog ("1 Reminder(s)") | ✓ 9 elements |
| Cancel meeting prompt ("取消会议提示") | ✓ 5 elements |
| **Meeting compose window** | **✗ 0x80040201** |

Full verification report: `wiki-next/concepts(概念)/hermes/T2(重要机制)/cua-outlook-hybrid-verification(混合验证).md`
