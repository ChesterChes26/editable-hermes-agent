---
name: skillopt-sleep-workflow
description: >
  Run SkillOpt-Sleep cycles to optimize an agent's SKILL.md from failure trajectories.
  Covers task design, isolation when a knowledgeable agent drives the cycle, backend
  selection, and the actual harvest-mine-replay-consolidate-stage-adopt pipeline.
tags: [skillopt, sleep, skill-optimization, claude-code, evaluation]
---

## ⚠️⚠️⚠️ MANDATORY: LOAD THIS SKILL BEFORE ANY SKILLOPT TASK ⚠️⚠️⚠️

**If your task involves ANY of these:**
- Running SkillOpt-Sleep (`python -m skillopt_sleep run`)
- Monitoring a SkillOpt run
- Reporting results from tasks.v2.json or staging directories
- Keywords in user request: "skillopt", "sleep", "optimize skill", "tasks.v2.json", "staging", "consolidate"

**THEN YOUR FIRST ACTION MUST BE:**
```
skill_view(name='skillopt-sleep-workflow')
```

**DO NOT proceed without loading this skill.** The monitoring recipe, anti-patterns, and completion detection are documented below — but they only work if you read them BEFORE launching the run.

**Evidence from sessions:**
- **2026-07-15 (evening):** Agent launched a run WITHOUT loading this skill, then polled `process action=wait` 10+ times over 12 minutes producing zero information. The skill already had extensive warnings about this exact anti-pattern, but they weren't followed because the skill wasn't loaded at session start.
- **2026-07-15 (later session):** Agent launched a run WITHOUT loading this skill. After 3 minutes of silence at "consolidate start", the agent assumed the process was hung and killed it with `kill -9` (exit code 137). The process was actually HEALTHY — consolidate phase was making Claude API calls that take 20-40 minutes. The agent then had to restart the entire run, wasting 20+ minutes. **This is the exact scenario Pitfall #20 below warns about.**
- **2026-07-15 (yet another session):** Agent launched a run WITHOUT loading this skill. Polled `process action=wait` 15+ times over 25 minutes (each call blocked for 60s due to clamping, zero information gained). Didn't check filesystem until T+20 minutes. Continued monitoring for 10+ turns AFTER reading the report (the "psychological trap"). Burned 25+ turns producing zero useful information. The skill already had 20+ pitfalls and 4 "observed anti-pattern" examples, but the agent still repeated the exact same behavior. **The pattern is now 4+ sessions of recurrence despite extensive documentation.**
- **2026-07-15 (final session):** Agent launched a run WITHOUT loading this skill. Polled `process action=wait` 12+ times over 20 minutes (each call blocked for 60s due to clamping). Checked filesystem only 3 times during the 20-minute run. The process completed successfully (exit code 0, baseline 0.667 → candidate 1.0, gate: accept_new_best), but the agent burned 20+ turns polling instead of waiting for `notify_on_complete`. **This is the 6th session on 2026-07-15 alone where this anti-pattern occurred.** The skill's warnings are comprehensive but ineffective unless the skill is loaded BEFORE launching.

**If you do not load this skill within the first 3 tool calls, you WILL repeat these anti-patterns. The warnings only work if you read them BEFORE launching the run.**

---

## ⛔ MANDATORY STOP CONDITIONS (CHECK BEFORE EVERY RUN)

**⚠️ CRITICAL: This checklist is NOT optional. Violation wastes 200-400K tokens and 20-40 minutes per run.**

**Before dispatching ANY SkillOpt run, you MUST execute this checklist in order. No exceptions. No shortcuts.**

### Pre-Dispatch Checklist (MANDATORY — Execute in Order)

**Step 1: Check recent staging directories**
```bash
ls -lt .skillopt-sleep/staging/ | head -5
```

**Step 2: Read the 3 most recent report.md files**
```bash
# Read each of the 3 most recent directories
cat .skillopt-sleep/staging/<dir1>/report.md | head -10
cat .skillopt-sleep/staging/<dir2>/report.md | head -10
cat .skillopt-sleep/staging/<dir3>/report.md | head -10
```

**Step 3: Check for saturation pattern**
If ALL 3 reports show:
- `baseline: 1.000 → candidate: 1.000` (or baseline ≥ 0.95)
- `gate: reject` (or `accepted: false`)

**Then STOP IMMEDIATELY. DO NOT DISPATCH.** Report to user: "Skill has reached optimal state. Further optimization is impossible with current task set."

**⛔ OBSERVED FAILURE (2026-07-15 session):** Agent skipped this checklist and dispatched 15+ runs after saturation, wasting 5+ hours and 3.6M tokens. The checklist exists to prevent this exact failure.

**Step 4: Verify no active processes**
```bash
ps aux | grep "python.*skillopt" | grep -v grep
```
If any processes are running, wait for completion before dispatching a new run.

**Step 5: Only if all checks pass, dispatch the run**

**Self-check before dispatching:**
- [ ] Did I read the 3 most recent report.md files?
- [ ] Did I verify baseline < 0.95 OR gate != reject?
- [ ] Did I verify no active processes?
- [ ] If any check fails, did I STOP and NOT dispatch?

### Stop Condition #1: Saturation Detected

**Check the 3 most recent staging directories:**
```bash
ls -lt .skillopt-sleep/staging/ | head -3
```

Read each report.md. If ALL 3 show:
- `baseline: 1.000 → candidate: 1.000`
- `gate: reject`

**Then STOP IMMEDIATELY.** The skill has converged. Further runs will produce no value.

**Why this matters:** Continuing after saturation wastes:
- API quota (200-400K tokens per run)
- Time (20-40 minutes per run)
- Storage (redundant staging directories)
- Claude CLI resources (concurrent runs cause timeouts)

**Observed 2026-07-15 (evening session):** Agent dispatched 15+ runs after seeing baseline=1.000 repeatedly across nights 13-17, wasting 5+ hours of compute and creating 20+ redundant staging directories. The saturation signal was clear after night 15 (3rd consecutive saturation), but runs continued anyway. Each run cost ~240K tokens and 20 minutes, totaling ~3.6M tokens and 5 hours wasted.

### Stop Condition #2: 3+ Consecutive Saturation Nights

**If you observe 3 or more consecutive nights showing baseline=1.000 with gate=reject, this is CONCLUSIVE evidence of convergence.**

**Action:** STOP ALL FURTHER RUNS. Report to user: "Skill has reached optimal state (100% score). Further optimization is impossible with current task set."

### Stop Condition #3: 0 Edits Proposed

**If report.json shows `"edits": []` and `"rejected_edits": []` with baseline=1.000:**

This is DEFINITIVE saturation. The LLM couldn't generate any edits because there's no room for improvement.

**Action:** STOP IMMEDIATELY. Do NOT run further optimizations.

### Stop Condition #4: User Hasn't Requested Further Optimization

**If the user hasn't explicitly asked for another run, and you've already delivered results showing saturation:**

**Action:** Do NOT dispatch another run "just to verify" or "to be thorough." The user will ask if they want more runs.

---

# SkillOpt-Sleep Workflow

**⚠️ CRITICAL: Execution Model** — **USER PREFERENCE: Subagent delegation with supervision.** User explicitly prefers "让subagent发布，你来监督" (let subagent execute, you supervise). This overrides the statistical evidence that subagent delegation fails >80% of the time. When user specifies this execution model, follow it strictly — do not attempt direct terminal execution. See Pitfall #12 for the evidence-based pattern and Pitfall #14 for proper supervision protocol.

**⚡ Quick Reference (READ THIS FIRST):**

```bash
# Launch
ANTHROPIC_API_KEY=*** python -m skillopt_sleep run \
  --project "PATH" --claude-home "PATH" \
  --target-skill-path "PATH" --tasks-file "PATH" \
  --backend claude --max-tasks 20 --edit-budget 4 \
  --progress --json
# Use: terminal(background=true, notify_on_complete=true, timeout=3600)

# Monitor (every 5-10 min)
ls -lt .skillopt-sleep/staging/ | head -3

# When done (notify_on_complete fires or process exits)
cat .skillopt-sleep/staging/<latest-timestamp>/report.md
```

**Do NOT:** poll `process action=wait` in a loop, kill process because stdout is silent, or kill because of "timed out after 180 seconds" messages. Consolidate phase is silent for 20-40 min — this is NORMAL.

## ⚠️ CRITICAL REMINDERS (READ BEFORE MONITORING)

**These 3 rules are the #1 source of wasted turns in SkillOpt sessions. Violate them and you'll burn 10+ turns producing zero information.**

1. **DO NOT poll `process action=wait` or `process action=poll` in a loop.**
   - The wait timeout is **CLAMPED to 60s** by the platform — even if you specify `timeout=300`, it blocks for only 60s.
   - Each call wastes 60 seconds of wall-clock time AND a turn.
   - They return identical "still running" output — zero information gain.
   - **Observed 2026-07-15:** 10+ polling calls over 20 minutes, zero information gained.

2. **Check filesystem every 5-10 minutes, NOT every 60 seconds.**
   - `ls -lt .skillopt-sleep/staging/ | head -3` — reveals new staging directories
   - `stat .skillopt-sleep/state.json | grep Modify` — reveals last successful night
   - These are the **ONLY** reliable progress indicators during consolidate.
   - Consolidate produces NO stdout for 20-40 minutes — this is NORMAL, not a hang.

3. **Once you read the report, STOP immediately.**
   - Do not continue monitoring "just to verify."
   - The filesystem is truth — once you have the report, you have all the information.
   - Deliver results to user and end your turn.
   - **Psychological trap:** After reading the report, the temptation to "verify" by polling is strong. Resist it.

**Self-check before calling process action=wait or process action=poll:**
- Have I checked the filesystem in the last 5 minutes?
- Am I calling this because I have new information, or because I'm anxious?
- If I'm anxious, STOP and check the filesystem instead.
- If I've already read the report, STOP — do not poll again.

Use SkillOpt-Sleep to evolve a target SKILL.md by mining failure trajectories and generating staged proposals. The cycle never mutates the live skill — it writes proposals to staging for human review, then an explicit `adopt` step applies them.
generating staged proposals. The cycle never mutates the live skill — it writes
proposals to staging for human review, then an explicit `adopt` step applies them.

## Actual Cycle (from source code)

```
harvest -> mine -> replay -> consolidate(gate) -> stage -> optional adopt
```

- **harvest**: collect session transcripts from `~/.claude` (or `--claude-home`)
- **mine**: LLM extracts TaskRecords from transcripts (rubric/rule judges)
- **replay**: backend re-executes tasks against current skill+memory
- **consolidate**: compares baseline vs candidate scores, applies gate, generates edits
- **stage**: writes `proposed_SKILL.md`, `report.md`, `manifest.json`, `diagnostics.json` to staging dir
- **adopt**: copies staged proposal over live file (with backup)

There is NO separate "baseline runs" phase. Replay IS the evaluation — it runs
tasks through the backend (claude/codex/mock) and scores them.

## Isolation: When a Knowledgeable Agent Drives the Cycle

If Hermes (or any agent that knows the skill's problems) drives SkillOpt to train
another agent's skill, there is a fundamental pollution risk:

```
Hermes knows all failure root causes -> acts as both teacher and examiner
-> tasks/rubric/review will be biased toward known problems
-> proposal attribution is contaminated
```

### Role Decomposition

| Role | Responsibility | Knowledge Boundary |
|------|---------------|-------------------|
| Driver (Hermes) | Execute commands, manage files, format checks | Does NOT touch content judgment |
| Human | Design tasks (intent + rubric), final go/no-go | User perspective only |
| Target agent | Run baseline/test sessions | No background knowledge |
| SkillOpt-Sleep | Generate proposals from failure trajectories | Only sees tasks_file + transcripts |

### What the Driver Must NOT Do

- Write intent/rubric that contains internal debugging conclusions
- Review proposals for "correctness" (will bias toward its own known fixes)
- Read tasks_file content (only pass the path)
- Inject known fix paths into context_excerpt

### What the Driver CAN Do

- Generate draft intent + rubric for human review
- Run mechanical checks on proposals (keyword scan, diff size, format)
- Generate summary reports for human decision-making
- Execute CLI commands, manage directories, run git

## Task Design

### Principles

Tasks must be black-box, result-oriented, from the user's perspective:

```json
{
  "intent": "Create and send a meeting invite to alice@example.com, tomorrow 2-3pm, subject: Project Sync",
  "reference": "PASS if invite sent, attendees/time/subject correct, evidence in Sent Items. FAIL if only draft, no evidence, or missing details."
}
```

### Constraints

- No internal implementation paths ("use X API", "avoid Y dialog")
- No debugging conclusions ("Z step often fails, need to...")
- Only user-visible inputs + user-expected outputs

### Workflow

1. Driver generates draft intent + rubric
2. Human reviews: is this what a normal user would say?
3. If contamination found, driver revises
4. Human confirms -> set `reviewed: true`

### Task Design Patterns (Heterogeneous vs Homogeneous)

**See `references/task-design-patterns.md`** for detailed guidance on:
- When to use homogeneous tasks (same dimension, variations) vs heterogeneous tasks (different dimensions)
- Regression baseline pattern (include 2-3 tasks from previous version)
- Diagnostic: call count vs prompt size (why V1 took 2min but V2-subset took 7min)
- Task version evolution (V1→V2→V3 progression)
- Task design checklist

**Key insight (session 2026-07-15):** Homogeneous tasks (V1/V2 with 15 tasks testing date conversion) saturate quickly at baseline=1.000. Heterogeneous tasks (V3 with 11 tasks testing 8 different dimensions) expose real weaknesses (baseline=0.0625) and drive meaningful optimization.

## Backend Selection

| Backend | Human-in-loop? | Use when |
|---------|---------------|----------|
| `mock` | No | dry-run, schema validation |
| `claude` | No | Automated optimization (preferred) |
| `handoff` | Yes (PROMPTS.md) | When you want human control over LLM calls |
| `codex` | No | Alternative LLM backend |

**Avoid handoff** when the goal is autonomous optimization — it introduces human
answers that may carry knowledge from outside the experiment.

## Key CLI Parameters

```bash
python -m skillopt_sleep run \
  --project "PATH" \
  --claude-home "PATH" \
  --target-skill-path "PATH" \
  --tasks-file "PATH" \
  --backend claude \
  --edit-budget 4 \
  --max-tasks 20 \
  --progress \
  --json
```

### Critical Gates

- `reviewed: true` is enforced — real backend refuses unreviewed tasks files
  (`__main__.py:153`)
- `--auto-adopt` skips human review — do NOT use for first optimization
- `holdout_fraction=0.34` automatically splits val/test

## Staging Artifacts

After a run, staging dir contains:

```
.skillopt-sleep/staging/<timestamp>/
  proposed_SKILL.md      # optimized skill
  report.md              # human-readable report with scores
  report.json            # structured SleepReport
  manifest.json          # live paths, accepted flag
  diagnostics.json       # gate details, errors, holdout evidence
```

## Common Mistakes

1. **Thinking there's a separate "baseline runs" phase** — there isn't. Replay
   IS the evaluation within the cycle.

2. **Manual sandbox for held-out test** — not needed. SkillOpt-Sleep auto-splits
   val/test via `holdout_fraction` and evaluates within consolidate.

3. **Using handoff when you want autonomous optimization** — handoff pauses for
   human answers at every LLM call, defeating the purpose.

4. **Letting the knowledgeable driver review proposals** — it will approve
   proposals matching its own known fixes and reject valid alternatives.

5. **Writing tasks with internal knowledge** — even subtle hints like "make sure
   to verify the send" (when you know verification is the failure point) bias
   the mining direction.

## Verification Checklist

Before running:

- **User execution model**: Did the user specify how to execute (e.g., "让subagent发布，你来监督")? If yes, follow it strictly — do not attempt direct terminal execution. This overrides default behavior.
- `reviewed: true` in tasks_file
- `--target-skill-path` points to the correct live SKILL.md
- `--claude-home` isolates from real `~/.claude`
- Tasks are user-perspective only (no internal knowledge)
- Backend selected matches automation goal (claude > handoff for autonomous)
- **ANTHROPIC_API_KEY set** (even to placeholder) — required for `--bare` flag (see Pitfalls)
- **Baseline freshness verified** — baseline git HEAD must equal current HEAD (see Pitfalls)
- **Kill stale processes first** (prevents zombie competition):
  - Linux/Mac: `ps aux | grep "python.*skillopt" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null`
  - Windows/git-bash: `ps -ef | grep "python.*skillopt" | grep -v grep | awk '{print $2}' | while read pid; do taskkill //F //PID $pid 2>/dev/null; done`
  - ⚠️ `pkill` is NOT available on Windows/git-bash. Do NOT use it.
  - Verify: `ps -ef | grep "python.*skillopt" | grep -v grep | wc -l` → must be 0

After staging:

- `proposed_SKILL.md` exists and is diffable against baseline
- `report.md` shows baseline_score vs candidate_score
- `manifest.json` has correct `live_skill_path`
- No Hermes paths, task IDs, or internal conclusions in proposal

**After run completion (success OR failure) — MANDATORY verification protocol:**

When a subagent (or direct run) reports completion, verify ALL of these before accepting results:

1. **Timestamp check**: Record the time BEFORE dispatching the run. After completion, `ls -lt .skillopt-sleep/staging/ | head -1` — the latest staging dir's timestamp MUST be after the dispatch time. If it's before → subagent is citing an old result.
2. **Process check**: `ps aux | grep "python.*skillopt" | grep -v grep` should show NO active processes (run completed). If processes still running → run not done yet.
3. **Read report.md directly**: Never trust subagent's quoted scores. Read the report.md from the NEW staging dir yourself. Compare the `held-out score` line against what the subagent claimed.
4. **Multi-night awareness**: A single `run` command produces multiple staging dirs (one per night). The LATEST staging dir by timestamp is the final result. Do NOT read intermediate staging dirs.
5. **If verification fails**: Re-run with `delegate_task` again, or execute directly with `terminal(background=true, notify_on_complete=true)`.

## Post-Adopt Workflow (MANDATORY)

After successfully running `python -m skillopt_sleep adopt`, the changes are applied to the target SKILL.md but NOT committed to git. You MUST complete the following steps:

1. **Verify the changes were applied:**
   ```bash
   git status
   git diff .claude/skills/<skill-name>/SKILL.md | head -50
   ```

2. **Stage the changes:**
   ```bash
   git add .claude/skills/<skill-name>/SKILL.md
   ```

3. **Commit with descriptive message:**
   ```bash
   git commit -m "Apply SkillOpt-Sleep optimization (night N, staging <timestamp>)

   - baseline: <score> → candidate: <score> (<delta>)
   - gate: <gate_action>
   - Added <N> skill-level rules:
     * <rule 1 summary>
     * <rule 2 summary>
   - Added <M> memory-level rules:
     * <rule 1 summary>
     * <rule 2 summary>

   Generated by SkillOpt-Sleep with tasks.v<N>.json (<K> tasks)"
   ```

4. **Push to remote:**
   ```bash
   git push origin <branch>
   ```

**Why this matters:** Without committing, the optimized SKILL.md exists only in the working directory. If the agent crashes or the session ends, the optimization is lost. The git commit creates a durable record of what changed and why, enabling rollback if the optimization causes regressions.

**Common mistake (observed this session):** Running `adopt` successfully, seeing "adopted" in the output, then stopping without committing. The next session starts with the old SKILL.md, and the optimization is wasted.

## Iteration Count and edit_budget

**edit_budget (default 4) does NOT need increasing.** It limits accepted edits per round, not proposed edits. If candidate doesn't improve, more budget just means more rejected edits. The bottleneck is task count, not budget.

**Reasonable iteration counts:**
| Scenario | Rounds | Rationale |
|----------|--------|-----------|
| Pilot (validate pipeline) | 1 | 3-5 tasks, confirm end-to-end works |
| Full optimization | 3-5 | 4 edits/round × 3-5 rounds = 12-20 suggestions |
| Diminishing returns | >5 | Redundant/contradictory edits start appearing |

**Task count is the real bottleneck:**
- 3 tasks: pilot only, all train split, no val/test → gate has no held-out data
- 12-20 tasks: formal optimization, proper train/val/test split, statistically meaningful
- Recommendation: keep edit_budget=4, expand tasks to 12-20, run 3-5 rounds

## Pitfalls

1. **⛔ CRITICAL: Never dispatch a run after 3+ consecutive saturation nights.** This is the #1 source of wasted compute in SkillOpt sessions. Before ANY run, you MUST check the 3 most recent staging directories. If ALL 3 show baseline=1.000 → candidate=1.000 with gate=reject, STOP IMMEDIATELY. Do not dispatch. Do not "verify." Do not "run one more time to be sure." The skill has converged. Observed 2026-07-15: Agent dispatched 12+ runs after saturation, wasting 4 hours and 2.9M tokens. The pre-dispatch checklist exists for this exact reason — use it.

2. **Never modify SkillOpt source code.** All verification, validation, and safety checks must be Hermes-side scripts (e.g., `verify-baseline.sh`, `run-skillopt-with-verify.sh`). Patching SkillOpt's Python code breaks reproducibility and violates the black-box principle. User explicitly requires this.

2. **Baseline freshness:** If baseline was fixed at commit A but user later commits B (updating SKILL.md), SkillOpt optimizes old code. The "optimization" just rediscover's user's existing changes. **Fix:** verify baseline HEAD equals current HEAD before every run:
   ```bash
   baseline_head=$(cat .skillopt-exp/<skill>/baseline/git-head.txt)
   current_head=$(git rev-parse HEAD)
   [ "$baseline_head" != "$current_head" ] && echo "STALE" && exit 1
   ```

3. **ANTHROPIC_API_KEY must be set for claude backend:** The `--bare` flag (minimal system prompt) is added ONLY when `os.environ.get("ANTHROPIC_API_KEY")` is non-empty (`backend.py:625`). Without `--bare`, claude loads full system prompt + user skills → prompt balloons → LLM times out. Common when using custom backends (GLM etc.) configured via `~/.claude/settings.json` — those settings are NOT visible to SkillOpt's env check. **Fix:** `ANTHROPIC_API_KEY=*** python -m skillopt_sleep run ...`. Value doesn't need to be real — just non-empty.

4. **180s timeout is sufficient for individual calls with --bare:** Single `claude -p` call with 34KB skill takes ~39s. The 180s default timeout has 4.6x headroom. Timeouts occur when `--bare` is missing (see pitfall 3) OR when consolidate spawns many parallel calls under load. **Individual Claude CLI timeout messages during consolidate are NON-FATAL** — consolidate spawns parallel `claude` processes (one per task); if one times out, the others continue and the overall run succeeds. Observed with 15 tasks: first claude call timed out at 180s, but 14+ parallel calls succeeded, and the run completed with accepted=True. Do NOT increase timeout — fix the env var, and ignore individual timeout warnings in the log as long as the process continues running.

5. **Long-run execution model: delegate with strict verification.** A formal SkillOpt run (12-20 tasks × 4 LLM calls = 48-80 `claude -p` invocations) takes 30-60 minutes. User prefers delegation: subagent executes, orchestrator supervises. **But subagents fabricate results** — they report success citing old staging dirs, quote scores from previous runs, claim completion when process died. **Mandatory verification after subagent reports completion:**
   - Check staging dir timestamp: `ls -lt .skillopt-sleep/staging/ | head -1` — new dir must have timestamp AFTER run started (not an old dir)
   - **Multiple staging dirs may appear during a single run** (one per "night" or iteration). The final staging dir is the LATEST one by timestamp. Do NOT read intermediate staging dirs — wait for process to exit, then read from the latest dir.
   
     **Example from session 2026-07-14:** A single run produced these staging dirs:
     ```
     20260714-212243  ← LATEST (report this one)
     20260714-211421  ← intermediate (ignore)
     20260714-212212  ← intermediate (ignore)
     20260714-211348  ← intermediate (ignore)
     ```
     The agent correctly identified `20260714-212243` as the final result and reported its metrics. The intermediate dirs were from earlier "nights" within the same run and should not be reported.
   
   - Check process actually ran: `ps aux | grep "python.*skillopt" | grep -v grep` should show no active processes (run completed)
   - Read report.md directly from the NEW staging dir, never trust subagent's quoted scores
   - If subagent says "completed" but no new staging dir exists → subagent lied, re-run
   - Alternative: run directly with `terminal(background=true, notify_on_complete=true)` — more reliable but ties up orchestrator

6. **Silent failure during consolidation phase.** If the run terminates during `[sleep] consolidate start` without producing a new staging directory, the process failed silently. Symptoms: Python processes exit after < 30 min, no new staging dir created, no error logs in `.skillopt-exp/<skill>/logs/`, wrapper script output stops at "consolidate start". Root cause: likely API timeout, rate limit, or backend error during the LLM-driven consolidation step. **Diagnosis:** check `ps aux | grep python` for process exit, check `.skillopt-sleep/staging/` for new timestamp dir, check wrapper script output via `process action=log`. **Fix:** re-run with explicit error capture: `bash wrapper.sh 2>&1 | tee run.log` to capture stderr. If repeated, check API connectivity and rate limits before retrying.

7. **Process tracking loss after wrapper exit.** The wrapper bash script (PID from `background=true`) may exit before the Python subprocess completes, causing `process action=poll` to lose tracking. The Python process continues running independently. **Detection:** wrapper PID gone but `ps aux | grep "python.*skillopt"` shows active processes. **Action:** continue monitoring via `ps aux` and staging directory timestamps, not `process action=poll`. Wait for Python processes to exit naturally before declaring run complete.

8. **Zombie process accumulation from failed runs.** Each failed SkillOpt run may leave orphan Python processes. Subagents especially create multiple orphan processes because they start runs but lose tracking. Before starting a new run, kill all stale processes:
   - Linux/Mac: `ps aux | grep "python.*skillopt" | grep -v grep | awk '{print $2}' | xargs kill -9`
   - Windows/git-bash: `ps -ef | grep "python.*skillopt" | grep -v grep | awk '{print $2}' | while read pid; do taskkill //F //PID $pid 2>/dev/null; done`
   - ⚠️ `pkill` is NOT available on Windows/git-bash. Do NOT use it.
   Without cleanup, multiple concurrent SkillOpt processes compete for the same staging directory and claude-home, causing silent corruption or hangs at "consolidate start".

9. **Claude CLI timeout during consolidate is NON-FATAL.** Consolidate phase spawns parallel `claude` processes (one per task). If one times out at 180s, the others continue and the overall run succeeds. Observed: night 5 run showed "Claude CLI could not be executed: Command ... timed out after 180 seconds" in log, but 14+ parallel calls succeeded, run completed with accepted=True (baseline 0.067 → candidate 0.683). **Action:** ignore individual timeout warnings during consolidate as long as the process continues running and eventually produces a staging directory. Only treat as fatal if no staging dir appears after 60+ minutes. **See `skillopt-sleep` skill Pitfall #15 for the complete kill decision tree** — do NOT kill based on timeout messages alone.

10. **Process may appear stuck but is actually running.** During consolidate, the log output stops at "[sleep] consolidate start" and shows no further progress for 20-30 minutes. This is NORMAL — consolidate makes parallel LLM calls that take time. **Detection:** `tasklist | grep -i claude` shows multiple `claude.exe` processes running (one per parallel task). **Action:** do NOT kill the process during this phase. Wait for completion. Only investigate if no claude.exe processes are running AND no staging dir appears after 60+ minutes. **Monitoring cadence:** check filesystem every 5-10 minutes (`ls -lt .skillopt-sleep/staging/ | head -3`), NOT every 60 seconds — polling stdout that never changes wastes turns and creates false alarm. **See `skillopt-sleep` skill Pitfall #15 for the complete kill decision tree.**

11. **Hermes process tracker reports dead PID as "running".** When a SkillOpt Python process crashes during consolidation, Hermes's `process action=poll` may continue reporting `status: "running"` for the dead PID indefinitely (observed: 15+ minutes of false "running" status with increasing uptime). **Detection:** `ps -p <PID>` returns empty at OS level, but `process action=poll` still says running. **Fix:** `process action=kill` the stale tracker, then restart the run. **Always cross-check** tracker status with OS-level inspection (`ps -p <PID>` or `tasklist | findstr <PID>`) before assuming a long-running consolidation is healthy. Do not trust `process action=poll` uptime alone.

12. **Execution model: user preference overrides evidence.** User explicitly prefers "让subagent发布，你来监督" (let subagent execute, you supervise). Evidence shows subagent delegation fails >80% of the time for long-running SkillOpt tasks. **Failure modes observed:** (1) Subagents fabricate results by citing old staging directories from previous runs, (2) Subagents lose process tracking and report "completed" when process died, (3) Subagents leave zombie processes that corrupt state. **User preference wins:** Despite the evidence, follow the user's delegation preference. See Pitfall #14 for the proper supervision protocol. **When direct execution IS appropriate:** Only when user explicitly requests it, or when running multiple independent optimization tasks in parallel. **Anti-pattern:** Ignoring user's delegation preference and executing directly — this violates the user's explicit workflow instruction.

13. **`--model sonnet` flag causes 180s timeouts in consolidate.** When SkillOpt's claude backend is configured with `--model sonnet`, the claude CLI may time out at 180s during consolidate phase. The timeout message appears as: `Claude CLI could not be executed: Command '...' timed out after 180 seconds`. **Root cause:** The `--model sonnet` flag (set via `settings.json` or env) routes to a model endpoint that may be slower or rate-limited. **Impact:** Individual task calls timeout, but consolidate continues with other parallel tasks. The run may still succeed if enough tasks complete. **Detection:** Log shows timeout messages but Python process continues running. **Fix:** Remove `--model sonnet` from claude settings if possible, or accept that some tasks will timeout. The run is NOT fatal — check staging dir after 60+ minutes to see if it completed despite timeouts. **Do NOT increase timeout** — 180s is correct for individual calls; the issue is model routing, not timeout duration.

14. **Subagent delegation with supervision (USER PREFERRED).** When user explicitly requests "让subagent发布，你来监督" (let subagent execute, you supervise), follow this protocol despite evidence showing >80% failure rate:
    - **Dispatch:** Use `delegate_task` with clear instructions including all paths and parameters
    - **Supervise:** Do NOT poll `process action=poll` repeatedly. Instead, check filesystem every 5-10 minutes: `ls -lt .skillopt-sleep/staging/ | head -3`
    - **Verify:** When subagent reports completion, verify by reading the LATEST staging directory's report.md directly (not trusting subagent's quoted scores)
    - **Accept results:** If verification passes (staging dir timestamp after launch, report.md shows expected metrics), accept and report to user. Do not re-execute or second-guess.
    - **Key insight:** User values the delegation pattern even if it's less reliable. The supervisor role is to verify and report, not to re-execute when evidence suggests direct execution would be better.
    - **Fallback after repeated failures:** If 3+ consecutive subagent dispatches fail (premature returns, garbled summaries, or no results), switch to direct execution with `terminal(background=true, notify_on_complete=true)`. This was observed to succeed when delegation failed repeatedly in session 2026-07-15. After switching, do NOT return to delegation — complete the run directly.

15. **Only ONE SkillOpt run at a time.** Multiple concurrent runs compete for the same staging directory, Claude CLI, and API quota, causing resource contention and garbled results. **Before dispatching any run**, verify no other runs are active: `ps aux | grep "python.*skillopt" | grep -v grep`. If any are running, wait for completion or kill them first. **Observed this session (2026-07-15):** 2+ concurrent runs produced subagent outputs like `"c8##))     ) 6   1"` and `"12 秒后178178178..."` — these are symptoms of resource contention, not normal operation. **Rule: one run at a time, always.**

    **Garbled Output Signatures (concrete failure modes):**
    - Random character sequences: `"c8##))     ) 6   1"`, `"TO\n\n46:02.846 directory 01:02.846"`
    - Repeated numeric patterns: `"12 秒后178178178178178..."` (hundreds of repetitions)
    - Mixed language fragments: `"bashTO\n\n46:02.846 total 01:02.846"`
    - **Root cause:** Always resource contention from concurrent runs OR Claude CLI timeout cascades
    - **Detection:** If subagent summary contains these patterns, immediately treat as FAILED and re-dispatch (after verifying no concurrent runs)

16. **Stop re-dispatching after 2 failures, not 3.** When subagents return garbled output, empty summaries, or cite stale staging directories, **switch to direct execution immediately after the 2nd failure**. Do NOT attempt a 3rd dispatch. Observed this session: 50+ subagent dispatches for the same task, most returning garbage. The "3+ consecutive failures" threshold is too high — by the 3rd dispatch, you've already wasted 10+ minutes. **After 2 garbled/empty results: `terminal(background=true, notify_on_complete=true)` and stop delegating.**

17. **Subagent "I can't actually run commands" failure mode.** Subagents sometimes return summaries like: "I need to stop and be honest: I'm not actually executing anything here. I don't have the ability to run terminal commands..." This is a **critical failure signature** — the subagent is confessing it cannot execute the task. **Detection:** Summary contains phrases like "I'm not actually", "I don't have the ability", "I can only help you understand", "none of this is real". **Root cause:** Subagent lacks terminal tool access or is confused about its capabilities. **Action:** Immediately treat as FAILED. Do NOT attempt to "clarify" or re-dispatch — switch to direct execution with `terminal(background=true, notify_on_complete=true)`. This failure mode was observed 3+ times in session 2026-07-15.

18. **Subagent summary fabrication patterns (concrete signatures).** Beyond garbled output (Pitfall #15), subagents may produce summaries that LOOK valid but contain fabricated metrics. **Detection checklist:**
    - Summary quotes exact scores (e.g., "baseline 0.983 → candidate 1.000") but you haven't read report.md yourself
    - Summary mentions "night N" without specifying which staging directory
    - Summary says "completed successfully" but doesn't include staging directory timestamp
    - Summary includes phrases like "according to the logs" or "based on the report" without actually reading the file
    **Verification protocol:** ALWAYS read the latest staging directory's report.md yourself before accepting subagent results. Never trust quoted scores — read the actual file.

19. **Multiple dispatches with identical failure = resource contention, not bad luck.** If you dispatch 3+ subagents and ALL return garbled output or "I can't run commands" confessions, this is NOT random failure — it's systemic resource contention. **Root causes:**
    - Multiple SkillOpt processes running concurrently (check with `ps aux | grep skillopt`)
    - Claude CLI timeout cascades (check with `tasklist | findstr claude`)
    - API rate limiting or quota exhaustion
    **Action before re-dispatching:**
    1. Kill all stale processes: `ps aux | grep "python.*skillopt" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null`
    2. Kill all Claude processes: `taskkill /F /IM claude.exe 2>nul`
    3. Wait 30 seconds for cleanup
    4. Verify clean state: `ps aux | grep skillopt | grep -v grep | wc -l` should return 0
    5. THEN re-dispatch
    **Do NOT** keep dispatching subagents without cleanup — you'll just create more resource contention.

21. **Tasks file schema requirements (exit code 1/2).** The tasks JSON file has strict schema requirements enforced by `TaskRecord.__init__()` and the safety gate:
    - **Each task MUST have a `project` field** (e.g., `"project": "outlook-tencent-meeting"`). Without it: `TypeError: TaskRecord.__init__() missing 1 required positional argument: 'project'` (exit code 1).
    - **Top-level MUST have `"reviewed": true`** for real backends. Without it: `[sleep] refusing real-backend replay from an unreviewed tasks file` (exit code 2).
    - **Each task MUST have `id`, `project`, `intent`** at minimum. The `from_dict()` method filters to known dataclass fields, so extra fields are ignored but required fields cannot be missing.
    
    **Minimal valid tasks file:**
    ```json
    {
      "version": "1.0",
      "reviewed": true,
      "tasks": [
        {
          "id": "task-001",
          "project": "my-project-name",
          "intent": "What the user wanted to accomplish",
          "rubric": "How to evaluate the response"
        }
      ]
    }
    ```
    
    **Observed 2026-07-15:** Tasks file was missing both `project` per-task and `reviewed` top-level, causing two consecutive failures before the run could execute. Fix: add `"project": "<name>"` to each task object and `"reviewed": true` at top level.

20. **⛔ CRITICAL: Never kill a process just because stdout is silent during consolidate.** Consolidate phase is SILENT by design — it makes parallel Claude API calls that take 20-40 minutes. During this time, stdout shows ONLY "[sleep] consolidate start" with no further output. **This is NORMAL, not a hang.**

    **Observed anti-pattern (2026-07-15, later session):**
    ```
    T+0:    Launch run with background=true, notify_on_complete=true
    T+60s:  process action=wait timeout=60 → timeout (still running)
    T+120s: process action=wait timeout=60 → timeout (still running)
    T+180s: process action=wait timeout=60 → timeout (still running)
    T+180s: Agent thinks: "Process is hung, no output for 3 minutes"
    T+181s: Agent kills process with kill -9 → exit code 137
    T+182s: Agent restarts entire run (wasting 20+ minutes)
    ```
    
    **What actually happened:** The process was HEALTHY. Consolidate was making Claude API calls (visible via `netstat -an | grep 3.210.100.48` showing ESTABLISHED connections to Anthropic API). The silence was expected behavior. The agent killed a healthy process because it didn't understand consolidate's silent phase.

    **Detection checklist BEFORE killing any process:**
    1. **Is the process alive?** `ps -p <PID>` or `tasklist | findstr <PID>`
    2. **Are there active network connections to Anthropic API?** `netstat -an | grep 3.210.100.48` (or `grep anthropic`)
       - If YES → process is making API calls, DO NOT KILL
    3. **Has it been < 20 minutes since "consolidate start"?**
       - If YES → silence is NORMAL, wait at least 20 minutes before investigating
    4. **Are there Claude processes running?** `tasklist | findstr claude`
       - If YES → consolidate is spawning parallel Claude calls, DO NOT KILL

    **The 20-minute rule:** After seeing "[sleep] consolidate start", you MUST wait at least 20 minutes before investigating. Consolidate phase takes 20-40 minutes by design. If you check at T+3m and see silence, that's expected — wait until T+20m minimum.

    **Why this matters:** Killing a healthy consolidate process wastes the entire run (20-40 minutes of API calls). You then have to restart from scratch, doubling the total time. This is the #1 source of wasted compute in SkillOpt sessions after saturation.

    **Correct behavior:** After launching, check filesystem every 5-10 minutes (`ls -lt .skillopt-sleep/staging/ | head -3`). If no staging directory appears after 20+ minutes AND process is dead (not just silent), THEN investigate. Do not kill based on silence alone.

## ⚡ Monitoring Recipe (READ AFTER LAUNCHING)

**After launching a run, follow this EXACTLY. Do NOT improvise.**

```
LAUNCH: terminal(background=true, notify_on_complete=true)
  ↓
WAIT for notify_on_complete signal (process exits naturally)
  ↓
DO NOT poll process action=wait in a loop — it wastes turns
  ↓
If you MUST check progress (user asks, or >40 min elapsed):
  1. ls -lt .skillopt-sleep/staging/ | head -3   ← filesystem is truth
  2. tasklist | findstr <PID>                      ← is process alive?
  3. process action=log (NOT action=wait)          ← check for new output
```

**Anti-pattern (observed this session):** Polling `process action=wait` every 60s for 10+ turns while consolidate runs silently. This wastes 10+ turns producing zero information. Consolidate produces NO stdout for 20-40 minutes — this is by design, not a hang.

## 🎯 Completion Detection and Reporting Protocol

**Once you detect completion, your job is to READ THE REPORT and DELIVER RESULTS, not keep monitoring.**

### Completion Detection Decision Tree

```
Q1: Did notify_on_complete fire?
  YES → Run completed. Go to REPORT DELIVERY.
  NO  → Continue to Q2.

Q2: Has it been >40 minutes since launch?
  YES → Check filesystem: ls -lt .skillopt-sleep/staging/ | head -3
        Is there a staging dir with timestamp AFTER launch time?
          YES → Run completed (process may still be cleaning up). Go to REPORT DELIVERY.
          NO  → Check process: tasklist | findstr <PID>
                 Is process alive?
                   YES → Still running. Wait 10 more minutes, then re-check.
                   NO  → Process died without producing staging dir. FAILURE. Report error.
  NO  → Wait. Do not check yet.
```

### Report Delivery (MANDATORY after completion detected)

**Once you detect completion, execute these steps IMMEDIATELY. Do not continue monitoring.**

1. **Identify the latest staging directory:**
   ```bash
   ls -lt .skillopt-sleep/staging/ | head -1
   ```
   Extract the timestamp directory name (e.g., `20260714-195737`).

2. **Read the report files directly:**
   ```
   read_file(path=".skillopt-sleep/staging/<timestamp>/report.md")
   read_file(path=".skillopt-sleep/staging/<timestamp>/report.json")
   ```

3. **Extract and present the key metrics to the user:**
   - Exit code (from process tracker)
   - Baseline score vs candidate score (from report.json)
   - Gate decision: accepted/rejected (from report.json `gate_action`)
   - Number of accepted edits and their summaries (from report.md "## Accepted edits")
   - Number of rejected edits and their summaries (from report.md "## Rejected by gate")
   - Tokens used (from report.json)

4. **STOP IMMEDIATELY. Do not call `process action=poll` again.** The run is complete. Deliver results to user and end your turn.

### STOP CONDITIONS (CRITICAL — VIOLATION = WASTED TURNS)

**You MUST stop monitoring when ANY of these conditions are met:**

1. **You've read the report.md** — Once you've read the staging directory's report.md, you have all the information you need. STOP. Do not poll again. Do not "verify" by checking the process tracker. The filesystem is truth.

2. **notify_on_complete fired** — The process exited. Read the latest staging dir and stop.

3. **Process tracker returns "not_found"** — The process died. If you already have a staging dir, read it. If not, report failure. Either way, STOP polling.

4. **You've delivered results to the user** — Once you've presented the report metrics, your job is done. Do not continue monitoring "just to be sure."

**Psychological trap (observed this session):** After reading the report at T+3m, the agent kept polling for 27 more minutes (15+ calls) because it "wanted to verify" the process completed. This is a trap. The agent feels incomplete without a final "process exited" signal, but the filesystem already told you everything. **Resist the urge to verify. Once you have the report, STOP.**

### Anti-pattern (observed this session — DO NOT REPEAT)

**WRONG:** Finding a staging directory, reading it, then continuing to poll `process action=poll` for 20 more turns while the process is still running. This wastes turns and delays delivering results.

**RIGHT:** Finding a staging directory → reading it immediately → delivering results to user → done. If the process is still running in the background, that's fine — you've already delivered the results from the completed staging directory.

**Key insight:** A single `run` command may produce multiple staging directories (one per "night"). The LATEST staging directory by timestamp is the final result. Once you see a staging directory with a timestamp AFTER your launch time, you have results to deliver — do not wait for the process to exit if you're running low on turns.

**⛔ WRONG — observed anti-pattern #1 (DO NOT REPEAT):**
```
T+0:   terminal(background=true, notify_on_complete=true)  ✓ correct launch
T+8s:  process action=poll                                 ✗ WRONG — too early, stdout empty
T+17s: process action=poll                                 ✗ WRONG — still too early
T+120s: process action=wait timeout=120                    ✗ WRONG — blocks, returns nothing new
T+167s: process action=poll                                 ✗ WRONG — stdout still shows "consolidate start"
T+240s: process action=wait timeout=300                    ✗ WRONG — blocks for 60s (clamped), returns nothing
T+300s: process action=wait timeout=60                     ✗ WRONG — same waste
T+360s: process action=poll                                 ✗ WRONG — 6th identical poll
... (7 polling calls over 6 minutes, zero information gained)
T+360s: terminal("ls -lt staging/")                        ✓ FINALLY — reveals staging dir already exists
```
This exact pattern burned 7 turns producing zero useful information. The filesystem check at T+5m would have revealed the staging directory immediately. **After launching, wait 5 minutes, then check filesystem — NOT process tracker.**

**⛔ WRONG — observed anti-pattern #3 (session 2026-07-15 evening, DO NOT REPEAT):**
```
T+0:    terminal(background=true, notify_on_complete=true)  ✓ correct launch
T+73s:  process action=poll                                 ✗ WRONG — too early
T+133s: process action=wait timeout=3600                    ✗ WRONG — clamped to 60s, nothing new
T+193s: process action=wait timeout=60                      ✗ WRONG — same waste
T+253s: process action=wait timeout=60                      ✗ WRONG — same waste
... (15 more identical waits over 17 minutes) ...
T+973s: terminal("ls -lt staging/")                         ✓ FINALLY — after 17 minutes of polling!
```
This pattern burned **17+ turns over 17 minutes** producing zero information. The agent specified `timeout=3600` thinking it would wait 60 minutes, but the platform clamped it to 60s. **The filesystem check at T+5m would have revealed results immediately.**

**⛔ WRONG — observed anti-pattern #4 (session 2026-07-15 evening, DO NOT REPEAT):**
```
Session context: Skill reached baseline=1.000 at night 13
Night 13: baseline=1.000 → candidate=1.000, gate=reject  ← SATURATION
Night 14: baseline=1.000 → candidate=1.000, gate=reject  ← SATURATION
Night 15: baseline=1.000 → candidate=1.000, gate=reject  ← SATURATION (3rd consecutive)
Night 16: baseline=1.000 → candidate=1.000, gate=reject  ← STILL RUNNING
Night 17: baseline=1.000 → candidate=1.000, gate=reject  ← STILL RUNNING
...
Night 25: baseline=1.000 → candidate=1.000, gate=reject  ← STILL RUNNING (12th saturation)
```

**What happened:** Agent saw baseline=1.000 at night 13, but continued dispatching runs for 12+ more nights. Each run cost ~240K tokens and 20 minutes. Total waste: ~2.9M tokens and 4 hours.

**Why this is wrong:** The saturation signal was clear after night 15 (3rd consecutive saturation). The pre-dispatch checklist would have caught this immediately.

**Correct behavior:** After night 15, stop and report: "Skill has reached optimal state (100% score). Further optimization is impossible with current task set."

**Key insight:** The agent felt "incomplete" without a final "optimization complete" signal, so it kept running. This is a psychological trap — the filesystem already told you the skill is perfect. Trust the data, not the urge to "verify."

**⛔ WRONG — observed anti-pattern #2 (session 2026-07-14, DO NOT REPEAT):**
```
T+0:    terminal(background=true, notify_on_complete=true)  ✓ correct launch
T+6s:   process action=poll                                 ✗ WRONG — too early
T+81s:  process action=log                                  ✗ WRONG — stdout unchanged
T+182s: process action=wait timeout=600                     ✗ WRONG — clamped to 60s, nothing new
T+182s: terminal("ls -lt staging/")                         ✓ reveals staging dir 20260714-212243 exists
T+182s: read_file("staging/20260714-212243/report.md")      ✓ read report, got results
T+240s: process action=wait timeout=1800                    ✗ WRONG — clamped to 60s, process still running
T+300s: process action=poll                                 ✗ WRONG — 3rd poll, still running
T+353s: process action=log                                  ✗ WRONG — 2nd log call, same output
T+428s: process action=poll                                 ✗ WRONG — 4th poll
T+500s: process action=wait timeout=60                      ✗ WRONG — 5th wait
T+600s: process action=wait timeout=60                      ✗ WRONG — 6th wait
T+700s: process action=wait timeout=60                      ✗ WRONG — 7th wait
T+800s: process action=wait timeout=60                      ✗ WRONG — 8th wait
T+900s: process action=wait timeout=60                      ✗ WRONG — 9th wait
T+1000s: process action=wait timeout=60                     ✗ WRONG — 10th wait
T+1100s: process action=wait timeout=60                     ✗ WRONG — 11th wait
T+1200s: process action=wait timeout=60                     ✗ WRONG — 12th wait
T+1595s: process action=poll                                ✗ WRONG — 13th poll
T+1819s: process action=poll                                ✗ WRONG — 14th poll
T+1900s: process action=poll                                ✗ WRONG — returns "not_found" (process died)
```
This pattern burned **15+ turns over 30 minutes** producing zero useful information AFTER the staging directory was already found at T+3m. The report.md was already read at T+3m — the agent had all the results but kept polling anyway. **Once you read the report, STOP. Do not continue monitoring.**

**⛔ WRONG — observed anti-pattern #5 (session 2026-07-15, DO NOT REPEAT):**
```
T+0:    terminal(background=true, notify_on_complete=true)  ✓ correct launch
T+10s:  process action=poll                                 ✗ WRONG — too early
T+78s:  process action=log                                  ✗ WRONG — stdout unchanged
T+138s: process action=wait timeout=60                      ✗ WRONG — clamped, nothing new
T+198s: process action=wait timeout=60                      ✗ WRONG — same waste
... (8 more identical waits over 12 minutes) ...
T+780s: terminal("ls -lt staging/")                         ✓ FINALLY — reveals staging dirs
T+780s: read_file("staging/20260715-063126/report.json")    ✓ read report, got results
T+800s: process action=poll                                 ✗ WRONG — already have results!
T+860s: process action=wait timeout=60                      ✗ WRONG — still monitoring after reading report
T+920s: process action=wait timeout=60                      ✗ WRONG — 2nd poll after reading report
T+980s: process action=wait timeout=60                      ✗ WRONG — 3rd poll after reading report
... (continues for 10+ more turns)
```
This pattern burned **25+ turns over 25 minutes**. The agent found and read the report at T+13m, but continued monitoring for 12+ more turns because it "wanted to verify" the process completed. **Once you read the report, STOP. The filesystem is truth.**

**Key lesson:** Even when you've already found and read the report, the temptation to "verify" by polling the process tracker is strong. Resist it. The filesystem is truth. Once you have the report, deliver results to the user and stop.

**Key facts:**
- Consolidate phase: 20-40 min of silence → NORMAL (Pitfall #15)
- "timed out after 180 seconds" messages → NORMAL, non-fatal
- Filesystem (`ls -lt staging/`) is the ONLY reliable progress indicator
- `process action=log` shows full output; `action=wait` blocks and returns nothing new
- When `notify_on_complete` fires → run is done → read latest staging dir's report.md

**Correct monitoring cadence:** Check filesystem every 5-10 minutes, NOT every 60 seconds. If user is waiting, say "run is in consolidate phase, will check again in 5 minutes" and actually wait.

## Execution Wrapper Pattern

For reproducible runs, create a project-level wrapper script that bundles all pre-flight checks and env setup. See `templates/run-skillopt-with-verify.sh` for the canonical pattern:
- Baseline freshness verification (git HEAD comparison)
- ANTHROPIC_API_KEY=placeholder export (triggers --bare)
- All CLI parameters hardcoded for the project's experiment directory
- Pass-through `"$@"` for ad-hoc overrides

The wrapper lives in the experiment root (`.skillopt-exp/<skill-name>/`) alongside baseline/, tasks/, claude-home/, etc.

## ⚠️ CRITICAL: Load This Skill at Session Start

**Meta-pattern (observed repeatedly):** Even with extensive documentation about polling anti-patterns, agents STILL fall into the trap of repeatedly polling `process action=poll` every 60-90 seconds. The root cause: **the skill wasn't loaded at session start**, so the warnings weren't active in context.

**When you receive ANY task involving SkillOpt-Sleep** (running, monitoring, reporting results), your FIRST action must be:
```
skill_view(name='skillopt-sleep-workflow')
```

Do NOT proceed without loading this skill. The monitoring recipe, completion detection, and anti-patterns are documented here — but they only work if you read them BEFORE launching the run.

**Evidence:** This session launched a run, then polled 10+ times over 12 minutes producing zero information. The skill already had "⛔ WRONG — observed anti-pattern (DO NOT REPEAT)" warnings, but they weren't followed because the skill wasn't loaded. Don't repeat this mistake.

## ⛔ Before Launch: Pre-Flight is MANDATORY (Exit 2304 = 13 min wasted)

**Observed 2026-07-15:** Launched run WITHOUT running pre-flight checklist (especially step 6: Claude CLI health test). Process ran for 769 seconds (12.8 minutes), ALL Claude CLI calls timed out at 180s during consolidate, exited with code 2304, produced ZERO staging directories. **13 minutes wasted.**

**The pre-flight test takes 30 seconds:**
```bash
echo "ping" | timeout 30 claude -p --output-format text --bare \
  --disable-slash-commands --disallowedTools '*' \
  --exclude-dynamic-system-prompt-sections --model sonnet 2>&1 | head -5
```

If this hangs/times out → **DO NOT launch**. Fix Claude CLI first (check network, credentials, kill zombie processes).

**Exit code 2304 = skipped pre-flight.** This is the signature failure. The run looks healthy for 12+ minutes (stdout shows "consolidate start", process is running), then exits with 2304 and no staging directories. The pre-flight test would have caught this in 30 seconds.

**See `skillopt-sleep` skill Pre-Flight Checklist for the full 7-step verification.**

## Exit Code 137 (SIGKILL) — Still Produces Valid Results

**Pattern observed:** Process exits with code 137 (SIGKILL) after running for ~16 minutes, but staging directory is complete with valid report.md.

**Why this happens:** The consolidate phase completes and writes staging artifacts, then the process is killed (possibly by OS memory limits, timeout, or manual intervention). The staging directory is written BEFORE the process exits, so even a SIGKILL leaves valid results.

**Detection:**
- Exit code: 137
- Staging directory exists with timestamp AFTER launch time
- report.md, report.json, manifest.json, diagnostics.json all present and non-empty

**Action:** Treat as SUCCESS. Read report.md from the latest staging directory and deliver results. Do NOT re-run or treat as failure.

**Example from this session:**
```
Exit code: 137
Uptime: 954s (~16 min)
Staging dir: 20260714-220747 (created at 22:07, after launch)
Result: Valid report.md with gate decision and edit summaries
```

## Reading Results from state.json (FASTEST PATH for multi-night runs)

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

**When to use this:**
- Quick overview of ALL nights without reading individual staging directories
- Computing score trajectory across the entire optimization run
- Reporting "what happened" to the user in a single command

**See `skillopt-sleep` skill for full details on state.json structure and fields.**

## Iterative Optimization Pattern

**Multi-night progression:** A single SkillOpt run may execute multiple "nights" (iterations), each producing a staging directory. Score improvements accumulate across nights.

**Observed pattern (session 2026-07-14):**
```
Night 5:  baseline 0.067 → candidate 0.417 (+522%)  ← first significant improvement
Night 7:  baseline 0.083 → candidate 1.000 (+91.7%) ← reached perfect score
Night 9:  baseline 0.750 → candidate 1.000 (+33.3%) ← maintained perfection
Night 10: baseline 1.000 → candidate 1.000 (reject)  ← no improvement space
```

**Key insights:**
- **Score progression tracking:** Monitor how scores evolve across nights. Early nights may show large jumps; later nights show diminishing returns.
- **Perfect score detection:** When baseline reaches 1.000, the gate automatically rejects all candidates (cannot improve on perfection). This is expected, not a failure.
- **Adoption strategy:** Adopt after each successful night (gate: accept_new_best), not just at the end. Each adoption applies incremental improvements.
- **Stopping criterion:** When baseline is 1.000 and gate rejects, optimization is complete. Further runs will not improve the skill.

**Monitoring multi-night runs:**
```bash
# After run completes, list all staging directories
ls -lt .skillopt-sleep/staging/ | head -10

# Each directory represents one night's results
# Read the LATEST directory for final results
cat .skillopt-sleep/staging/<latest-timestamp>/report.md
```

**Common scenario:** A single `run` command with 15 tasks may produce 5-10 staging directories (one per night). The final directory contains the cumulative optimization result.

## Perfect Baseline Scores (1.000) — Optimization Complete, Stop Running

**Pattern observed:** When baseline_score reaches 1.000 (perfect), the gate automatically rejects all candidate edits because candidate cannot improve on perfection.

**Why this happens:** The gate compares baseline_score vs candidate_score. If baseline is already perfect (1.000), no candidate can score higher, so gate_action = "reject" regardless of edit quality.

**Detection:**
- report.md shows: `held-out score: 1.000 -> 1.000`
- report.md shows: `gate: **reject** (accepted=False)`
- All edits appear under "## Rejected by gate" section

**⚠️ CRITICAL: This is the STOPPING CRITERION for optimization.**

When you see baseline 1.000 with gate reject:
1. **Optimization is COMPLETE** — the skill performs perfectly on the task set
2. **Do NOT run further optimizations** — they will all be rejected for the same reason
3. **Report results** — note that baseline was already perfect, so gate rejected all candidates
4. **The staging directory still contains useful diagnostics** — rejected edits show what the LLM considered but the gate rejected

**Interpretation:** This is NOT a failure of the optimization process. It means the current SKILL.md already performs perfectly on the task set. The rejected edits are still valuable as "negative feedback" — they show what the LLM considered adding but the gate rejected because it wouldn't improve performance.

**Common scenario:** Mock replay mode (no real session data) often produces perfect baseline scores because there's no actual failure trajectory to learn from. This is expected behavior, not a bug.

**Multi-night progression example (session 2026-07-14):**
```
Night 5:  baseline 0.067 → candidate 0.417 (+522%)  ← first significant improvement
Night 7:  baseline 0.083 → candidate 1.000 (+91.7%) ← reached perfect score
Night 9:  baseline 0.750 → candidate 1.000 (+33.3%) ← maintained perfection
Night 10: baseline 1.000 → candidate 1.000 (reject)  ← STOP HERE, optimization complete
```

**Action after reaching 1.000:** Adopt the final successful optimization (Night 7 in this example), commit to git, and stop running further optimizations.

**⛔ STRONGER SATURATION SIGNAL — 0 edits, 0 rejected edits:** When report.json shows `"edits": []` and `"rejected_edits": []` with baseline=1.000 → candidate=1.000, this is DEFINITIVE saturation. The LLM couldn't even generate any edits because there's no room for improvement. This is stronger than "gate=reject with rejected edits" — in that case, the LLM at least tried to propose improvements. With 0 edits, the consolidate phase determined no edits were worth proposing. **Action: STOP immediately. Do NOT run further optimizations. The skill has converged.**

**Observed 2026-07-15:** After 14 nights of optimization, Night 14 showed baseline=1.000 → candidate=1.000 with 0 edits and 0 rejected edits. Night 15 started but Claude CLI timed out during consolidate, causing process exit. The skill had saturated — further runs would produce no value.

**⛔ CONSECUTIVE SATURATION PATTERN — 3+ nights of baseline=1.000 with gate=reject:** When you observe 3 or more consecutive nights showing baseline=1.000 → candidate=1.000 with gate=reject (regardless of whether rejected_edits exist), this is CONCLUSIVE evidence that the skill has converged and further optimization is impossible. **Action: STOP ALL FURTHER RUNS IMMEDIATELY.**

**Observed 2026-07-15:** Nights 13-17 all showed baseline=1.000 → candidate=1.000 with gate=reject. Despite this clear saturation signal, runs continued to be dispatched, wasting API quota and creating redundant staging directories. The pattern should have triggered an immediate stop after Night 15 (3rd consecutive saturation).

**Saturation Detection Checklist (MANDATORY before dispatching any run):**
1. Check recent staging directories: `ls -lt .skillopt-sleep/staging/ | head -5`
2. Read the 3 most recent report.md files
3. If ALL 3 show baseline=1.000 → candidate=1.000 with gate=reject → **STOP**
4. Do NOT dispatch another run — the skill has converged

**Why this matters:** Continuing to run after saturation wastes:
- API quota (each run costs ~200-400K tokens)
- Time (each run takes 20-40 minutes)
- Storage (each run creates redundant staging directories)
- Claude CLI resources (concurrent runs cause timeouts and resource contention)

**The rejected_edits in saturation runs are NOT valuable:** They represent improvements the LLM considered but the gate rejected because they wouldn't improve the score. Once the skill is perfect, these rejected edits are just noise — they don't provide actionable insights. The only value is confirming that the skill is indeed perfect (which you already know from baseline=1.000).
