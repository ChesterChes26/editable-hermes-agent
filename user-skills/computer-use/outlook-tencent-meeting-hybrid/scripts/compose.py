"""
Outlook COM meeting compose tool — fills (compose subcommand) then sends (send subcommand) an AppointmentItem
that was created by the Tencent Meeting Outlook plugin.

Used in hybrid CUA + COM pipeline:
  cua-driver:  clicks Schedule Meeting → handles Tencent dialog → OK
  COM:         fills AppointmentItem fields → calls Send()
  cua-driver:  verifies in Calendar window

Token reporting is built-in:
  - compose subcommand auto-captures token baseline
  - send subcommand sends the meeting (report deferred to report.py finalize)

Usage:
  python compose.py compose \\
      --to user@example.com \\
      --start "2026-07-01 08:30" \\
      --end "2026-07-01 11:30"

  python compose.py send
"""
import sys
import os
import json
import argparse
import time
import tempfile
import win32com.client
from datetime import datetime
from _shared import STATE_FILE, dispatch_outlook_app, extract_meeting_id_from_body

# Allow importing from the same scripts directory (for report.py helpers)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from report import (
    get_session_jsonl_path,
    read_jsonl,
)

# Import capture functions for Step 3 auto-screenshot
try:
    from capture_snapshot import find_windows_by_class, capture_window
    _CAPTURE_AVAILABLE = True
except ImportError:
    _CAPTURE_AVAILABLE = False


def save_compose_state(baseline_uuid, to, start_str, end_str, snapshots=None, subject="", meeting_id=""):
    """Save meeting params and optional snapshot paths for later report generation.

    Reads existing state file first to preserve snapshot paths written earlier
    by capture_snapshot.py --update-state-key (steps 1, 2, 4, 5), then merges.

    Uses atomic write (temp file + rename) to prevent concurrent corruption.
    """
    # Read existing state to preserve snapshot paths written by
    # capture_snapshot.py --update-state-key (called before/after compose)
    existing = {}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    # Preserve started_at from existing state (set by capture_snapshot.py
    # on first step capture) — only set it here if not already present
    state = {
        "baseline": baseline_uuid,
        "to": to,
        "start": start_str,
        "end": end_str,
        "subject": subject,
    }
    if "started_at" not in existing:
        state["started_at"] = datetime.now().isoformat()

    # Store meeting_id extracted from body at compose time
    # (avoids re-fetching item.Body during report generation)
    if meeting_id:
        state["meeting_id"] = meeting_id

    # Merge snapshots: preserve existing, add/overwrite with new
    merged_snapshots = existing.get("snapshots", {})
    if snapshots:
        merged_snapshots.update(snapshots)
    if merged_snapshots:
        state["snapshots"] = merged_snapshots

    # Merge step_times: preserve existing, record new timestamps
    merged_times = existing.get("step_times", {})
    if snapshots:
        now_iso = datetime.now().isoformat()
        for key in snapshots:
            if key not in merged_times:
                merged_times[key] = now_iso
    if merged_times:
        state["step_times"] = merged_times

    # Atomic write: temp file + rename
    tmp_path = STATE_FILE + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
        os.replace(tmp_path, STATE_FILE)
    except Exception:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise
    print(f"[report] Baseline captured: {baseline_uuid}")



# ── Baseline capture ────────────────────────────────────────────────────────

def capture_baseline():
    """Capture the token baseline uuid before starting the meeting task.

    Returns the uuid of the most recent assistant message in the current
    Claude Code session JSONL. Falls back to Hermes SQLite baseline.
    """
    # ── Hermes path: use SQLite baseline ──
    if not os.environ.get("CLAUDE_CODE_SESSION_ID"):
        try:
            baseline_file = os.path.join(os.environ.get("TEMP", ""), "hermes_tokens_baseline.txt")
            if os.path.exists(baseline_file):
                with open(baseline_file, "r") as f:
                    content = f.read().strip()
                # Use the Hermes baseline token string instead of UUID
                print(f"[baseline] Using Hermes SQLite baseline: {content}")
                return content
        except Exception as e:
            print(f"WARNING: Failed to read Hermes baseline: {e}", file=sys.stderr)
        print("WARNING: No Hermes baseline found, continuing without baseline", file=sys.stderr)
        return "hermes_nobaseline|0|0|0|0"

    # ── Claude Code path ──
    jsonl_path = get_session_jsonl_path()
    lines = read_jsonl(jsonl_path)
    for line in reversed(lines):
        if line.get("type") == "assistant":
            return line["uuid"]
    print("ERROR: No assistant message found in session.", file=sys.stderr)
    return None


def _normalize_attendees(raw):
    """Normalize attendee email string to Outlook COM format.

    Outlook COM requires semicolons as the separator for multiple attendees.
    This function:
      1. Replaces commas with semicolons
      2. Splits on semicolons, strips whitespace per entry
      3. Deduplicates (case-insensitive)
      4. Returns normalized string and recipient count

    Examples:
      "a@b.com, c@d.com" → ("a@b.com; c@d.com", 2)
      "a@b.com; c@d.com" → ("a@b.com; c@d.com", 2)
      "a@b.com"          → ("a@b.com", 1)
    """
    import re
    if not raw or not raw.strip():
        return "", 0
    raw = raw.strip().replace(",", ";")
    entries = [e.strip() for e in raw.split(";") if e.strip()]
    seen = set()
    unique = []
    for e in entries:
        low = e.lower()
        if low not in seen:
            seen.add(low)
            unique.append(e)
    return "; ".join(unique), len(unique)


# ── Meeting operations ──────────────────────────────────────────────────────

def find_meeting_inspector(outlook, retries=10, delay=0.5):
    """Find the ActiveInspector whose CurrentItem is an AppointmentItem.

    Retries with backoff because the AppointmentItem Inspector (rctrl_renwnd32)
    may not be created instantly after the Tencent Meeting dialog OK is clicked.
    """
    last_error = None
    for attempt in range(1, retries + 1):
        for ins in outlook.Inspectors:
            try:
                item = ins.CurrentItem
                if item.Class == 26:  # olAppointmentItem
                    if attempt > 1:
                        print(f"[retry] Inspector found on attempt {attempt}")
                    return ins, item
            except Exception as exc:
                last_error = exc
                continue
        if attempt < retries:
            time.sleep(delay * attempt)  # linear backoff: 0.5s, 1.0s, 1.5s...
    print(f"ERROR: No AppointmentItem inspector found after {retries} attempts.",
          file=sys.stderr)
    if last_error:
        print(f"  Last COM error: {last_error}", file=sys.stderr)
    return None, None


def translate_body_to_en(body):
    """Translate Tencent Meeting Chinese body template to English.

    Uses regex substitution for known template patterns.
    The Tencent Meeting plugin generates a fixed Chinese template;
    this function replaces known Chinese phrases with English equivalents.
    """
    import re

    translations = [
        # Common patterns in Tencent Meeting body text
        (r"邀请您参加腾讯会议", "invites you to a Tencent Meeting"),
        (r"点击链接入会，或添加至会议列表：", "Click the link to join, or add to your meeting list:"),
        (r"点击链接入会或添加至会议列表：", "Click the link to join, or add to your meeting list:"),
        (r"#腾讯会议：", "#Tencent Meeting: "),
        (r"#腾讯会议: ", "#Tencent Meeting: "),
        (r"\n\n+", "\n\n"),  # normalize multiple blank lines
    ]

    result = body
    for pattern, replacement in translations:
        result = re.sub(pattern, replacement, result)
    return result


def compose_meeting(to, subject, start_str, end_str, snapshot_dir=None, translate_body=False, optional_to="", outlook_app=None):
    """Fill the open AppointmentItem fields via COM.

    Also auto-captures the token baseline and saves compose state
    so the later send step can generate the execution report.

    If snapshot_dir is provided, captures a screenshot of the meeting
    form window (Step 3) after fields are filled and saved.

    Args:
        outlook_app: Optional pre-existing Outlook.Application COM handle.
            When provided, skips dispatch_outlook_app (no GetObject/ROT).
            Intended for Hermes pipelines that use launch_outlook_gui().
    """
    # ── Auto-capture baseline ──
    baseline_uuid = capture_baseline()

    # Outlook connection: prefer passed-in handle, fall back to GetObject
    if outlook_app is not None:
        outlook = outlook_app
        print("Using pre-existing COM handle (launch_outlook_gui)")
    else:
        outlook = dispatch_outlook_app(use_getobject=True)
    ins, item = find_meeting_inspector(outlook)
    if item is None:
        print("ERROR: No open AppointmentItem inspector found.", file=sys.stderr)
        sys.exit(1)

    print(f"Found meeting: Subject={item.Subject}")
    print(f"  Plugin-set Location: {item.Location}")
    body_text = str(item.Body)
    print(f"  Plugin-set Body (first 200): {body_text[:200]}")
    meeting_id = extract_meeting_id_from_body(body_text)
    if meeting_id:
        print(f"  Meeting ID: {meeting_id}")

    if to:
        to_normalized, count = _normalize_attendees(to)
        item.RequiredAttendees = to_normalized
        print(f"  → RequiredAttendees := {to_normalized}  ({count} recipient{'s' if count != 1 else ''})")
    if optional_to:
        opt_normalized, opt_count = _normalize_attendees(optional_to)
        item.OptionalAttendees = opt_normalized
        print(f"  → OptionalAttendees := {opt_normalized}  ({opt_count} recipient{'s' if opt_count != 1 else ''})")
    if subject:
        item.Subject = subject
    if start_str:
        item.Start = start_str
        print(f"  → Start := {start_str}")
    if end_str:
        item.End = end_str
        print(f"  → End := {end_str}")

    item.Save()
    location = item.Location

    # ── Optional: translate body from Chinese to English ──
    if translate_body:
        original_body = str(item.Body)
        translated = translate_body_to_en(original_body)
        if translated != original_body:
            item.Body = translated
            item.Save()
            print(f"  Body translated to English")
        else:
            print(f"  Body already English (no translation needed)")

    print(f"\n  Location (meeting link): {location}")
    print(f"  Ready to Send. EntryID: {item.EntryID[:40]}...")

    # ── Step 3 snapshot: capture the filled meeting form ──
    snapshots = {}
    if snapshot_dir and _CAPTURE_AVAILABLE:
        try:
            os.makedirs(snapshot_dir, exist_ok=True)
            output_path = os.path.join(snapshot_dir, "step3_meeting_form.png")
            # Meeting form window uses class rctrl_renwnd32
            matches = find_windows_by_class("rctrl_renwnd32")
            if matches:
                hwnd, title = matches[0]
                if capture_window(hwnd, output_path):
                    snapshots["step3"] = os.path.abspath(output_path)
                    print(f"[snapshot] Step 3 captured → {snapshots['step3']}")
                else:
                    print("WARNING: Step 3 snapshot capture failed (non-fatal).",
                          file=sys.stderr)
            else:
                print("WARNING: Step 3 snapshot: no rctrl_renwnd32 window found.",
                      file=sys.stderr)
        except Exception as e:
            print(f"WARNING: Step 3 snapshot error (non-fatal): {e}",
                  file=sys.stderr)
    elif snapshot_dir and not _CAPTURE_AVAILABLE:
        print("WARNING: capture_snapshot module not available, skipping Step 3 screenshot.",
              file=sys.stderr)

    # Save compose state (with snapshots if any)
    if baseline_uuid:
        save_compose_state(baseline_uuid, to, start_str, end_str,
                           snapshots if snapshots else None, subject,
                           meeting_id=meeting_id)

    return item, location


def send_meeting(outlook_app=None):
    """Send the open AppointmentItem via COM.

    Does NOT generate the execution report — that is deferred to
    report.py finalize (called after all step snapshots are captured).

    Args:
        outlook_app: Optional pre-existing Outlook.Application COM handle.
    """
    if outlook_app is not None:
        outlook = outlook_app
    else:
        outlook = dispatch_outlook_app(use_getobject=True)
    ins, item = find_meeting_inspector(outlook)
    if item is None:
        print("ERROR: No open AppointmentItem to send.", file=sys.stderr)
        sys.exit(1)
    item.Send()
    print(f"Meeting '{item.Subject}' sent successfully.")
    print(f"Location: {item.Location}")

    return item.Location


def get_location(outlook_app=None):
    """Read Location from the open AppointmentItem.

    Args:
        outlook_app: Optional pre-existing Outlook.Application COM handle.
    """
    if outlook_app is not None:
        outlook = outlook_app
    else:
        outlook = dispatch_outlook_app(use_getobject=True)
    ins, item = find_meeting_inspector(outlook)
    if item is None:
        print("ERROR: No open AppointmentItem.", file=sys.stderr)
        sys.exit(1)
    print(item.Location)
    return item.Location


# ── UTF-8 stdout setup ──────────────────────────────────────────────────────

def setup_utf8_stdout():
    """Force UTF-8 output on Windows to avoid GBK encoding errors."""
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ── main ────────────────────────────────────────────────────────────────────

def main():
    setup_utf8_stdout()
    parser = argparse.ArgumentParser(description="Outlook meeting COM compose tool")
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compose", help="Fill meeting fields (don't send)")
    c.add_argument("--to", default="")
    c.add_argument("--optional-to", default="",
                   help="Optional attendees (semicolon-separated)")
    c.add_argument("--subject", default="")
    c.add_argument("--start", default="")
    c.add_argument("--end", default="")
    c.add_argument("--snapshot-dir", default=None,
                   help="Directory for Step 3 meeting form screenshot")
    c.add_argument("--translate-body", action="store_true", default=False,
                   help="Translate meeting body from Chinese to English")
    sub.add_parser("send", help="Send the open meeting")
    sub.add_parser("location", help="Read Location from open meeting")
    args = parser.parse_args()
    if args.cmd == "compose":
        compose_meeting(args.to, args.subject, args.start, args.end,
                        snapshot_dir=args.snapshot_dir,
                        translate_body=args.translate_body,
                        optional_to=args.optional_to)
    elif args.cmd == "send":
        send_meeting()
    elif args.cmd == "location":
        get_location()


if __name__ == "__main__":
    main()
