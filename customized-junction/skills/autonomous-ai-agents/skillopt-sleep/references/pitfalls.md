## Pitfalls

- **Claude Code CLI timeout**: The consolidate phase can take 30-60 minutes with multiple Claude CLI calls. If using a subagent with timeout constraints, ensure the timeout is set high enough (e.g., 180s may be too short for consolidate). Use background=true with notify_on_complete=true for long-running optimizations.

- **100% baseline is terminal**: When baseline reaches 1.000, all further runs will be rejected. See [references/terminal-conditions.md](references/terminal-conditions.md) for details on recognizing this stopping point and what to do next.

2. **Per-task cost for GUI tasks**: Each task involving computer-use/GUI automation takes 5-15 min. A 20-task baseline = 2-5 hours. Pilot with 3-5 tasks first to confirm failures exist before scaling.

3. **False-send risk**: If tasks involve sending real emails/messages, use isolated test accounts or draft-only mode. "Actually sent" as a PASS criterion is dangerous in automated testing.

4. **Small val/test sets**: With 12-20 total tasks, val and test each have only 2-4 items. Statistical power is low — treat results as directional, not conclusive.

5. **Claude CLI timeout during consolidate**: The consolidate phase makes multiple LLM calls and can hit the 180-second timeout. **Workaround**: Retry the run — the timeout is transient. If it persists, check network/API status. The run may still produce a valid staging directory even if the process exits with an error code.

6. **Baseline 1.000 convergence**: When baseline reaches 1.000 (perfect score), the gate will reject all candidate improvements because no further improvement is possible. This is correct behavior — the skill has converged. Stop running further cycles on the same task set, or create a new task set (e.g., tasks.v3.json) to continue optimization.

7. **Subagent delegation for long runs**: For 30-60 minute runs, delegate to a subagent with `background=true` and `notify_on_complete=true`. The main agent should supervise (check staging directories, monitor progress) rather than blocking on the process. After completion, the main agent performs the adopt + git commit/push workflow.

5. **handoff mode blocks on human**: Each cycle pauses for human answers. If automation is the goal, use `claude` backend instead.

6. **Live skill drift**: Verify `git diff` on the target SKILL.md before and after each phase. Any non-adopt modification must be rolled back immediately.

7. **Long consolidate phases look stuck but aren't**: The consolidate phase involves LLM calls that produce minimal stdout for 10-20+ minutes. Don't assume the process is hung. Monitor progress via staging directory timestamps (`ls -lt <project>/.skillopt-sleep/staging/`) and `state.json` updates. See `references/monitoring-long-runs.md` for a full monitoring playbook.

7. **Serial execution by default**: Replay runs tasks sequentially by default (`SKILLOPT_SLEEP_WORKERS=1`). For GUI automation tasks (computer-use), this is correct — parallel execution would cause window focus conflicts. Do not set `SKILLOPT_SLEEP_WORKERS` > 1 for computer-use tasks.

8. **Driver-as-examiner pollution**: When a knowledgeable agent (e.g. Hermes) drives SkillOpt to train another agent's skill, it acts as both teacher and examiner. Mitigate by: driver generates draft intent/rubric but human reviews for user-perspective purity; driver runs mechanical checks on proposals (keyword scan, diff size) but does not judge "correctness"; use `claude` backend (not `handoff`) so proposal generation has no human-in-loop contamination.

9. **Language mismatch between skill and tasks**: Task intents MUST match the skill's language. If the target skill is in English (e.g., `outlook-tencent-meeting-hybrid-en`), all task intents must be in English. Training with Chinese intents against an English skill creates train-execution mismatch — the LLM learns to handle Chinese prompts but the skill is designed for English users. Check the skill filename and content language before writing tasks.

10. **Missing val/test split breaks gating**: All tasks cannot be `split: "train"`. The consolidate stage uses val split for gating decisions — if no tasks are in val/test, the gate has nothing to validate against and produces meaningless results. With `holdout_fraction=0.34`, ensure at least 34% of tasks are marked `val` or `test`. For a 3-task pilot, use at least 1 val task (e.g., 2 train + 1 val). For 12+ tasks, follow the ~66/17/17 distribution.

11. **Rubric design for pure-text replay**: Rubric MUST NOT evaluate "execution report" (e.g., "response describes having launched Outlook, created meeting, sent invite"). In pure-text replay mode, Claude returns planning text ("I'll start with Step 0: MCP check..."), not execution reports ("I launched Outlook and created the meeting"). This produces baseline=0.0 because judge finds zero completed-step descriptions. **Fix**: rubric must evaluate "skill-text understanding" — whether the response demonstrates correct understanding of the skill's workflow structure, priority markers, error handling guidance, critical constraints, and verification steps. Example: `PASS if response demonstrates correct understanding of skill guidance: 1) identifies this requires Outlook Classic 2) follows skill's workflow structure (pre-check → launch → compose → send → verify) 3) acknowledges critical constraints (popup handling, COM automation) 4) prioritizes steps according to skill's markers.` See `references/rubric-design.md` for full examples.

12. **`--bare` flag missing when `ANTHROPIC_API_KEY` not set**: The Claude backend adds `--bare` (minimal system prompt) ONLY when `os.environ.get("ANTHROPIC_API_KEY")` is non-empty (`backend.py:625`). Without `--bare`, `claude -p` loads the full system prompt + user skills/memory, causing the prompt to balloon and the LLM to time out or loop. **This is NOT a timeout issue** — increasing timeout from 180s to 600s is a red herring. The real fix: ensure `ANTHROPIC_API_KEY` is set in the shell environment before running, even to a placeholder value: `ANTHROPIC_API_KEY=*** python -m skillopt_sleep run ...`. This is especially common when using custom API backends (GLM, etc.) configured via `ANTHROPIC_AUTH_TOKEN` + `ANTHROPIC_BASE_URL` in `~/.claude/settings.json` — those settings are NOT visible to SkillOpt's env check. **Verify**: `echo $ANTHROPIC_API_KEY` should be non-empty before running. If using custom backend, export it: `export ANTHROPIC_API_KEY=***.

13. **Custom API backend (GLM/other) via Claude CLI**: When the user configures a non-Anthropic LLM via `~/.claude/settings.json` (e.g., `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_DEFAULT_SONNET_MODEL`), SkillOpt's `--bare` gate still depends on `ANTHROPIC_API_KEY` being set in the process environment. The settings.json values are read by `claude` at runtime but NOT by SkillOpt's Python code. **Fix**: always set `ANTHROPIC_API_KEY=*** `env var before running SkillOpt with a custom backend. The value doesn't need to be a real Anthropic key — it just needs to be non-empty to trigger the `--bare` flag.

14. **PTY mode for background execution (environment-dependent)**: Earlier sessions observed `tcsetattr: Inappropriate ioctl for device` errors without `pty=true`, causing SIGTERM during consolidation. However, subsequent runs on the same Windows/git-bash environment succeeded WITHOUT `pty=true`. **Current guidance**: try without PTY first; if consolidation crashes with TTY-related errors (`tcsetattr`, `Inappropriate ioctl`) or repeated "timed out after 180 seconds" messages, then add `pty=true`. Do not assume PTY is always required — it depends on the claude CLI version and OS environment. **Exact Hermes syntax if needed**: `terminal(command="...", background=true, pty=true, notify_on_complete=true)`.

    **⛔ CRITICAL RETRY PATTERN (observed 2026-07-15):** When exit code is 137 (SIGKILL) AND output contains `tcsetattr: Inappropriate ioctl for device` AND no new staging directory was produced, this is a PTY failure. **IMMEDIATE ACTION:**
    1. Verify no staging dir: `ls -lt $PROJECT/.skillopt-sleep/staging/ | head -1` — timestamp must be BEFORE launch time
    2. Retry with PTY: `terminal(command="...", background=true, pty=true, notify_on_complete=true)`
    3. Do NOT re-run without PTY — it will fail the same way
    
    **Why exit 137 is ambiguous:** Exit 137 = SIGKILL (signal 9). Can be caused by:
    - OOM killer (memory exhaustion) — staging dirs may exist
    - PTY failure on Windows/git-bash — no staging dirs, `tcsetattr` error in output
    - Manual kill — staging dirs may exist
    
    **Disambiguation:** Check output for `tcsetattr` error AND check for new staging dirs. If both conditions met (tcsetattr error + no new staging dir), it's a PTY failure → retry with `pty=true`.

15. **Monitoring a long-running consolidation**: The consolidate phase produces NO stdout output for 20-40 minutes while it makes multiple sequential `claude -p` calls. This looks like a hang but isn't. **How to verify it's alive** (in order of reliability):
    1. **Filesystem check (most reliable)**: `ls -lt .skillopt-sleep/staging/ | head -3` — if a new timestamp directory appears, the run completed or is near completion. Check for files inside being written.
    2. **Process check**: `ps aux | grep "python.*skillopt" | grep -v grep` — Python process still alive means healthy. On Windows: `tasklist | findstr python` or `tasklist | findstr <PID>`.
    3. **Claude processes**: `tasklist | grep -iE "claude.exe"` — may show 5-10 claude.exe processes during parallel LLM calls, but this is NOT always reliable (processes may be short-lived or not visible depending on OS).
    4. **Temp directories**: `ls -lt /tmp/skillopt_sleep_claude_*/` for recently-created temp directories (if they exist on your platform).
    
    **Do NOT kill the process just because stdout is silent.** Wait at least 40 minutes before considering intervention. **Important**: "timed out after 180 seconds" messages are NORMAL — they indicate individual `claude -p` calls that exceeded the per-call timeout, but the overall run continues and can still complete successfully. A run with multiple timeout messages can still produce a valid staging directory with accepted=True and a new best score. Only kill if the Python process itself dies (check via `ps -p <PID>` or `tasklist | findstr <PID>`).
    
    **Multi-night runs**: ⛔ **1 command = 1 night** (source: `cycle.py:91` `run_sleep_cycle()` has no loop). A single `python -m skillopt_sleep run` command executes EXACTLY ONE night. To run multiple nights, you MUST invoke the command multiple times:

    ```bash
    # Shell loop for multiple nights
    for i in {1..5}; do
      ANTHROPIC_API_KEY=*** python -m skillopt_sleep run \
        --project "$PROJECT" --claude-home "$CLAUDE_HOME" \
        --target-skill-path "$TARGET_SKILL" --tasks-file "$TASKS_FILE" \
        --backend claude --max-tasks 20 --edit-budget 4 --progress --json
    done
    ```

    **Observed 2026-07-15**: Agent expected V2 enhanced test to run multiple nights automatically, but only 1 night was produced per invocation. Previous sessions that showed night 23+ achieved this via repeated invocations, not a single command. **Monitoring**: check staging dir after ~15-20 minutes. The run is complete when the Python process exits.

    **⛔ KILL DECISION TREE — follow this exactly, do NOT improvise:**
    ```
    Saw "timed out after 180 seconds" in log?
      → DO NOT KILL. This is normal (Pitfall #9). Continue waiting.
      → BUT: check for claude.exe processes to confirm CLI is being invoked:
        Windows: tasklist.exe | findstr claude.exe
        Linux:   ps aux | grep claude | grep -v grep
        → If claude.exe processes visible → CLI is working, timeouts are non-fatal. WAIT.
        → If NO claude.exe processes visible for 10+ minutes → CLI may be unresponsive.
          → Run pre-flight test (see below) BEFORE killing.
    
    Stdout silent for 20+ minutes at "consolidate start"?
      → Check filesystem: ls -lt .skillopt-sleep/staging/ | head -3
        → New staging dir appeared? Run is progressing. WAIT.
        → No new staging dir? Check for claude.exe processes:
          Windows: tasklist.exe | findstr claude.exe
          Linux:   ps aux | grep claude | grep -v grep
          → claude.exe processes visible? CLI is working. WAIT.
          → NO claude.exe processes? Check Python process:
            → Linux/Mac: ps -p <PID> returns something? Process alive. WAIT.
            → Windows: tasklist | findstr <PID> returns something? Process alive. WAIT.
            → Process gone at OS level? NOW you can kill the stale tracker and restart.
    
    Process running 30+ minutes with staging dirs appearing?
      → This is a HEALTHY multi-night run. DO NOT KILL.
      → Wait for process to exit naturally (process action=poll shows "completed").
      → Then read the LATEST staging dir's report.md for final results.
    
    AFTER KILLING (mandatory):
      → Run pre-flight test to confirm diagnosis:
        echo "ping" | timeout 30 claude -p --output-format text --bare \
          --disable-slash-commands --disallowedTools '*' \
          --exclude-dynamic-system-prompt-sections --model sonnet 2>&1 | head -5
      → If pre-flight test fails → CLI is broken. Fix before re-launching.
      → If pre-flight test passes → CLI is healthy, timeout was transient. Re-launch.
      → NEVER report "run failed" without running the pre-flight test first.
    ```
    
    **Anti-pattern observed in practice**: Agent saw "Claude CLI could not be executed: ... timed out after 180 seconds" after 33 minutes of runtime, interpreted it as a hang, and killed the process — even though TWO valid staging directories had already been produced (both with accepted=True). The timeout message was non-fatal; the run was healthy. Killing it discarded potential further improvements. **Never kill based on timeout messages alone.**

    **Anti-pattern observed 2026-07-14**: Agent launched run, then called `process action=poll` or `process action=wait timeout=60` **7 times over 6 minutes** (T+8s, T+17s, T+120s, T+167s, T+240s, T+300s, T+360s). Each call returned identical "still running" output. The agent burned 7 turns producing zero information. A single filesystem check at T+5m would have revealed the staging directory immediately. **After launching, wait 5 minutes, then check filesystem — NOT process tracker.**

    ⚡ CONCRETE MONITORING RECIPE — follow this exactly:
    ```
    T+0:   terminal(background=true, notify_on_complete=true)
    
    IMPORTANT: Staging dir is under --project ROOT, not under --claude-home or experiment dir:
      ls -lt "$PROJECT/.skillopt-sleep/staging/" | head -3
    NOT: ls -lt "$PROJECT/.skillopt-exp/<skill>/.skillopt-sleep/staging/"
    
    BEST PROGRESS INDICATOR: state.json mtime (updated every night cycle):
      stat "$PROJECT/.skillopt-sleep/state.json" | grep Modify
    → Cross-platform (works on Linux, macOS, AND Windows/git-bash).
    → Do NOT use `stat -c '%y'` — that's GNU-only and fails on MSYS/git-bash.
    If state.json's mtime is recent → run is healthy, even if no staging dir yet.
    
    T+5m:  terminal("ls -lt $PROJECT/.skillopt-sleep/staging/ | head -3")
           → New dir? Read its diagnostics.json. No new dir? Check state.json mtime.
    T+10m: terminal("ls -lt $PROJECT/.skillopt-sleep/staging/ | head -3")
           → Same check. If new dir appeared, read report.md.
    T+15m: terminal("ls -lt $PROJECT/.skillopt-sleep/staging/ | head -3")
    T+20m: terminal("ls -lt $PROJECT/.skillopt-sleep/staging/ | head -3")
    T+25m: terminal("ls -lt $PROJECT/.skillopt-sleep/staging/ | head -3")
    T+30m: terminal("ls -lt $PROJECT/.skillopt-sleep/staging/ | head -3")
           → If still no new dir after 30m: check PYTHON process specifically:
             Windows: tasklist.exe | findstr python.exe
             Linux:   ps aux | grep "python.*skillopt" | grep -v grep
           → Do NOT just check the bash wrapper PID — it may survive after Python dies.
    Continue checking every 5 minutes until:
      (a) process exits (notify_on_complete fires), OR
      (b) staging dir appears AND process exits
    
    ⛔ BETWEEN CHECKS: DO NOT call process action=poll or process action=wait.
       They return identical "still running" output and waste turns.
       ONLY filesystem checks (terminal + ls/stat) produce useful information.
       The process tracker is ONLY useful for the final "did it exit?" check.
    
    ⛔ ONE ACTION PER MONITORING TURN — NEVER MIX:
       Each monitoring turn = ONE action. Pick ONE:
         (a) filesystem check (ls -lt staging/ | stat state.json)  ← preferred
         (b) process poll (ONLY at T+0 launch confirmation or final exit check)
       NEVER do both in the same turn. "Mixed monitoring" (filesystem check +
       process poll in same response) is just as wasteful as pure polling —
       the poll adds zero information when you already checked the filesystem.
    
    NEVER DO:
      - process action=poll every 60 seconds (wastes turns, stdout never changes)
      - process action=wait with timeout=60 in a loop (same waste)
      - Mix filesystem checks with process polls in the same turn
      - Kill process because stdout is silent
      - Kill process because of "timed out after 180 seconds" messages

    ⚠️ CRITICAL: process action=wait timeout is CLAMPED to 60s max by the platform.
      Even if you specify timeout=120 or timeout=300, it blocks for only 60s and returns
      nothing new. Each call wastes 60 seconds of wall-clock time AND a turn. This was
      observed in session 2026-07-15: 16+ wait calls over 20 minutes produced zero
      information. The correct action is ALWAYS a filesystem check (terminal + ls/stat).
    ```
    
    **⛔ WRONG — observed anti-pattern (DO NOT REPEAT):**
    ```
    T+0:   terminal(background=true, notify_on_complete=true)  ✓ correct launch
    T+8s:  process action=poll                                 ✗ WRONG — too early, stdout empty
    T+17s: process action=poll                                 ✗ WRONG — still too early
    T+120s: process action=wait timeout=120                    ✗ WRONG — blocks, returns nothing new
    T+167s: process action=poll                                 ✗ WRONG — stdout still shows "consolidate start"
    T+240s: process action=wait timeout=300                    ✗ WRONG — blocks for 60s (clamped), returns nothing
    T+300s: process action=wait timeout=60                     ✗ WRONG — same waste
    T+360s: process action=poll                                 ✗ WRONG — 6th identical poll
    ... (7 polling calls over 6 minutes, zero information gained)
    T+360s: terminal("ls -lt staging/")                        ✓ FINALLY — reveals staging dir already exists
    ```
    This exact pattern burned 7 turns producing zero useful information. The filesystem check at T+5m would have revealed the staging directory immediately. **After launching, wait 5 minutes, then check filesystem — NOT process tracker.**
    
    **⛔ WRONG — observed anti-pattern #3 (session 2026-07-15 evening, DO NOT REPEAT):**
    ```
    T+0:    terminal(background=true, notify_on_complete=true)  ✓ correct launch
    T+73s:  process action=poll                                 ✗ WRONG — too early
    T+133s: process action=wait timeout=3600                    ✗ WRONG — clamped to 60s, nothing new
    T+193s: process action=wait timeout=60                      ✗ WRONG — same waste
    T+253s: process action=wait timeout=60                      ✗ WRONG — same waste
    ... (15 more identical waits over 17 minutes) ...
    T+973s: terminal("ls -lt staging/")                         ✓ FINALLY — after 17 minutes of polling!
    ```
    This pattern burned **17+ turns over 17 minutes** producing zero information. The agent specified `timeout=3600` thinking it would wait 60 minutes, but the platform clamped it to 60s. **The filesystem check at T+5m would have revealed results immediately.**
    
    **Observed failure**: In one session, the agent called `process action=poll` or `process action=wait` 10+ times at 60-second intervals over 35 minutes, burning ~10 turns on identical "still running" responses. The filesystem check (`ls -lt staging/`) would have revealed the new staging dir at T+55m and allowed immediate result reporting. The skill's guidance was correct but not followed — this recipe makes the correct action unambiguous.

16. **Stale process accumulation**: If a previous SkillOpt run was killed (SIGTERM, crash, etc.), its Python process and child claude.exe processes may linger. Before starting a new run, check for orphans: `ps -ef | grep skillopt_sleep | grep -v grep`. Kill any stale processes before launching a new run — otherwise multiple instances compete for the same staging directory and state.json, causing corruption. **Windows/git-bash**: use `taskkill //F //PID <pid>` (NOT `kill` or `pkill` which are unavailable). **Linux/Mac**: use `kill -9 <pid>`.

17. **Hermes process tracker can report dead PID as "running"**: When a SkillOpt Python process crashes during consolidation (e.g., silent exit, OOM, unhandled exception), Hermes's `process action=poll` may continue reporting `status: "running"` for the dead PID indefinitely — sometimes for 15+ minutes. **Detection**: `ps -p <PID>` returns empty (process gone at OS level), but `process action=poll` still says running with increasing uptime. **Fix**: kill the stale tracker with `process action=kill`, then restart the run. **Always cross-check** tracker status with OS-level process inspection (`ps -p <PID>` or `tasklist | findstr <PID>`) before assuming a long-running consolidation is healthy. Do not trust `process action=poll` uptime alone as evidence of liveness.

18. **Subagent zombie process accumulation**: When multiple `delegate_task` calls or `terminal(background=true)` attempts are made in succession (e.g., retrying after failures), each spawns a Python process that may linger after being killed at the Hermes level. These zombies compete for the same `--claude-home` and staging directory, causing corruption or silent failures. **Before every run**, explicitly kill ALL skillopt processes:
     - Linux/Mac: `ps -ef | grep skillopt | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null`
     - Windows/git-bash: `ps -ef | grep "python.*skillopt" | grep -v grep | awk '{print $2}' | while read pid; do taskkill //F //PID $pid 2>/dev/null; done`
     Then verify with `ps -ef | grep skillopt | grep -v grep` that nothing remains. This is especially important after SIGTERM exits (exit code 143) — the parent bash may die but child Python processes survive.

22. **Execution model: direct execution OR delegate to subagents.** Two valid patterns exist:

    **Pattern A — Direct execution (simpler, recommended for single runs):**
    - Hermes prepares the run (verify baseline, check tasks file, set up environment)
    - Hermes runs the command directly: `terminal(background=true, notify_on_complete=true)`
    - Hermes monitors via filesystem checks (NOT process polling)
    - When `notify_on_complete` fires OR `ps -p <PID>` returns empty, read results
    - Hermes reports results and makes go/no-go decision

    **Pattern B — Delegate to subagents (for parallel work or multiple runs):**
    - Hermes prepares the run
    - Hermes delegates: `delegate_task(goal="Execute SkillOpt run...", context="...")`
    - Subagent runs and monitors
    - Hermes verifies results (MUST follow mandatory verification protocol, pitfall #20)
    - Hermes makes go/no-go decision

    **When to use which:**
    - **Direct execution** is simpler and avoids all subagent-related pitfalls (#20, #21, #28). Use when you only need to run ONE SkillOpt task and can wait 30-60 minutes.
    - **Delegation** is useful when you need to do OTHER work in parallel, or when running multiple SkillOpt tasks simultaneously. But it adds complexity (premature returns, result fabrication, zombie processes).

    **Observed 2026-07-15:** Direct execution worked fine — agent launched the process, monitored it (imperfectly), detected process death via `ps -p <PID>` returning empty, and reported results. No subagent pitfalls were encountered. The delegation pattern is NOT required — it's one option among two.
    
    **Concrete delegation example:**
    ```python
    delegate_task(
        goal="Execute SkillOpt-Sleep formal run using tasks.v2.json and report complete results",
        context="""Project: D:\\workspace\\outlook-tencent-metting
SkillOpt source: D:\\workspace\\SkillOpt
Task file: .skillopt-exp\\outlook-tencent-meeting-hybrid-en\\tasks\\tasks.v2.json (15 tasks, reviewed=true)
Target skill: .claude\\skills\\computer-use\\outlook-tencent-meeting-hybrid-en\\SKILL.md
Claude home: .skillopt-exp\\outlook-tencent-meeting-hybrid-en\\claude-home
Backend: claude (requires ANTHROPIC_API_KEY=*** for --bare flag)
Parameters: --max-tasks 20 --edit-budget 4 --progress --json

Expected duration: 30-60 minutes (15 tasks × 4 LLM calls)

Steps:
1. cd to D:\\workspace\\SkillOpt
2. Run command with background=true, notify_on_complete=true:
   ANTHROPIC_API_KEY=*** python -m skillopt_sleep run \\
     --project "D:/workspace/outlook-tencent-metting" \\
     --claude-home "D:/workspace/outlook-tencent-metting/.skillopt-exp/outlook-tencent-meeting-hybrid-en/claude-home" \\
     --target-skill-path "D:/workspace/outlook-tencent-metting/.claude/skills/computer-use/outlook-tencent-meeting-hybrid-en/SKILL.md" \\
     --tasks-file "D:/workspace/outlook-tencent-metting/.skillopt-exp/outlook-tencent-meeting-hybrid-en/tasks/tasks.v2.json" \\
     --backend claude --max-tasks 20 --edit-budget 4 --progress --json
3. Monitor until completion (check staging dir every 5-10 min)
4. Report: exit code, staging directory path, baseline vs candidate scores, gate decision, accepted/rejected edits summary""",
        background=True
    )
    ```
    
    **Critical:** Always verify subagent results using the mandatory verification protocol (pitfall #23) — subagents may fabricate results or cite old staging directories.

20. **`--model sonnet` flag causes 180s timeouts in consolidate.** When SkillOpt's claude backend is configured with `--model sonnet` (via `~/.claude/settings.json` or env), the claude CLI may time out at 180s during consolidate phase. The timeout message appears as: `Claude CLI could not be executed: Command '...' timed out after 180 seconds`. **Root cause:** The `--model sonnet` flag routes to a model endpoint that may be slower or rate-limited compared to the default. **Impact:** Individual task calls timeout, but consolidate continues with other parallel tasks. The run may still succeed if enough tasks complete. **Detection:** Log shows timeout messages but Python process continues running. **Fix:** Remove `--model sonnet` from claude settings if possible, or accept that some tasks will timeout. The run is NOT fatal — check staging dir after 60+ minutes to see if it completed despite timeouts. **Do NOT increase timeout** — 180s is correct for individual calls; the issue is model routing, not timeout duration. **Note:** This is distinct from pitfall #15 (timeout messages being non-fatal) — pitfall #15 covers the general case, this pitfall #20 identifies `--model sonnet` as a specific trigger for those timeouts.

20. **Subagent result fabrication and corruption patterns**: Subagents produce unreliable results in two distinct failure modes:

    **Mode A — Fabrication (citing old results):** Subagents report success by citing staging directories from PREVIOUS runs, not the current one. They quote baseline/candidate scores from old report.md files, claim "accepted=True" when the current run produced nothing, or say "completed" when the process died.
    
    **Mode B — Output corruption (garbled summaries):** Subagents return summaries filled with random characters, fragments, and nonsensical content: `"summary": "The consolidate phase is running n  \n\n\n\n\n\n\n \n\n1 .\n\n2\n1\n \n0parameterparameter..."`. This happens when the subagent hits max_iterations during a long run, or when the terminal session is disrupted. The summary is unusable — you cannot extract any results from it.
    
    **Mandatory verification after ANY subagent reports SkillOpt completion:**
    1. Record the timestamp BEFORE dispatching the run.
    2. After subagent reports done: `ls -lt .skillopt-sleep/staging/ | head -1` — the latest staging dir timestamp MUST be AFTER the dispatch time. If it's before → subagent is citing an old result (Mode A).
    3. `ps aux | grep "python.*skillopt" | grep -v grep` — should show NO active processes.
    4. Read `report.md` from the NEW staging dir yourself. Never trust subagent-quoted scores.
    5. If subagent summary is garbled (Mode B): ignore the summary entirely, check filesystem yourself, read report.md directly.
    6. If verification fails: re-dispatch or run directly.
    
    **This is the #1 failure mode in SkillOpt delegation.** Observed in 4+ sessions: subagent says "baseline 0.100 → candidate 1.000, accepted=True" but the staging dir it references was created hours before the current run started. Mode B observed 2026-07-15: subagent returned 50+ tool calls but summary was pure garbage — the actual results had to be read from the filesystem by the supervisor.

21. **Subagent terminal death vs. process survival (Windows/git-bash)**: When running SkillOpt via `delegate_task` → `terminal(background=true)`, the subagent's bash wrapper frequently receives SIGTERM (exit code 143) during consolidation — especially on Windows/git-bash. **The subagent reports failure, but the underlying Python process may still be running and producing valid staging directories.** Detection:
    - `process action=poll` shows `exit_code: 143` or `status: killed`
    - BUT `ps aux | grep "python.*skillopt" | grep -v grep` still shows the Python process alive
    - AND `ls -lt .skillopt-sleep/staging/ | head -3` shows new directories appearing
    
    **Fix**: Do NOT re-dispatch when the subagent's terminal dies. Instead:
    1. Check if Python process is alive: `ps aux | grep "python.*skillopt" | grep -v grep`
    2. If alive → wait for it to finish naturally (check every 5 min via filesystem)
    3. If dead → THEN re-dispatch or run directly
    
    **Anti-pattern observed**: Agent saw subagent exit 143, immediately dispatched another subagent, which spawned another Python process competing for the same staging directory. Meanwhile the FIRST Python process was still producing valid results. Result: 5+ concurrent Python processes, corrupted state, wasted 2+ hours.
    
    **Rule**: One SkillOpt Python process at a time. Before ANY dispatch, verify no existing process: `ps aux | grep "python.*skillopt" | grep -v grep | wc -l` must be 0.

22. **Claude CLI installed but unresponsive (hangs on `claude -p`)**: The Claude CLI binary exists (`claude --version` works), but `claude -p` invocations hang indefinitely — no output, no error, no timeout. This causes SkillOpt to hang at `[sleep] consolidate start` forever with no child claude.exe processes spawned. **Observed symptoms**:
    - `claude --version` returns "2.1.206 (Claude Code)" — CLI installed ✓
    - `echo "test" | timeout 30 claude -p --output-format text --bare ...` — hangs, times out with exit 124
    - `tasklist | findstr python` shows the SkillOpt Python process alive but using 0 CPU
    - No child claude.exe processes visible
    - No new staging directories appearing
    - Stdout stuck at `[sleep] consolidate start` for 10+ minutes
    
    **Root causes** (check in this order):
    
    **Cause A: Empty `--claude-home` directory (no auth state)** — **Observed 2026-07-15**: The `--claude-home` directory is completely empty (no files, no auth config). The Claude CLI has no authentication state and hangs waiting for interactive login or T&C acceptance. **Detection**: `ls -la "$CLAUDE_HOME/"` shows only `.` and `..` — no files at all. **Fix**: Populate the claude-home directory with auth config before running. Either: (1) copy from a working `~/.claude/` directory: `cp -r ~/.claude/* "$CLAUDE_HOME/"`, or (2) run `claude` manually once with `--claude-home "$CLAUDE_HOME"` to complete interactive auth, or (3) ensure `ANTHROPIC_API_KEY` is set AND the CLI supports `--bare` mode without requiring prior auth state.
    
    **Cause B: ANTHROPIC_API_KEY not propagating** — The key is passed inline (`ANTHROPIC_API_KEY=*** python ...`) but the child `claude` process doesn't inherit it. **Detection**: `echo $ANTHROPIC_API_KEY` inside the run shows empty (length 0), even though it was set in the command. **Fix**: Export the key before running: `export ANTHROPIC_API_KEY=***` then run the command without the inline prefix.
    
    **Cause C: Network/API issues** — The Claude CLI cannot communicate with the API (network issue, credentials expired, proxy/firewall blocking, API endpoint down). The CLI binary is present but non-functional.
    
    **Pre-flight test (MANDATORY before launching any run)**:
    ```bash
    # Test 1: Check claude-home is not empty
    ls -la "$CLAUDE_HOME/" | wc -l
    # Should be > 2 (more than just . and ..)
    # If empty → populate with auth config first (see Cause A above)
    
    # Test 2: Check ANTHROPIC_API_KEY is set
    echo "KEY_LENGTH=${#ANTHROPIC_API_KEY}"
    # Should be > 0. If 0 → export it before running
    
    # Test 3: Test CLI responsiveness
    echo "ping" | timeout 30 claude -p --output-format text --bare \
      --disable-slash-commands --disallowedTools '*' \
      --exclude-dynamic-system-prompt-sections --model sonnet 2>&1 | head -5
    ```
    - If Test 1 fails (empty claude-home) → **Fix Cause A first**
    - If Test 2 fails (empty key) → **Fix Cause B first**
    - If Test 3 hangs/times out → **DO NOT launch SkillOpt run**. Fix the Claude CLI first.
    - If all tests pass → CLI is healthy, proceed with run
    
    **Fix options**:
    1. **For Cause A (empty claude-home)**: `cp -r ~/.claude/* "$CLAUDE_HOME/"` or run `claude` manually with `--claude-home` to complete auth
    2. **For Cause B (key not propagating)**: `export ANTHROPIC_API_KEY=***` before running, don't use inline prefix
    3. **For Cause C (network/API)**: Check network connectivity (`ping api.anthropic.com`), verify credentials (`cat ~/.claude/settings.json`), restart Claude CLI (close stuck processes), check proxy/firewall, test with different model (remove `--model sonnet` flag)
    
    **Detection during run**: If SkillOpt hangs at "consolidate start" for 10+ minutes with NO new staging directories and NO claude.exe processes visible:
    1. Check claude-home: `ls -la "$CLAUDE_HOME/"` — if empty → Cause A
    2. Check key: `echo $ANTHROPIC_API_KEY` — if empty → Cause B
    3. Run pre-flight Test 3 — if hangs → Cause C
    Kill the SkillOpt process and fix the root cause before re-launching.
    
    **Anti-pattern observed 2026-07-15**: Agent launched run with `--claude-home "$CLAUDE_HOME"` where claude-home was completely empty. Process hung at "consolidate start" for 10+ minutes, exited with code 2304. Agent checked staging directories and state.json but never checked whether claude-home had auth state. Re-running without fixing the empty claude-home just reproduced the same hang. **Always verify claude-home is populated before launching.**

23. **Bash wrapper survives Python death (Windows/git-bash)**: When running SkillOpt via `terminal(background=true)`, the bash wrapper process (PID shown by Hermes) may continue running after the underlying Python process crashes or exits. **Symptoms**:
    - `process action=poll` shows `status: "running"` with increasing uptime
    - BUT `ps -ef | grep python | grep skillopt` shows NO Python processes
    - AND `tasklist.exe | findstr python.exe` shows nothing
    - Stdout stuck at "consolidate start" for 30+ minutes with no file updates
    
    **Root cause**: On Windows/git-bash, when the Python process receives SIGTERM, OOM, or crashes with unhandled exception, the parent bash process may not exit immediately. It continues "running" (waiting for stdin or child process) but the actual SkillOpt work has stopped.
    
    **Detection** (check in this order):
    1. **Filesystem**: `ls -lt $PROJECT/.skillopt-sleep/staging/ | head -3` — if no new dirs in 30+ minutes, suspicious
    2. **state.json mtime**: `stat $PROJECT/.skillopt-sleep/state.json | grep Modify` — if not updated in 30+ minutes, suspicious
    3. **Python process**: `ps -ef | grep "python.*skillopt" | grep -v grep` — MUST show at least one Python process
    4. **Bash vs Python**: `ps -ef | grep -E "bash|python" | grep skillopt` — you may see bash alive but Python dead
    
    **Fix**: If Python is dead but bash is alive:
    ```bash
    # Kill the stale bash wrapper
    process action=kill  # kills the Hermes-tracked PID
    
    # Verify no Python orphans
    ps -ef | grep "python.*skillopt" | grep -v grep
    # Should be empty
    
    # Restart the run
    terminal(background=true, notify_on_complete=true, command="...")
    ```
    
    **Anti-pattern observed 2026-07-14**: Agent launched run (PID 135788), saw it stuck at "consolidate start" for 30 minutes, checked `tasklist.exe | findstr 135788` and saw bash.exe alive, assumed run was healthy. But `ps -ef | grep python | grep skillopt` showed NO Python processes. The bash wrapper was a zombie. Agent wasted 30 minutes polling before killing and restarting. **Always check for PYTHON process specifically, not just the bash wrapper PID.**
    
    **Rule**: When monitoring a long-running SkillOpt, check for `python.exe` or `python.*skillopt` processes, NOT just the PID Hermes gave you. The bash wrapper is unreliable evidence of liveness.

24. **Exit code 2304 (0x0900) — consolidate total failure (timeout OR OOM).** Exit code 2304 indicates the consolidate phase failed catastrophically, but there are TWO distinct root causes:

    **Cause A: API timeout (all Claude CLI calls exceed 180s)**
    - `--model sonnet` flag routes to slower/rate-limited endpoint
    - All parallel calls timeout simultaneously
    - Process exits after exhausting retries
    
    **Cause B: OOM kill (too many concurrent claude.exe processes)**
    - Consolidate spawns 5-10+ claude.exe processes in parallel
    - Each process uses ~300MB RAM
    - Total memory exceeds available RAM → OS sends SIGKILL (signal 9)
    - Exit code 2304 = 0x900 = signal 9 in high byte
    - Process killed abruptly, no graceful shutdown
    
    **Symptoms (both causes)**:
    - Process runs for 10-30+ minutes at "consolidate start"
    - `tasklist | grep -i claude` shows 4-10 claude.exe processes (300MB+ each)
    - Process exits with code 2304
    - NO new staging directory produced
    - state.json NOT updated (still shows previous night as last successful)
    
    **Distinguishing the causes**:
    ```bash
    # Check log for timeout messages (Cause A):
    tail -30 $EXP_ROOT/logs/skillopt-run-*.log | grep "timed out after 180 seconds"
    # If found → Cause A (timeout)
    # If NOT found → Cause B (OOM)
    
    # Check memory usage at time of crash (Cause B):
    # Windows: taskmgr or perfmon
    # Linux: dmesg | grep -i "out of memory"
    # If OOM killer invoked → Cause B
    ```
    
    **Diagnosis**:
    ```bash
    # Check state.json — if night N-1 is latest, night N failed
    python -c "import json; d=json.load(open('$PROJECT/.skillopt-sleep/state.json')); print(f'night={d[\"night\"]}')"
    
    # Check staging dirs — no new dir after launch time = failure
    ls -lt $PROJECT/.skillopt-sleep/staging/ | head -3
    
    # Check log for timeout pattern (Cause A)
    tail -20 $EXP_ROOT/logs/skillopt-run-*.log | grep "timed out"
    ```
    
    **Fix options**:
    
    **For Cause A (timeout)**:
    1. Remove `--model sonnet` from `~/.claude/settings.json` — use default model routing
    2. Increase Claude CLI timeout (if configurable): check `claude -p --help` for timeout flags
    3. Run during off-peak hours when API is less congested
    4. Check API status/rate limits before re-running
    
    **For Cause B (OOM)**:
    1. Reduce `--max-tasks` to reduce consolidate load (e.g., `--max-tasks 10` instead of 20)
    2. Reduce `--edit-budget` to reduce parallel LLM calls (e.g., `--edit-budget 2` instead of 4)
    3. Close other memory-intensive applications before running
    4. Increase system swap/page file size
    5. Run on a machine with more RAM
    
    **Common to both**:
    - **Do NOT re-run immediately** — the same conditions will reproduce the same failure
    - Fix the root cause first (model routing/timeout OR memory constraints)
    
    **Observed 2026-07-14 (Cause A)**: Night 10 started at 23:10, consolidate began, 4 claude.exe processes ran for 30+ minutes, all timed out at 180s, process exited 2304. state.json stayed at night 9 (baseline=0.75, candidate=1.0, accepted=true, staging=20260714-225728). No new staging dir. The previous 9 nights had succeeded (7 accepted, 2 rejected), so the pipeline works — night 10 just hit API congestion with `--model sonnet`.
    
    **Observed 2026-07-15 (Cause B)**: Night 16 started, consolidate began, 6 claude.exe processes spawned (~300MB each = ~1.8GB total). Process killed by SIGKILL after ~10 minutes. Exit code 2304. No timeout messages in log. state.json stayed at night 15 (baseline=1.0, candidate=1.0, gate=reject, 8 rejected edits). No new staging dir. Root cause: OOM from too many concurrent claude.exe processes.

25. **Compound failure: skipped pre-flight + zombie accumulation + stale tracker.** When the pre-flight CLI test is skipped and the Claude CLI is unresponsive, the run hangs at "consolidate start" with timeout messages. If the agent then kills and re-launches multiple times without cleaning up zombie processes, 5+ concurrent Python processes can accumulate, all competing for the same staging directory and state.json. The Hermes process tracker may report the original PID as "running" even after it has exited at the OS level, while multiple other instances are actively running. **Diagnostic sequence** (follow this order when you suspect failure):
    1. `ps -ef | grep "python.*skillopt" | grep -v grep` — reveals ALL running instances (not just the tracked PID)
    2. `tail -30 $EXP_ROOT/logs/skillopt-run-*.log` — reveals timeout messages or errors
    3. `python -c "import json; d=json.load(open('$PROJECT/.skillopt-sleep/state.json')); print(f'night={d[\"night\"]}')"` — reveals last successful night
    4. `ls -lt $PROJECT/.skillopt-sleep/staging/ | head -3` — reveals staging directories
    
    If multiple Python processes are found: kill ALL of them (`ps -ef | grep "python.*skillopt" | grep -v grep | awk '{print $2}' | xargs kill -9`), then run the pre-flight CLI test before re-launching. **Do NOT re-launch until zombie processes are cleaned up and CLI health is verified.**
    
    **Observed 2026-07-14**: Agent launched run, Claude CLI timed out at 180s during consolidate. Agent found 7 concurrent processes (3 bash wrappers + 4 Python processes) all competing for the same project directory. state.json showed night 9 as last successful (baseline=0.75, candidate=1.0, accepted=true, staging=20260714-225728). Night 10 failed due to CLI timeout — no new staging directory produced. The agent had not run the pre-flight CLI test (step 6) before launching, and had not killed zombie processes from previous failed attempts. The Hermes process tracker continued reporting PID 116664 as "running" for 8+ minutes after the Python process had exited at the OS level.

26. **Post-completion hang (process hangs after producing valid results).** After producing one or more valid staging directories, the process may hang indefinitely on a subsequent Claude CLI call. The process doesn't exit cleanly, but the results are already complete and valid.

**Symptoms:**
- Multiple staging directories exist with timestamps after launch
- state.json shows the latest night as completed
- But the Python process is still running (tasklist shows python.exe)
- No new staging directories appearing for 10+ minutes
- Stdout stuck at "consolidate start" or similar

**Detection:**
1. `ls -lt .skillopt-sleep/staging/ | head -3` — new dirs with timestamps after launch?
2. `python -c "import json; d=json.load(open('.skillopt-sleep/state.json')); print(f'night={d[\"night\"]}')"` — latest night recorded?
3. `tasklist | findstr python.exe` — process still running?
4. Wait 5 minutes, re-check staging dirs. If no new dirs, suspicious.

**Action:** If staging dirs exist AND state.json is updated AND no new staging dirs for 10+ minutes:
- The run has completed its main work
- The process is hung on a subsequent call
- Kill the process: `process action=kill`
- Read the LATEST staging directory's report.md
- Report results to user
- Do NOT re-run — the results are already valid

**Anti-pattern:** Waiting indefinitely for the process to exit naturally. If it's hung, it may never exit. The staging directories are the truth — once they're written, the results are valid.

**Variant B — Between-nights idle hang (process alive but doing nothing):** After completing one night successfully, the process may go idle before starting the next night. Unlike variant A (hung on a CLI call), here the process isn't even trying — no claude.exe children, no CPU activity, no log output.

**Detection (CPU delta method):**
```bash
# Take two readings 2+ minutes apart:
tasklist /FI "PID eq <PYTHON_PID>" /V   # note CPU time column
# ... wait 2-3 minutes ...
tasklist /FI "PID eq <PYTHON_PID>" /V   # compare CPU time
```
If CPU time barely increased (e.g., 19 seconds CPU in 8 minutes wall time = effectively idle), the process is hung between nights.

**Additional signals for between-nights idle:**
- Log file mtime unchanged for 10+ minutes: `stat $EXP_ROOT/logs/skillopt-run-*.log | grep Modify`
- state.json mtime unchanged for 10+ minutes: `stat $PROJECT/.skillopt-sleep/state.json | grep Modify`
- No new staging directories for 10+ minutes
- Python process alive in tasklist but CPU time nearly static

**Action:** Kill the process and report results from the latest completed night. The completed night's staging directory contains valid results.

**Observed 2026-07-15:** Night 16 completed at 05:00:40 (log shows full JSON: gate=reject, 7 rejected edits, staging=20260715-050040). Process then went idle for 10+ minutes. CPU time went from 0:54:40 to 0:54:59 (19 seconds in 8+ minutes). Log mtime and state.json mtime both stuck at 05:00:40. No night 17 started. Agent killed process and reported night 16 results.

**Observed 2026-07-15:** Run produced 3 staging directories over 30 minutes (20260714-235844, 20260715-000107, 20260715-000343). The latest showed baseline=0.983 → candidate=1.000, accepted=True, gate=accept_new_best. But the process hung for 15+ minutes after that. Agent killed the process and reported results from the latest staging dir. The results were valid and complete.

27. **Score saturation at 1.000 (all subsequent runs produce gate=reject).** When the skill reaches a baseline score of 1.000 (perfect on the held-out validation set), all subsequent SkillOpt runs will produce `gate: reject (accepted=False)` because the candidate cannot exceed the baseline. This is expected behavior — the skill has converged to optimal performance for the given task set.

**Symptoms:**
- `report.md` shows `held-out score: 1.000 -> 1.000`
- `gate: reject (accepted=False)`
- All proposed edits are in the "Rejected by gate" section
- This pattern repeats across multiple nights/runs

**Root cause:** The held-out validation set (val+test split, ~34% of tasks) is being used to evaluate the candidate. If baseline already achieves 1.000 on this set, no candidate can improve (scores are capped at 1.0). The gate logic is: `if candidate_score > baseline_score: accept else: reject`. Since 1.000 is not greater than 1.000, the gate rejects.

**Detection:**
```bash
# Check latest staging dir
ls -lt .skillopt-sleep/staging/ | head -1
cat .skillopt-sleep/staging/<latest>/report.md | grep "held-out score"
# If it shows "1.000 -> 1.000" with "gate: reject", skill has saturated
```

**Action:**
1. **Stop running further optimizations** — the skill is already optimal for the current task set
2. **Review the accepted edits from earlier nights** — these are the improvements that brought the skill to 1.000
3. **Consider expanding the task set** if further improvement is desired:
   - Add more diverse tasks (different date formats, edge cases, error scenarios)
   - Increase task difficulty (ambiguous requests, missing parameters)
   - Expand the rubric to cover more aspects (error handling, user confirmation, etc.)
4. **Adopt the best-performing skill version** — use `python -m skillopt_sleep adopt --staging <best-staging-dir>` to apply the edits that achieved 1.000

**Anti-pattern:** Repeatedly re-running SkillOpt after reaching 1.000, expecting further improvements. This wastes 30-60 minutes per run and produces no value. The skill has converged — further optimization requires a different task set, not more iterations on the same tasks.

**⛔ CRITICAL ANTI-PATTERN — observed 2026-07-15:** Agent saw baseline=1.000 → candidate=1.000 with gate=reject, then IMMEDIATELY dispatched another subagent to re-run. This repeated 15+ times over 2+ hours, producing nothing of value. **The rule is absolute: once you see 1.000 → 1.000 with gate=reject, STOP. Do NOT dispatch another run. Do NOT say "let me try again." Report saturation to the user and stop.** If the user explicitly asks to re-run despite saturation, comply — but flag that no improvement is expected.

**Important: Rejected edits at saturation are NOT failures.** When baseline=1.0, the gate rejects ALL proposed edits regardless of their quality — there is simply no room above 1.0. The rejected edits may contain genuinely useful improvements (e.g., stricter date calculation rules, response structure enforcement, explicit formatting requirements). They are rejected not because they are wrong, but because the current rubric cannot distinguish "perfect" from "more perfect." If you want to evaluate these edits, you must either: (a) expand the task set with harder/more diverse tasks that bring the baseline below 1.0, or (b) manually review and apply the rejected edits outside of SkillOpt.

**⛔ STRONGER SATURATION SIGNAL — 0 edits, 0 rejected edits:** When report.json shows `"edits": []` and `"rejected_edits": []` with baseline=1.000 → candidate=1.000, this is DEFINITIVE saturation. The LLM couldn't even generate any edits because there's no room for improvement. This is stronger than "gate=reject with rejected edits" — in that case, the LLM at least tried to propose improvements. With 0 edits, the consolidate phase determined no edits were worth proposing. **Action: STOP immediately. Do NOT run further optimizations. The skill has converged.**

**⛔ BROKEN-RECORD SATURATION SIGNAL — same edit category across nights:** When consecutive nights produce rejected edits in the SAME CATEGORY (e.g., night 16: 7 anti-truncation rules rejected, night 17: 8 anti-truncation rules rejected), this confirms saturation. The LLM is not discovering new failure modes — it's persistently proposing variations of the same fix because the rubric doesn't penalize the issue it's trying to solve. **This is NOT a sign that "the next run might finally accept them."** The gate will never accept at baseline=1.0 regardless of edit quality. Recognizing the broken-record pattern helps confirm saturation is real and stops the "maybe next time" temptation.

**Observed 2026-07-15:** After 10 nights of optimization, the skill reached baseline=1.000 (staging 20260715-000343). Subsequent runs (20260715-002231, 20260715-002936, 20260715-011418) all showed `held-out score: 1.000 -> 1.000` with `gate: reject`. Night 12 produced 6 rejected edits (date calculation rules, response structure enforcement, explicit date formatting) — all valid improvements that the rubric couldn't measure because baseline was already perfect. Night 14 showed 0 edits, 0 rejected edits (definitive saturation). The skill had saturated for the given 15-task set.

28. **Subagent premature return ("process launched" without completion).** When delegating SkillOpt runs to subagents, the subagent may return after 15-30 seconds with a summary like "Process launched successfully, PID 12345, will report when done." This is NOT a completion report — the subagent returned before the 30-60 minute run finished. **Symptoms:**
    - Subagent returns in <60 seconds
    - Summary says "process launched" or "running in background"
    - No staging directory timestamp, no scores, no gate decision
    - Subagent's `api_calls` count is very low (2-5)
    
    **Root cause:** The subagent launched the process but didn't wait for `notify_on_complete` to fire. It returned immediately instead of monitoring until completion.
    
    **Detection:**
    - Subagent duration < 60 seconds → premature return
    - Subagent summary lacks: staging dir path, baseline/candidate scores, gate decision
    
    **Fix:** Re-dispatch with explicit instruction to WAIT for completion:
    ```
    goal="Execute SkillOpt run and WAIT for completion. Do NOT return until the process exits.
    Use terminal(background=true, notify_on_complete=true) and then wait for the notification.
    Report: exit code, staging directory, baseline vs candidate scores, gate decision, accepted/rejected edits."
    ```
    
    **Anti-pattern observed 2026-07-15:** Agent dispatched subagent, got back "Process launched, PID 114336" after 21 seconds. Agent then dispatched ANOTHER subagent. This repeated 8+ times, each subagent returning prematurely while the underlying Python process was still running. The agent wasted 2+ hours on premature returns instead of waiting for the single process to complete.
    
    **Rule:** If subagent returns in <60 seconds without scores, it's a premature return. Do NOT dispatch another subagent. Instead: check if the process is still running (`ps aux | grep "python.*skillopt"`), and if so, wait for it to finish naturally.

29. **Tool loop anti-pattern during monitoring (distinct from process polling).** When monitoring a SkillOpt run, the agent may repeatedly check `ps aux | grep "skillopt_sleep run"` or `ls -lt .skillopt-sleep/staging/` with identical results, triggering tool loop warnings like `repeated_exact_failure_warning` or `idempotent_no_progress_warning`. **This is distinct from pitfall #15 (process polling)** — here the agent is checking the filesystem or process list, but the results haven't changed because the run is still in progress.

**Symptoms:**
- Tool loop warning: "repeated_exact_failure_warning; count=N; terminal has failed N times with identical arguments"
- Tool loop warning: "idempotent_no_progress_warning; count=N; read_file returned the same result N times"
- Agent keeps checking `ps aux | grep "skillopt_sleep run"` and getting empty results (process not found)
- Agent keeps checking `ls -lt .skillopt-sleep/staging/` and getting the same latest directory

**Root cause:** The agent doesn't recognize that "no new staging directory" + "no process found" = "run hasn't started yet OR run completed and process exited." It keeps checking the same things expecting different results.

**Fix when you see a tool loop warning:**
1. **STOP the current check pattern immediately** — do NOT retry the same command
2. **Assess what you know:**
   - If `ls -lt staging/` shows a directory with timestamp AFTER your launch time → run completed, read report.md
   - If `ps aux | grep skillopt` is empty AND no new staging dir → run may not have started, or process exited without producing results
   - If you're waiting for a subagent → just say "Waiting for subagent completion notification" and stop checking
3. **Do NOT dispatch another subagent** just because you're stuck in a loop — the original subagent may still be running
4. **Report current state to user** and wait for their instruction or the subagent's completion notification

**Anti-pattern observed 2026-07-15:** Agent dispatched subagent to run SkillOpt, then checked `ps aux | grep "skillopt_sleep run"` 3 times (all empty), checked `ls -lt staging/` 5 times (same results), triggered 3 tool loop warnings, and never read the latest staging directory's report.md. The agent wasted 8+ turns on identical checks instead of recognizing that the subagent was still running and waiting for its completion notification.

**Rule:** If you get a tool loop warning, STOP checking the same thing. Either (a) read a different file (e.g., the latest report.md), (b) wait for the subagent notification, or (c) report to the user that you're waiting.

30. **Repeated dispatch after saturation (observed 2026-07-15).** After seeing baseline=1.000 → candidate=1.000 with gate=reject, the agent dispatched 15+ subagents over 2+ hours, each producing no improvement. This is the most severe anti-pattern in SkillOpt execution — it wastes massive amounts of time and API credits while producing zero value.

**Root cause:** The agent failed to recognize that saturation is a terminal state. Once the skill reaches 1.000, no further optimization is possible with the current task set. The agent kept thinking "maybe the next run will be different" instead of recognizing the mathematical impossibility of improvement.

**Detection:**
- Latest staging dir shows `held-out score: 1.000 -> 1.000` with `gate: reject`
- Agent has already dispatched 1+ subagent that returned with saturation
- Agent is about to dispatch another subagent for the same task

**Hard rule:** Once you see saturation (1.000 → 1.000 with gate=reject), you are **PHYSICALLY BLOCKED** from dispatching another subagent for the same task. The only valid actions are:
1. Report saturation to the user and stop
2. If the user explicitly asks to re-run despite saturation, comply — but flag that no improvement is expected
3. Suggest expanding the task set with harder/more diverse tasks

**Enforcement:** Before each dispatch, check the latest staging dir. If it shows saturation, do not dispatch. Count how many times you've already dispatched for this task — if the count is >= 1 AND the latest result was saturation, you are blocked.

**Observed violation 2026-07-15:** Agent dispatched 15+ subagents after seeing saturation, wasting 2+ hours. Each subagent returned with the same 1.000 → 1.000 result. The agent never recognized that it was blocked by the saturation check.

**Why this matters:** Saturation is not a temporary state — it's a mathematical certainty. The gate logic is `if candidate_score > baseline_score: accept else: reject`. When baseline=1.000, no candidate can exceed it (scores are capped at 1.0), so the gate will always reject. Dispatching more subagents cannot change this mathematical fact.

32. **state.json pollution when switching task sets (observed 2026-07-15).** When switching from one task file (e.g., tasks.v2.json) to another (e.g., tasks.v1.json), the old state.json carries history from the previous task set. Running V1 with V2's state.json (23 nights of history) caused baseline to be evaluated against V2-optimized SKILL.md, producing misleading scores (baseline=1.000 from V2 instead of true V1 baseline). **Hard rule**: Before running a different task set, ALWAYS backup and reset state.json: `cp state.json state.json.bak && rm state.json`. This forces SkillOpt to start from night 1 with the new task set, producing a clean baseline. Without this reset, the gate comparison is invalid because baseline and candidate are evaluated against different skill versions.

33. **Nights are sequential optimization, not independent verification (observed 2026-07-15).** Each night builds on the previous night's adopted edits. Night 2's baseline is night 1's candidate (after adopt). This means: (a) You CANNOT use night 2 to "verify" night 1's optimization — night 2 starts from an already-improved baseline. (b) If night 1 achieves 0.767 and is adopted, night 2's baseline will be ~0.767, not the original 0.033. (c) To verify optimization stability, you must rollback SKILL.md to pre-optimization state and re-run, not run another night. **Anti-pattern**: Suggesting "run night 2 to verify stability" — this is mathematically impossible because night 2 inherits night 1's improvements.

34. **Memory edits lifecycle with --auto-adopt (observed 2026-07-15).** When using `--auto-adopt`, SkillOpt writes skill edits to SKILL.md (inside `<!-- SKILLOPT-SLEEP:LEARNED -->` block) AND memory edits to CLAUDE.md at project root. The CLAUDE.md file is created/modified by auto-adopt. **Problem**: Memory edits are ephemeral — they must be deleted after each night (per iron rules), but deleting CLAUDE.md loses those memory edits permanently. In one observed run, 4 valuable memory edits (ambiguous date handling, output completeness, execution report requirement, anti-truncation) were written to CLAUDE.md, then deleted, and lost. **Options**: (a) Accept that memory edits are disposable — skill edits in SKILL.md are the primary optimization target. (b) Before deleting CLAUDE.md, manually merge valuable memory edits into SKILL.md as skill edits. (c) Do not use `--auto-adopt` — manually review and select which edits to apply. **Recommendation**: After each night, read the staging report.md's rejected edits section (which includes memory edits with rationale), then decide if any should be manually added to SKILL.md before deleting CLAUDE.md.

35. **git revert is too coarse for mixed commits (observed 2026-07-15).** When a SkillOpt run produces edits to SKILL.md (eval-specific rules to discard) AND task file additions (to keep), `git revert` undoes EVERYTHING. Observed: commit d85285b contained SKILL.md eval rules (+11 lines) + tasks.v1.json field additions (+4 lines) + tasks.v2-enhanced.json (new file, +249 lines). Reverting it to discard only the SKILL.md eval rules also deleted the valuable task files. **Fix**: (a) Use `git checkout <commit>~1 -- <specific-file>` to selectively revert only SKILL.md, keeping task files. (b) Better: separate commits — commit task files first, then commit SKILL.md eval changes separately, so reverts are surgical. **Hard rule**: Never mix eval-specific SKILL.md changes with task file additions in one commit.

36. **Commit discipline for SkillOpt runs.** Separate commits for: (1) task file additions/modifications, (2) SKILL.md eval rule changes from SkillOpt. This allows clean reverts of eval rules without losing task files. Pattern: commit task files first → run SkillOpt → commit only SKILL.md changes if valid. If eval rules are bad, revert only the SKILL.md commit, keeping task files intact.

37. **Consolidate hang: Python alive + claude.exe gone = stuck (observed 2026-07-15).** When consolidate runs for 30+ minutes with no staging output, check BOTH the Python process AND claude.exe processes. If Python is alive but NO claude.exe processes exist, the run is stuck — the CLI cannot spawn new calls. **Diagnostic**:
    ```bash
    # Check Python (should show process alive)
    ps aux | grep "python.*skillopt" | grep -v grep
    # Check claude.exe (should show processes during active consolidate)
    tasklist | grep -i claude
    ```
    **Decision**: Python alive + claude.exe gone + no staging output for 30+ min → **KILL and restart**. The run will not recover on its own. Run the pre-flight CLI test (step 6) before re-launching to diagnose why claude.exe cannot spawn.
    
    **Observed 2026-07-15**: Night 2 ran 46 minutes at "consolidate start". Python process (PID 148948) alive the entire time. But `tasklist | grep -i claude` showed claude.exe disappeared after ~20 minutes. No new staging directories. Process had to be killed manually. Pre-flight test would have revealed CLI health issues before launch.
    
    **Contrast with healthy consolidate**: During healthy consolidation, claude.exe processes appear and disappear in bursts (each burst = one batch of parallel LLM calls). If you see NO claude.exe for 10+ consecutive minutes while Python is alive, the run is stuck.

31. **Dispatch-then-check anti-pattern (observed 2026-07-15).** After dispatching a subagent to run SkillOpt, the agent immediately checked state.json, saw it still existed (because the run hadn't finished yet), misinterpreted this as "the run didn't start", backed up state.json, and dispatched a second subagent. This caused duplicate execution and confusion.

**Root cause:** The agent didn't wait for the subagent's completion notification before taking additional action. It checked intermediate state and made incorrect inferences.

**Symptoms:**
- Subagent A dispatched at T+0
- Agent checks state at T+5s (sees state.json still exists)
- Agent misinterprets: "run didn't start"
- Agent takes action (backs up state.json, dispatches subagent B)
- Subagent A completes at T+5m with valid results
- Subagent B completes at T+10m with duplicate results
- Result: two staging directories, confused state, wasted time

**Hard rule:** After dispatching a subagent, **STOP and WAIT** for the completion notification. Do NOT:
- Check state.json or staging directories
- Back up or modify any files
- Dispatch another subagent
- Take any action related to this task

The only valid actions after dispatch are:
1. Wait for the subagent's completion notification
2. If 60 minutes pass with no notification, check filesystem and diagnose
3. If subagent reports failure, then check filesystem and decide next steps

**Why this matters:** Checking intermediate state before the subagent completes leads to incorrect inferences. The state you see is incomplete (the run is in progress), so any action you take based on that state is likely wrong.

**Observed violation 2026-07-15:** Agent dispatched subagent A for V1 testing, then immediately checked state.json, saw it still existed, backed it up, and dispatched subagent B. Both subagents ran, producing duplicate staging directories (20260715-102155 and 20260715-102328). The agent wasted time and created confusion.

**Enforcement:** After calling `delegate_task`, do not make any other tool calls related to this task until the subagent's completion notification arrives. If you feel the urge to "check if it started" or "verify the state", resist it. The subagent will report when done.

38. **Response Structure Rule causes prompt inflation → consolidate timeout (observed 2026-07-15).** When the target skill includes a "Response Structure Rule" requiring per-step structured output (e.g., 8 steps × 4 elements = 32 subsections), the attempt response balloons from ~2K chars to ~28K chars. This large response is then embedded into the reflect prompt (skill 35K + failure response 28K = 36K chars) and gate scoring prompt (37K chars). With the default 180s timeout per Claude CLI call, these oversized prompts cause timeouts during consolidate phase.

    **Observed comparison (same 3 tasks, same skill, same backend):**
    - V1 (rubric evaluates "core understanding" only): attempt responses ~1-3K chars, 6 total calls, ~2 min, all pass → no reflect needed → fast finish
    - V2 (rubric evaluates Response Structure Rule compliance): attempt responses up to 28K chars, 13 total calls, ~7 min, some failures → reflect (36K prompt) → gate scoring (37K prompt) → slow but completed

    **Root cause chain:**
    ```
    Skill requires "output ALL steps with 4 elements each"
    → attempt response = 28K chars (agent outputs 32 subsections)
    → response embedded in reflect prompt as failure evidence
    → reflect prompt = 36K chars (skill 35K + failure 28K)
    → gate scoring prompt = 37K chars
    → each call takes 60-180s → total consolidate = 7+ min
    → with 15+ tasks, this scales to timeout territory
    ```

    **Mitigation options (pick one):**
    1. **Increase Claude CLI timeout** in `backend.py` line 561: `timeout: int = 180` → `timeout: int = 600`. Simple but treats the symptom.
    2. **Truncate failure responses in reflect prompt**: In `backend.py:reflect()`, the `fail_text` joins `r.response[:160]` per failure — this is already truncated. But the full skill text (35K) is always included. Consider whether the skill can be made more concise.
    3. **Relax the Response Structure Rule**: Instead of requiring ALL 8 steps × 4 elements, require only task-relevant steps. E.g., for a date-handling task, only require Step 3 (compose) to show the date conversion. This reduces attempt responses from 28K to ~3-5K.
    4. **Use `--edit-budget 2` instead of 4**: Fewer edits = fewer reflect iterations = fewer large prompts.

    **Key insight**: The Response Structure Rule is valuable for pure-text evaluation (it forces the agent to show understanding), but it creates a token-cost feedback loop. The skill's own "Token optimization" guidance ("Keep each element concise (1-2 sentences)") is not enforced by the LLM — it still outputs verbose subsections. If consolidate timeouts become a pattern, option 3 (relax the rule) is the most sustainable fix.

    **Detection**: If V1 runs fast but V2 hangs at consolidate, check attempt response sizes:
    ```bash
    grep "Claude CLI RESPONSE" /tmp/skillopt_v2_run.log | head -10
    # If responses are 10K+ chars → prompt inflation is the cause
    ```
