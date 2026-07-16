---
name: skillopt-eval-workflow
version: 2
description: SkillOpt-Sleep evaluation workflow — eval isolation, multi-night mechanics, task design
tags: [skillopt, evaluation, workflow, claude-code]
---

# SkillOpt-Sleep Evaluation Workflow

## When to Use

Running SkillOpt-Sleep optimization on Claude Code skills. Covers eval isolation, task design, and multi-night execution.

## Core Architecture: Eval Rules Serve Dual Purpose (confirmed 2026-07-15)

**Observation**: The `SKILL-eval.md` isolation pattern is **no longer necessary**.

**Why**: SkillOpt appends learned rules to a `<!-- SKILLOPT-SLEEP:LEARNED START -->` block at the end of SKILL.md. These rules (e.g., "Response Completeness Gate", "Response Length Priority") serve a **dual purpose**:

- **Eval mode** (SkillOpt replay): Claude reads SKILL.md → outputs text → judge scores. Here the rules matter because judge can only evaluate text.
- **Real execution**: Agent reads SKILL.md → executes tools step-by-step. The structured response rules **also help here** by forcing the agent to explicitly think through error handling at each step. This prevents the agent from getting stuck at any phase (e.g., UI element not found, COM connection failed, popup blocking interaction). The "Current State, Goal, Method, Error Handling" structure per step is essentially a pre-execution checklist.

**Token cost is a preventive investment**: ~1,200-1,800 tokens per response for structured output. This costs less than the tokens wasted when an agent blindly retries a failed step 10 times.

**Decision framework** (confirmed by user):
1. Does this edit fix a real bug? → Adopt into main skill body
2. Does this edit help both eval and real execution? → Adopt into main skill body (not just LEARNED block)
3. Does this edit genuinely conflict with real execution? → Reject (verify conflicts yourself, don't trust subagent flagging)

**⛔ Subagent reviews can overstate "conflicts"**: When reviewing SkillOpt edits via subagent delegation, the subagent may flag "conflicts" with existing instructions that don't actually exist. Observed 2026-07-15: subagent flagged 3 "conflicts" (Closing Protocol vs Response Structure, redundant error handling, token optimization contradiction) — all were misidentified. Always verify conflicts yourself before rejecting edits.

**Still apply**:
- Delete CLAUDE.md after each night (memory edits leak into next night)
- Reset state.json when switching task sets (otherwise old history contaminates baseline)

**Legacy pattern** (no longer needed but kept for reference):
```
SKILL-eval.md     ← eval only (SKILL.md + eval rules appended)
sync-eval-skill.sh  ← copies SKILL.md → SKILL-eval.md + appends eval rules
```

## SkillOpt Multi-Night Mechanics

**Critical**: `skillopt_sleep run` executes exactly **1 night per invocation**. There is no loop.

Source: `skillopt_sleep/cycle.py:91` — `run_sleep_cycle()` runs one cycle and returns.

**To run N nights**:
```bash
for i in {1..5}; do
  ./run-skillopt.sh tasks.json
  rm -f CLAUDE.md  # clean memory edits between nights
done
```

**Night accumulation**: Each night reads the SKILL.md as modified by the previous night's adopt. Baseline of night N = candidate of night N-1.

**state.json**: Tracks night counter and history. Must be backed up and cleared when switching task sets, otherwise old history makes baseline comparison meaningless.

## Task Design Lessons

### V1 (3 tasks) — Too Simple

- 3 basic meeting invite tasks (absolute date, tomorrow, next Monday)
- Result: baseline 0.975 → candidate 0.975, **0 edits generated**
- Why: Current SKILL.md already handles these perfectly. No failures → no learning signal.

### V2 (15 tasks) — Better but Homogeneous

- 10 train + 3 val + 2 test
- All tasks structurally identical (different recipients/dates/subjects)
- Result: baseline 0.033 → candidate 1.000, but only after adding edge cases

### V2 Enhanced (20 tasks) — Effective

Added 5 edge cases that triggered real failures:
1. **Implicit requirement** — User doesn't mention Tencent Meeting, but skill requires it
2. **User conflict** — User explicitly says "don't use Tencent Meeting"
3. **Ambiguous date** — "下周" without specifying which day
4. **Missing time** — "明天下午" without specific hour
5. **Vague request** — "发个会议" instead of "创建会议邀请"

**Key insight**: Edge cases that test skill rule interpretation (not just parameter variation) are what generate useful edits. Parameter-only variation produces no failures → no learning.

### Task Format Requirements

Tasks need these fields for SkillOpt to accept them:
- `id`, `project`, `intent`, `reference` (rubric), `split` (train/val/test)
- `reviewed: true` at top level
- `reference_kind: "rubric"` for rubric-based evaluation

## Pitfalls

1. **Subagent dispatch race**: After dispatching a SkillOpt run, WAIT for the result before checking state or dispatching another. Checking state mid-run leads to duplicate dispatches.

2. **state.json contamination**: Running a new task set against old state.json produces meaningless baseline scores. Always backup + clear state.json before switching task sets.

3. **CLAUDE.md leak**: `--auto-adopt` generates CLAUDE.md (memory edits). If not deleted, these persist into the next night and contaminate results.

4. **Eval rules are neutral, but review before adopting**: SkillOpt's learned rules (e.g., "Response Completeness Gate", "Response Length Priority") are neutral for real execution — they help eval mode but don't conflict with step-by-step execution. **However**, still review before adopting:
   - Rules that fix real bugs → adopt into main skill body
   - Rules that only help eval mode → keep in `LEARNED` block, don't merge
   - Rules that conflict with real execution → reject

5. **Consolidate hang is NOT fixed by timeout increase or batch splitting**: Increasing `backend.py` timeout from 180s to 600s is INEFFECTIVE — the hang is caused by `claude.exe` crashing at the OS level, not Python timing out. Batch splitting (10 tasks per batch) also does NOT reliably fix it. The issue is likely API-side (rate limiting, model overload). When claude.exe disappears, kill immediately and retry — don't wait 30+ minutes. See `references/consolidate-hang-diagnosis.md` for full diagnosis.

6. **Monitoring cadence when user wants per-night approval**: Do NOT use `process action=poll` or `process action=wait` — they return identical "still running" output and waste turns. Instead:
   - Check filesystem every 5 minutes: `ls -lt .skillopt-sleep/staging/ | head -3`
   - Check claude.exe health at 15 minutes: `tasklist | grep -i claude`
   - If claude.exe is gone → process is DEAD, kill immediately
   - Between checks: DO NOTHING. Do not poll. Do not wait.

6. **Monitoring cadence when user wants per-night approval**: Do NOT use `process action=poll` or `process action=wait` — they return identical "still running" output and waste turns. Instead:
   - Check filesystem every 5 minutes: `ls -lt .skillopt-sleep/staging/ | head -3`
   - Check claude.exe health at 15 minutes: `tasklist | grep -i claude`
   - If claude.exe is gone → process is DEAD, kill immediately
   - Between checks: DO NOTHING. Do not poll. Do not wait.

6. **git revert is too coarse for mixed commits**: When a SkillOpt run produces edits to SKILL.md (eval rules to discard) AND task file additions (to keep), `git revert` undoes EVERYTHING. Lesson from 2026-07-15: commit d85285b contained SKILL.md eval rules + tasks.v1.json field additions + tasks.v2-enhanced.json. Reverting it deleted all three. Fix: use `git checkout <commit>~1 -- <specific-file>` to selectively revert only SKILL.md, keeping task files. Or: separate commits for eval rules vs task additions in the first place.

7. **Commit discipline for SkillOpt runs**: Don't mix SKILL.md eval rule changes with task file additions in one commit. Separate them so reverts are clean. Pattern: (1) commit task files first, (2) run SkillOpt, (3) commit only SKILL.md changes if valid.

## File Reference

- `sync-eval-skill.sh` — Sync script (project root)
- `run-skillopt.sh` — Run wrapper (project root)
- `SKILL-eval.md` — Generated eval skill (gitignored)
- `.skillopt-exp/<skill>/.skillopt-sleep/state.json` — Night state
- `.skillopt-sleep/staging/<timestamp>/report.json` — Night results
