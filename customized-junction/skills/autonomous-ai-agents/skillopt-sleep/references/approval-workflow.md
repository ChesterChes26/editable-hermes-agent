# Approval Workflow for Adopt/Commit

## Critical Rule: No Automatic Adoption

After a successful SkillOpt-Sleep run, DO NOT automatically:
- Run `skillopt_sleep adopt`
- Make git commits
- Apply edits to the target SKILL.md

## Required Workflow

1. Read the staging report.md
2. Present to user:
   - Gate decision (accept/reject)
   - Baseline vs candidate scores
   - Summary of proposed edits (added/replaced rules)
3. Ask: "Adopt these changes?"
4. Wait for explicit user approval
5. Only then run adopt and commit

## Why This Matters

The user may want to:
- Review the proposed changes before applying
- Compare against previous runs
- Decide not to adopt (e.g., when baseline is already 1.0)
- Manually edit the proposed rules

Automatic adoption without approval has caused unwanted commits in past sessions.
