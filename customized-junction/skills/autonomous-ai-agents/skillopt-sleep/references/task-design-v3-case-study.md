# V3 Task Design Case Study: Dimension Diversity

## Problem with V1/V2

**V1** (3 tasks): All tested date conversion + basic workflow
- task-001: absolute date
- task-002: "tomorrow" (relative date)
- task-003: "next Monday" (relative date)

**V2** (20 tasks): Same dimension, just more variations
- 10 train + 5 val + 5 test
- All tested date conversion + workflow structure
- Different names/dates/subjects, but same capability

**Result**: V1 and V2 both reached 100% score quickly because they only tested 1-2 dimensions.

## V3 Design: 8 Different Dimensions

**Goal**: Test 8 different capability dimensions, 1 task per dimension

| # | Scenario | Dimension Tested | Split |
|---|----------|------------------|-------|
| 1 | Basic workflow + absolute date | Baseline regression | train |
| 2 | Relative date (tomorrow) | Date conversion | train |
| 3 | Relative date (next Monday) | Date calculation | val |
| 4 | Multiple recipients + CC | Parameter parsing | train |
| 5 | All-day event (no time) | Event type handling | train |
| 6 | Vague request (no details) | Clarification behavior | train |
| 7 | Cross-timezone (EST) | Timezone conversion | val |
| 8 | Physical location + Tencent Meeting | Hybrid meeting | train |
| 9 | Recurring meeting (weekly) | Recurrence pattern | test |
| 10 | Colloquial request | Natural language parsing | train |
| 11 | Room booking only | Capability boundary | test |

**Split distribution**: 7 train (64%) + 2 val (18%) + 2 test (18%)

## Results

**Baseline**: 6.25% (val tasks failed)
**Candidate**: 62.5% (after SkillOpt optimization)
**Improvement**: +900%

**Accepted edits** (2):
1. Response Completeness Gate — force all 9 steps in response
2. Response Length Priority — completeness > brevity

**Rejected edits** (3):
1. Parameter extraction rule (no improvement on val)
2. Meeting output contract (no improvement on val)
3. Completeness override (duplicate of accepted edit)

## Key Insights

1. **V3 exposed real blind spots**: V1/V2 couldn't find these because they only tested date conversion
2. **Low baseline is expected**: When testing new dimensions, baseline will be low (6.25% vs 100% in V2)
3. **Optimization is effective**: +900% improvement shows SkillOpt can learn new capabilities
4. **Gate works correctly**: Rejected 3 edits that didn't improve val score

## Lessons

- **Dimension diversity > task count**: 11 tasks testing 8 dimensions is more valuable than 20 tasks testing 1 dimension
- **Low baseline is OK**: It means you're testing something new, not that the system is broken
- **Val set is critical**: It prevents overfitting to train tasks and ensures generalization

## Comparison

| Metric | V1 (3 tasks) | V2 (20 tasks) | V3 (11 tasks) |
|--------|--------------|---------------|---------------|
| Dimensions tested | 2 | 2 | 8 |
| Baseline | 100% | 100% | 6.25% |
| Final score | 100% | 100% | 62.5% |
| Improvement | 0% | 0% | +900% |
| Claude CLI calls | 6 | 37 | 42 |
| Run time | 2 min | 10 min | 10 min |

**Conclusion**: V3 is more valuable despite lower final score because it tested more dimensions and found real blind spots.
