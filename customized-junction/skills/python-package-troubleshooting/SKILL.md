---
name: python-package-troubleshooting
description: "Diagnose pip install failures, check Python version compatibility, and run CLI tools from source."
version: 1.0.0
category: software-development
---

# Python Package Troubleshooting

Diagnose why `pip install <pkg>` fails silently or refuses to install, and run CLI tools when entry points aren't available.

## Trigger Conditions

- `pip install <pkg>` runs but doesn't install anything (no error, just nothing happens)
- `pip show <pkg>` returns "not found" but the package exists on PyPI
- User is on a very new Python version (just released major/minor)
- Entry point command (`hermes`, `claude`, etc.) not found after install

## Step 1: Check Python Version Compatibility

```bash
pip index versions <package-name>
```

This queries PyPI and shows available versions AND the locally installed version (if any). It also reveals the Python version constraint implicitly — if `pip install` does nothing, the installed Python is likely outside `requires_python`.

For the explicit constraint:

```bash
curl -s "https://pypi.org/pypi/<package>/<version>/json" | python -c "import sys,json; d=json.load(sys.stdin); print(d['info'].get('requires_python','not specified'))"
```

Example: `hermes-agent` requires `>=3.11,<3.14` — Python 3.14 is excluded.

**Fix:** either downgrade Python to a supported version, or edit `pyproject.toml` in the source to relax the constraint and `pip install -e .`.

## Step 2: Run CLI from Source (when entry point not in PATH)

When the package is installed but the command isn't found:

```bash
python -c "import sys; print(sys.prefix + '\\Scripts')"   # find entry point location (Windows)
# or on POSIX:
python -c "import sys; print(sys.prefix + '/bin')"
```

Add that path to system PATH, or use the full path directly.

When the entry point ISN'T installed at all (source-only, no `pip install`):

Find the entry point module in `pyproject.toml`:

```bash
grep -A5 'console_scripts' pyproject.toml
```

Example output:
```
hermes = "hermes_cli.main:main"
```

Then run directly:
```bash
python -m hermes_cli.main
```

Equivalent to the `hermes` command.

## Step 3: Alternative Install Methods

When pip can't reach PyPI or downloads are blocked:

| Method | Command | Notes |
|--------|---------|-------|
| **Wheel download** | Download `.whl` from pypi.org, then `pip install ./pkg.whl` | Offline-capable |
| **Source + proxy** | `git -c http.proxy=... clone <repo> && pip install -e .` | Bypass CDN firewall |
| **Relax version constraint** | Edit `pyproject.toml` `requires-python`, then `pip install -e .` | Only if source available |
| **npm mirror** | `npm config set registry https://registry.npmmirror.com` | For npm packages |

## Pitfalls

- **`pip install` silently does nothing**: always check `requires_python` first — this is the #1 cause when it looks like the command ran but nothing was installed.
- **`pip show` vs `pip index versions`**: `pip show` only reports locally installed packages. `pip index versions` queries PyPI. Use the latter to confirm a package EXISTS before troubleshooting.
- **Editing `pyproject.toml` for Python version**: relaxing `requires-python` lets you install, but doesn't guarantee runtime compatibility. Use only when downgrading Python isn't practical.
