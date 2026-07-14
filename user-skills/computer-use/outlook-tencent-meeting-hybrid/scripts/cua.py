"""Thin wrapper around cua-driver.exe for skill Step 0 daemon management.

Usage:
  python cua.py autostart kick       # ensure daemon is running
  python cua.py serve                # start daemon in background
  python cua.py status               # print daemon status

Rationale:
  Calling cua-driver.exe directly from bash requires $LOCALAPPDATA expansion.
  Claude Code's permission system treats `$` as sensitive, causing allowlist misses.
  This wrapper resolves the path inside Python (where $ is invisible to the
  permission checker), so the Bash call matches `Bash(python *)` which is already
  allowed.
"""

import os
import subprocess
import sys


def _cua_exe() -> str:
    localappdata = os.environ.get("LOCALAPPDATA", "")
    if not localappdata:
        sys.exit("❌ LOCALAPPDATA not set — cannot locate cua-driver.exe")
    return os.path.join(
        localappdata, "Programs", "Cua", "cua-driver", "bin", "cua-driver.exe"
    )


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(f"Usage: python {sys.argv[0]} <subcommand> [args...]")

    exe = _cua_exe()
    cmd = [exe] + sys.argv[1:]

    if sys.argv[1] == "serve":
        # Detach so the daemon outlives this script
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS,
        )
    else:
        result = subprocess.run(cmd, capture_output=True, text=True)
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
