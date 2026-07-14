"""
Standalone window screenshot tool using PrintWindow API.

Captures a specified window by title substring or class name,
saves as PNG. Designed for background/occluded windows — uses
PrintWindow + PW_RENDERFULLCONTENT just like cua-driver's
get_window_state.  As long as the window is not minimized
(SW_SHOWNOACTIVATE is fine), the capture is reliable.

Optionally updates the compose state JSON so screenshot paths
are available to the execution report (--update-state-key).

Usage:
  # Step 1/4/5: capture Outlook main window (use "Outlook" for locale-agnostic matching)
  # Chinese Windows uses "收件箱"/"日历", English uses "Inbox"/"Calendar"
  python capture_snapshot.py --title-substring "Outlook" --output step1_main.png

  # Step 2: capture Tencent Meeting plugin dialog
  python capture_snapshot.py --title-substring "Tencent Meeting" --output step2_dialog.png

  # Step 3: captured internally by compose.py (not called directly)

  # Step 4/5: warn-only — don't fail if window not found
  python capture_snapshot.py --title-substring "Outlook" --output step5_cal.png --warn-only

  # With state update:
  python capture_snapshot.py --title-substring "Outlook" --output step1.png --update-state-key step1
"""
import sys
import os
import json
import time
import argparse
import ctypes
import ctypes.wintypes
import tempfile
from _shared import STATE_FILE


# ── DPI awareness ─────────────────────────────────────────────────────────────
# Without this, PrintWindow captures at logical (scaled) resolution on high-DPI
# displays — a 1920px window becomes a 960px screenshot on 200% scaling.
# Each tier checks the return value explicitly because ctypes.windll does NOT
# raise on HRESULT failures (E_ACCESSDENIED if DPI was already set, etc.).
def _set_dpi_awareness():
    DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
    PROCESS_PER_MONITOR_DPI_AWARE = 2

    # Windows 10 1703+: Per-Monitor V2 (preferred, handles mixed-DPI best)
    if hasattr(ctypes.windll.user32, "SetProcessDpiAwarenessContext"):
        result = ctypes.windll.user32.SetProcessDpiAwarenessContext(
            DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
        )
        if result:  # non-zero = success (returns old context handle)
            return

    # Windows 8.1+: Per-Monitor DPI Aware
    if hasattr(ctypes.windll.shcore, "SetProcessDpiAwareness"):
        hr = ctypes.windll.shcore.SetProcessDpiAwareness(
            PROCESS_PER_MONITOR_DPI_AWARE
        )
        if hr == 0:  # S_OK
            return
        # hr != 0 → E_ACCESSDENIED (already set) or E_INVALIDARG — drop to fallback

    # Windows Vista+: Legacy System DPI Aware (last resort)
    if hasattr(ctypes.windll.user32, "SetProcessDPIAware"):
        result = ctypes.windll.user32.SetProcessDPIAware()
        if result:  # non-zero BOOL = success
            return

_set_dpi_awareness()


def update_state_snapshot(key, path):
    """Atomically write a snapshot path into the compose state JSON.

    Uses temp-file + rename to prevent concurrent corruption.
    Creates the state file with minimal structure if it doesn't exist.
    Also records a timestamp so per-step durations can be calculated.
    """
    from datetime import datetime

    # Read existing state (or create empty)
    state = {}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
        except json.JSONDecodeError:
            backup = STATE_FILE + ".corrupted"
            print(f"WARNING: State file corrupted, backing up to {backup}",
                  file=sys.stderr)
            try:
                os.replace(STATE_FILE, backup)
            except OSError:
                print(f"WARNING: Could not back up corrupted state file.",
                      file=sys.stderr)
            state = {}
        except IOError:
            state = {}

    # Ensure snapshots dict exists
    if "snapshots" not in state:
        state["snapshots"] = {}
    state["snapshots"][key] = path

    # Record step timestamp for per-step duration calculation
    if "step_times" not in state:
        state["step_times"] = {}
    now_iso = datetime.now().isoformat()
    state["step_times"][key] = now_iso

    # Set started_at on first step capture (ensures duration calculation
    # starts from the true beginning, not from compose.py's later invocation)
    if "started_at" not in state:
        state["started_at"] = now_iso

    # Atomic write: temp file + rename
    tmp_path = STATE_FILE + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
        os.replace(tmp_path, STATE_FILE)
    except Exception:
        # Clean up temp file on failure
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


# ── Window finding ───────────────────────────────────────────────────────────

def find_windows_by_title(title_substring, pid=None):
    """Find all visible top-level windows whose title contains the substring.

    If pid is provided, only windows belonging to that process are returned.
    """
    try:
        import win32gui
        import win32process
    except ImportError:
        print("ERROR: pywin32 is required. Install with: pip install pywin32",
              file=sys.stderr)
        sys.exit(1)

    result = []

    def callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd) and not _is_window_minimized(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title_substring.lower() in title.lower():
                if pid is not None:
                    _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                    if found_pid != pid:
                        return True
                windows.append((hwnd, title))
        return True

    win32gui.EnumWindows(callback, result)
    return result


def find_windows_by_class(class_name, pid=None):
    """Find all visible top-level windows with the given class name.

    If pid is provided, only windows belonging to that process are returned.
    """
    try:
        import win32gui
        import win32process
    except ImportError:
        print("ERROR: pywin32 is required. Install with: pip install pywin32",
              file=sys.stderr)
        sys.exit(1)

    result = []

    def callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd) and not _is_window_minimized(hwnd):
            cls = win32gui.GetClassName(hwnd)
            if cls == class_name:
                if pid is not None:
                    _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                    if found_pid != pid:
                        return True
                title = win32gui.GetWindowText(hwnd)
                windows.append((hwnd, title))
        return True

    win32gui.EnumWindows(callback, result)
    return result


def prefer_window_by_subtitle(matches, prefer_substring):
    """Given a list of (hwnd, title) tuples, return the one whose title
    contains prefer_substring (case-insensitive).

    If no match contains prefer_substring, falls back to the first match
    with a warning to stderr.
    """
    if not prefer_substring or len(matches) <= 1:
        return matches[0]
    prefer_lower = prefer_substring.lower()
    for hwnd, title in matches:
        if prefer_lower in title.lower():
            return (hwnd, title)
    print(
        f"WARNING: --prefer-substring '{prefer_substring}' did not match "
        f"any window title among {len(matches)} candidates. "
        f"Using first match: '{matches[0][1]}'.",
        file=sys.stderr,
    )
    return matches[0]


# ── Window capture ───────────────────────────────────────────────────────────

def _is_window_minimized(hwnd):
    """Check if a window is minimized (iconic)."""
    try:
        import win32gui
        return win32gui.IsIconic(hwnd)
    except Exception:
        return False


def capture_window(hwnd, output_path):
    """Capture a window using PrintWindow + PW_RENDERFULLCONTENT.

    Uses the same API chain as cua-driver's get_window_state:
      1. PrintWindow(hwnd, dc, PW_RENDERFULLCONTENT)  — primary path
      2. PrintWindow(hwnd, dc, 0)                     — fallback

    Returns True on success, False on failure.
    """
    try:
        import win32gui
        import win32ui
        import win32con
    except ImportError:
        print("ERROR: pywin32 is required. Install with: pip install pywin32",
              file=sys.stderr)
        sys.exit(1)

    try:
        from PIL import Image
    except ImportError:
        print("ERROR: Pillow is required. Install with: pip install Pillow",
              file=sys.stderr)
        sys.exit(1)

    # Check minimized — PrintWindow doesn't work on minimized windows
    if _is_window_minimized(hwnd):
        print(f"WARNING: Window {hwnd} is minimized, cannot capture.",
              file=sys.stderr)
        return False

    # Get window dimensions
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width = right - left
    height = bottom - top

    if width <= 0 or height <= 0:
        print(f"ERROR: Window {hwnd} has invalid dimensions: {width}x{height}",
              file=sys.stderr)
        return False

    # Create device contexts
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()

    # Create compatible bitmap
    save_bitmap = win32ui.CreateBitmap()
    save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
    save_dc.SelectObject(save_bitmap)

    success = False
    try:
        # Primary: PrintWindow with PW_RENDERFULLCONTENT (0x2)
        # This flag tells Windows to render the full client area even for
        # DirectComposition/WinRT-backed windows, and works on occluded windows.
        PW_RENDERFULLCONTENT = 0x00000002
        result = ctypes.windll.user32.PrintWindow(
            ctypes.wintypes.HWND(hwnd),
            save_dc.GetSafeHdc(),
            PW_RENDERFULLCONTENT
        )

        if result == 0:
            # Fallback: try without PW_RENDERFULLCONTENT
            result = ctypes.windll.user32.PrintWindow(
                ctypes.wintypes.HWND(hwnd),
                save_dc.GetSafeHdc(),
                0
            )

        if result == 0:
            err = ctypes.get_last_error()
            print(f"WARNING: PrintWindow failed for hwnd {hwnd} (error {err}).",
                  file=sys.stderr)
            # Continue anyway — bitmap may be partially rendered
            # (some windows still produce usable output despite 0 return)

        # Convert to PIL Image
        bmpinfo = save_bitmap.GetInfo()
        bmpstr = save_bitmap.GetBitmapBits(True)
        img = Image.frombuffer(
            'RGB',
            (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
            bmpstr, 'raw', 'BGRX', 0, 1
        )

        # Ensure output directory exists
        out_dir = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(out_dir, exist_ok=True)

        img.save(output_path, 'PNG')
        success = True

    except Exception as e:
        print(f"ERROR: Capture failed for hwnd {hwnd}: {e}", file=sys.stderr)

    finally:
        # Cleanup GDI resources
        # Order matters: deselect bitmap → delete compatible DC →
        # detach window DC from MFC wrapper → release window DC
        try:
            save_dc.DeleteDC()
        except Exception:
            pass
        try:
            # Detach the raw handle from mfc_dc so its destructor
            # won't call ::DeleteDC on a window-DC handle (which must
            # be released via ReleaseDC, not deleted).
            mfc_dc.Detach()
        except Exception:
            pass
        try:
            win32gui.ReleaseDC(hwnd, hwnd_dc)
        except Exception:
            pass
        try:
            win32gui.DeleteObject(save_bitmap.GetHandle())
        except Exception:
            pass

    return success


# ── Main entry point ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Capture a window screenshot using PrintWindow API"
    )

    # Window matching (at least one of --title-substring or --class-name required)
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument(
        "--title-substring", type=str, default=None,
        help="Match window by title substring (case-insensitive)"
    )
    group.add_argument(
        "--class-name", type=str, default=None,
        help="Match window by exact class name"
    )

    # Optional pid filter (avoids false positives from unrelated apps)
    parser.add_argument(
        "--pid", type=int, default=None,
        help="Only match windows belonging to this process ID"
    )

    # Output
    parser.add_argument(
        "--output", type=str, required=True,
        help="Output PNG file path"
    )

    # Error handling
    parser.add_argument(
        "--warn-only", action="store_true",
        help="If window not found or capture fails, print warning and exit 0"
    )

    # State integration
    parser.add_argument(
        "--update-state-key", type=str, default=None,
        help="Update compose state JSON with snapshot path under this key "
             "(e.g. 'step1', 'step2', 'step4', 'step5')"
    )

    # Pick first match (default) vs. all matches
    parser.add_argument(
        "--all", action="store_true",
        help="Capture all matching windows (numbered suffix added to output)"
    )

    # Disambiguation (when multiple windows match)
    parser.add_argument(
        "--prefer-substring", type=str, default=None,
        help="When multiple windows match --title-substring, prefer the one "
             "whose title also contains this substring (case-insensitive). "
             "Falls back to first match with a warning if none match. "
             "Example: --title-substring 'Outlook' --prefer-substring 'Calendar'"
    )

    # Pre-capture delay
    parser.add_argument(
        "--delay", type=int, default=0,
        help="Pre-capture delay in milliseconds (for UI settle after navigation)"
    )

    # Post-capture validation
    parser.add_argument(
        "--min-width", type=int, default=100,
        help="Minimum expected width of the captured image (default: 100)"
    )
    parser.add_argument(
        "--min-height", type=int, default=100,
        help="Minimum expected height of the captured image (default: 100)"
    )

    args = parser.parse_args()

    # Validate: at least one matching criterion required
    if not args.title_substring and not args.class_name:
        print("ERROR: Must specify --title-substring or --class-name.",
              file=sys.stderr)
        sys.exit(1)

    # Find matching windows
    if args.title_substring:
        matches = find_windows_by_title(args.title_substring, pid=args.pid)
    else:
        matches = find_windows_by_class(args.class_name, pid=args.pid)

    if not matches:
        msg = f"No visible window found matching "
        if args.title_substring:
            msg += f'title "{args.title_substring}"'
        else:
            msg += f'class "{args.class_name}"'
        if args.warn_only:
            print(f"WARNING: {msg}. Skipping.", file=sys.stderr)
            sys.exit(0)
        else:
            print(f"ERROR: {msg}.", file=sys.stderr)
            sys.exit(1)

    # Capture
    if args.all:
        # Capture all matching windows with numbered suffix
        captured = []
        for i, (hwnd, title) in enumerate(matches):
            base, ext = os.path.splitext(args.output)
            if len(matches) > 1:
                out = f"{base}_{i + 1}{ext}"
            else:
                out = args.output
            if capture_window(hwnd, out):
                captured.append(out)
                print(f"Captured [{title}] → {out}")
        if not captured and not args.warn_only:
            sys.exit(1)
        # For state update with --all, update with the first capture
        if captured and args.update_state_key:
            update_state_snapshot(args.update_state_key, captured[0])
            print(f"[state] snapshots.{args.update_state_key} = {captured[0]}")
    else:
        # Apply prefer-substring disambiguation
        if args.prefer_substring and len(matches) > 1:
            print(
                f"INFO: {len(matches)} matching windows; applying "
                f"--prefer-substring '{args.prefer_substring}' for disambiguation.",
                file=sys.stderr,
            )
        hwnd, title = prefer_window_by_subtitle(matches, args.prefer_substring)

        if len(matches) > 1 and not args.prefer_substring:
            print(f"INFO: {len(matches)} matching windows found, using first: "
                  f"\"{title}\" (hwnd={hwnd})", file=sys.stderr)

        # Apply pre-capture delay if specified
        if args.delay and args.delay > 0:
            delay_sec = args.delay / 1000.0
            print(
                f"INFO: Waiting {delay_sec:.1f}s for UI settle...",
                file=sys.stderr,
            )
            time.sleep(delay_sec)

        if capture_window(hwnd, args.output):
            abs_path = os.path.abspath(args.output)

            # Post-capture size validation
            try:
                from PIL import Image
                img = Image.open(abs_path)
                if img.width < args.min_width or img.height < args.min_height:
                    msg = (f"Captured image too small: {img.width}x{img.height} "
                           f"(minimum: {args.min_width}x{args.min_height})")
                    if args.warn_only:
                        print(f"WARNING: {msg}", file=sys.stderr)
                    else:
                        print(f"ERROR: {msg}", file=sys.stderr)
                        sys.exit(1)
            except Exception as e:
                print(f"WARNING: Could not validate captured image: {e}",
                      file=sys.stderr)

            print(abs_path)
            if args.update_state_key:
                update_state_snapshot(args.update_state_key, abs_path)
                print(f"[state] snapshots.{args.update_state_key} = {abs_path}",
                      file=sys.stderr)
        else:
            msg = f"Failed to capture window \"{title}\" (hwnd={hwnd})"
            if args.warn_only:
                print(f"WARNING: {msg}.", file=sys.stderr)
                sys.exit(0)
            else:
                print(f"ERROR: {msg}.", file=sys.stderr)
                sys.exit(1)


if __name__ == "__main__":
    main()
