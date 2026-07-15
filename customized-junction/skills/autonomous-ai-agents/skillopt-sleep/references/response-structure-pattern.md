# Response Structure Pattern for Pure-Text SkillOpt Evaluation

## Problem

SkillOpt's `claude` backend runs in **pure-text replay mode** — it cannot execute actual CUA/GUI operations. It only evaluates whether the agent's response text demonstrates correct understanding of the skill's workflow.

If the target skill doesn't instruct the agent to show structured thinking at each step, the agent may:
- Stop after Step 0a (daemon startup) without describing subsequent steps
- Output only tool calls without explaining reasoning
- Skip error handling entirely

This produces low baseline scores (e.g., 0.150) because the rubric can't find evidence of understanding.

## Solution: Skill Controls Response Structure

The **target skill** (not the rubric) must define a response structure that forces the agent to show structured thinking at each step. The rubric then evaluates whether these elements are present and correct.

### Required Per-Step Structure

For EACH step (Step 0-5), the skill must require the agent to include:

```markdown
## Step N: [Step Name]

**Current State Awareness:**
Assume Step N-1 succeeded. Current state is [expected state description].

**Next Action Goal:**
What this step aims to accomplish.

**Execution Method:**
Specific commands/actions to take.

**Error Handling:**
- Failure scenario 1 → Recovery action
- Failure scenario 2 → Recovery action
```

### Why Skill Controls This (Not Rubric)

1. **Skill is the agent's execution guide** — if the skill doesn't require structured output, the agent won't produce it
2. **Rubric can only evaluate what exists** — if the agent doesn't output the 4 elements, rubric evaluates "air"
3. **Actual CUA execution also benefits** — agents that articulate state/goal/method/errors perform better in real execution too

### Token Cost

- ~100-150 tokens per step × 6 steps = 600-900 tokens total
- This is acceptable — it's the cost of evaluable output
- Keep each element concise (1-2 sentences)

## How to Add This to a Target Skill

Add a section like this to the target SKILL.md:

```markdown
## 🔴 Response Structure Rule

For EACH step (Step 0-5), your response MUST include these 4 elements:

1. **Current State Awareness** — What you assume about current state (based on previous step success)
2. **Next Action Goal** — What this step aims to accomplish
3. **Execution Method** — Specific commands/actions
4. **Error Handling** — At least 2 failure scenarios with recovery actions

Keep each element concise (1-2 sentences). Do NOT repeat information from previous steps.
```

## Rubric Design for This Pattern

Rubric evaluates whether the agent's response covers the 4 elements for task-relevant steps:

```
PASS if response demonstrates understanding of Step N:
1) Correctly describes current state (based on previous step success assumption)
2) Clearly states the goal of this step
3) Gives specific execution method matching skill guidance
4) Lists at least 2 failure scenarios with recovery actions

FAIL if response:
- Missing any of the 4 elements
- State awareness contradicts expected flow
- Execution method contradicts skill guidance
- No error handling logic
```

### Task-Specific Focus

Different tasks should focus rubric evaluation on different steps:

- **Task with absolute dates**: Focus on compose step (Step 3) — correct parameter passing
- **Task with relative dates ("tomorrow")**: Focus on date resolution logic before compose
- **Task with relative dates ("next Monday")**: Focus on correct date calculation

The rubric should reference the task-specific core points, not require all 6 steps equally.

## Observed Anti-Pattern (2026-07-15)

V1 tasks (3 tasks) used rubric "PASS if response demonstrates correct understanding of skill guidance" without requiring structured per-step output. Agent stopped at Step 0a (daemon startup) and produced no evidence of understanding Steps 1-5. Baseline=0.150, no improvement possible because the rubric couldn't find what it wasn't looking for.

**Root cause**: Skill didn't require structured response, rubric evaluated "general understanding" instead of specific per-step elements.

**Fix**: Add Response Structure Rule to skill, redesign rubric to evaluate the 4 elements per task-relevant step.

## Critical: Rubric-Skill Alignment

**When you modify the target skill, you MUST also update the rubric to evaluate the new requirement.**

Example: If you add "Response Structure Rule" to the skill (requiring 4 elements per step), the rubric must explicitly check for those 4 elements.

**Checklist before running:**
1. Did I modify the skill text? → Yes → Update rubric
2. Does the rubric evaluate the new requirement? → No → Add evaluation criteria
3. Are the rubric's PASS/FAIL conditions aligned with the skill's requirements? → Verify

**Anti-pattern observed:** Added Response Structure Rule to skill but forgot to update rubric. Result: SkillOpt couldn't detect whether the agent followed the new rule, baseline stayed at 0.150, all proposed edits rejected.

## Token Cost and Timeout Risk

**Problem**: The Response Structure Rule forces the agent to output ALL steps with full structure (e.g., 8 steps × 4 elements = 32 subsections). This causes attempt responses to balloon from ~2K chars to ~28K chars.

**Impact on consolidate phase**:
```
attempt response = 28K chars (32 subsections)
→ embedded in reflect prompt as failure evidence
→ reflect prompt = 36K chars (skill 35K + failure 28K)
→ gate scoring prompt = 37K chars
→ each Claude CLI call takes 60-180s
→ total consolidate = 7+ min for 3 tasks
→ with 15+ tasks, scales to timeout territory
```

**Observed 2026-07-15**:
- V1 (rubric evaluates "core understanding"): attempt responses ~1-3K, 6 calls, ~2 min, all pass
- V2 (rubric evaluates Response Structure Rule): attempt responses up to 28K, 13 calls, ~7 min, timeouts

**Mitigation strategies**:
1. **Relax the rule**: Instead of requiring ALL steps, require only task-relevant steps. For a date-handling task, only require Step 3 (compose) to show date conversion.
2. **Increase Claude CLI timeout**: Change `backend.py:561` from `timeout: int = 180` to `timeout: int = 600`.
3. **Reduce edit budget**: Use `--edit-budget 2` instead of 4 to reduce reflect iterations.

**Detection**: If V1 runs fast but V2 hangs at consolidate, check attempt response sizes:
```bash
grep "Claude CLI RESPONSE" /tmp/skillopt_v2_run.log | head -10
# If responses are 10K+ chars → prompt inflation is the cause
```

**Recommendation**: The Response Structure Rule is valuable for pure-text evaluation, but creates a token-cost feedback loop. If consolidate timeouts become a pattern, relax the rule to require only task-relevant steps rather than all steps.
