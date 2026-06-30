"""
Outlook COM meeting compose tool — fills and sends an AppointmentItem
created by the Tencent Meeting Outlook plugin.

Used in hybrid CUA + COM pipeline:
  cua-driver:  clicks Schedule Meeting, handles Tencent dialog, OK
  COM:         fills AppointmentItem fields, calls Send()

Usage:
  python outlook_com.py compose \\
      --to user@example.com \\
      --start "2026-07-01 08:30" \\
      --end "2026-07-01 11:30"

  python outlook_com.py send
  python outlook_com.py location
"""
import sys
import argparse
import win32com.client


def find_meeting_inspector(outlook):
    """Find the ActiveInspector whose CurrentItem is an AppointmentItem."""
    for ins in outlook.Inspectors:
        try:
            item = ins.CurrentItem
            if item.Class == 26:  # olAppointmentItem
                return ins, item
        except Exception:
            continue
    return None, None


def compose_meeting(to, subject, start_str, end_str):
    outlook = win32com.client.Dispatch("Outlook.Application")
    ins, item = find_meeting_inspector(outlook)
    if item is None:
        print("ERROR: No open AppointmentItem inspector found.", file=sys.stderr)
        sys.exit(1)

    print(f"Found meeting: Subject={item.Subject}")
    print(f"  Plugin-set Location: {item.Location}")

    if to:
        item.RequiredAttendees = to
        print(f"  -> RequiredAttendees := {to}")
    if subject:
        item.Subject = subject
    if start_str:
        item.Start = start_str
        print(f"  -> Start := {start_str}")
    if end_str:
        item.End = end_str
        print(f"  -> End := {end_str}")

    item.Save()
    location = item.Location
    print(f"\n  Location: {location}")
    return item, location


def send_meeting():
    outlook = win32com.client.Dispatch("Outlook.Application")
    ins, item = find_meeting_inspector(outlook)
    if item is None:
        print("ERROR: No open AppointmentItem to send.", file=sys.stderr)
        sys.exit(1)
    item.Send()
    print(f"Meeting '{item.Subject}' sent successfully.")
    return item.Location


def get_location():
    outlook = win32com.client.Dispatch("Outlook.Application")
    ins, item = find_meeting_inspector(outlook)
    if item is None:
        print("ERROR: No open AppointmentItem.", file=sys.stderr)
        sys.exit(1)
    print(item.Location)
    return item.Location


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compose")
    c.add_argument("--to", default="")
    c.add_argument("--subject", default="")
    c.add_argument("--start", default="")
    c.add_argument("--end", default="")
    sub.add_parser("send")
    sub.add_parser("location")
    args = parser.parse_args()

    if args.cmd == "compose":
        compose_meeting(args.to, args.subject, args.start, args.end)
    elif args.cmd == "send":
        send_meeting()
    elif args.cmd == "location":
        get_location()


if __name__ == "__main__":
    main()
