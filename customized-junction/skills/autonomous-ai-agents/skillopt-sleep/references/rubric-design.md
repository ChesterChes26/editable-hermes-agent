# Rubric Design for Pure-Text Replay

## The Core Problem

In pure-text replay mode, Claude returns **planning text**, not execution reports. Rubrics must match this reality.

### Wrong Rubric (Execution-Report Style) → baseline=0.0

```text
PASS if response describes correct steps in order:
  1) Launch Outlook Classic (not new Outlook)
  2) Create New Meeting/Event
  3) Fill attendees field with test@example.com
  4) Set date 2026-07-15, time 10:00-10:30
  5) Set subject 'Project Sync'
  6) Add Tencent Meeting info (join link/ID/password)
  7) Verify all fields before send
  8) Send the invite
FAIL if any step missing or incorrect.
```

**Why it fails:**
- Claude's response: "I'll start with Step 0: MCP Availability Check..."
- Judge looks for: "Launched Outlook Classic", "Created meeting", "Sent invite"
- Result: 0 matches → baseline=0.0, candidate=0.0
- SkillOpt produces no meaningful optimization

### Correct Rubric (Skill-Text Understanding Style) → baseline=0.35

```text
PASS if response demonstrates correct understanding of skill guidance:
  1) Response identifies this requires Outlook Classic (not new Outlook)
  2) Response mentions Tencent Meeting integration step
  3) Response follows skill's workflow structure (pre-check → launch → compose → send → verify)
  4) Response acknowledges critical constraints (e.g., popup handling, COM automation)
  5) Response prioritizes steps according to skill's markers
FAIL if response ignores skill's priority markers, misorders workflow steps, or omits critical constraints mentioned in skill.
```

**Why it works:**
- Claude's response: "I'll start with Step 0: MCP Availability Check..."
- Judge looks for: understanding of workflow structure, priority markers, constraints
- Result: partial matches → baseline=0.35
- SkillOpt can identify which skill sections are misunderstood and propose targeted improvements

## Key Principles

1. **Evaluate comprehension, not completion**: Judge whether Claude understood the skill's guidance, not whether it "completed" the task
2. **Focus on skill-text signals**: Workflow structure, priority markers, error handling, critical constraints, verification steps
3. **Avoid execution verbs**: Don't use "launched", "created", "sent", "filled" — these imply completed actions
4. **Use understanding verbs**: "identifies", "follows", "acknowledges", "prioritizes", "demonstrates"

## Example Task with Correct Rubric

```json
{
  "id": "task-001",
  "intent": "Create and send a meeting invitation via Outlook Classic + Tencent Meeting. Recipient: test@example.com. Time: 2026-07-15 10:00-10:30. Subject: Project Sync.",
  "reference_kind": "rubric",
  "reference": "PASS if response demonstrates correct understanding of skill guidance: 1) identifies this requires Outlook Classic 2) mentions Tencent Meeting integration 3) follows workflow structure (pre-check → launch → compose → send → verify) 4) acknowledges critical constraints (popup handling, COM automation) 5) prioritizes steps per skill's markers. FAIL if response ignores priority markers, misorders workflow, or omits critical constraints."
}
```

## Task Intent Pattern: Core-Point Evaluation

When the goal is to verify the agent understood key concepts (not execute all steps), use "briefly describe" intent:

```json
{
  "id": "task-001",
  "intent": "请简要描述你打算如何处理这个会议邀请任务，重点关注：Outlook 启动方式、腾讯会议集成步骤、发送后验证。",
  "reference": "评估 response 是否覆盖了 task 的核心要点：\n1) 是否正确理解了 Outlook 启动方式（subprocess.Popen）\n2) 是否理解了腾讯会议集成步骤（Step 2）\n3) 是否理解了发送后验证（Sent Items + Calendar）\n\nPASS: 覆盖以上 3 个核心要点\nFAIL: 遗漏任何核心要点"
}
```

**Why this works:**
- Intent asks for "brief description" (简要描述), not full execution
- Intent explicitly lists the core points to focus on
- Rubric evaluates whether those specific points are understood
- Agent can't fake understanding by describing steps it doesn't comprehend

**When to use this pattern:**
- Pilot testing (3-5 tasks) to verify skill comprehension
- When you want to test conceptual understanding before full execution testing
- When the skill has complex workflows and you want to isolate specific concepts

## Verification Checklist

Before running SkillOpt-Sleep, verify rubric:
- [ ] Uses "demonstrates understanding" language, not "completed action" language
- [ ] References skill-text signals (workflow, priorities, constraints)
- [ ] Does NOT require evidence of actual GUI execution
- [ ] Pilot test: run 1-2 tasks with `--backend mock` to confirm rubric produces non-zero baseline
- [ ] If using "briefly describe" pattern: intent explicitly lists core points, rubric checks those points
