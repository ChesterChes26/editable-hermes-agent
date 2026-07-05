"""canonicalize — replace local paths with portable $VAR placeholders.
Run BEFORE commit: scans git-tracked user-* dirs, replaces local paths
defined in path-vars.yaml with $VAR_NAME references.

Usage: python canonicalize.py [--dry-run]
"""
import os
import sys
from pathlib import Path
import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
HERMES_HOME = Path(os.environ.get("HERMES_HOME", str(Path.home() / "AppData" / "Local" / "hermes")))
VARS_FILE = HERMES_HOME / "path-vars.yaml"

SCAN_DIRS = ["user-skills", "user-plugins", "user-config"]
SCAN_GLOBS = ("*.md", "*.py", "*.yaml", "*.json", "*.sh", "*.bat", "*.mjs")
EXCLUDE_GLOBS = ("*.lock", "*.hub", "*.bundled_manifest", ".usage.json")

DRY_RUN = "--dry-run" in sys.argv


def load_vars():
    with open(VARS_FILE, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    variables = cfg["variables"]
    replacements = []
    for var_name, local in variables.items():
        canonical = local.replace("\\", "/")
        variants = [
            (local, f"${var_name}"),
            (local.replace("\\", "\\\\"), f"${var_name}"),
            (canonical, f"${var_name}"),
        ]
        replacements.extend(variants)
    return replacements


def should_exclude(name: str) -> bool:
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

    for scan_dir in SCAN_DIRS:
        sd = base / scan_dir
        if not sd.exists():
            continue
        for ext in SCAN_GLOBS:
            for fp in sd.rglob(ext):
                if should_exclude(fp.name):
                    continue
                total_files += 1
                rel = str(fp.relative_to(base))
                try:
                    content = fp.read_text(encoding="utf-8")
                except Exception as e:
                    print(f"  SKIP {rel}: {e}")
                    continue

                new_content = content
                for old, new in replacements:
                    new_content = new_content.replace(old, new)

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

    print(f"\nScanned: {total_files} files")
    if DRY_RUN:
        print(f"Would canonize: {total_changes} lines (dry-run)")
    else:
        print(f"Canonized: {total_changes} lines" if total_changes else "✓ All paths already canonical")


if __name__ == "__main__":
    main()
