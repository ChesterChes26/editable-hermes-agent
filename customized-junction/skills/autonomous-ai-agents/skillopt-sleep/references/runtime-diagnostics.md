# SkillOpt Runtime Diagnostics

## Debug Logging Pattern

When SkillOpt consolidation fails or behaves unexpectedly, add debug logging to `ClaudeCliBackend._call()` in `skillopt_sleep/backend.py`:

```python
def _call(self, prompt: str, *, max_tokens: int = 1024) -> str:
    # ... existing setup code ...
    
    # Debug: print prompt info
    print(f"\n{'='*60}", flush=True)
    print(f"Claude CLI CALL (prompt: {len(prompt)} chars, timeout: {self.timeout}s)", flush=True)
    print(f"{'='*60}", flush=True)
    print(prompt[:2000] + ("..." if len(prompt) > 2000 else ""), flush=True)
    
    try:
        proc = subprocess.run(cmd, capture_output=True, ...)
    except Exception as exc:
        print(f"\nClaude CLI TIMEOUT/ERROR: {exc}", flush=True)
        # ... error handling ...
    
    out = (proc.stdout or "").strip()
    
    # Debug: print response info
    print(f"\n{'='*60}", flush=True)
    print(f"Claude CLI RESPONSE ({len(out)} chars)", flush=True)
    print(f"{'='*60}", flush=True)
    print(out[:2000] + ("..." if len(out) > 2000 else ""), flush=True)
    if proc.stderr:
        print(f"\nSTDERR: {proc.stderr[:500]}", flush=True)
    
    return out
```

## Call Chain Analysis

A single consolidation with N train tasks and M val tasks produces:

```
Phase 1: Baseline Scoring (val)       = 2M calls
Phase 2: Replay Train (skill evolve)  = 2N calls
Phase 3: Reflect (skill)              = 1 call
Phase 4: Gate Apply (skill)           = 2M calls
Phase 5: Replay Train (memory evolve) = 2N calls
Phase 6: Reflect (memory)             = 1 call
Phase 7: Gate Apply (memory)          = 2M calls
Phase 8: Final Scoring (val)          = 2M calls

Total: 6M + 4N + 2 calls
```

**Verified with V3 run**: 7 train + 2 val = 6(2) + 4(7) + 2 = **42 calls** ✓

**Why val is scored 4 times**: Baseline (Phase 1) establishes reference, gate skill (Phase 4) validates skill edits, gate memory (Phase 7) validates memory edits, final (Phase 8) confirms final score. Each scoring = attempt + judge = 2 calls per val task.

## Diagnostic Commands

```bash
# Count total calls
grep -c "Claude CLI CALL" /tmp/skillopt_run.log

# Extract call chain with prompt sizes
grep -E "Claude CLI (CALL|RESPONSE)" /tmp/skillopt_run.log | awk '{print NR": "$0}'

# Find timeout errors
grep "TIMEOUT" /tmp/skillopt_run.log

# Extract specific phase (e.g., reflect with 37K prompt)
grep -A20 "Claude CLI CALL (prompt: 37K" /tmp/skillopt_run.log

# Find failed tasks (score = 0)
grep -B5 '"score": 0' /tmp/skillopt_run.log
```

## Common Issues

### Issue: Timeout on first call
**Symptom**: `Claude CLI could not be executed: Command '...' timed out after 180 seconds` on consolidate start
**Root cause**: Usually transient (API slow, network jitter). Retry often succeeds.
**Evidence**: Night 10 failed, Night 16 with same 15 tasks succeeded.

### Issue: V1 fast, V2 slow
**Symptom**: V1 (3 tasks) completes in 2min, V2 (15 tasks) takes 15-30min or times out
**Root cause**: Not prompt size (180s timeout is per-call, sufficient for 37K prompts). It's call count.
- V1: 6 calls (all pass, skip reflect)
- V2: 37 calls (15 train × 2 + 1 reflect + 3 val × 2 + gate scoring)
**Diagnosis**: Check call count in log, not prompt size.

### Issue: Large attempt responses
**Symptom**: Some attempts return 28K+ chars instead of 1-3K
**Root cause**: Skill requires "complete workflow description" (e.g., "Response Structure Rule — Mandatory for every step")
**Impact**: These large responses get included in reflect prompt (skill 35K + failure 28K = 63K), but still complete within 180s.
**Mitigation**: Not a timeout issue. If needed, truncate failure responses in reflect() to 1K each.

## Key Insight

**180s timeout is per Claude CLI call, not per task or per consolidation.** Each call (attempt/judge/reflect) has independent 180s limit. With 42 calls at 10-30s each, total runtime is 7-21 minutes, but no single call should timeout unless there's an API issue.
