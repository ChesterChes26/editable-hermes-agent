"""Shared constants and helpers for the Outlook-Tencent-Meeting hybrid pipeline.

Used by compose.py, capture_snapshot.py, and report.py.
"""

import os
import sys
import time
import tempfile

# ── State file (compose params + snapshot paths) ───────────────────────────────

STATE_FILE = os.path.join(tempfile.gettempdir(), "outlook_meeting_compose_state.json")


# ── Meeting ID extraction ──────────────────────────────────────────────────────

def extract_meeting_id_from_body(body):
    """Extract Tencent Meeting ID from body text.

    Matches #TencentMeeting：293-571-983 or #腾讯会议：659-495-443
    (full-width or ASCII colon). Returns the dashed ID string, or empty
    string if not found.
    """
    import re
    if not body:
        return ""
    match = re.search(
        r'#(?:TencentMeeting|腾讯会议)[：:]\s*(\d{3}(?:-\d{3})+)',
        body,
    )
    return match.group(1) if match else ""


# ── COM helpers ────────────────────────────────────────────────────────────────

def dispatch_outlook_app(retries=3, retry_delay=3, use_getobject=False):
    """Connect to Outlook.Application with retry for transient COM errors.

    When use_getobject=True (recommended for Step 3+ when Outlook is known
    to be running): uses GetObject to attach to the existing ROT entry
    without ever trying to start a new instance. This avoids the "Only
    one version of Outlook can run at a time" dialog that Outlook shows
    when Dispatch detects a live process and tries to cold-start anyway.

    Does NOT fall back to Dispatch when GetObject fails — this is
    intentional. Dispatch on an already-running Outlook process triggers
    the "Only one version of Outlook can run at a time" dialog, which
    blocks until the user manually dismisses it.

    When use_getobject=False (Step 0c / Outlook not yet running): uses
    pure Dispatch which can cold-start Outlook if it isn't running yet.
    DO NOT use this when Outlook is already running in GUI mode.

    CO_E_SERVER_EXEC_FAILURE (0x80080005) and MK_E_UNAVAILABLE
    (0x800401E3) errors can occur when the Tencent Meeting plugin is
    still performing MAPI operations (populating the meeting form) or
    when Outlook has not registered its ROT entry.
    The caller should wait longer and retry, or investigate whether
    Outlook is properly registered in the ROT.
    """
    import win32com.client

    if use_getobject:
        # ── GetObject-only path (Step 3+ when Outlook is known to be running) ──
        # Poll the ROT with backoff — the Tencent Meeting plugin may hold the
        # MAPI lock while populating the form, making GetObject fail transiently.
        # Short initial delay + rapid retries with linear backoff gives the
        # plugin time to release the lock without excessive total wait.
        pre_delay = 2
        max_retries = 6
        print(f"Waiting {pre_delay}s for plugin COM operations to settle, then polling ROT...")
        time.sleep(pre_delay)

        for attempt in range(1, max_retries + 1):
            try:
                result = win32com.client.GetObject(None, "Outlook.Application")
                print(f"COM connected via GetObject (attempt {attempt}/{max_retries})")
                return result
            except Exception as e:
                err_msg = str(e)
                if "only one version" in err_msg.lower() or "0x80080005" in err_msg:
                    print(
                        f"COM GetObject attempt {attempt}/{max_retries}: "
                        f"MAPI conflict ({e})\n"
                        f"  Retrying in {attempt}s...",
                        file=sys.stderr,
                    )
                else:
                    print(
                        f"COM GetObject attempt {attempt}/{max_retries}: {e}",
                        file=sys.stderr,
                    )
                    if attempt < max_retries:
                        print(f"  Retrying in {attempt}s...", file=sys.stderr)
            if attempt < max_retries:
                time.sleep(attempt)  # linear backoff: 1s, 2s, 3s, 4s, 5s, 6s

        raise RuntimeError(
            f"GetObject failed after {max_retries} attempts — Outlook ROT entry "
            f"persistently unavailable. The Tencent Meeting plugin may be holding "
            f"the MAPI subsystem lock. Dismiss any Outlook popups and retry."
        )

    # ── Legacy Dispatch-only path (Step 0c, Outlook may not be running yet) ──
    for attempt in range(1, retries + 1):
        try:
            return win32com.client.Dispatch("Outlook.Application")
        except Exception as e:
            if attempt < retries:
                print(
                    f"COM Dispatch attempt {attempt}/{retries} failed: {e}\n"
                    f"  Retrying in {retry_delay}s (plugin may still be initialising)...",
                    file=sys.stderr,
                )
                time.sleep(retry_delay)
            else:
                print(
                    f"COM Dispatch failed after {retries} attempts: {e}",
                    file=sys.stderr,
                )
                raise


# ── GUI launch (Hermes) ─────────────────────────────────────────────────────

def launch_outlook_gui():
    """Launch Outlook via COM Dispatch and ensure the main window is visible.

    Returns (outlook_app, pid, hwnd).

    Designed for Hermes environments where subprocesses lack a COM message
    pump. Claude Code's main process has a message pump that makes Explorer
    windows inherit WS_VISIBLE automatically; Hermes subprocesses do not,
    so we explicitly call ShowWindow after Explorers.Add.

    Call this ONCE at pipeline startup.  The returned outlook_app handle
    is passed directly to compose.py — no GetObject / ROT needed.
    """
    import win32com.client, win32gui, win32process, win32con
    import subprocess as _sp

    outlook = win32com.client.Dispatch("Outlook.Application")
    ns = outlook.GetNamespace("MAPI")
    inbox = ns.GetDefaultFolder(6)  # olFolderInbox

    # Check if an Explorer already exists (auto-created on some machines)
    if outlook.Explorers.Count == 0:
        explorer = outlook.Explorers.Add(inbox, 0)
    else:
        explorer = outlook.Explorers.Item(1)

    time.sleep(2)  # let Outlook finish initialising the window

    # Get PID for window enumeration
    pid = int(_sp.check_output(
        ['powershell', '-Command', '(Get-Process outlook).Id'],
        timeout=5
    ).decode().strip())

    # Find and show the rctrl_renwnd32 window
    hwnd_ref = [None]

    def _enum_cb(h, _):
        _, wp = win32process.GetWindowThreadProcessId(h)
        if str(wp) == str(pid) and _class_name(h) == 'rctrl_renwnd32':
            hwnd_ref[0] = h

    win32gui.EnumWindows(_enum_cb, None)
    hwnd = hwnd_ref[0]

    if hwnd:
        # SW_SHOWNOACTIVATE first (sets WS_VISIBLE without stealing focus),
        # then maximize to fill the screen
        win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
        time.sleep(0.5)
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        print(f"Outlook GUI visible: HWND={hwnd}  PID={pid}")
    else:
        print("WARNING: rctrl_renwnd32 not found after Explorers.Add",
              file=sys.stderr)

    return outlook, pid, hwnd


def _class_name(hwnd):
    """Return window class name (extracted for picklability)."""
    import win32gui
    return win32gui.GetClassName(hwnd)