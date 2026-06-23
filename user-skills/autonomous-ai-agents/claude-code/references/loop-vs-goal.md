# /loop vs /goal — Full Comparison (from official docs)

Source: https://code.claude.com/docs/en/goal and https://code.claude.com/docs/en/scheduled-tasks

## Compare ways to keep a session running

Three approaches keep the current session running between prompts. Pick based on what
should start the next turn:

| Approach | Next turn starts when | Stops when |
|---|---|---|
| `/goal` | The previous turn finishes | A model confirms the condition is met |
| `/loop` | A time interval elapses | You stop it, or Claude decides the work is done |
| Stop hook | The previous turn finishes | Your own script or prompt decides |

`/goal` and a Stop hook both fire after every turn. `/goal` is a session-scoped shortcut:
you type a condition and it's active for the current session only. A Stop hook lives in
your settings file, applies to every session in its scope, and can run a script for
deterministic checks or a prompt for model-evaluated ones.

Auto mode on its own approves tool calls within a single turn but doesn't start a new
one. `/goal` adds a separate evaluator that checks your condition after every turn, so
completion is decided by a fresh model rather than the one doing the work. The two are
complementary: auto mode removes per-tool prompts, and `/goal` removes per-turn prompts.

## /loop detailed

Three modes:

| What you provide | Example | What happens |
|---|---|---|
| Interval and prompt | `/loop 5m check the deploy` | Your prompt runs on a fixed schedule |
| Prompt only | `/loop check the deploy` | Your prompt runs at an interval Claude chooses each iteration |
| Interval only, or nothing | `/loop` | The built-in maintenance prompt runs, or your loop.md if one exists |

Supported interval units: `s` (seconds), `m` (minutes), `h` (hours), `d` (days).
Seconds are rounded up to the nearest minute (cron granularity). Intervals that don't
map to a clean cron step (e.g., `7m`, `90m`) are rounded and Claude tells you what it
picked.

Dynamic scheduling: when you omit the interval, Claude picks a delay between 1 minute
and 1 hour based on what it observed. Short waits while a build is finishing, longer
waits when nothing is pending. Claude may use the Monitor tool directly instead of
polling when appropriate.

On Bedrock, Vertex AI, and Microsoft Foundry: a prompt with no interval runs on a fixed
10-minute schedule instead. `/loop` with no prompt prints the usage message instead of
running the maintenance prompt.

Built-in maintenance prompt: works through (in order):
1. Continue any unfinished work from the conversation
2. Tend to the current branch's PR: review comments, failed CI, merge conflicts
3. Run cleanup passes such as bug hunts or simplification when nothing else is pending

Custom default prompt: create `.claude/loop.md` at the project root. It replaces the
built-in maintenance prompt. Ignored whenever you supply a prompt on the command line.

Tasks are session-scoped and resume with `--resume`/`--continue` if unexpired: a
recurring task created within the last 7 days, or a one-shot whose scheduled time hasn't
passed yet.

## /goal detailed

Requires Claude Code v2.1.139 or later.

The `/goal` command sets a completion condition and Claude keeps working toward it
without you prompting each step. After each turn, a small fast model checks whether the
condition holds. If not, Claude starts another turn instead of returning control to you.
The goal clears automatically once the condition is met.

Use a goal for substantial work with a verifiable end state:
- Migrating a module to a new API until every call site compiles and tests pass
- Implementing a design doc until all acceptance criteria hold
- Splitting a large file into focused modules until each is under a size budget
- Working through a labeled issue backlog until the queue is empty

One goal can be active per session. Setting a goal starts a turn immediately, with the
condition itself as the directive.

Write an effective condition: the evaluator judges your condition against what Claude has
surfaced in the conversation. It doesn't run commands or read files independently, so
write the condition as something Claude's own output can demonstrate. "All tests in
test/auth pass" works because Claude runs the tests and the result lands in the
transcript for the evaluator to read.

A condition that holds up across many turns usually has:
- One measurable end state: a test result, a build exit code, a file count, an empty queue
- A stated check: how Claude should prove it, such as "npm test exits 0" or "git status is clean"
- Constraints that matter: anything that must not change on the way there

Max 4,000 characters. Include `or stop after 20 turns` to bound runtime.

Check status: `/goal` (no arguments) shows condition, duration, turns evaluated, token
spend, and evaluator's most recent reason.

Clear: `/goal clear` (aliases: stop, off, reset, none, cancel). `/clear` also removes
any active goal.

Resume: a goal still active when a session ended is restored on `--resume`/`--continue`.
Turn count, timer, and token-spend baseline reset on resume.

Non-interactive: `claude -p "/goal CHANGELOG.md has an entry for every PR merged this week"`
runs the loop to completion in a single invocation. Ctrl+C to interrupt.

How evaluation works: `/goal` wraps a session-scoped prompt-based Stop hook. Each time
Claude finishes a turn, the condition and the conversation so far are sent to your
configured small fast model (defaults to Haiku). The model returns a yes-or-no decision
and a short reason. "No" tells Claude to keep working and includes the reason as guidance
for the next turn. "Yes" clears the goal. The evaluator runs on whichever provider your
session is configured for and does not call tools.

Requirements: `/goal` runs only in workspaces where you have accepted the trust dialog,
because the evaluator is part of the hooks system. Unavailable when `disableAllHooks` is
set or when `allowManagedHooksOnly` is set in managed settings.
