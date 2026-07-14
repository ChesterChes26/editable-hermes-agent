# Using SkillOpt-Sleep to Improve an Existing Operational Skill

Use this when the user has a concrete `SKILL.md` that behaves like an agent plugin (tool orchestration, GUI/COM workflow, coding workflow) and asks how to make it more reliable.

## Principle

SkillOpt trains the skill document, not the agent runtime or model. For an existing operational skill, the useful optimization target is not prose quality; it is whether a fresh agent uses the skill correctly under pressure.

## Preferred workflow

1. Fix known factual contradictions manually first.
   - Do not ask SkillOpt to rediscover verified ground truth.
   - Example classes: wrong tool order, stale platform-specific workaround, known COM/ROT behavior, known API contract.

2. Create a reviewed task file instead of relying only on transcript harvest.
   - Operational skills often have external side effects, sparse transcripts, and workflow failures that are better represented as rubrics.
   - Use `reviewed: true` before running a real backend.

3. Point SkillOpt-Sleep at the exact live skill.

```bash
python -m skillopt_sleep run \
  --project "D:/path/to/project" \
  --tasks-file "D:/path/to/project/skillopt-sleep-tasks/<skill>.tasks.json" \
  --target-skill-path "D:/path/to/project/.claude/skills/<category>/<skill>/SKILL.md" \
  --backend handoff \
  --edit-budget 4 \
  --progress
```

4. Review staged output before adopt.
   - Inspect `.skillopt-sleep/staging/<timestamp>/proposed_SKILL.md`, `report.md`, and `manifest.json`.
   - Reject broad rewrites, unverified fallbacks, or edits that collapse platform-specific paths into one vague path.

5. Pressure-test with fresh-context scenarios before adopt/commit.
   - Ask for a plan, not real side-effect execution, when the workflow can send mail, book meetings, delete data, or publish.

## Reviewed task file shape

```json
{
  "format": "skillopt_sleep.tasks.v1",
  "project": "D:/path/to/project",
  "transcript_source": "manual-reviewed",
  "n_sessions": 0,
  "target_skill_path": "D:/path/to/project/.claude/skills/<category>/<skill>/SKILL.md",
  "reviewed": true,
  "tasks": [
    {
      "id": "skill-001-no-wrong-fallback",
      "project": "D:/path/to/project",
      "intent": "User asks for the normal task this skill handles.",
      "context_excerpt": "The skill states the correct tool split and known platform constraints.",
      "attempted_solution": "Agent used a tempting but invalid fallback.",
      "outcome": "fail",
      "reference_kind": "rubric",
      "reference": "A correct answer must follow the verified tool split, name the invalid fallback as prohibited, and preserve the required verification/reporting contract.",
      "tags": ["skill", "workflow", "tool-use"],
      "split": "train",
      "origin": "real"
    }
  ]
}
```

## What to encode as tasks

Good tasks:
- Trigger/load accuracy: user asks in natural language and the agent should choose this skill.
- Known bad fallback: agent tries a tool path the skill forbids.
- State tracking: stale ids/handles, wrong target window/process, missing explicit identifiers.
- Verification: screenshot/report/state checks in the required order.
- Output contract: final report shape, no hidden tool-result-only deliverable.
- Cost discipline: avoid expensive screenshots/reads when text state is sufficient.

Avoid:
- One-off transcripts with no reusable failure class.
- Live side-effect execution as the replay target.
- Asking SkillOpt to resolve a factual conflict already settled by real verification.

## Adoption rule

SkillOpt-Sleep proposes bounded edits; it does not replace skill review. Treat the staged proposal like a code patch: diff it, check whether it preserves the skill's contract, then adopt only if it improves the pressure scenarios.