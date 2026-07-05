"""localize — replace portable $VAR placeholders with local machine paths.
Run AFTER pull: scans runtime dirs, replaces $VAR references with
local paths defined in path-vars.yaml.

Usage: python localize.py [--dry-run]
"""
import os
import sys
from pathlib import Path
import yaml

HERMES_HOME = Path(os.environ.get("HERMES_HOME", str(Path.home() / "AppData" / "Local" / "hermes")))
VARS_FILE = HERMES_HOME / "path-vars.yaml"

SCAN_DIRS = ["skills", "plugins", "scripts", "hooks", "memories", "profiles", "cron"]
ROOT_FILES = ["config.yaml", ".env"]
SCAN_GLOBS = ("*.md", "*.py", "*.yaml", "*.json", "*.sh", "*.bat", "*.mjs")
EXCLUDE_GLOBS = (".lock", ".hub", ".bundled_manifest", ".usage.json")

DRY_RUN = "--dry-run" in sys.argv


def load_vars():
    with open(VARS_FILE, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    variables = cfg["variables"]
    replacements = []
    for var_name, local in variables.items():
        # Forward-slash form for consistency in runtime files
        canonical = local.replace("\\", "/")
        replacements.append((f"${var_name}", canonical))
    return replacements


def should_skip(rel_path: str) -> bool:
    rel = rel_path.replace("\\", "/")
    name = Path(rel_path).name
    for pat in EXCLUDE_GLOBS:
        if pat.startswith("*"):
            if name.endswith(pat[1:]):
                return True
        elif name == pat:
            return True
    return False


def main():
    base = Path.cwd()
    replacements = load_vars()
    total_files = 0
    total_changes = 0

    for d in SCAN_DIRS:
        sd = base / d
        if not sd.exists():
            continue
        for ext in SCAN_GLOBS:
            for fp in sd.rglob(ext):
                rel = str(fp.relative_to(base))
                if should_skip(rel):
                    continue
                total_files += 1
                try:
                    content = fp.read_text(encoding="utf-8")
                except Exception as e:
                    print(f"  SKIP {rel}: {e}")
                    continue

                new_content = content
                for var_ref, local in replacements:
                    new_content = new_content.replace(var_ref, local)

                if new_content != content:
                    changed_lines = sum(
                        1 for a, b in zip(content.split("\n"), new_content.split("\n")) if a != b
                    )
                    total_changes += changed_lines
                    if DRY_RUN:
                        print(f"  WOULD FIX: {rel} ({changed_lines} lines)")
                    else:
                        fp.write_text(new_content, encoding="utf-8")
                        print(f"  ✓ {rel} ({changed_lines} lines)")

    # Root-level files
    for name in ROOT_FILES:
        fp = base / name
        if not fp.exists():
            continue
        total_files += 1
        content = fp.read_text(encoding="utf-8")
        new_content = content
        for var_ref, local in replacements:
            new_content = new_content.replace(var_ref, local)
        if new_content != content:
            changed_lines = sum(
                1 for a, b in zip(content.split("\n"), new_content.split("\n")) if a != b
            )
            total_changes += changed_lines
            if DRY_RUN:
                print(f"  WOULD FIX: {name} ({changed_lines} lines)")
            else:
                fp.write_text(new_content, encoding="utf-8")
                print(f"  ✓ {name} ({changed_lines} lines)")

    print(f"\nScanned: {total_files} files")
    if DRY_RUN:
        print(f"Would localize: {total_changes} lines (dry-run)")
    else:
        print(f"Localized: {total_changes} lines" if total_changes else "✓ All paths already local")


if __name__ == "__main__":
    main()
