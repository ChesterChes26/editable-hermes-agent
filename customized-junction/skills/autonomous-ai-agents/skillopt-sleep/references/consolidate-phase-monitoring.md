# Consolidate Phase Monitoring (2026-07-15)

Session observation: SkillOpt-Sleep consolidate phase behavior that differs from the "staging dir appears every night" mental model.

## Key Insight

During the **consolidate phase** (where Claude generates candidate edits via LLM API calls), the process can run **15-20+ minutes with NO visible filesystem changes**:
- `state.json` is NOT updated until the night completes
- No new staging directories appear until the night completes  
- The process IS working if the Python process is alive

This is distinct from the "staging dir appears every night" guidance — staging dirs only appear AFTER consolidate completes and the night's work is finalized.

## How to Verify the Process is Actually Working

```bash
# Check Python process is alive
ps -ef | grep "python.*skillopt" | grep -v grep

# Check for active Claude temp directories (created during consolidate)
ls -la /tmp/skillopt_sleep_claude_* 2>/dev/null | tail -5

# Check state.json mtime (only updates at night completion)
stat "$PROJECT/.skillopt-sleep/state.json" | grep Modify
```

If Python process is alive AND Claude temp dirs exist with recent mtimes → process is working normally. WAIT.

## Anti-Pattern: Repeated Polling

Observed 2026-07-15: Agent called `process action=poll` or `process action=wait timeout=60` **16+ times over 20 minutes**. Each call returned identical "still running" output. The agent burned 16 turns producing zero information.

**Correct pattern:** After launching with `background=true, notify_on_complete=true`:
- T+0: Launch
- T+5m: Filesystem check (staging dirs, state.json mtime)
- T+10m: Same check
- T+15m: Same check
- Continue every 5-10 minutes until `notify_on_complete` fires
- BETWEEN checks: DO NOTHING. Do not poll. Do not wait. Do not check stdout.

## Expected Final Output (JSON mode)

```json
{
  "night": 21,
  "accepted": false,
  "gate_action": "reject",
  "baseline": 1.0,
  "candidate": 1.0,
  "n_tasks": 15,
  "n_accepted_edits": 0,
  "n_rejected_edits": 8,
  "edits": [],
  "rejected_edits": [...],
  "staging_dir": "<project>/.skillopt-sleep/staging/<timestamp>"
}
```

When `baseline == candidate`, the gate rejects (no improvement). Rejected edits are preserved in the output and show what the system tried but didn't adopt — useful for understanding failure patterns.

## Staging Directory Contents

After a night completes, the staging dir contains:
- `report.json` — Full structured results
- `report.md` — Human-readable summary
- `diagnostics.json` — Detailed diagnostics
- `manifest.json` — Run metadata
