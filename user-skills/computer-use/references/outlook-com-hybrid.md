# Outlook COM Hybrid — Fill Meeting Forms When cua-driver Can't

When cua-driver hits the `rctrl_renwnd32` UIA wall (see SKILL.md pitfall),
fall back to COM automation via `win32com.client`.

## Prerequisite

```bash
pip install pywin32
```

## Verification Script (30 lines)

Run before coding to confirm COM pipeline works on this machine:

```python
import win32com.client

# Dispatch connects to existing Outlook — GetActiveObject may hang
outlook = win32com.client.Dispatch('Outlook.Application')

# Create + delete a test item (verifies write access)
appt = outlook.CreateItem(1)  # 1 = olAppointmentItem
appt.Subject = 'VERIFY-TEST-DELETE-ME'
appt.Start = '2026-07-01 08:30'
appt.End = '2026-07-01 08:35'
appt.Save()
appt.Delete()
print('COM pipeline OK')
```

## The Tool (outlook_com.py)

Three subcommands for the hybrid pipeline:

```
python outlook_com.py compose --to user@example.com --start "2026-07-01 08:30" --end "2026-07-01 11:30"
python outlook_com.py send
python outlook_com.py location
```

### compose — fills the open meeting form

Finds the `ActiveInspector` whose `CurrentItem.Class == 26` (AppointmentItem),
then sets:
- `item.RequiredAttendees` = --to
- `item.Start` = --start
- `item.End` = --end

Preserves the plugin-set `Location` and `Body` (meeting link + agenda).

### send — sends the meeting

Calls `item.Send()` on the current AppointmentItem inspector.

### location — reads the meeting link

Outputs `item.Location` (the Tencent/Zoom/Teams join URL).

## Calendar Verification

```python
outlook = win32com.client.Dispatch('Outlook.Application')
ns = outlook.GetNamespace('MAPI')
cal = ns.GetDefaultFolder(9)  # olFolderCalendar
items = cal.Items
items.Sort('[Start]')
filter = "[Start] >= '2026-07-01 00:00' AND [Start] < '2026-07-02 00:00'"
for item in items.Restrict(filter):
    print(item.Subject, item.Start, item.Location)
```

## COM Gotchas

1. **`GetActiveObject` hangs** when Outlook is running as foreground GUI. Use `Dispatch` instead — it connects to the existing instance.

2. **No inspector = meeting window not open.** The Tencent Meeting plugin must have completed (click OK on the dialog) before `compose` runs. Wait for a cua `list_windows` to confirm the meeting window exists.

3. **Nag dialogs block inspector creation.** The "Keep using Outlook" activation nag can prevent the plugin from spawning the meeting window. Dismiss it first.

4. **Outlook security prompts.** Corporate Outlook may pop a "A program is trying to access Outlook" dialog. This is an environment config issue — check Outlook Trust Center → Programmatic Access settings.

5. **`Dispatch` can timeout** if Outlook is busy. Set a generous timeout (30s) on the first call after plugin interaction.

## Full Pipeline

```
1. cua launch_app → Outlook
2. cua click Schedule Meeting (#22-24, varies by session)
3. cua toggle Enable Waiting Room (#2) → OK (#10)
4. cua list_windows → confirm meeting window exists
5. COM outlook_com.py compose --to ... --start ... --end ...
6. COM outlook_com.py send
7. COM verify calendar (optional)
8. cua screenshot for visual confirmation (optional)
```

## Known Limitation

This hybrid works because the Tencent Meeting plugin creates the AppointmentItem
via COM itself — it sets `Location` and `Body` with the meeting link. We only
append the user-specified fields. A fully manual meeting creation (without the
plugin) would need to set `Location`, `Body`, and the meeting options ourselves,
which is more fragile.
