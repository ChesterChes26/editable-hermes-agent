# SkillOpt-Sleep Monitoring Checklist

**LOAD THIS DURING EXECUTION** — condensed from SKILL.md pitfalls #15, #27. Print or keep open during runs.

---

## ⛔ PRE-DISPATCH SATURATION CHECK (MANDATORY — DO THIS FIRST)

**BEFORE dispatching ANY subagent or run, check for saturation:**

```bash
# Check latest staging directory
ls -lt $PROJECT/.skillopt-sleep/staging/ | head -1
cat $PROJECT/.skillopt-sleep/staging/<latest>/report.md | grep "held-out score"
```

**If you see:**
- `held-out score: 1.000 -> 1.000`
- `gate: reject (accepted=False)`

**THEN: STOP IMMEDIATELY. DO NOT DISPATCH.**

Report to user: "Skill has reached 1.000 (saturation). Further runs will produce gate=reject. To improve further, expand the task set with harder/more diverse tasks."

**Why this matters:** Observed 2026-07-15: Agent saw saturation, then dispatched 15+ subagents over 2+ hours, producing nothing of value. The saturation check MUST happen before any dispatch, not just during monitoring.

**Cascade breaker:** If you've already dispatched 3+ subagents and none produced usable results (premature returns, garbled summaries, or saturation), STOP dispatching entirely. Report current state to user and wait for instruction.

---

## ⛔ THE GOLDEN RULE

**After launching, DO NOT call `process action=poll` or `process action=wait`.**  
**ONLY use filesystem checks (`ls`, `stat`) to monitor progress.**

The process tracker is USELESS during consolidation (20-40 min of silence is NORMAL).  
Filesystem checks are the ONLY source of truth.

---

## Launch Sequence

```bash
# 1. Kill all existing processes (MANDATORY)
ps -ef | grep "python.*skillopt" | grep -v grep | awk '{print $2}' | while read pid; do taskkill //F //PID $pid 2>/dev/null; done

# 2. Verify clean state
ps -ef | grep "python.*skillopt" | grep -v grep | wc -l  # must be 0

# 3. Launch with background=true, notify_on_complete=true
terminal(
  command="ANTHROPIC_API_KEY=*** python -m skillopt_sleep run ...",
  background=True,
  notify_on_complete=True,
  timeout=3600
)
```

---

## Monitoring Cadence (FOLLOW THIS EXACTLY)

```
T+0:   Launch (see above)
       
T+5m:  terminal("ls -lt $PROJECT/.skillopt-sleep/staging/ | head -3")
       → New dir? Read its report.json. No new dir? Check state.json mtime.
       
T+10m: terminal("ls -lt $PROJECT/.skillopt-sleep/staging/ | head -3")
       → Same check. If new dir appeared, read report.md.
       
T+15m: terminal("ls -lt $PROJECT/.skillopt-sleep/staging/ | head -3")

T+20m: terminal("ls -lt $PROJECT/.skillopt-sleep/staging/ | head -3")

Continue every 5-10 minutes until notify_on_complete fires.
```

**BETWEEN CHECKS: DO NOTHING.**  
Do not poll. Do not wait. Do not check stdout.  
The process tracker is ONLY useful for the final "did it exit?" check.

---

## What NOT to Do (OBSERVED ANTI-PATTERNS)

❌ **WRONG** — Polling process tracker:
```
T+8s:   process action=poll          # TOO EARLY, stdout empty
T+17s:  process action=poll          # SAME WASTE
T+120s: process action=wait          # BLOCKS, returns nothing new
T+167s: process action=poll          # stdout still shows "consolidate start"
T+240s: process action=wait          # BLOCKS for 60s (clamped), returns nothing
... (7+ polling calls over 6 minutes, ZERO information gained)
```

✅ **RIGHT** — Filesystem checks only:
```
T+0:    Launch
T+5m:   terminal("ls -lt staging/ | head -3")  # reveals staging dir immediately
T+10m:  terminal("ls -lt staging/ | head -3")  # confirms progress
```

---

## How to Know When Done

1. **notify_on_complete fires** → process exited → run is done
2. **OR**: `ps -p <PID>` returns empty → process gone at OS level
3. **Then**: read `.skillopt-sleep/staging/<latest-timestamp>/report.md`

---

## Reading Results (FASTEST PATH)

```bash
# Option 1: state.json history (all nights at once)
python -c "
import json
d = json.load(open('$PROJECT/.skillopt-sleep/state.json'))
for h in d['history'][-5:]:
    status = '✓' if h['accepted'] else '✗'
    print(f\"Night {h['night']:2d}: {status} baseline={h['baseline']:.3f} → candidate={h['candidate']:.3f}\")
"

# Option 2: Latest staging dir
ls -lt $PROJECT/.skillopt-sleep/staging/ | head -1
cat $PROJECT/.skillopt-sleep/staging/<latest>/report.md
```

---

## When a Run Fails

**Check these in order** (do NOT poll stdout repeatedly):

1. **Log file**: `tail -30 $EXP_ROOT/logs/skillopt-run-*.log`
2. **state.json**: `python -c "import json; d=json.load(open('$PROJECT/.skillopt-sleep/state.json')); print(f'night={d[\"night\"]}')"`
3. **Staging dirs**: `ls -lt $PROJECT/.skillopt-sleep/staging/ | head -3`
4. **Python process**: `ps -ef | grep "python.*skillopt" | grep -v grep`

**Common failure: exit code 2304** = all Claude CLI calls timed out. See SKILL.md pitfall #24.

---

## Critical Reminders

⚠️ **process action=wait timeout is CLAMPED to 180s max**  
Even if you specify timeout=1800 or timeout=3600, it blocks for only 180s. Each call wastes 180 seconds AND a turn. Observed 2026-07-15: agent called `process action=wait` with timeout=1800, got "timeout_note: Requested wait of 1800s was clamped to configured limit of 180s".

⚠️ **"timed out after 180 seconds" messages are NORMAL**  
They indicate individual claude -p calls that exceeded timeout, but the overall run continues. Do NOT kill based on timeout messages alone.

⚠️ **Consolidate phase is SILENT for 20-40 minutes**  
This looks like a hang but isn't. Check filesystem, NOT stdout.

⚠️ **Bash wrapper may survive Python death**  
Always check for `python.*skillopt` processes, not just the bash wrapper PID.

---

## Session Examples

**2026-07-15 (session 2, same day):** Agent launched run, then called `process action=wait` 3 times (T+69s, T+129s, T+189s), then `process action=poll` at T+408s, then `process action=log` at T+450s, then killed the process at T+500s. Total: 6 process tracker calls over 7 minutes, all returning identical output. The agent never checked the filesystem once. The process was stuck at "consolidate start" with a Claude CLI timeout — the agent should have checked for claude.exe processes and run the pre-flight test before killing, but didn't follow the kill decision tree.

**2026-07-15 (session 1, same day):** Agent launched run, then called `process action=poll` or `process action=wait` **16+ times over 20 minutes**. Each call returned identical "still running" output. Burned 16 turns producing zero information. A single filesystem check at T+5m would have revealed the staging directory immediately.

**2026-07-14:** Agent called `process action=poll` 7 times over 6 minutes. Same waste. Filesystem check at T+5m would have revealed results immediately.

**Pattern:** The skill documents this anti-pattern extensively, but agents STILL fall into it across multiple sessions on the same day. The issue isn't missing information — it's behavioral. **When in doubt, check filesystem. Never poll process tracker during consolidation.**

---

## Quick Decision Tree

```
Saw "timed out after 180 seconds"?
  → DO NOT KILL. Check filesystem: ls -lt staging/ | head -3
  → New staging dir? Run is healthy. WAIT.
  → No new dir? Check Python process: ps -ef | grep "python.*skillopt"
  → Python alive? WAIT. Python dead? Kill and restart.

Stdout silent for 20+ minutes?
  → Check filesystem: ls -lt staging/ | head -3
  → New dir? Run is progressing. WAIT.
  → No new dir? Check Python process.
  → Python alive? WAIT (consolidate is silent). Python dead? Kill and restart.

Process running 30+ minutes with staging dirs appearing?
  → HEALTHY multi-night run. DO NOT KILL.
  → Wait for process to exit naturally.
  → Read LATEST staging dir's report.md for results.
```

---

## Summary

**DO:** Launch once, check filesystem every 5-10 min, wait for notify_on_complete.  
**DON'T:** Poll process tracker, kill based on timeout messages, assume silence = hang.

**The filesystem is truth. The process tracker is noise during consolidation.**
