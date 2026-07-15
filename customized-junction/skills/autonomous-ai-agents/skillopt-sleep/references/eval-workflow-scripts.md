# Eval Workflow Scripts

## sync-eval-skill.sh

Syncs the original SKILL.md to SKILL-eval.md and appends SkillOpt evaluation rules.

**Usage:**
```bash
./sync-eval-skill.sh
```

**What it does:**
1. Copies SKILL.md → SKILL-eval.md
2. Appends `<!-- SKILLOPT EVAL RULES START -->` block with:
   - Output completeness requirement (single response, all steps)
   - Step structure requirement (4 elements per step)
   - Date handling requirement (relative → absolute YYYY-MM-DD)
   - Error handling requirement (2+ concrete failure scenarios)

**When to run:**
- Before EVERY SkillOpt execution
- After any manual SKILL.md changes

## run-skillopt.sh

Wrapper script that auto-syncs SKILL-eval.md and runs SkillOpt.

**Usage:**
```bash
./run-skillopt.sh <tasks-file> [extra-args]

# Example:
./run-skillopt.sh .skillopt-exp/outlook-tencent-meeting-hybrid-en/tasks/tasks.v2.json
```

**What it does:**
1. Calls `./sync-eval-skill.sh`
2. Runs SkillOpt with `--target-skill-path ".../SKILL-eval.md"`
3. Uses `--auto-adopt` for automatic edit application

**Post-run checklist:**
- [ ] Check if CLAUDE.md was generated → delete it: `rm -f CLAUDE.md`
- [ ] Read staging report: `cat .skillopt-sleep/staging/<latest>/report.md`
- [ ] Present results to user for approval before next night

## SKILL-eval.md

**Location:** `.claude/skills/computer-use/outlook-tencent-meeting-hybrid-en/SKILL-eval.md`

**Status:** In .gitignore (generated file, not committed)

**Content:** Original SKILL.md + eval rules block

**Key difference from SKILL.md:**
- SKILL.md: For real execution (step-by-step tool calls)
- SKILL-eval.md: For SkillOpt evaluation (single-response output)

## Why This Pattern?

SkillOpt's pure-text replay mode requires the agent to "describe" all steps in a single response, because it cannot execute tools. This conflicts with real execution mode where the agent executes tools step-by-step.

**Without isolation:**
- Eval rules pollute SKILL.md
- Real execution gets confused by "output all steps in single response" requirement
- Maintenance nightmare (which rules are for eval vs real?)

**With isolation:**
- SKILL.md stays clean for real execution
- SKILL-eval.md has eval-specific rules
- Clear separation of concerns
- Easy to sync and maintain

## Workflow Summary

```
Before SkillOpt run:
  ./sync-eval-skill.sh  (or ./run-skillopt.sh which calls it)

During SkillOpt run:
  Uses SKILL-eval.md as target

After SkillOpt run:
  1. Read staging report
  2. Delete CLAUDE.md if generated
  3. Present results to user
  4. If approved, manually merge useful edits from SKILL-eval.md to SKILL.md
  5. Re-sync SKILL-eval.md before next night
```
