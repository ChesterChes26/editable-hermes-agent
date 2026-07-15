# Task Review Workflow

Pre-run and post-run review patterns for SkillOpt-Sleep task sets.

## Pre-Run: Task Review (MANDATORY)

**Before running any task set, present a summary to the user for approval.**

### What to Present

1. **Task count and distribution**
   ```bash
   python -c "
   import json
   d = json.load(open('tasks.v2.json'))
   tasks = d['tasks']
   print(f'Total tasks: {len(tasks)}')
   splits = {}
   for t in tasks:
       s = t.get('split', '?')
       splits[s] = splits.get(s, 0) + 1
   print(f'Split distribution: {splits}')
   origins = {}
   for t in tasks:
       o = t.get('origin', '?')
       origins[o] = origins.get(o, 0) + 1
   print(f'Origin distribution: {origins}')
   "
   ```

2. **Task diversity analysis**
   - Are there edge cases? (ambiguous dates, missing parameters, user conflicts)
   - Are there complexity gradients? (simple → complex)
   - Are val/test splits large enough? (minimum 3 each for statistical power)

3. **Rubric quality check**
   - Do rubrics evaluate "skill-text understanding" (not execution reports)?
   - Are PASS/FAIL criteria specific and measurable?
   - Do rubrics cover the skill's critical constraints?

### User Approval Gate

**Do NOT proceed until user confirms:**
- Task set meets requirements
- Rubrics are appropriate
- Edge cases are included (if testing optimization ability)

**Example presentation:**
```
V2 Enhanced Task Set Review:
- 20 tasks (15 train + 3 val + 2 test)
- 15 regular tasks + 5 edge cases
- Edge cases: implicit requirements, user conflicts, ambiguous dates, missing time, vague requests
- Expected: baseline ~0.3-0.7 (should trigger failures for optimization)

Proceed? (yes/no)
```

## Environment Isolation (When Switching Task Sets)

**Problem**: When running different task sets (v1, v2, v2-enhanced) against the same skill, the `state.json` accumulates history from previous runs. This causes:
- Baseline scores to be contaminated by previous optimizations
- Gate decisions to be based on mixed task sets
- Inability to accurately evaluate a new task set's strength

**Solution**: Before running a different task set, backup and clear state.json.

### Procedure

```bash
# 1. Backup current state
cp .skillopt-sleep/state.json .skillopt-sleep/state.json.bak

# 2. Clear state (start fresh)
rm .skillopt-sleep/state.json

# 3. Run new task set
ANTHROPIC_API_KEY=*** python -m skillopt_sleep run --tasks-file tasks.v2-enhanced.json ...
```

### When to Isolate

- **Switching from v1 → v2**: Isolate (different task complexity)
- **Switching from v2 → v2-enhanced**: Isolate (added edge cases)
- **Running v2 again (same file)**: Do NOT isolate (continue optimization)
- **Running v3 after v2**: Isolate (different task set)

### Verification

After isolation, verify clean state:
```bash
ls -la .skillopt-sleep/state.json
# Should show "No such file or directory"
```

## Post-Run: Strength Evaluation

**After a run completes, dispatch a review subagent to evaluate task set strength and edit quality.**

### What to Evaluate

1. **Task set strength** (1-10 scale)
   - Did baseline score reveal weaknesses? (0.0-0.3 = too easy, 0.3-0.7 = good, 0.7-1.0 = too hard)
   - Did candidate score show improvement? (>20% improvement = effective optimization)
   - Were edge cases effective? (did they trigger failures in baseline?)

2. **Edit quality**
   - Are accepted edits addressing real failures?
   - Are rejected edits genuinely unhelpful, or just below threshold?
   - Do edits align with skill's purpose?

3. **Next steps recommendation**
   - Continue optimization? (if candidate < 0.9)
   - Expand task set? (if baseline > 0.7, tasks too easy)
   - Adjust rubrics? (if edits don't align with expectations)

### Review Subagent Template

```python
delegate_task(
    goal="Review SkillOpt-Sleep run results and evaluate task set strength",
    context="""
Project: D:\\workspace\\outlook-tencent-metting
Task file: .skillopt-exp\\outlook-tencent-meeting-hybrid-en\\tasks\\tasks.v2-enhanced.json
Staging report: .skillopt-sleep\\staging\\<timestamp>\\report.md

Analyze:
1. Read tasks file, analyze task distribution (regular vs edge cases)
2. Read staging report, analyze baseline/candidate scores
3. Analyze accepted/rejected edits, judge quality
4. Evaluate task set strength:
   - Is baseline low enough to trigger optimization? (0.3-0.7 ideal)
   - Is candidate high enough to show improvement? (>20% better)
   - Did edge cases successfully trigger failures?
5. Recommend next steps:
   - Continue optimization? (if candidate < 0.9)
   - Expand task set? (if baseline > 0.7)
   - Adjust rubrics? (if edits don't align)

Output format:
- Task set strength score (1-10)
- Edge case effectiveness analysis
- Edit quality assessment
- Next steps recommendation
""",
    role="leaf"
)
```

### Interpreting Results

**Task set strength score:**
- **1-3**: Too easy (baseline > 0.7) — expand with harder tasks or edge cases
- **4-6**: Good balance (baseline 0.3-0.7) — effective for optimization
- **7-10**: Too hard (baseline < 0.3) — simplify tasks or adjust rubrics

**Edit quality:**
- **High quality**: Edits address specific failures, align with skill purpose
- **Low quality**: Edits are generic, don't address root causes, or conflict with skill

**Next steps:**
- **Continue**: If candidate < 0.9 and edits are high quality
- **Expand**: If baseline > 0.7 (tasks too easy) or edge cases didn't trigger failures
- **Adjust**: If edits don't align with expectations (rubric may be wrong)

## Anti-Patterns

**❌ Running without user review**: User may want to adjust tasks or rubrics before running. Always present summary first.

**❌ Skipping environment isolation**: Running v2 after v1 without clearing state.json contaminates baseline. Always isolate when switching task sets.

**❌ Skipping post-run review**: Without evaluation, you don't know if the task set was effective or if edits are high quality. Always dispatch review subagent.

**❌ Continuing optimization without checking strength**: If baseline > 0.7, tasks are too easy — optimization won't produce meaningful improvements. Expand task set first.

## Observed Session (2026-07-15)

**V1 test**: 3 tasks, baseline 0.975 → candidate 0.975 (no improvement). Task set too easy.

**V2 enhanced**: 20 tasks (15 regular + 5 edge cases), baseline 0.033 → candidate 0.767 (+22x improvement). Edge cases successfully triggered failures. 7 high-quality edits accepted.

**Lesson**: V1 was too simple (3 tasks, no edge cases). V2 enhanced had enough complexity to trigger optimization. Post-run review confirmed task set strength = 6/10 (good balance).
