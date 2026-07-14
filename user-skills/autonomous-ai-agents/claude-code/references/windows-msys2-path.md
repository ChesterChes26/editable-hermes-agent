# Windows MSYS2 + Claude Code PATH Fix

Complete recipe verified 2026-07-03.

## Problem

Claude Code on Windows uses `bash -c` (non-interactive, non-login). Neither `.bashrc` nor `/etc/profile` is loaded. If PATH contains Windows-style entries (`C:\Windows\system32;...`), bash interprets `:` as separator → garbage.

## Root Cause Table

| Shell mode | Loads .bashrc? | Triggered by |
|------------|---------------|--------------|
| Login (`bash -l`) | via `.bash_profile` | MSYS2 terminal |
| Interactive (`bash -i`) | directly | Hermes session |
| Non-interactive (`bash -c`) | **no** (unless BASH_ENV) | **Claude Code** |

## Part 1: ~/.bashrc

```bash
# Fix PATH for MSYS2 non-login shell (Claude Code)
if [ -f /etc/profile ]; then
    . /etc/profile
fi
export PATH="/c/Users/<user>/AppData/Local/Programs/Python/Python313:$PATH"
```

- `source /etc/profile` adds `/mingw64/bin`, `~/bin` (bash default already has `/usr/bin` and `/bin` for coreutils)
- Python path MUST use MSYS2 format (`/c/Users/...`), not Windows (`C:\Users\...`)
- Both lines prepend to PATH — they take priority over any broken inherited entries

## Part 2: ~/.claude/settings.json

```json
{
  "env": {
    "BASH_ENV": "/c/Users/<user>/.bashrc"
  }
}
```

This is the **key** — without it, Part 1 is never read by Claude Code's `bash -c` subprocess.

## Verification

```bash
# Simulate Claude Code's real scenario: Windows PATH → bash -c
WINDOWS_PATH="C:\\Windows\\system32;C:\\Windows;C:\\Program Files\\nodejs"

# Without BASH_ENV → everything fails
env -i HOME="$HOME" PATH="$WINDOWS_PATH" /usr/bin/bash --norc -c 'type cat; type python'

# With BASH_ENV → .bashrc loads → everything works
env -i HOME="$HOME" PATH="$WINDOWS_PATH" BASH_ENV="$HOME/.bashrc" /usr/bin/bash -c 'type cat; type python; python --version'
```

Or via Claude Code directly:

```bash
claude -p 'type cat && type python && python --version' --max-turns 3 --allowedTools Bash
```

## BASH_ENV: absolute path vs tilde

Use **absolute MSYS2 path** (`/c/Users/<user>/.bashrc`), NOT `~/.bashrc`. Reason:

- `BASH_ENV` is set by Claude Code as a literal environment variable string from `settings.json`
- Bash does tilde-expand `~` in `BASH_ENV` using the `HOME` variable
- Claude Code subprocesses may NOT have `HOME` set (minimal environment from Windows)
- Without `HOME`, `~` expands to empty string → `.bashrc` not loaded → fix silently fails

## Notes

- `source /etc/profile` is technically redundant for coreutils (bash default PATH has `/usr/bin`) but adds `/mingw64/bin` and user bins
- `export PATH=...Python...` is what actually fixed the reported error
- `BASH_ENV` in `settings.json` is scoped to Claude Code only; system-wide alternative is `setx BASH_ENV`
- The fix works through explicit `.bashrc` loading (BASH_ENV), not through PATH inheritance from parent
