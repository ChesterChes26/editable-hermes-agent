"""
Path Sync — 将 runtime 中硬编码的旧路径替换为当前机器路径。

用法:
  python sync.py              # 执行替换
  python sync.py --dry-run    # 仅扫描，不修改
  python sync.py --verify     # 替换后验证无残留

映射表在下方 MAPPINGS 中定义，换机时修改此处即可。
"""
import os
import sys
from pathlib import Path

# ============================================================
# 路径映射表 — 换机时修改这里
# ============================================================
MAPPINGS = [
    # (旧路径, 新路径) — 三种斜杠变体都要覆盖
    (r"D:\obsidian\2026", r"$OBSIDIAN_VAULT"),
    (r"D:/obsidian/2026", r"$OBSIDIAN_VAULT"),
    (r"D:\\obsidian\\2026", r"$OBSIDIAN_VAULT"),
    (r"C:\Users\chester.chen", r"$HOME"),
    (r"C:/Users/chester.chen", r"$HOME"),
    (r"C:\\Users\\chester.chen", r"$HOME"),
    # (r"$HORIZON_HOME", r"<新路径>"),  # horizon 待定
]

# ============================================================
# 排除规则
# ============================================================
EXCLUDE_DIRS = {
    "skills/devops/horizon",
    "plugins/horizon",
    "skills/devops/path-sync",   # 自身包含映射表中的旧路径，跳过
}

EXCLUDE_GLOBS = (
    "*.lock", "*.hub", "*.bundled_manifest", ".usage.json",
)

SCAN_GLOBS = ("*.md", "*.py", "*.yaml", "*.json", "*.sh", "*.bat", "*.mjs")

SCAN_DIRS = ["skills", "plugins", "scripts", "hooks", "memories", "profiles"]

# Root-level config files (scanned separately since they're not in a subdirectory)
ROOT_FILES = ["config.yaml", ".env"]

DRY_RUN = "--dry-run" in sys.argv
VERIFY = "--verify" in sys.argv


def should_skip(rel_path: str) -> bool:
    # 统一为正斜杠，兼容 Windows
    rel = rel_path.replace("\\", "/")
    for d in EXCLUDE_DIRS:
        if rel.startswith(d + "/") or rel == d:
            return True
    name = os.path.basename(rel_path)
    for pat in EXCLUDE_GLOBS:
        if pat.startswith("*"):
            if name.endswith(pat[1:]):
                return True
        elif name == pat:
            return True
    return False


def scan_files(base: Path):
    # Subdirectory scans
    for d in SCAN_DIRS:
        sd = base / d
        if not sd.exists():
            continue
        for ext in SCAN_GLOBS:
            for fp in sd.rglob(ext):
                rel = str(fp.relative_to(base))
                if not should_skip(rel):
                    yield fp, rel
    # Root-level files
    for name in ROOT_FILES:
        fp = base / name
        if fp.exists():
            yield fp, name


def main():
    base = Path.cwd()
    print(f"Scanning: {base}")
    total_files = 0
    total_changes = 0

    for fp, rel in scan_files(base):
        total_files += 1
        try:
            content = fp.read_text(encoding="utf-8")
        except Exception as e:
            print(f"  SKIP {rel}: {e}")
            continue

        new_content = content
        for old, new in MAPPINGS:
            new_content = new_content.replace(old, new)

        if new_content != content:
            changed_lines = sum(
                1 for a, b in zip(content.split("\n"), new_content.split("\n")) if a != b
            )
            total_changes += changed_lines

            if VERIFY:
                print(f"  ❌ RESIDUE: {rel} ({changed_lines} lines)")
            elif DRY_RUN:
                print(f"  WOULD FIX: {rel} ({changed_lines} lines)")
            else:
                fp.write_text(new_content, encoding="utf-8")
                print(f"  ✓ {rel} ({changed_lines} lines)")

    print(f"\nScanned: {total_files} files")

    if VERIFY:
        if total_changes > 0:
            print(f"❌ {total_changes} residual lines found — run without --verify to fix")
            sys.exit(1)
        else:
            print("✓ All paths up to date — no residues")
    elif DRY_RUN:
        print(f"Would fix: {total_changes} lines in total (dry-run, no changes made)")
    else:
        if total_changes > 0:
            print(f"Fixed: {total_changes} lines")
        else:
            print("✓ All paths already up to date")


if __name__ == "__main__":
    main()
