# Task Design Patterns

## Homogeneous vs Heterogeneous Task Design

**Problem observed (V1/V2):** Tasks tested the same dimension repeatedly with superficial variation.

- V1 (3 tasks): All tested "send meeting invite + date conversion"
  - task-001: absolute date
  - task-002: relative date (tomorrow)
  - task-003: relative date (next Monday)
  - Rubric nearly identical across tasks

- V2 (15 tasks): Still tested "send meeting invite + date conversion"
  - 10 train tasks: different names/dates/subjects, same core test
  - 5 edge cases: implicit requirements, user conflicts, ambiguous dates
  - Rubric still homogeneous (workflow structure + date handling)

**Result:** V2 ran for multiple nights but baseline quickly reached 1.000 (saturation). The tasks didn't expose new skill weaknesses because they all tested the same capability.

**Solution (V3):** Heterogeneous task design — each task tests a different dimension.

- V3 (11 tasks): 3 regression baseline + 8 new scenarios
  - Regression baseline: basic workflow, tomorrow, next Monday (from V2)
  - New scenarios: multi-recipient+CC, all-day event, vague request, cross-timezone, hybrid location, recurring meeting, colloquial request, room booking
  - Each task has a unique rubric targeting a specific capability

**Result:** V3 baseline was 0.0625 (vs V2's 1.000), exposing real skill weaknesses. Optimization improved to 0.625 with 2 accepted edits.

## When to Use Each Pattern

### Homogeneous (V1/V2 pattern)
**Use when:**
- Validating a specific fix (e.g., "did we fix date conversion?")
- Testing robustness across variations of the same scenario
- Skill is new and you want to confirm basic capability

**Avoid when:**
- Skill has reached saturation (baseline 1.000)
- You want to discover new weaknesses
- You're optimizing for generalization

### Heterogeneous (V3 pattern)
**Use when:**
- Discovering skill weaknesses across multiple dimensions
- Optimizing for generalization (not just one scenario)
- Skill has reached saturation on homogeneous tasks

**Design principles:**
1. **Identify capability dimensions** (not just scenario variations)
   - Date handling, parameter parsing, error handling, clarification, edge cases, etc.
2. **One task per dimension** (avoid redundancy)
3. **Include regression baseline** (2-3 tasks from previous version to ensure no regressions)
4. **Unique rubrics** (each task tests something different)

## Regression Baseline Pattern

**Purpose:** Ensure new optimizations don't break existing capabilities.

**Implementation:**
- Include 2-3 tasks from the previous task version
- Place them in the train split (so they drive reflect)
- Use the same rubric as the original tasks

**Example (V3):**
```json
{
  "id": "v3-baseline-001",
  "intent": "Basic workflow + absolute date (from V2 train-001)",
  "rubric": "Same as V2 train-001 rubric",
  "split": "train",
  "origin": "v2-regression"
}
```

**Split allocation:**
- 3 regression baseline tasks (train)
- 5-8 new scenario tasks (train/val/test)
- Total: 8-11 tasks

## Diagnostic: Call Count vs Prompt Size

**Problem:** V1 (3 tasks) took ~2 minutes, V2-subset (3 tasks) took ~7 minutes. Why?

**Root cause analysis:**
- V1: 6 Claude CLI calls (3 tasks × attempt+judge)
  - All tasks passed → no failures → no reflect → no gate scoring
  - Total: 6 calls × ~10-20s = ~2 minutes

- V2-subset: 13 Claude CLI calls
  - 6 calls: replay (3 tasks × attempt+judge)
  - 1 call: reflect (failures detected)
  - 6 calls: gate scoring (val tasks × attempt+judge)
  - Total: 13 calls × ~10-20s = ~7 minutes

**Key insight:** Time difference is driven by **call count**, not prompt size.

**Diagnostic technique:**
```bash
# Count Claude CLI calls
grep -E "Claude CLI (CALL|RESPONSE)" run.log | wc -l

# Check prompt sizes
grep "Claude CLI CALL" run.log | grep -o "prompt: [0-9]* chars"

# Identify which phase is slow
grep -E "(consolidate|staging|reflect|gate)" run.log
```

**Implications:**
- Large prompts (37K chars) complete in 10-30s — not the bottleneck
- More tasks = more calls = longer runtime
- 180s timeout is sufficient for individual calls (has 6-18x headroom)
- To reduce runtime: reduce task count or optimize call efficiency

## Task Version Evolution

**V1 → V2 → V3 progression:**

| Version | Tasks | Dimensions | Baseline | Purpose |
|---------|-------|-----------|----------|---------|
| V1 | 3 | 1 (date conversion) | 0.975 | Pilot validation |
| V2 | 15 | 1 (date conversion) + 5 edge cases | 1.000 | Saturation test |
| V3 | 11 | 8 (heterogeneous) | 0.0625 | Weakness discovery |

**Lesson:** Homogeneous tasks saturate quickly. Heterogeneous tasks expose real weaknesses and drive meaningful optimization.

## Task Design Checklist

Before running SkillOpt with a new task version:

- [ ] **Identify capability dimensions** (not just scenario variations)
  - List all skills the agent should demonstrate
  - Map each dimension to a test scenario
- [ ] **Include regression baseline** (2-3 tasks from previous version)
  - Ensures no regressions
  - Provides continuity across versions
- [ ] **One task per dimension** (avoid redundancy)
  - Each task should test something unique
  - Unique rubrics for each task
- [ ] **Proper split allocation**
  - 5-7 train tasks (drive reflect)
  - 2 val tasks (gate scoring)
  - 1-2 test tasks (held-out evaluation)
- [ ] **Set `reviewed: true`** (required for real backend)
- [ ] **Verify task schema** (id, project, intent, reference, split, etc.)
