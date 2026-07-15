# SkillOpt Iron Rules

These are HARD CONSTRAINTS. Never violate.

## Rule 1: No Auto Commit

**All SkillOpt-produced commits MUST be approved by user. NEVER auto adopt+commit.**

- SkillOpt `run` completes normally, produces staging results
- After run ends, manually review report.md
- Only execute `adopt` + `git commit` after explicit user approval

**Why:** Prevents unreviewed changes from entering main branch.
**Lesson (2026-07-15):** 22 commits auto-applied without approval, required full rollback.

## Rule 2: Isolated Training Branch

**SkillOpt training MUST NOT run on main/working branch. MUST checkout separate test branch first.**

```bash
# Before training:
git checkout -b <branch>-skillopt   # e.g., chester-skillopt

# After training:
# User decides whether to merge to main
```

**Why:** Protects main branch. If training produces bad results, delete test branch — main unaffected.

## Rule 3: Inheritance Mode (auto_adopt=True)

**Use `--auto-adopt` so nights inherit improvements within a run, but NEVER auto commit to git.**

```bash
ANTHROPIC_API_KEY=*** python -m skillopt_sleep run \
  --auto-adopt \
  --project "PATH" --claude-home "PATH" \
  --target-skill-path "PATH" --tasks-file "PATH" \
  --backend claude --max-tasks 20 --edit-budget 4 \
  --progress --json
```

**How it works:**
- Night 1: based on v0 → gate=accept → adopt to working dir (v1)
- Night 2: based on v1 → gate=reject → no adopt (stays v1)
- Night 3: based on v1 → gate=accept → adopt to working dir (v2)
- ...
- Run ends → user reviews all staging dirs → manually chooses best to commit

**Why:** Cumulative improvement. Without inheritance, every night starts from same baseline and may rediscover same fixes. With inheritance, accepted improvements compound.

**Key distinction:**
- `adopt` = apply edits to SKILL.md in working directory (file system level)
- `git commit` = record changes in version history
- `auto_adopt` controls the former, never the latter

## Rule 4: Branch Isolation for Each Training Campaign

**Each training campaign (new task set or new skill) gets its own branch.**

```bash
# Campaign 1:
git checkout -b skillopt-campaign-1
# ... run training, review, decide merge ...

# Campaign 2:
git checkout main
git checkout -b skillopt-campaign-2
# ... independent from campaign 1 ...
```

**Why:** Different campaigns may produce conflicting optimizations. Isolation prevents cross-contamination.

## Rule 5: Rubric-Skill Alignment

**When you modify the target skill, you MUST also update the rubric to evaluate the new requirement.**

Example: If you add "Response Structure Rule" to the skill (requiring 4 elements per step), the rubric must explicitly check for those 4 elements.

**Checklist before running:**
1. Did I modify the skill text? → Yes → Update rubric
2. Does the rubric evaluate the new requirement? → No → Add evaluation criteria
3. Are the rubric's PASS/FAIL conditions aligned with the skill's requirements? → Verify

**Anti-pattern observed:** Added Response Structure Rule to skill but forgot to update rubric. Result: SkillOpt couldn't detect whether the agent followed the new rule, baseline stayed at 0.150, all proposed edits rejected.

## Rule 6: State Reset Between Campaigns

**When starting a new test campaign (V1→V2, or re-running with different tasks/rubric), MUST backup and remove state.json so the new run starts from night 0.**

```bash
# Before new campaign:
mv .skillopt-exp/<skill>/.skillopt-sleep/state.json \
   .skillopt-exp/<skill>/.skillopt-sleep/state.json.bak
```

**Why:** state.json accumulates night history across runs. If you don't reset, the new run continues from the last night number and the history mixes old and new campaigns. The scoring baseline may also be contaminated by prior adopted edits.

**When to apply:**
- Switching task versions (v1→v2 or v2→v1)
- Re-running after major skill/rubric changes
- Starting a fresh optimization campaign on the same skill

## Rule 7: CLAUDE.md Cleanup After --auto-adopt

**When using `--auto-adopt`, SkillOpt generates CLAUDE.md (memory edits) in the project root. MUST delete it after each night or after the run completes. SKILL.md is the single source of truth.**

```bash
# After run completes (or after each night if monitoring):
rm -f "$PROJECT/CLAUDE.md"
```

**Why:** SkillOpt has two learning channels — skill edits (SKILL.md) and memory edits (CLAUDE.md). Memory edits duplicate and conflict with skill edits. The user's design principle: SKILL.md controls output structure, rubric evaluates comprehension. Memory layer adds noise.

**What gets generated:**
- `--auto-adopt` applies both skill edits AND memory edits
- Memory edits land in `<project>/CLAUDE.md`
- Skill edits land in the target SKILL.md (desired)

**Workflow:**
1. Run with `--auto-adopt` (nights inherit improvements)
2. After run: delete CLAUDE.md
3. Review staging report for skill edits only
4. Commit SKILL.md changes to git
