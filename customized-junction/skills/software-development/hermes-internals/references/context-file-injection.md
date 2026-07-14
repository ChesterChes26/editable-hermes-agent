# Context File Injection Pipeline

How Hermes auto-discovers and injects AGENTS.md, CLAUDE.md, .cursorrules,
.hermes.md, and SOUL.md into the system prompt.

## Architecture Overview

Two independent mechanisms interact:

1. **Context files** (`prompt_builder.py`) — always-on auto-injection gated by
   `skip_context_files`. Loads project-local instruction files.

2. **Coding posture** (`coding_context.py`) — opt-in mode (`auto`/`focus`/`on`)
   that detects a code workspace and injects a workspace brief + git snapshot.
   These files also double as project-root markers (`_PROJECT_MARKERS`).

Context file injection does NOT depend on coding posture — it runs regardless.

## Call Chain

```
agent/system_prompt.py:331-339   build_system_prompt_parts()
  → agent/runtime_cwd.py:53-61   resolve_context_cwd()     — where to look
  → agent/prompt_builder.py:1647 build_context_files_prompt()
      → _load_hermes_md()        priority 1 (walk to git root)
      → _load_agents_md()        priority 2 (cwd only)
      → _load_claude_md()        priority 3 (cwd only)
      → _load_cursorrules()      priority 4 (cwd only)
      → load_soul_md()           separate, always from HERMES_HOME
```

## Priority Chain (First-Match-Wins)

`prompt_builder.py:1669-1674` — Python `or` short-circuit. Only ONE project
context type is ever loaded. AGENTS.md + CLAUDE.md both present → only
AGENTS.md.

| Loader | Files | Search Scope | Line |
|--------|-------|-------------|------|
| `_load_hermes_md` | `.hermes.md`, `HERMES.md` | cwd → up to git root | 1562 |
| `_load_agents_md` | `AGENTS.md`, `agents.md` | cwd only | 1585 |
| `_load_claude_md` | `CLAUDE.md`, `claude.md` | cwd only | 1601 |
| `_load_cursorrules` | `.cursorrules` + `.cursor/rules/*.mdc` | cwd only | 1617 |

`.hermes.md` discovery (`_find_hermes_md`, line 81): walks cwd and all parent
directories up to (and including) the git root. First match wins.

## Working Directory Resolution

`agent/runtime_cwd.py:53` — three-tier priority:

1. `_SESSION_CWD` contextvar (per-session gateway override)
2. `TERMINAL_CWD` env var (gateway daemon / cron workdir)
3. `os.getcwd()` (CLI launch dir)

Gateway sets `TERMINAL_CWD` at startup to avoid reading its install dir.
CLI leaves it unset, falls through to launch dir.

## Security Scanning

`prompt_builder.py:46-62` — `_scan_context_content()` uses
`tools/threat_patterns.py::scan_for_threats(scope="context")`.

Scope `"context"` covers: classic injection, promptware/C2 patterns,
role-play hijack. Does NOT apply strict-scope patterns (SSH backdoor,
persistence, exfil-URL) — too aggressive for context files in cloned repos.

On any match → entire file replaced with `[BLOCKED: ...]` placeholder.
Content never reaches the system prompt. User has no intervention opportunity.

## Truncation

`prompt_builder.py:957-977`:
- Default cap: `CONTEXT_FILE_MAX_CHARS = 20_000`
- Configurable via `context_file_max_chars` in config.yaml
- Head/tail strategy: first 70% + last 20%, marker in middle
- Warnings accumulated in `_truncation_warnings` ContextVar, drained after build

## skip_context_files Gating

`agent/agent_init.py:304` — controls whether injection runs at all:

| Context | skip_context_files | Source |
|---------|-------------------|--------|
| CLI normal session | `False` | default |
| TUI / Desktop / ACP | `False` (unless `HERMES_IGNORE_RULES=true`) | `tui_gateway/server.py:3553` |
| Subagent (`delegate_task`) | `True` | `delegate_tool.py:1228` |
| Cron (no workdir) | `True` | `scheduler.py:1751` |
| Cron (with workdir) | `False` | `scheduler.py:1751` |
| Batch runner | `True` | `batch_runner.py:344` |
| Curator | `True` | `curator.py:1759` |
| `--ignore-rules` flag | `True` | `cli_agent_setup_mixin.py:384` |

## Cron workdir Mechanism

`cron/scheduler.py:1537-1559`: when a cron job has `workdir` set:

1. `os.environ["TERMINAL_CWD"] = _job_workdir` (line 1558)
2. `skip_context_files = not bool(_job_workdir)` → `False` (line 1751)
3. `resolve_context_cwd()` reads `TERMINAL_CWD` → points to project dir
4. `build_context_files_prompt()` discovers context files from there

If workdir directory was deleted between job creation and execution, falls
back gracefully (logged warning, `TERMINAL_CWD` untouched).

## SOUL.md (Independent Path)

`~/.hermes/SOUL.md` is loaded separately via `load_soul_md()` (line 1534).
It's injected in two possible places:
1. **Stable tier** — as agent identity (slot #1 in system prompt), via
   `load_soul_md()` called from `system_prompt.py:91-101`
2. **Context tier** — as a context file, via `build_context_files_prompt()`
   with `skip_soul=False`

When loaded as identity, `skip_soul=True` prevents double injection.

## System Prompt Placement

`agent/system_prompt.py:323-339` — context files land in the **context tier**
(middle layer), joined with caller-supplied `system_message`:

```
stable tier:   identity + tool guidance + skills + env hints + platform hints
context tier:  system_message + context files (AGENTS.md etc.)
volatile tier: memory + user profile + timestamp
```

## Prompt Cache Impact

The entire system prompt is built once per session and cached. Context files
are in the context tier which may change between sessions (different cwd) but
is stable within a session. Context compression triggers a rebuild.

## Key Files Summary

| File | Role |
|------|------|
| `agent/prompt_builder.py:1647-1686` | `build_context_files_prompt()` — orchestrator |
| `agent/prompt_builder.py:46-62` | `_scan_context_content()` — security scan |
| `agent/prompt_builder.py:1513-1531` | `_truncate_content()` — size cap |
| `agent/runtime_cwd.py:53-61` | `resolve_context_cwd()` — where to look |
| `agent/system_prompt.py:331-339` | Injection into system prompt |
| `agent/agent_init.py:304` | `skip_context_files` gate |
| `agent/coding_context.py:84` | `_CONTEXT_FILES` constant |
| `cron/scheduler.py:1537-1559` | workdir → TERMINAL_CWD bridge |
| `tools/delegate_tool.py:1228` | subagent skip |
