# Terminal Conditions for SkillOpt-Sleep

## 100% Baseline Performance

When `baseline_score` reaches 1.000 (100% of tasks pass), the gate will reject all candidate edits because no improvement is possible. This is the **natural stopping point** for optimization.

### Symptoms
- `baseline_score: 1.000`
- `candidate_score: 1.000`
- `gate_action: reject`
- `accepted: false`
- Multiple consecutive runs showing the same pattern

### What This Means
The skill has reached its practical limit for the current task distribution. Continuing to run more sleep cycles will waste resources (API calls, time) without producing any accepted edits.

### Next Steps
1. **Stop optimizing this task set** — you've reached the ceiling
2. **Add harder tasks** to `tasks.json` that expose remaining weaknesses
3. **Accept the skill is complete** for the current task distribution

### Example
```json
{
  "night": 20,
  "baseline": 1.000,
  "candidate": 1.000,
  "gate_action": "reject",
  "accepted": false,
  "n_accepted_edits": 0,
  "n_rejected_edits": 5
}
```

This pattern repeated across multiple nights indicates the optimization is complete.
