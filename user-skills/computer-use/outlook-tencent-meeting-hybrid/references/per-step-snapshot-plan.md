# Per-Step Window Screenshots — Implementation Plan

Source: Claude Code plan `C:/Users/chester.chen/.claude/plans/lazy-zooming-quiche.md`

## Architecture

Three new/changed files:

| File | Action | Purpose |
|------|--------|---------|
| `capture_snapshot.py` | **Create** | Standalone `win32gui.PrintWindow` window capture — no cua-driver dependency |
| `report.py` | **Create** (plan says "modify" but file doesn't exist in skill yet) | `print_execution_report()` with snapshot rendering (`📷 file:///...`) |
| `compose.py` | Modify | Add `--snapshot-dir`, auto-capture step 3, `report` subcommand |

## Snapshot Strategy Per Step

| Step | Window Match | Fallback | Critical? |
|------|-------------|----------|-----------|
| 1 (Outlook after dismiss) | `--title-substring "收件箱"` | `--class-name "rctrl_renwnd32"` | Yes |
| 2 (Tencent Meeting dialog) | `--title-substring "Tencent Meeting"` | `--class-name "#32770"` | Yes |
| 3 (Filled meeting form) | `--class-name "rctrl_renwnd32"` (auto via compose.py) | `--title-substring "Meeting"` | Yes |
| 4 (Outlook after send) | `--title-substring "收件箱"` + `--warn-only` | — | No |
| 5 (Calendar view) | `--title-substring "Calendar"` + `--warn-only` | — | No |

## capture_snapshot.py Design

- Uses `win32gui.PrintWindow` + `PW_RENDERFULLCONTENT` with BitBlt fallback
- `--save-to-state --state-key <key>` to register in compose state JSON
- `--warn-only` flag for non-critical steps (exit 0 on failure)
- No cua-driver dependency — works standalone

## State JSON Schema (extended)

```json
{
  "baseline": "<uuid>",
  "to": "...", "start": "...", "end": "...",
  "snapshot_dir": "C:/Users/.../Temp/outlook_meeting_snapshots/<uuid>",
  "snapshots": {
    "step1_main_window": "C:/.../step1_main_window.png",
    "step2_tencent_dialog": "C:/.../step2_tencent_dialog.png",
    "step3_meeting_form": "C:/.../step3_meeting_form.png",
    "step4_after_send": "C:/.../step4_after_send.png",
    "step5_calendar": "C:/.../step5_calendar.png"
  }
}
```

## Report Output Change

Each step line gains a snapshot link:

```
Step 3   COM compose  ✓  --to user@... --start "..." --end "..."
  📷 file:///C:/Users/.../Temp/outlook_meeting_snapshots/<uuid>/step3_meeting_form.png
```

## Error Handling

- All snapshot failures are **non-fatal** — pipeline continues
- Steps 4-5 use `--warn-only` to avoid aborting on transient window states
- Atomic state file writes (temp + rename) prevent corruption

## Plan-to-Reality Gap

The plan says "Modify `report.py`" but `report.py` does not exist in the skill.
It needs to be **created** with `print_execution_report()` as the entry point.
Current report rendering is inline in SKILL.md Step 7 template — that logic should be extracted into `report.py`.
