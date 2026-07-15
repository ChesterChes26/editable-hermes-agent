# Consolidate Hang Diagnosis

## Problem

Consolidate phase hangs indefinitely. Process shows "running" but produces no output for 15-30+ minutes. No new staging directories appear.

## Root Cause

**claude.exe crashes at the OS level.** The Python process stays alive but stuck waiting for a dead subprocess.

This is NOT:
- A Python `subprocess.run(timeout=...)` issue
- A task count issue (happens with 10 tasks too)
- A memory/resource issue

Increasing timeout from 180s to 600s in `backend.py` is INEFFECTIVE because the real failure is claude.exe vanishing, not Python timing out.

## Diagnosis (run at T+15 minutes)

```bash
# Check if claude.exe is still alive
tasklist | grep -i claude

# Check if Python process is still alive
ps aux | grep python | grep -v grep
```

**Decision tree**:
| claude.exe | Python | Status | Action |
|------------|--------|--------|--------|
| PRESENT | PRESENT | Working normally | Wait |
| ABSENT | PRESENT | **DEAD** | Kill immediately |
| ABSENT | ABSENT | Already exited | Check staging dirs |

## Observed Cases (2026-07-15)

1. **20 tasks, single run**: Hung 46 minutes, claude.exe disappeared, Python still alive
2. **10 tasks, batch 1**: Hung 18 minutes, claude.exe disappeared, Python still alive
3. **Both cases**: No staging directory produced, state.json unchanged

## What to Do

1. **Kill immediately** when claude.exe is gone (don't wait 30+ minutes)
2. Check if any staging dir was produced (partial results may exist)
3. **Retry** — the hang is often transient (API/model availability)
4. If it hangs again, try:
   - Different `--model` (e.g., remove `--model sonnet`)
   - Off-peak hours
   - Check Claude CLI health with pre-flight test

## What NOT to Do

- ❌ Increase timeout in backend.py (ineffective)
- ❌ Split into smaller batches (doesn't reliably fix it)
- ❌ Wait 30+ minutes "just in case" (claude.exe won't come back)
- ❌ Call `process action=poll` repeatedly (returns identical output)

## Pre-Flight Test

Before launching, verify Claude CLI health:
```bash
echo "ping" | timeout 30 claude -p --output-format text --bare \
  --disable-slash-commands --disallowedTools '*' \
  --exclude-dynamic-system-prompt-sections 2>&1 | head -5
```

If this hangs or times out → DO NOT launch. Fix Claude CLI first.
