# Consolidate Phase: Full Call Chain

Source: `consolidate.py:87-266`, verified with V3 run (2026-07-15, 42 calls).

## 8 Phases

```
consolidate(backend, tasks, skill, memory)
│
├─ Phase 1: Baseline Scoring (val tasks)
│  ├─ attempt(val_1) → 34K prompt → response
│  ├─ judge(val_1, response) → 1K prompt → score
│  ├─ attempt(val_2) → 34K prompt → response
│  └─ judge(val_2, response) → 1K prompt → score
│  = 2 × n_val calls
│  Output: baseline_score = avg(scores)
│
├─ Phase 2: Replay Train (skill evolution)
│  ├─ attempt(train_1..N) × N → 34K each
│  └─ judge(train_1..N) × N → 1K each
│  = 2 × n_train calls
│  Output: failures (score < 1.0), successes (score >= 1.0)
│
├─ Phase 3: Reflect (skill)
│  └─ reflect(failures[:8], successes, skill, memory) → 37K prompt
│  = 1 call
│  Output: List[EditRecord] (proposed skill edits, max edit_budget)
│
├─ Phase 4: Gate Apply (skill)
│  ├─ apply edits → cand_skill
│  ├─ attempt(val_1..2) × 2 → 35K each
│  └─ judge(val_1..2) × 2 → 6K each
│  = 2 × n_val calls
│  Decision: if cand_score > baseline → accept edits, else reject
│
├─ Phase 5: Replay Train (memory evolution, with updated skill)
│  ├─ attempt(train_1..N) × N → 34K each
│  └─ judge(train_1..N) × N → 1K each
│  = 2 × n_train calls
│  Output: new failures under improved skill
│
├─ Phase 6: Reflect (memory)
│  └─ reflect(failures[:8], successes, cand_skill, memory) → 37K prompt
│  = 1 call
│  Output: List[EditRecord] (proposed memory edits)
│
├─ Phase 7: Gate Apply (memory)
│  ├─ apply edits → cand_memory
│  ├─ attempt(val_1..2) × 2 → 35K each
│  └─ judge(val_1..2) × 2 → 6K each
│  = 2 × n_val calls
│  Decision: if cand_score > baseline → accept edits, else reject
│
└─ Phase 8: Final Scoring (val tasks, with final skill+memory)
   ├─ attempt(val_1..2) × 2 → 35K each
   └─ judge(val_1..2) × 2 → 6K each
   = 2 × n_val calls
   Output: candidate_score = avg(final scores)
```

## Formula

```
Total = 6 × n_val + 4 × n_train + 2
```

## V3 Example (7 train + 2 val + 2 test)

| Phase | Calls | Prompt Size | Response Size |
|-------|-------|-------------|---------------|
| 1. Baseline | 4 | 34K, 1K | 918, 626, 632, 559 |
| 2. Replay train (skill) | 14 | 34K, 1K | 622-1128, 536-771 |
| 3. Reflect (skill) | 1 | 37K | 2798 |
| 4. Gate skill | 4 | 35K, 6K | 6108, 900, 696, 664 |
| 5. Replay train (memory) | 14 | 34K, 1K | 585-958, 355-773 |
| 6. Reflect (memory) | 1 | 37K | 2489 |
| 7. Gate memory | 4 | 35K, 1K | 1040, 753, 515, 463 |
| 8. Final | 4 | 35K, 6K | 463, ... |
| **Total** | **42** | | |

## Key Observations

1. **attempt prompts are ~34K** because they include the full SKILL.md (~35K chars)
2. **reflect prompts are ~37K** because they include skill + up to 8 failures (each truncated to 160 chars)
3. **gate judge prompts are ~6K** (larger than replay judge ~1K) because they include the full rubric + response
4. **No parallelism** — all calls are serial within a phase
5. **Train replayed twice** — Phase 2 uses original skill, Phase 5 uses improved skill (after skill edits applied)
6. **Val scored 4 times** — Phase 1 (baseline), Phase 4 (gate skill), Phase 7 (gate memory), Phase 8 (final)

## Why 180s Timeout is Sufficient

- Each call takes 10-30 seconds
- Max prompt: 37K chars (reflect) — completes in ~20s
- Max response: 28K chars (attempt with full workflow output) — completes in ~30s
- 180s provides 6-18x headroom per call
- Timeout failures are transient (API slowness), not systematic

## Debugging: Where Did a Run Get Stuck?

```bash
# Count calls per phase by prompt size pattern:
grep "Claude CLI CALL" /tmp/skillopt_run.log | \
  awk '{for(i=1;i<=NF;i++) if($i ~ /prompt:/) print $(i+1)}' | \
  sort | uniq -c

# Phases by prompt size:
# ~34K = attempt (Phase 2 or 5)
# ~35K = gate attempt (Phase 4, 7, or 8)
# ~37K = reflect (Phase 3 or 6)
# ~1K  = judge (Phase 1, 2, or 5)
# ~6K  = gate judge (Phase 4, 7, or 8)
```
