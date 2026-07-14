# Hermes Agent Install Troubleshooting (2026-07)

Specific failure modes encountered when installing hermes-agent on Windows with Python 3.14.

## Python 3.14 Incompatibility

**Symptom:** `pip install hermes-agent` runs without error but does nothing. `pip show hermes-agent` returns "not found."

**Root cause:** `requires-python = ">=3.11,<3.14"` in pyproject.toml. Python 3.14 is explicitly excluded.

**Fix A (recommended):** Use Python 3.11–3.13.

**Fix B:** Edit pyproject.toml in source:
```
requires-python = ">=3.11,<3.14"  →  requires-python = ">=3.11"
```
Then `pip install -e .` from source directory.

## Desktop Build Failure

**Symptom:** `hermes desktop` build fails on Windows.

**Workaround:** The desktop app is just a graphical shell. Core functionality works from CLI:
```bash
python -m hermes_cli.main
```

## Entry Point Not in PATH

**Symptom:** `hermes` command not recognized after `pip install -e .`.

**Immediate fix:**
```bash
python -m hermes_cli.main
```

**Permanent fix:** Add `Scripts` directory to PATH:
```bash
python -c "import sys; print(sys.prefix + '\\Scripts')"
```
