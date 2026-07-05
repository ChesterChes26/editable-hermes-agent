# Path Migration: 2026-07-05 Session Evidence

## Context
Horizon moved from `D:\workspace\AI-research\Horizon` to `$HORIZON_HOME`.
Branch switched from `main` to `chester-edit`.

## Files with stale D: path (found and fixed)
- `hermes-e-data/skills/devops/horizon/SKILL.md` — 14 occurrences
- `hermes-e-data/skills/devops/horizon/references/daily-ai-news-workflow.md`
- `hermes-e-data/skills/devops/horizon/references/diagnosis-session.md` — 3 occurrences
- `hermes-e-data/skills/devops/horizon/references/jsonrpc-commands.md` — 7 occurrences
- `hermes-e-data/skills/devops/horizon/references/pipeline-blocking-analysis.md`
- `hermes-e-data/skills/devops/horizon/references/read-write-tool-split.md`
- `hermes-e-data/skills/devops/horizon/references/stale-session-bytecode-debug.md`
- `hermes-e-data/skills/devops/horizon/horizon/SKILL.md` — nested copy
- `hermes-e-data/skills/devops/path-sync/SKILL.md` — sibling skill
- `hermes-e-data/skills/devops/path-sync/scripts/sync.py` — commented path

## Files NOT to touch
- `editable-hermes-agent/user-plugins/horizon/__init__.py` — source repo, reverted
- `editable-hermes-agent/user-skills/devops/horizon/` — source of truth, sync FROM not TO

## Sed recipe (all 3 path variants)
```bash
find . -name "*.md" -exec sed -i \
  -e 's|D:/workspace/AI-research/Horizon|$HORIZON_HOME|g' \
  -e 's|D:\\workspace\\AI-research\\Horizon|$HORIZON_HOME|g' \
  -e 's|/d/workspace/AI-research/Horizon|/e/new_workspace/Horizon|g' \
  {} \;
```

## Verification
```bash
grep -rl "AI-research\|D:.*Horizon" \
  hermes-e-data/plugins/ hermes-e-data/skills/ Horizon/src/ \
  --include="*.py" --include="*.md" --include="*.yaml" --include="*.json"
# Should return empty
```

## What went wrong (agent mistakes)
1. Modified plugin `HORIZON_CWD` instead of finding stale skill files
2. Created NTFS junction as workaround — **resolved 2026-07-05 18:07**. The junction `D:/workspace/AI-research/Horizon -> /e/new_workspace/Horizon` survived and became the root cause of "ghost path" (幽灵路径) reappearing in subsequent sessions. `cmd //c "rmdir"` did NOT work because cmd follows NTFS junctions into the target. Final removal used `python -c "import shutil; shutil.rmtree(r'D:\\workspace\\AI-research\\Horizon')"` then `rmdir "D:/workspace/AI-research"`. After removal, gateway restart was required to flush the stale plugin module that still had `_RUNS_ROOT` resolved through the (now-deleted) junction.
3. Modified `editable-hermes-agent/user-plugins/` which is source, not runtime
4. Spent excessive effort hunting for non-existent Python handler source — the `runs_root` came from plugin code that resolves `HORIZON_CWD` through `Path.resolve()`; the D: path appeared because a stale directory existed at the old location and `_read_runs_root()`'s `mkdir(exist_ok=True)` recreated it

## Post-migration symlink/junction check (CRITICAL)
After path migration, explicitly check for leftover NTFS junctions at the OLD path:
```bash
# 1. Detect
ls -la "D:/workspace/AI-research/Horizon" 2>&1
# Junction: shows "lrwxrwxrwx ... -> /e/new_workspace/Horizon"
# Regular dir: shows "drwxr-xr-x"

# Definitive: check reparse point attribute
python -c "
import ctypes
attrs = ctypes.windll.kernel32.GetFileAttributesW(r'D:\workspace\AI-research\Horizon')
print(f'Is reparse point: {bool(attrs != 0xFFFFFFFF and attrs & 0x400)}')
"

# 2. Remove — cmd //c rmdir DOES NOT WORK (follows junction into target)
#    Use shutil.rmtree instead:
python -c "import shutil; shutil.rmtree(r'D:\workspace\AI-research\Horizon')"
rmdir "D:/workspace/AI-research"

# 3. Gateway restart — plugin module in memory still has stale Path.resolve()
hermes gateway restart
# Then /reset the session
```
`grep` over file contents alone will NOT find junction residues — they live at the filesystem level, not in text files. A surviving junction lets the old path remain a valid directory; `Path.resolve()` on Windows follows reparse points silently, polluting every `_RUNS_ROOT.resolve()` call with the old D: prefix.
