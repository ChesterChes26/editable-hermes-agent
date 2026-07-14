# Raw COM Workflow (Hermes Pipeline)

When bypassing `compose.py` and using raw `win32com.client.Dispatch` directly, the state file must be manually written before calling `report.py finalize`.

## State File Location

```
%TEMP%\outlook_meeting_compose_state.json
```

Resolved via `_shared.STATE_FILE` (see `scripts/_shared.py` line 13).

## Required JSON Structure

```json
{
  "snapshots": {
    "step1": "absolute/path/to/step1_main_window.png",
    "step2": "absolute/path/to/step2_tencent_dialog.png",
    "step4": "absolute/path/to/step4_sent_items.png",
    "step5": "absolute/path/to/step5_calendar.png"
  },
  "baseline": {
    "input_tokens": 12819,
    "output_tokens": 530,
    "cache_read_tokens": 142464,
    "api_call_count": 3
  },
  "to": "email1@example.com;email2@example.com",
  "start": "2026-07-11 15:00",
  "end": "2026-07-11 16:00",
  "subject": "Meeting Subject",
  "location": "https://meeting.tencent.com/dm/MEETING_ID",
  "meeting_id": "MEETING_ID",
  "compose_args": "COM direct (Hermes pipeline)"
}
```

## Writing the State File

```python
import json, os, tempfile

state = {
    'snapshots': {
        'step1': r'C:\path\to\step1.png',
        'step2': r'C:\path\to\step2.png',
        'step4': r'C:\path\to\step4.png',
        'step5': r'C:\path\to\step5.png',
    },
    'baseline': {
        'input_tokens': 12819,
        'output_tokens': 530,
        'cache_read_tokens': 142464,
        'api_call_count': 3
    },
    'to': 'recipient@example.com',
    'start': '2026-07-11 15:00',
    'end': '2026-07-11 16:00',
    'subject': 'Meeting Subject',
    'location': 'https://meeting.tencent.com/dm/MEETING_ID',
    'meeting_id': 'MEETING_ID',
    'compose_args': 'COM direct (Hermes pipeline)'
}

state_file = os.path.join(tempfile.gettempdir(), 'outlook_meeting_compose_state.json')
with open(state_file, 'w') as f:
    json.dump(state, f)
```

## Raw COM Meeting Composition

```python
import win32com.client
from datetime import datetime

# Connect to running Outlook
outlook = win32com.client.Dispatch('Outlook.Application')

# Find the meeting inspector (created by clicking "Schedule Meeting" in GUI)
meeting_item = None
for i in range(1, outlook.Inspectors.Count + 1):
    insp = outlook.Inspectors.Item(i)
    item = insp.CurrentItem
    if item and hasattr(item, 'Subject') and 'chuckGen' in item.Subject:
        meeting_item = item
        break

if not meeting_item:
    raise RuntimeError('Meeting window not found')

# Set meeting properties
meeting_item.RequiredAttendees = 'email1@example.com;email2@example.com'
meeting_item.Start = datetime(2026, 7, 11, 15, 0, 0)
meeting_item.End = datetime(2026, 7, 11, 16, 0, 0)
meeting_item.Duration = 60

# Save to apply changes
meeting_item.Save()

# Send the meeting
meeting_item.Send()
```

## Pitfall: Time Zone Handling

When setting `Start` and `End` as `datetime` objects, Outlook interprets them in the local time zone. The COM output shows UTC (e.g., `2026-07-11 07:00:00+00:00` for 15:00 UTC+8). This is expected behavior — the meeting appears correctly in the calendar.

## Pitfall: State File Not Auto-Written

`compose.py` automatically writes the state file when invoked. When using raw COM (bypassing `compose.py`), you must manually write the state file before calling `report.py finalize`, otherwise the report fails with:

```
ERROR: Compose state missing required keys: ['baseline', 'to', 'start', 'end']
```

## Workflow: Raw COM Path

1. Click "Schedule Meeting" in Outlook GUI (creates meeting window)
2. Use raw COM to set `RequiredAttendees`, `Start`, `End`, `Duration`
3. Call `meeting_item.Save()` then `meeting_item.Send()`
4. Manually write state JSON to `%TEMP%\outlook_meeting_compose_state.json`
5. Call `report.py finalize`
6. Call `report_html.py --open`

## When to Use Raw COM

- When `compose.py` is unavailable or fails
- When you need fine-grained control over meeting properties
- When debugging COM behavior directly

## When to Use compose.py

- Standard workflow (recommended)
- Automatic state file management
- Automatic snapshot directory handling
