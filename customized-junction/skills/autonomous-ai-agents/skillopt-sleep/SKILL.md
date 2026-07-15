---
name: skillopt-sleep
description: Use SkillOpt-Sleep to optimize an AI agent's skill via black-box task evaluation — baseline failure collection, staged proposal generation, held-out validation, and adopt gate. Covers CLI verification, task design, isolation, and pitfalls.
tags: [skillopt, skill-optimization, claude-code, evaluation, held-out]
---

# SkillOpt-Sleep: Skill Optimization via Sleep Cycles

Use when optimizing a target agent's SKILL.md through iterative failure-driven refinement with SkillOpt-Sleep. The core loop: let the agent fail on black-box tasks → mine failure patterns → generate staged proposals → validate on held-out set → adopt if gate passes.

## When to Load

- User asks to optimize/improve a skill using SkillOpt-Sleep
- User wants to run a sleep cycle against a target SKILL.md
- User asks about task design, baseline evaluation, or held-out validation for skill optimization
- User wants to optimize a computer-use/GUI skill (see "Hybrid Workflow" section)

## ⚡ Quick Reference (READ THIS FIRST)

**Before running, understand this pattern. Do NOT improvise monitoring.**

**📋 DURING EXECUTION: Load `references/monitoring-checklist.md`** — condensed monitoring recipe with exact cadence, anti-patterns, and decision tree. Keep it open during runs to avoid the #1 failure mode (polling process tracker instead of checking filesystem).

**📋 AFTER SUCCESSFUL RUN: Load `references/post-run-workflow.md`** — step-by-step workflow for adopting changes, committing to git, and pushing to remote. Includes commit message template and verification checklist.

### ⛔⛔⛔ PRE-DISPATCH MANDATORY CHECK — DO THIS BEFORE EVERY DISPATCH ⛔⛔⛔

**YOU MUST COMPLETE ALL 3 STEPS BEFORE DISPATCHING A SUBAGENT OR RUNNING DIRECTLY:**

**STEP 1: CHECK SATURATION (non-negotiable)**
```bash
ls -lt .skillopt-sleep/staging/ | head -1
cat .skillopt-sleep/staging/<latest>/report.md | grep "held-out score"
```
**If "1.000 -> 1.000" with "gate: reject" → STOP IMMEDIATELY. You are PHYSICALLY BLOCKED from dispatching. Report to user: "Skill has reached 1.000. Further runs produce no improvement."**

**STEP 2: COUNT YOUR DISPATCHES (enforcement mechanism)**
Before dispatching, ask yourself: "How many subagents have I already dispatched for THIS task?"
- If count >= 1 AND latest result was saturation → **YOU ARE BLOCKED. DO NOT DISPATCH.**
- If count >= 3 regardless of result → **YOU ARE BLOCKED. Switch to direct execution or stop.**
- Only dispatch if count == 0 OR (count < 3 AND no saturation)

**STEP 3: VERIFY NO EXISTING PROCESS (prevent zombie accumulation)**
```bash
ps aux | grep "python.*skillopt" | grep -v grep
```
- If processes found → **DO NOT DISPATCH.** Wait for existing process to complete or kill it first.
- If no processes → proceed to dispatch

**⛔⛔⛔ VIOLATION CONSEQUENCES ⛔⛔⛔**
If you dispatch after seeing saturation:
- You waste 30-60 minutes per dispatch
- You burn API credits for zero value
- You violate the mathematical impossibility of improvement (1.000 cannot exceed 1.000)
- You repeat the exact anti-pattern from 2026-07-15 session (15+ dispatches, 2+ hours wasted)

**This is not a guideline. This is a HARD CONSTRAINT.**

### ⛔⛔⛔ CRITICAL CHECKS — DO THESE FIRST ⛔⛔⛔

**CHECK 1: SATURATION (before dispatching ANY run OR subagent)**
```bash
ls -lt .skillopt-sleep/staging/ | head -1
cat .skillopt-sleep/staging/<latest>/report.md | grep "held-out score"
```
**If "1.000 -> 1.000" with "gate: reject" → STOP. Do NOT dispatch. Do NOT delegate. Report to user: "Skill has reached 1.000. Further runs produce no improvement."**

**⛔ CRITICAL: This check MUST run BEFORE dispatching a subagent, not just before running directly.** Observed 2026-07-15 (twice!): Agent saw 1.000 → 1.000 in staging directory, then dispatched 15+ subagents over 2+ hours, each producing no improvement. The saturation check applies to ALL dispatch paths (direct execution AND subagent delegation).

**CHECK 2: TOOL LOOP DETECTION (during execution)**
If you see "tool loop warning" or "repeated_exact_failure_warning" → **STOP immediately**. You've checked the same thing 2-3+ times. Do NOT retry. Report current state to user and wait for subagent completion.

**CHECK 3: PRE-FLIGHT (before launch)**
Run step 6 of Pre-Flight Checklist: test Claude CLI health. Exit code 2304 = skipped pre-flight = 13+ minutes wasted.

**CHECK 4: CASCADE BREAKER (during execution)**
**ABSOLUTE HARD LIMIT: MAX 3 DISPATCHES PER SESSION for the same SkillOpt run.** This is not a suggestion — it is a hard limit. If you've dispatched 3 subagents and none produced usable results (premature returns, garbled summaries, or saturation), you MUST:
1. **STOP DISPATCHING IMMEDIATELY** — do not attempt a 4th dispatch under any circumstances
2. Check filesystem yourself: `ls -lt .skillopt-sleep/staging/ | head -3`
3. Read the latest `report.md` directly
4. Report whatever you find to the user
5. **SWITCH TO DIRECT EXECUTION** with `terminal(background=true, notify_on_complete=true)`
6. If direct execution also fails after 2 attempts, **STOP COMPLETELY and report to user** — do not continue dispatching

**Enforcement mechanism:** Before each dispatch, count how many subagents you've already dispatched for this task. If the count is >= 3, you are physically blocked from dispatching another. The only way to proceed is to switch to direct execution or stop and report.

**Observed violation 2026-07-15:** Agent dispatched 15+ subagents over 2+ hours, violating this rule 5x over. The cascade breaker must be treated as a hard constraint, not a guideline.

This rule prevented the 2026-07-15 cascade where 15+ subagents were dispatched over 2+ hours producing nothing of value.

**CHECK 5: SUBAGENT DISPATCH LOOP (before dispatching after a failure)**
Before dispatching a subagent AFTER a previous subagent failed or returned prematurely:
1. Check if the PREVIOUS subagent's process is still running: `ps aux | grep "python.*skillopt" | grep -v grep`
2. If a process IS running → the previous subagent may still be working. WAIT for it to complete or timeout (60 minutes max).
3. If NO process is running → check filesystem for results: `ls -lt .skillopt-sleep/staging/ | head -3`
4. Only THEN dispatch a new subagent if: (a) no process running, (b) no results in filesystem, (c) you've waited at least 5 minutes since the last dispatch.

**Anti-pattern observed 2026-07-15:** Agent dispatched subagent A, got "process launched" after 21 seconds. Agent immediately dispatched subagent B. This repeated 15+ times. Meanwhile, the underlying Python process from subagent A was still running and producing valid results. The agent wasted 2+ hours on redundant dispatches instead of waiting for the single process to complete.

**CHECK 6: MONITORING (after launch — READ THIS BEFORE LAUNCHING)**
After launching with `background=true, notify_on_complete=true`:
1. **Wait 5 minutes** (do nothing — consolidation is silent for 20-40 min, this is NORMAL)
2. **Check filesystem**: `ls -lt $PROJECT/.skillopt-sleep/staging/ | head -3`
3. **DO NOT call** `process action=poll`, `process action=wait`, or `process action=log` repeatedly — they return identical "still running" output and waste turns. The process tracker is USELESS during consolidation.
4. **Between filesystem checks: DO NOTHING.** Do not poll. Do not wait. Do not check stdout.
5. **Repeat filesystem check every 5-10 minutes** until `notify_on_complete` fires or staging dir appears.

**⛔ CRITICAL: `process action=wait` timeout is CLAMPED to 180s max by the platform.** Even if you specify `timeout=1800`, it blocks for only 180s and returns nothing new. Each call wastes 180 seconds AND a turn. Observed 2026-07-15: agent called `process action=wait` 6+ times with timeouts of 3600s, 300s, 600s, 180s — all clamped to 180s, all returning identical output. Zero information gained. **The ONLY useful monitoring action is filesystem checks.**

**⛔⛔⛔ ANTI-PATTERNS FROM 2026-07-15 SESSIONS ⛔⛔⛔**
- Session 1: Agent dispatched 15+ subagents after seeing 1.000 → 1.000 (wasted 2+ hours)
- Session 1: Agent called `ls -lt staging/` 20+ times with identical results (tool loop)
- Session 1: Agent never checked saturation before dispatching
- Session 2: Agent called `process action=wait` 3 times (T+69s, T+129s, T+189s), then `process action=poll` at T+408s, then killed at T+500s — never checked filesystem once
- Session 2: Agent killed process after seeing "timed out after 180 seconds" without following kill decision tree (should have checked for claude.exe processes and run pre-flight test)
- **DO NOT REPEAT THESE MISTAKES**

### Before Launch (MANDATORY — DO NOT SKIP)
**Before dispatching ANY run, check if the skill has already reached 1.000:**
```bash
ls -lt .skillopt-sleep/staging/ | head -1
cat .skillopt-sleep/staging/<latest>/report.md | grep "held-out score"
```
**If it shows "1.000 -> 1.000" with "gate: reject" → STOP IMMEDIATELY. Do NOT dispatch another run.** Report saturation to the user and stop. See pitfall #27 for details.

**⛔⛔⛔ CRITICAL: This is the #1 anti-pattern observed in 2026-07-15 session. Agent saw 1.000 → 1.000 with gate=reject, then dispatched 15+ subagents over 2+ hours, producing nothing of value. DO NOT REPEAT THIS. ⛔⛔⛔**

### Before Launch (MANDATORY — DO NOT SKIP)
Run the full Pre-Flight Checklist below — especially **step 6: test Claude CLI health**.
**⛔ Exit code 2304 = skipped pre-flight = 13+ minutes wasted.** Observed 2026-07-15: launched without CLI test, consolidate started, ALL claude calls timed out at 180s, process exited 2304 after 769 seconds with zero staging directories produced. The pre-flight test takes 30 seconds and prevents this exact failure.

### ⛔ Core Execution Model: 1 Command = 1 Night

**Each `skillopt_sleep run` invocation executes exactly ONE night.** Source: `cycle.py:91` — `run_sleep_cycle()` has no loop, returns after one cycle.

**To run multiple nights:**
```bash
# Shell loop (集中训练模式)
for i in {1..5}; do
  echo "=== Night $i ==="
  ANTHROPIC_API_KEY=*** python -m skillopt_sleep run \
    --project "..." --tasks-file "..." --auto-adopt ...
  rm -f CLAUDE.md   # cleanup memory edits (see below)
done

# Or cron (持续优化模式)
0 2 * * * cd /path/to/SkillOpt && ANTHROPIC_API_KEY=*** python -m skillopt_sleep run ...
```

**Night accumulation:** Each night reads the SKILL.md as modified by the previous night's adopt. Night 2's baseline = Night 1's candidate. Improvements accumulate through the file, not through state.json.

## ⛔ Post-Night Cleanup: CLAUDE.md Must Be Deleted

When using `--auto-adopt`, SkillOpt writes memory edits to `CLAUDE.md` in the project root. These are **not** skill edits — they're agent-level memory that pollutes future runs.

**After each night:** `rm -f CLAUDE.md`

**Why:** CLAUDE.md is loaded as "memory" in the replay prompt. If it accumulates rules from previous nights, the agent gets double-instructions (skill + memory say the same thing), wasting tokens and creating conflicts.

## ⛔ State Reset When Switching Task Sets

When running a different tasks file (e.g., switching from tasks.v1.json to tasks.v2-enhanced.json), **backup and delete state.json**:
```bash
cp .skillopt-sleep/state.json .skillopt-sleep/state.json.bak
rm .skillopt-sleep/state.json
```

**Why:** state.json's history is used for gate decisions. Old history from a different task set contaminates baseline/candidate comparisons.

## ⛔ SkillOpt Edits ≠ Real Skill Improvements

SkillOpt generates edits to pass its evaluation framework, not to improve the actual skill workflow. Distinguish:

**SkillOpt-specific edits** (for passing pure-text replay):
- "Force all steps in single response" — replay can't execute tools, so agent must "describe" everything
- "Error Handling must have 2+ concrete scenarios" — rubric scoring requirement
- "Output completeness checklist" — judge needs to see all categories

**Real skill improvements** (genuine workflow fixes):
- Bug fixes (e.g., replace Dispatch cold-start with subprocess.Popen)
- New feature support (e.g., handle new meeting types)
- Performance optimization (e.g., skip GetObject retries)

**SkillOpt edits go in `<!-- SKILLOPT-SLEEP:LEARNED START -->` block** — isolated from original skill content. Review carefully before merging into the main skill body.

## ⛔ Core Execution Model: 1 Command = 1 Night

**Each `skillopt_sleep run` invocation executes exactly ONE night.** Source: `cycle.py:91` — `run_sleep_cycle()` has no loop, returns after one cycle.

**To run multiple nights:**
```bash
# Shell loop (集中训练模式)
for i in {1..5}; do
  echo "=== Night $i ==="
  ANTHROPIC_API_KEY=*** python -m skillopt_sleep run \
    --project "..." --tasks-file "..." --auto-adopt ...
  rm -f CLAUDE.md   # cleanup memory edits (see below)
done

# Or cron (持续优化模式)
0 2 * * * cd /path/to/SkillOpt && ANTHROPIC_API_KEY=*** python -m skillopt_sleep run ...
```

**Night accumulation:** Each night reads the SKILL.md as modified by the previous night's adopt. Night 2's baseline = Night 1's candidate. Improvements accumulate through the file, not through state.json.

## ⛔ Post-Night Cleanup: CLAUDE.md Must Be Deleted

When using `--auto-adopt`, SkillOpt writes memory edits to `CLAUDE.md` in the project root. These are **not** skill edits — they're agent-level memory that pollutes future runs.

**After each night:** `rm -f CLAUDE.md`

**Why:** CLAUDE.md is loaded as "memory" in the replay prompt. If it accumulates rules from previous nights, the agent gets double-instructions (skill + memory say the same thing), wasting tokens and creating conflicts.

## ⛔ State Reset When Switching Task Sets

When running a different tasks file (e.g., switching from tasks.v1.json to tasks.v2-enhanced.json), **backup and delete state.json**:
```bash
cp .skillopt-sleep/state.json .skillopt-sleep/state.json.bak
rm .skillopt-sleep/state.json
```

**Why:** state.json's history is used for gate decisions. Old history from a different task set contaminates baseline/candidate comparisons.

## ⛔ SkillOpt Edits ≠ Real Skill Improvements

SkillOpt generates edits to pass its evaluation framework, not to improve the actual skill workflow. Distinguish:

**SkillOpt-specific edits** (for passing pure-text replay):
- "Force all steps in single response" — replay can't execute tools, so agent must "describe" everything
- "Error Handling must have 2+ concrete scenarios" — rubric scoring requirement
- "Output completeness checklist" — judge needs to see all categories

**Real skill improvements** (genuine workflow fixes):
- Bug fixes (e.g., replace Dispatch cold-start with subprocess.Popen)
- New feature support (e.g., handle new meeting types)
- Performance optimization (e.g., skip GetObject retries)

**SkillOpt edits go in `<!-- SKILLOPT-SLEEP:LEARNED START -->` block** — isolated from original skill content. Review carefully before merging into the main skill body.

## ⛔ Dispatch-Wait Pitfall: One Subagent at a Time

**Problem**: After dispatching subagent A for a SkillOpt run, checking status too early (before result returns), misinterpreting "no result yet" as "didn't start", then dispatching subagent B — creating duplicate runs.

**Rule**: After dispatching a subagent, WAIT for the completion notification. Do NOT check status and re-dispatch just because the result hasn't arrived yet. Subagents run in background — the result WILL come back as a new message.

**Anti-pattern observed 2026-07-15**: Dispatched deleg_d08b0e95 for V1 test, immediately checked state.json (still empty because subagent hadn't finished), assumed it didn't start, backed up state.json and dispatched deleg_dc1f6876 — creating a second V1 run from a different starting point.

## ⛔ Consolidate Hang: claude.exe Disappears (NOT a Python Timeout)

**Problem**: Consolidate phase hangs indefinitely. Process shows "running" but produces no output for 30+ minutes. No new staging directories.

**Root cause (confirmed 2026-07-15)**: The Claude CLI process (`claude.exe`) **disappears/crashes** during consolidate. The Python process stays alive but stuck waiting for a dead subprocess. This is NOT a Python `subprocess.run(timeout=...)` issue — increasing timeout from 180s to 600s does NOT help because the real failure is claude.exe vanishing, not Python timing out.

**Diagnosis** (run when process seems stuck for 15+ min):
```bash
tasklist | grep -i claude    # if EMPTY → claude.exe crashed → process is DEAD
ps aux | grep python         # if present → Python alive but waiting for dead child
```

**Decision tree**:
- claude.exe PRESENT + Python PRESENT → still working, wait
- claude.exe ABSENT + Python PRESENT → **DEAD**, kill immediately
- Both ABSENT → already exited, check staging dirs

**Timeout increase (180s → 600s) is INEFFECTIVE** for this failure mode. The `subprocess.run(timeout=600)` in `backend.py` only catches Python-level timeouts. When claude.exe crashes at the OS level, the subprocess call never returns — it hangs forever regardless of timeout setting.

**Batch splitting (10 tasks per batch) also does NOT reliably fix this.** Observed 2026-07-15: 10-task batch hung for 18+ minutes, claude.exe disappeared. The issue may be API-side (rate limiting, model overload) rather than task count.

**What to do when consolidate hangs**:
1. Kill the process immediately (don't wait 30+ minutes)
2. Check if any staging dir was produced (partial results may exist)
3. Retry — the hang is often transient (API/model availability)
4. If it hangs again, try a different `--model` or off-peak hours

### ⛔ 180s Timeout IS Sufficient for Single Calls (confirmed 2026-07-15)

**Evidence from today's session**: V2-subset (3 tasks, same structure as V2 full) completed all 13 Claude CLI calls without timeout. Max prompt size was 37K chars, max response was 28K chars. Each call took 10-30 seconds.

**V2 full (15 tasks) timeout on Night 10 was TRANSIENT**:
- Night 10 (23:10): First call timed out after 180s → run failed
- Night 16 (05:00): Same parameters → **completed successfully** (baseline=1.0, candidate=1.0)

**Conclusion**: 180s per-call timeout is adequate. The timeout was caused by transient API/network issues, not systematic prompt-size problems.

### ⛔ Call Count Determines Run Time (Not Prompt Size)

**V1 (3 tasks) vs V2-subset (3 tasks) timing difference**:
- V1: 6 calls, ~2 min (all pass → no failures → skip reflect → done)
- V2-subset: 13 calls, ~7 min (failures → reflect → gate scoring)

**CORRECTED call count formula** (verified with V3 run, 42 calls):
```
Phase 1: Baseline scoring (val)       = 2 × n_val
Phase 2: Replay train (skill evolve)  = 2 × n_train
Phase 3: Reflect (skill)              = 1
Phase 4: Gate apply (skill)           = 2 × n_val
Phase 5: Replay train (memory evolve) = 2 × n_train
Phase 6: Reflect (memory)             = 1
Phase 7: Gate apply (memory)          = 2 × n_val
Phase 8: Final scoring (val)          = 2 × n_val

Total: 6 × n_val + 4 × n_train + 2
```

**Why train is replayed TWICE**: Skill evolution happens first (Phase 2), then memory evolution (Phase 5) re-evaluates under the improved skill. This sequential approach isolates skill-level vs memory-level improvements.

**Why val is scored THREE times**: Baseline (Phase 1) establishes reference, gate skill (Phase 4) validates skill edits, gate memory (Phase 7) validates memory edits, final (Phase 8) confirms final score.

**For V3 (7 train + 2 val)**: 6×2 + 4×7 + 2 = **42 calls** ✓
**For 15 tasks (10 train + 3 val + 2 test)**: 6×3 + 4×10 + 2 = **62 calls**

**Run time**: 42 calls × 10-30s = 7-21 minutes. V3 actual: ~10 minutes.

**Prompt sizes** (from V3 logs):
- attempt: ~34-35K chars (skill + task + memory)
- judge: ~1-1.5K chars (rubric + response)
- reflect: ~37K chars (skill + failures + successes)
- gate judge: ~6K chars (larger rubric + response)

**Implication**: Large task sets have longer run times due to serial call count. Prompt size per call is NOT the bottleneck (37K prompts complete in 10-30s). If a run times out, retry — it's likely transient API slowness.

**See `references/consolidate-call-chain.md` for full phase-by-phase breakdown with V3 example.**

## ⛔ Batch Script for Large Task Sets

**Problem**: 20+ tasks in a single run can cause consolidate phase to timeout or hang.

**Solution**: `run-skillopt-batch.sh` splits tasks into batches:
```bash
./run-skillopt-batch.sh .skillopt-exp/.../tasks/tasks.v2.json 10
# → Creates 2 batches of 10 tasks each
# → Runs each batch as a separate night
# → Auto-syncs SKILL-eval.md before each batch
# → Deletes CLAUDE.md after each batch
```

The script creates temp JSON files with subset of tasks, runs each through SkillOpt, and pauses between batches for review.

## ⛔ Eval Rules Isolation: SKILL-eval.md Pattern

**Problem**: SkillOpt eval rules (forcing single-response output, step structure) pollute the original SKILL.md and conflict with real execution mode (step-by-step tool calls).

**Solution**: Use a separate SKILL-eval.md for evaluation:

```bash
# sync-eval-skill.sh — run before each SkillOpt execution
cp SKILL.md SKILL-eval.md
cat << 'EOF' >> SKILL-eval.md
<!-- SKILLOPT EVAL RULES START -->
## SkillOpt 评估专用规则（不影响真实执行）
1. 输出完整性要求：必须在单个response中描述完整工作流
2. 步骤结构要求：每个步骤必须包含4个元素
3. 日期处理要求：相对日期必须显式转换为绝对YYYY-MM-DD格式
<!-- SKILLOPT EVAL RULES END -->
EOF

# run-skillopt.sh — wrapper that auto-syncs
./sync-eval-skill.sh
python -m skillopt_sleep run --target-skill-path ".../SKILL-eval.md" ...
```

**Key rules**:
- SKILL-eval.md is in .gitignore (generated file)
- Original SKILL.md stays clean (no eval rules)
- After SkillOpt run, manually merge useful edits from SKILL-eval.md to SKILL.md if applicable

## ⛔ Git Revert Pitfall: Preserve Task Files

**Problem**: When reverting a SkillOpt commit that includes both SKILL.md changes AND new task files, `git revert` deletes everything — including valuable task files.

**Solution**: Before reverting, identify which files to preserve:
```bash
# Check what the commit contains
git show <commit> --stat

# If it includes task files you want to keep:
# 1. Revert only SKILL.md changes
git checkout <commit>~1 -- path/to/SKILL.md
git commit -m "Revert SKILL.md eval rules (preserve task files)"

# 2. Or manually restore task files after revert
git show <commit>:path/to/tasks.v2.json > path/to/tasks.v2.json
git add path/to/tasks.v2.json
git commit -m "Restore task files"
```

**Observed 2026-07-15**: `git revert d85285b` deleted tasks.v2-enhanced.json (20 tasks) along with SKILL.md eval rules. Had to manually restore from commit history.

## ⛔ Multi-Night Approval Workflow

**User preference**: Review each night's results before proceeding to the next night.

**Pattern**:
```bash
# Night 1
./sync-eval-skill.sh
python -m skillopt_sleep run --target-skill-path ".../SKILL-eval.md" ...
# → Wait for completion, read report.md
# → Present results to user for approval
# → User approves → proceed to Night 2

# Night 2
./sync-eval-skill.sh  # Re-sync to pick up Night 1's adopted changes
python -m skillopt_sleep run --target-skill-path ".../SKILL-eval.md" ...
# → Wait for completion, read report.md
# → Present results to user for approval
# ...
```

**Key points**:
- Do NOT use shell loop for multi-night runs when user wants per-night approval
- After each night, delete CLAUDE.md: `rm -f CLAUDE.md`
- Re-sync SKILL-eval.md before each night to pick up adopted changes
- Present staging report to user before proceeding

## Launch
```bash
ANTHROPIC_API_KEY=*** python -m skillopt_sleep run \
  --project "PATH" --claude-home "PATH" \
  --target-skill-path "PATH" --tasks-file "PATH" \
  --backend claude --max-tasks 20 --edit-budget 4 \
  --auto-adopt --progress --json
```
Use `terminal(background=true, notify_on_complete=true, timeout=3600)`.

**Important**: Always include `--auto-adopt` so nights inherit improvements. Results stay in staging directories until user approves commit (see `references/iron-rules.md`).

**⚠️ Remember: This runs exactly 1 night.** For multiple nights, use a shell loop (see "Core Execution Model" section above).

**⚠️ Remember: This runs exactly 1 night.** For multiple nights, use a shell loop (see "Core Execution Model" section above).

**Windows/git-bash**: Use `cd "D:/workspace/SkillOpt"` (POSIX), NOT `cd /d D:\\workspace\\SkillOpt` (cmd.exe syntax — fails with "bash: cd: too many arguments").

---

## ⛔⛔⛔ MONITORING CHEAT SHEET — READ THIS FIRST ⛔⛔⛔

**After launching, DO THIS:**
```
T+0:   terminal(background=true, notify_on_complete=true)  ← LAUNCH
T+5m:  terminal("ls -lt $PROJECT/.skillopt-sleep/staging/ | head -3")  ← CHECK FILESYSTEM
T+10m: terminal("ls -lt $PROJECT/.skillopt-sleep/staging/ | head -3")  ← CHECK FILESYSTEM
T+15m: terminal("ls -lt $PROJECT/.skillopt-sleep/staging/ | head -3")  ← CHECK FILESYSTEM
...continue every 5-10 min until notify_on_complete fires
```

**NEVER DO THIS:**
- ❌ `process action=poll` (wastes turns, returns identical output)
- ❌ `process action=wait timeout=60` (wastes 60 seconds, returns nothing new)
- ❌ `process action=log` repeatedly (stdout doesn't change during consolidate)

**THE ONLY USEFUL ACTION IS FILESYSTEM CHECKS.** The process tracker is USELESS during consolidation (20-40 minutes of silence is NORMAL).

**Anti-pattern observed 2026-07-15 (twice!):** Agent launched run, then called `process action=poll` or `process action=wait` **16+ times over 20 minutes**. Each call returned identical "still running" output. The agent burned 16 turns producing zero information. A single filesystem check at T+5m would have revealed the staging directory immediately. **DO NOT REPEAT THIS MISTAKE.**

---

## ⛔ MONITORING — READ THIS IMMEDIATELY AFTER LAUNCH ⛔

**DO NOT call `process action=poll` or `process action=wait` repeatedly.** They return identical "still running" output and waste turns. The process tracker is USELESS during consolidation (20-40 minutes of silence is NORMAL).

**The ONLY useful monitoring action is filesystem checks:**
```bash
# Check for new staging directories (updated every night cycle):
ls -lt "$PROJECT/.skillopt-sleep/staging/" | head -3

# Check state.json mtime (most reliable — updated at start of each night):
stat "$PROJECT/.skillopt-sleep/state.json" | grep Modify
```

**Correct monitoring cadence:**
- T+0: Launch with `background=true, notify_on_complete=true`
- T+5m: `terminal("ls -lt $PROJECT/.skillopt-sleep/staging/ | head -3")`
- T+10m: Same check
- T+15m: Same check
- Continue every 5-10 minutes until `notify_on_complete` fires

**BETWEEN filesystem checks: DO NOTHING.** Do not poll. Do not wait. Do not check stdout. The process tracker is ONLY useful for the final "did it exit?" check after `notify_on_complete` fires.

**Consolidate phase (15-20+ min, no filesystem changes):** See `references/consolidate-phase-monitoring.md` for how to verify the process is working when staging dirs and state.json are silent.

**Anti-pattern observed 2026-07-15:** Agent launched run, then called `process action=poll` or `process action=wait timeout=60` **16+ times over 20 minutes**. Each call returned identical "still running" output. The agent burned 16 turns producing zero information. A single filesystem check at T+5m would have revealed the staging directory immediately. **After launching, wait 5 minutes, then check filesystem — NOT process tracker.**

---

### Monitor (correct pattern)
```
T+0:   Launch with background=true, notify_on_complete=true
T+5m:  terminal("stat $PROJECT/.skillopt-sleep/state.json | grep Modify")
       ### Monitor (correct pattern)
       ```
       T+0:   Launch with background=true, notify_on_complete=true
       T+5m:  terminal("ls -lt $PROJECT/.skillopt-sleep/staging/ | head -3")
       T+10m: terminal("ls -lt $PROJECT/.skillopt-sleep/staging/ | head -3")
       T+15m: terminal("ls -lt $PROJECT/.skillopt-sleep/staging/ | head -3")
       ...continue every 5-10 min until notify_on_complete fires

       ⛔ BETWEEN CHECKS: DO NOT call process action=poll or process action=wait.
          They return identical "still running" output and waste turns.
          The filesystem check is the ONLY useful monitoring action.

       ⛔ TOOL LOOP DETECTION: If you get a tool loop warning (e.g., "repeated_exact_failure_warning"
          or "idempotent_no_progress_warning"), STOP immediately. This means you've checked the same
          thing 2-3+ times with identical results. Do NOT retry the same check. Instead:
          1. Report the current state to the user (what you've observed so far)
          2. If waiting for a subagent: say "Waiting for subagent completion notification"
          3. If the process is done: read the latest staging dir and report results
          4. Do NOT dispatch another subagent just because you're stuck in a loop
       ```

### What NOT to do
- ❌ `process action=wait timeout=60` in a loop (wastes turns, stdout never changes)
- ❌ `process action=poll` every 60 seconds (same waste)
- ❌ `process action=log` repeatedly (same waste — stdout doesn't change during consolidate)
- ❌ Kill process because stdout is silent (consolidate is silent for 20-40 min — NORMAL)
- ❌ Kill process because of "timed out after 180 seconds" messages (usually NON-FATAL)

**Exception**: Timeout messages ARE fatal if you skipped the pre-flight CLI test (step 6) and the CLI is completely non-functional. If you ran the pre-flight test and it passed, timeout messages during the run are non-fatal — the run can still succeed. If you didn't run the pre-flight test and see timeouts, the CLI may be broken — check with the pre-flight test before killing.

### How to know when done
- `notify_on_complete` fires → process exited → run is done
- OR: `ps -p <PID>` returns empty → process gone
- Then: read `.skillopt-sleep/staging/<latest-timestamp>/report.md`

### Where to find results
```bash
# FASTEST PATH — log file has full JSON output (no need to find staging dir):
cat "$EXP_ROOT/skillopt-run-full.log"
# OR for older runs: tail -100 "$EXP_ROOT/logs/skillopt-run-*.log"
# The log contains the complete JSON report including all rejected edits with rationale.

# Alternative — staging directory:
ls -lt .skillopt-sleep/staging/ | head -1  # latest staging dir
cat .skillopt-sleep/staging/<timestamp>/report.md
```

### When a run fails (exit code ≠ 0 or hangs)
**Check these in order** (do NOT poll stdout repeatedly):
1. **Log file** (most diagnostic value):
   ```bash
   tail -30 "$EXP_ROOT/logs/skillopt-run-*.log"
   ```
   Look for: "timed out after 180 seconds", Python tracebacks, API errors
2. **state.json** (last successful night):
   ```bash
   python -c "import json; d=json.load(open('$PROJECT/.skillopt-sleep/state.json')); print(f'night={d[\"night\"]}, baseline={d.get(\"baseline_score\")}, candidate={d.get(\"candidate_score\")}')"
   ```
3. **Staging dirs** (any new output since launch?):
   ```bash
   ls -lt "$PROJECT/.skillopt-sleep/staging/" | head -3
   ```
4. **Python process** (is it actually alive?):
   ```bash
   tasklist.exe | findstr python.exe   # Windows
   ps aux | grep "python.*skillopt"    # Linux/Mac
   ```

**Common failure: exit code 2304** = all Claude CLI calls timed out during consolidate. See pitfall #24. Usually caused by `--model sonnet` routing to slow endpoint. Fix: remove `--model sonnet` from claude settings or run during off-peak hours.

**For edge cases (zombie processes, tracker reporting dead PID as running, etc.), see Pitfalls #15-#21 below.**

### Partial evaluation after CLI timeout (degraded but not dead)

**Symptoms:**
- Claude CLI timeout message appears in log (e.g., "timed out after 180 seconds")
- Process is still running after 20+ minutes
- Only some tasks were evaluated (e.g., 3 instead of 20)
- No new staging directories appeared after the initial timeout
- Latest staging dir shows `n_tasks: 3` instead of requested 20

**Diagnosis:**
1. Check if process is still alive: `ps aux | grep "python.*skillopt" | grep -v grep`
2. Check latest staging dir: `ls -lt .skillopt-sleep/staging/ | head -1`
3. Read report: `cat .skillopt-sleep/staging/<latest>/report.json`
4. Check `n_tasks` field — if less than requested, partial evaluation occurred

**Decision tree:**
- If process is still running AND no new staging dirs after 30+ minutes → **degraded run**, likely won't recover
- If `n_tasks` in latest staging < requested tasks → **partial evaluation**, some tasks failed
- If baseline_score == candidate_score AND no edits → **no improvement possible**, run is wasted

**Action:**
- DO NOT kill immediately — wait for `notify_on_complete` or 60 minutes
- When process exits, read the latest staging dir's `report.md`
- If `accepted: false` AND `n_tasks < requested` → **degraded run**, diagnose CLI health before retrying
- Run pre-flight CLI test (step 6) before next attempt

**Root cause:** Usually Claude CLI timeout on one or more tasks during consolidate phase. The process continues but skips failed tasks, resulting in partial evaluation. Observed 2026-07-15: process ran 30+ minutes, evaluated only 3/20 tasks, produced no edits.

## Architecture & Limitations

**SkillOpt-Sleep is a workflow orchestrator, NOT an LLM.** It delegates all LLM inference to external CLI backends:

```
Driver (Hermes / cron / manual)
  ↓
SkillOpt-Sleep (Python workflow)
  ↓
External CLI backend
  ├─ claude -p (Claude Code CLI, text mode)
  ├─ codex exec (OpenAI Codex CLI)
  └─ copilot / mock
  ↓
LLM API (Anthropic / OpenAI / etc.)
```

**No LLM configuration in SkillOpt itself.** Just needs `ANTHROPIC_API_KEY` env var for claude backend. Config resolution: `DEFAULTS` → `~/.skillopt-sleep/config.json` → CLI overrides.

### Critical: Pure-Text Replay

The `claude` backend invokes `claude -p` in **isolated text-only mode** (`backend.py:618-630`):

```python
cmd = [self.claude_path, "-p", "--output-format", "text"]
cmd += [
    "--disable-slash-commands",      # no skill loading
    "--disallowedTools", "*",        # no tools at all
    "--exclude-dynamic-system-prompt-sections",
]
# cwd = temp directory, no project CLAUDE.md
```

Skill text is injected via prompt concatenation (`backend.py:680-690`):
```python
prompt = f"# Skill\n{skill}\n\n# Memory\n{memory}\n\n# Task\n{task.intent}\n\nReturn ONLY the final answer text."
```

**Consequence:** Cannot verify computer-use / GUI skills. Replay only evaluates whether the response text describes correct steps — it cannot execute GUI operations, call APIs, or produce real-world side effects.

## Hybrid Workflow for Computer-Use Skills

When the target skill drives GUI operations (e.g., Outlook + Tencent Meeting), use a two-part approach:

### Part A: SkillOpt Text Optimization
Optimize skill text quality via pure-text replay. **Rubric must be text-based** (describes correct steps), NOT execution-based (requires actual GUI success).

**Critical design principle**: For CUA skills evaluated via pure-text replay, the target skill must define a structured response format that forces the agent to show understanding at each step. See `references/response-structure-pattern.md` for the per-step response structure (state awareness, goal, method, error handling).

**Text-based rubric example:**
```text
PASS if response describes correct steps in order:
  1) Launch Outlook Classic (not new Outlook)
  2) Create New Meeting/Event
  3) Fill attendees field with correct email
  4) Set correct date/time
  5) Set correct subject
  6) Add Tencent Meeting info (join link/ID/password)
  7) Verify all fields before send
  8) Send the invite
FAIL if any step is missing, out of order, or incorrect.
```

### Part B: Hermes-Driven GUI Verification
After SkillOpt adopt, Hermes drives Claude Code computer-use sessions to verify actual GUI execution. Human + Hermes co-evaluate.

```
Part A: ① baseline → ② tasks_file → ③ dry-run → ④ run → ⑤ review → ⑥ go/no-go → ⑦ adopt
  ↓
Part B: ⑧ Hermes GUI test → ⑨ co-evaluate
  ↓
FAIL → analyze → back to Part A or manual fix
```

**GUI test rubric example:**
```text
PASS if:
- Outlook Classic 启动成功
- 会议邀请创建成功
- 所有字段正确（收件人、时间、主题）
- 腾讯会议信息已添加
- 邮件已发送（白名单地址）
- Sent Items 有记录
```

## Prerequisites

Verify SkillOpt-Sleep is installed and CLI params exist:

```bash
cd /path/to/SkillOpt
python -m skillopt_sleep --help
python -m skillopt_sleep run --help   # check --target-skill-path, --tasks-file, --backend, --claude-home
```

Key CLI params (confirmed present as of 2026-07):
- `--project PATH` — project root
- `--claude-home PATH` — isolates state (overrides ~/.claude)
- `--target-skill-path PATH` — the live SKILL.md to evolve
- `--tasks-file PATH` — reviewed TaskRecord JSON
- `--backend {mock,claude,codex,copilot,handoff}`
- `--edit-budget N` — max edits per cycle
- `--max-tasks N` — cap tasks per run
- `--staging PATH` — for adopt command

## Isolation Setup

```bash
PROJECT='/path/to/target-project'
TARGET_SKILL='/path/to/target-project/.claude/skills/.../SKILL.md'
EXP_ROOT='/path/to/target-project/.skillopt-exp/<skill-name>'
CLAUDE_HOME_EXP="$EXP_ROOT/claude-home"
TASKS_FILE="$EXP_ROOT/tasks/tasks.v1.json"

mkdir -p "$EXP_ROOT"/{baseline,logs,tasks,runs,reports,candidates,claude-home}

# Save baseline
cp "$TARGET_SKILL" "$EXP_ROOT/baseline/SKILL.baseline.md"
sha256sum "$TARGET_SKILL" > "$EXP_ROOT/baseline/SKILL.baseline.sha256"
```

**Windows/git-bash note**: Use POSIX syntax for `cd`: `cd "D:/workspace/SkillOpt"` (NOT `cd /d D:\workspace\SkillOpt` which is cmd.exe syntax and fails with "bash: cd: too many arguments" in git-bash).

## Task Design Rules

1. **Black-box**: tasks describe user goals only, never mention internal fixes or known root causes
2. **Result-oriented**: PASS/FAIL based on observable outcomes, not process
3. **No leakage**: if optimizing Claude Code's skill from Hermes findings, never write Hermes conclusions into task intent, reference, judge, or context
4. **Splits**: train (~66%), val (~17%), test (~17%). With `holdout_fraction=0.34`, roughly 34% goes to holdout (val+test). Test stays OUT of tasks_file — saved separately for final human validation
5. **Minimum viable**: 12-20 tasks total. If <10, collect more baseline failures first
6. **Pilot first**: run 3-5 baseline tasks before committing to full task set — confirms failures exist and are classifiable
7. **Dimension diversity > task count**: Each task should test a **different capability dimension**, not just more variations of the same thing. Observed 2026-07-15: V1 (3 tasks) and V2 (20 tasks) both tested date conversion + workflow structure—just with different dates/names. V3 tested 11 dimensions (multi-recipient, all-day events, vague requests, cross-timezone, location handling, recurring, colloquial input, room booking) with 3 regression baselines. **Result**: V3 baseline was 6.25% (vs V2's 100%), but optimization produced +900% improvement and found real blind spots. V1/V2 produced 0% improvement because they had nothing left to learn. **Diversity catches real skill blind spots; quantity just reinforces what you already know.** See `references/task-design-v3-case-study.md` for full V3 design and results.

### TaskRecord Schema

```json
{
  "id": "task-001",
  "project": "/path/to/project",
  "intent": "User-visible goal description only",
  "context_excerpt": "Visible inputs and acceptance criteria, no internal fixes",
  "system": "",
  "attempted_solution": "",
  "outcome": "unknown",
  "reference_kind": "rubric",
  "reference": "PASS only if ... FAIL if ...",
  "judge": {},
  "tags": [],
  "source_sessions": [],
  "split": "train",
  "origin": "real",
  "derived_from": ""
}
```

### Tasks File Outer Wrapper

```json
{
  "format": "skillopt_sleep.tasks.v1",
  "project": "/path/to/project",
  "transcript_source": "claude-code-manual-reviewed",
  "n_sessions": 0,
  "target_skill_path": "/path/to/SKILL.md",
  "reviewed": true,
  "tasks": [...]
}
```

**Critical**: `reviewed: true` is required — the real backend refuses unreviewed tasks (`__main__.py:153`).

## Execution Flow

**There is NO separate "baseline runs" phase.** The cycle is:
```
harvest → mine → replay → consolidate(gate) → stage → optional adopt
```
Replay IS the evaluation — it runs tasks through the backend and scores them.

### 1. Dry-Run

```bash
python -m skillopt_sleep dry-run \
  --project "$PROJECT" \
  --claude-home "$CLAUDE_HOME_EXP" \
  --target-skill-path "$TARGET_SKILL" \
  --tasks-file "$TASKS_FILE" \
  --backend mock --progress --json
```

Confirms: schema validity, path resolution, no live skill modification.

### 2. Generate Proposal

Prefer `claude` backend for automation; `handoff` if human-in-loop needed.

**When running via Hermes terminal**: use `background=true` + `notify_on_complete=true`. The `pty=true` flag is NOT required on most environments — only add it if you observe TTY-related errors (`tcsetattr`, `Inappropriate ioctl`). Expect 30-60 minutes total; the consolidate phase alone takes 20-40 minutes with no stdout output (see Pitfall #15).

**Exact Hermes terminal() call syntax:**
```python
terminal(
    command="ANTHROPIC_API_KEY=*** python -m skillopt_sleep run ...",
    background=True,
    notify_on_complete=True,
    timeout=3600
)
```

```bash
ANTHROPIC_API_KEY=*** python -m skillopt_sleep run \
  --project "$PROJECT" \
  --claude-home "$CLAUDE_HOME_EXP" \
  --target-skill-path "$TARGET_SKILL" \
  --tasks-file "$TASKS_FILE" \
  --backend claude \
  --max-tasks 20 --edit-budget 4 --progress --json
```

Handoff mode: if exit code 3, answer prompts in `.skillopt-sleep-handoff/PROMPTS.md`, write answers to `answers/<sha256[:16]>.md`, re-run same command. **Use fresh context for answers** — do not leak cross-session knowledge.

### 3. Review Staged Proposal

```bash
python -m skillopt_sleep status \
  --project "$PROJECT" \
  --claude-home "$CLAUDE_HOME_EXP" \
  --target-skill-path "$TARGET_SKILL"

STAGING='/path/to/.skillopt-sleep/staging/<timestamp>'
diff -u "$TARGET_SKILL" "$STAGING/proposed_SKILL.md"
```

**Must reject** proposals that:
- Contain names/paths/conclusions from the optimizing agent (information leakage)
- Hardcode test task answers or task IDs
- Remove safety/verification/reporting constraints
- Allow unverified success claims
- Modify files outside the target skill
- Are too large to audit (full rewrites)

### 4. Held-Out Evaluation

SkillOpt-Sleep automatically splits tasks into train/val/test via `holdout_fraction` (default 0.34). The consolidate stage evaluates on val for gating and test for final scoring. No manual sandbox setup needed.

### 5. Adopt

```bash
python -m skillopt_sleep adopt \
  --project "$PROJECT" \
  --claude-home "$CLAUDE_HOME_EXP" \
  --target-skill-path "$TARGET_SKILL" \
  --staging "$STAGING"
```

Adopt criteria: gate accepted + human review passed + test split达标 + no regression + no info leakage + no hardcoded answers.

## Replay Mechanism Deep Dive

### Three-Step Evaluation Process

Each task goes through 3 stages, each is a separate `claude -p` call:

**Step 1: attempt** (`backend.py:371-378`) — Claude reads skill + task, returns text description:
```
Complete the following task for the user. Follow the skill and memory guidance...

# Skill
<skill full text 455 lines>

# Memory
<memory text>

# Task
<task.intent>

Return ONLY the final answer text, nothing else.
```

**Step 2: judge** (`backend.py:397-413`) — Claude scores the response against rubric:
```
Score how well the response satisfies the rubric, 0..1.
Return ONLY JSON {"score": <0..1>, "reason": "..."}.

# Rubric
<task.reference>

# Response
<step 1 response>
```
score >= 0.8 → hard=1 (PASS), else hard=0 (FAIL)

**Step 3: consolidate** — Compare baseline vs candidate:
```
baseline_score = mean(all tasks with original skill hard scores)
candidate_score = mean(all tasks with modified skill hard scores)
```
If candidate_score > baseline_score → gate passes → proposed_SKILL.md generated

**Cost: 4 LLM calls per task** (attempt_v1, judge_v1, attempt_v2, judge_v2)

### Claude's Isolation

Claude does NOT know it's being used by SkillOpt. Each `claude -p` call is an isolated session with:
- `--bare` (minimal system prompt)
- `--disable-slash-commands` (no skill loading)
- `--disallowedTools *` (no tools)
- `--exclude-dynamic-system-prompt-sections`
- cwd = temp directory (no project CLAUDE.md)

Claude plays 3 different roles across calls:
1. **attempt**: thinks it's an assistant completing a task
2. **judge**: thinks it's a grader evaluating text
3. **reflect**: thinks it's a skill author improving documentation

No cross-call memory. Each call is independent.

### LLM Dependency

Pure-text training effectiveness depends heavily on the LLM's comprehension ability:

- **attempt stage**: Different LLMs parse skill instructions with varying precision (ambiguity handling, step ordering, detail capture)
- **judge stage**: Different LLMs have different strictness levels (some FAIL on missing keywords, others PASS on semantic match)
- **reflect stage**: Different LLMs produce different quality edit proposals from the same failure patterns

**Implication**: Use the same LLM for training as the target execution environment. Training with Claude for a Claude Code skill maintains consistency.

**Essence**: Replay is "reading comprehension + simulated execution" — Claude reads the skill, mentally walks through the GUI steps, and describes what it would do. It never actually executes anything.

## Reference Files
## References

- `references/iron-rules.md` — **必读**：5 条铁律（禁止自动 commit、独立分支训练、继承模式、活动隔离、rubric-skill 对齐）
- `references/pitfalls.md` — 30+ 个已观察到的陷阱和反模式（监控错误、僵尸进程、饱和检测等）
- `references/response-structure-pattern.md` — **CUA skill 纯文本评估**：目标 skill 必须定义每步响应结构（状态认知、目标、方法、错误处理），rubric 评估这些要素是否完整
- `references/cli-examples.md` — Verified working CLI commands and directory structure convention
- `references/long-running-sleep-cycles.md` — Subagent delegation pattern, timeout handling, zombie process cleanup, and multi-staging verification for 30-60 minute runs
- `references/task-review-workflow.md` — **Pre-run task review + environment isolation + post-run strength evaluation**
- `references/consolidate-call-chain.md` — **Full 8-phase call chain with V3 example (42 calls)**, prompt sizes, and debugging commands
- `references/runtime-diagnostics.md` — **Debug logging pattern** (add to `ClaudeCliBackend._call()`), diagnostic grep commands, call count formula, and common issues (timeout, V1 vs V2 performance, large responses)

## Pre-Flight Checklist (run before EVERY SkillOpt execution)

```
□ 0. Check for saturation (MUST run before dispatching):
     python -c "import json; d=json.load(open('$PROJECT/.skillopt-sleep/state.json')); print(f'night={d[\"night\"]}, baseline={d.get(\"baseline_score\", d.get(\"history\", [{}])[-1].get(\"baseline\", \"N/A\"))}')"
     → If baseline=1.000 in the latest history entry → STOP. Do NOT dispatch.
     → Report saturation to user: "Skill has reached 1.000 on the current task set. Further runs will produce gate=reject. To improve further, expand the task set with harder/more diverse tasks."
     → See pitfall #27 for full details.

□ 1. Kill all existing processes (MUST run before every launch):
     Linux/Mac:
       ps aux | grep "python.*skillopt" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null
     Windows/git-bash (pkill NOT available, xargs kill may fail):
       ps -ef | grep "python.*skillopt" | grep -v grep | awk '{print $2}' | while read pid; do taskkill //F //PID $pid 2>/dev/null; done
     Alternative Windows (manual):
       ps -ef | grep "python.*skillopt" | grep -v grep
       → then: taskkill //F //PID <pid1> //PID <pid2> ...
     Verify (all platforms): ps -ef | grep "python.*skillopt" | grep -v grep | wc -l  →  must be 0
     ⚠️ NOTE: `pkill` is NOT available on Windows/git-bash. Do NOT use it.

□ 2. Verify baseline freshness:
     cat .skillopt-exp/<skill>/baseline/git-head.txt
     git rev-parse HEAD
     → Must match

□ 2a. Rubric-skill alignment check (if skill was modified):
     → If you modified the target skill since last run, verify rubric evaluates new requirements
     → Check: Does rubric reference the new skill requirements? (e.g., "Response Structure Rule", new constraints)
     → If no → Update tasks file rubric before running
     → See iron-rules.md Rule 5 for details

□ 3. Verify tasks file:
     python -c "import json; d=json.load(open('tasks.v2.json')); print(f'Tasks: {len(d[\"tasks\"])}, Reviewed: {d.get(\"reviewed\")}')"
     → Must show reviewed=True and correct task count

□ 4. Record current timestamp:
     date +%s
     → Save this. After run, verify new staging dir timestamp > this value.

□ 5. Set ANTHROPIC_API_KEY:
     echo $ANTHROPIC_API_KEY
     → Must be non-empty (even placeholder triggers --bare)

□ 6. Test Claude CLI health (MANDATORY):
     echo "ping" | timeout 30 claude -p --output-format text --bare \
       --disable-slash-commands --disallowedTools '*' \
       --exclude-dynamic-system-prompt-sections --model sonnet 2>&1 | head -5
     → Must return text within 30 seconds. If hangs/times out → DO NOT launch.
     → Fix Claude CLI first (check network, credentials, kill zombie processes).
     → See pitfall #22 for full troubleshooting.

□ 7. Dispatch ONCE and wait:
     delegate_task(goal="Execute SkillOpt run...", context="...")
     → Do NOT dispatch again until subagent reports OR 60 minutes pass.
     → If subagent reports failure: check filesystem FIRST (pitfall #21).
```

## Reading Results from state.json (FASTEST PATH for multi-night runs)

**Quick triage via manifest.json**: Each staging directory contains `manifest.json` with three key fields:
- `accepted: true/false` — whether this night's edits were adopted
- `has_skill: true/false` — whether SKILL.md was modified
- `has_memory: true/false` — whether agent memory was modified

This lets you quickly assess a staging dir without reading the full `report.md`:
```bash
cat .skillopt-sleep/staging/<timestamp>/manifest.json
# {"live_skill_path": "...", "live_memory_path": "...", "has_skill": true, "has_memory": false, "accepted": true}
```

**Canonical final result**: The authoritative "final result" is `state.json`'s `history[-1]` (last entry), NOT necessarily the staging dir with the latest timestamp. ⛔ **1 command = 1 night** — each `skillopt_sleep run` invocation produces exactly ONE staging directory. To run multiple nights, invoke the command multiple times (shell loop or cron).

The `.skillopt-sleep/state.json` file contains a `history` array with EVERY night's results in a single read. This is faster than parsing individual staging directories:

```bash
# Quick trajectory overview (all nights at once):
python -c "
import json
d = json.load(open('$PROJECT/.skillopt-sleep/state.json'))
for h in d['history']:
    status = '✓' if h['accepted'] else '✗'
    print(f\"Night {h['night']:2d}: {status} baseline={h['baseline']:.3f} → candidate={h['candidate']:.3f}  tasks={h['n_tasks']}  staging={h['staging'].split(chr(92))[-1]}\")
"
```

**Output example:**
```
Night  1: ✗ baseline=0.000 → candidate=0.000  tasks=3   staging=20260714-160633
Night  3: ✓ baseline=0.150 → candidate=0.200  tasks=3   staging=20260714-164156
Night  5: ✓ baseline=0.433 → candidate=0.667  tasks=15  staging=20260714-191208
Night 12: ✓ baseline=0.667 → candidate=1.000  tasks=15  staging=20260715-020152
Night 13: ✗ baseline=0.667 → candidate=0.667  tasks=15  staging=20260715-022254
```

**When to use this vs report.md:**
- **state.json history** → quick overview of ALL nights, score trajectory, which nights were accepted
- **staging/<timestamp>/report.md** → detailed edit descriptions, rationale, token usage for ONE night
- **staging/<timestamp>/diagnostics.json** → gate details, holdout evidence, errors for ONE night

**Key fields in state.json:**
- `night` — current/last night number
- `history[]` — array of all nights with `night`, `accepted`, `baseline`, `candidate`, `n_tasks`, `staging` path
- `task_archive[]` — full task definitions with rubrics (useful for understanding what was evaluated)
- `slow_memory` — accumulated learnings across nights

**Pro tip:** The `history` array lets you compute the full optimization trajectory without reading any staging directories. If you just need to report "what happened across all nights," read state.json once and format the history array.

## Stop Conditions

Abort immediately if:
- Live SKILL.md modified before adopt
- Proposal contains information leakage from the optimizing agent
- Proposal hardcodes test answers
- Agent prompts reveal internal fix paths
- Candidate causes severe regression on test split
- Tasks may send real external messages to unintended recipients

## Critical: Baseline Freshness Verification

**Problem**: If baseline was fixed at commit A, but user later commits B (updating SKILL.md), SkillOpt optimizes old code. The "optimization" just rediscover's user's manual changes.

**Solution**: Before running SkillOpt, verify baseline HEAD equals current HEAD:

```bash
# verify-baseline.sh (in Hermes experiment directory)
baseline_head=$(cat .skillopt-exp/<skill>/baseline/git-head.txt)
current_head=$(git rev-parse HEAD)

if [ "$baseline_head" != "$current_head" ]; then
  echo "ERROR: baseline is stale"
  echo "  baseline: $baseline_head"
  echo "  current:  $current_head"
  echo "Re-run stage ① to fix baseline with current HEAD"
  exit 1
fi
```

**Wrapper script** (run-skillopt-with-verify.sh):
```bash
#!/usr/bin/env bash
# Verify baseline freshness, then run SkillOpt
bash verify-baseline.sh || exit 1
ANTHROPIC_API_KEY=*** python -m skillopt_sleep run ...
```

**Never modify SkillOpt source code** to add verification. Keep verification in Hermes-side scripts.

## Critical: ANTHROPIC_API_KEY Must Be Set

**Problem**: Claude backend adds `--bare` flag ONLY when `os.environ.get("ANTHROPIC_API_KEY")` is non-empty (`backend.py:625`). Without `--bare`, claude loads full system prompt + user skills → prompt balloons → LLM times out or loops.

**Common scenario**: User configures custom backend (GLM, etc.) via `~/.claude/settings.json` with `ANTHROPIC_AUTH_TOKEN` + `ANTHROPIC_BASE_URL`. These are NOT visible to SkillOpt's env check.

**Fix**: Always set `ANTHROPIC_API_KEY=*** `env var before running:
```bash
ANTHROPIC_API_KEY=placeholder python -m skillopt_sleep run ...
```

The value doesn't need to be a real Anthropic key — just non-empty to trigger `--bare`.

**Verify before running**:
```bash
echo $ANTHROPIC_API_KEY  # should be non-empty
```

## Critical: Never Modify SkillOpt Source

All verification, validation, and safety checks must be implemented in Hermes-side scripts (e.g., `verify-baseline.sh`, `run-skillopt-with-verify.sh`). Never patch SkillOpt's Python code — it breaks reproducibility and violates the black-box principle.

## Post-Run Verification Checklist

**After a run completes (successfully or not), check these in order:**

1. **Exit code**: 
   - `0` = success
   - `137` (SIGKILL) = killed but results likely valid (check staging dirs)
   - `2304` = Claude CLI timeout OR OOM during consolidate (see pitfall #24)
   - `143` (SIGTERM) = killed, may have partial results

2. **Staging directories**: 
   ```bash
   ls -lt .skillopt-sleep/staging/ | head -3
   ```
   - New dir with timestamp AFTER launch? → Results exist, read report.md
   - No new dir? → Run failed, check logs

3. **state.json** (last successful night):
   ```bash
   python -c "import json; d=json.load(open('.skillopt-sleep/state.json')); print(f'night={d[\"night\"]}, baseline={d.get(\"baseline_score\")}, candidate={d.get(\"candidate_score\")}, accepted={d.get(\"accepted\")}')"
   ```
   - Shows latest night number and scores
   - If night N failed, state.json still shows night N-1

4. **report.md** (from LATEST staging dir):
   ```bash
   cat .skillopt-sleep/staging/<latest-timestamp>/report.md
   ```
   - `held-out score: X -> Y` shows improvement (Y > X = success)
   - `gate: accept_new_best` = optimization succeeded
   - `gate: reject` = no improvement (or saturation at 1.000, see pitfall #27)
   - `tokens used: N` shows API cost

5. **Log file** (for failures):
   ```bash
   tail -30 "$EXP_ROOT/logs/skillopt-run-*.log"
   ```
   - Look for: "timed out after 180 seconds", Python tracebacks, API errors

**Quick decision tree:**
- Exit 0 + new staging dir + gate=accept → **SUCCESS**, adopt the changes
- Exit 0 + new staging dir + gate=reject → **Saturation** (see pitfall #27), stop running
- Exit 137 + new staging dir → **Killed but valid**, read report.md and adopt
- Exit 137 + NO new staging dir + `tcsetattr` in output → **PTY failure** (see pitfall #14), retry with `pty=true`
- Exit 2304 + no new staging dir → **CLI timeout** (see pitfall #24), fix CLI before retrying
- No exit + no new staging dir after 60min → **Hung**, kill and check zombie processes

## Reviewing Results: report.md Format

After a successful run, the staging directory contains `report.md` with these fields:

```markdown
# SkillOpt-Sleep — night N report

- project: `<project-path>`
- backend: `<backend-name>`  replay: `<replay-mode>`
- sessions harvested: <N>
- tasks mined: <N>  (replayed: <M>)
- held-out score: <baseline> -> <candidate>
- gate: **<gate-decision>** (accepted=<True|False>)
- tokens used: <N>

## Accepted edits
- [<type>] <edit-content>
  _why: <rationale>_

## Rejected by gate (kept as negative feedback)
- [<type>] <edit-content>
```

**Key fields to check:**

- **held-out score**: Shows baseline → candidate improvement on the held-out validation set. A large jump (e.g., 0.100 → 1.000) indicates strong optimization.
- **gate decision**: `accept_new_best` means the candidate outperformed baseline and was accepted. Other gates: `reject_no_improvement`, `reject_regression`.
- **tasks mined vs replayed**: `tasks mined: 15 (replayed: 3)` means 15 tasks were in the file but only 3 were in the held-out split (val+test) and actually evaluated. The rest were used for training/consolidate.
- **Edit type prefixes**: `[skill/add]` = added to SKILL.md, `[skill/replace]` = modified existing SKILL.md content, `[memory/add]` = would go to agent memory (often rejected for skill optimization).

**Timing expectations:**

- **Per-task cost**: ~4 LLM calls per task (attempt_v1, judge_v1, attempt_v2, judge_v2)
- **Typical run time**: 30-60 minutes for 15-20 tasks with `claude` backend (consolidation phase is the longest)
- **Token usage**: 50k-100k tokens per run (shown in report.md)
- **Consolidation phase**: Can take 20-40 minutes with no stdout output — this is normal, not a hang

**Interpreting accepted vs rejected edits:**

- **Accepted edits** are applied to the target SKILL.md when you run `adopt`
- **Rejected edits** are kept as negative feedback for future cycles — they didn't pass the gate (often because they're memory-level lessons, not skill-level improvements)
- Review both lists before adopting — accepted edits should align with your optimization goals
