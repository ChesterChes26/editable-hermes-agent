# Working CLI Command Examples

Verified working command patterns for SkillOpt-Sleep runs.

## Full Run with Claude Backend (outlook-tencent-meeting-hybrid)

```bash
cd /d/workspace/SkillOpt && ANTHROPIC_API_KEY=*** python -m skillopt_sleep run \
  --project "D:/workspace/outlook-tencent-metting" \
  --claude-home "D:/workspace/outlook-tencent-metting/.skillopt-exp/outlook-tencent-meeting-hybrid-en/claude-home" \
  --target-skill-path "D:/workspace/outlook-tencent-metting/.claude/skills/computer-use/outlook-tencent-meeting-hybrid-en/SKILL.md" \
  --tasks-file "D:/workspace/outlook-tencent-metting/.skillopt-exp/outlook-tencent-meeting-hybrid-en/tasks/tasks.v2.json" \
  --backend claude \
  --max-tasks 20 \
  --edit-budget 4 \
  --progress \
  --json
```

Key parameters:
- `--backend claude` — uses Claude Code as the replay agent (non-interactive, no human handoff)
- `--max-tasks 20` — cap on tasks per cycle
- `--edit-budget 4` — max edits per consolidate cycle
- `--progress` — show progress indicators
- `--json` — machine-readable output

## Directory Structure Convention

```
<project>/.skillopt-exp/<experiment-name>/
├── tasks/
│   └── tasks.v2.json          # Task definitions
├── claude-home/               # Isolated Claude state (--claude-home)
├── logs/
│   └── skillopt-run-v2.log    # Detailed run logs
├── staging/                   # (created by tool at project root)
├── baseline/                  # Baseline results
├── candidates/                # Candidate skill versions
├── runs/                      # Historical run data
└── reports/                   # Generated reports
```

Note: `.skillopt-sleep/staging/` lives at the **project root**, not under `.skillopt-exp/`.

## Launch Pattern (Hermes Agent)

Always use background mode with notification for long runs:
```
terminal(background=true, notify_on_complete=true, timeout=3600, workdir=<skillopt-dir>)
```

Expected runtime: 30-60 minutes for --max-tasks 20.
