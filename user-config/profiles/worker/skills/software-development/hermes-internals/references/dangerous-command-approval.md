# Dangerous Command Approval Architecture

Two-tier detection system in `tools/approval.py` — every `terminal()` call passes
through `check_all_command_guards()` (`approval.py:1334`) before execution.

## Two-Tier Detection

### Tier 1: HARDLINE_PATTERNS (unconditional block)

Defined at `approval.py:260-282`. **Never bypassed** by yolo, mode=off, or
cron approve-mode. 12 patterns for catastrophic operations:

| Pattern | Description |
|---------|-------------|
| `rm -rf /` | Recursive delete of root filesystem |
| `rm -rf /home`, `/etc`, `/usr`, ... | Recursive delete of system dir |
| `rm -rf ~/` or `$HOME` | Recursive delete of home |
| `mkfs` | Format filesystem |
| `dd ... of=/dev/sd*` | Raw block device write |
| `> /dev/sd*` | Redirect to block device |
| `:(){ :\|:& };:` | Fork bomb |
| `kill -1` | Kill all processes |
| `shutdown`, `reboot`, `halt`, `poweroff` | System power ops (anchored to cmd start via `_CMDPOS`) |
| `init 0/6` | Init shutdown/reboot |
| `systemctl poweroff/reboot` | Systemctl power ops |
| `telinit 0/6` | Telinit shutdown/reboot |

Entry path: `check_all_command_guards()` → `detect_hardline_command()` →
`_hardline_block_result()` → `approved=False, hardline=True`.

### Sudo stdin guard (also unconditional)

`approval.py:312-328` — when `SUDO_PASSWORD` is unset, any `sudo -S` is
blocked. Prevents LLM password guessing via stdin. Runs BEFORE yolo check.

### Tier 2: DANGEROUS_PATTERNS (subject to approval mode)

Defined at `approval.py:378-520`. ~47 patterns that go through mode-dependent
approval. Categories:

| Category | Example patterns |
|----------|-----------------|
| Delete | `rm -rf`, `find -exec rm`, `find -delete`, `xargs rm` |
| Permissions | `chmod 777`, `chown -R root` |
| SQL | `DELETE FROM` (no WHERE), `DROP TABLE/DATABASE`, `TRUNCATE` |
| System config writes | `tee/>/>>` to `/etc/`, `~/.ssh/`, `~/.bashrc`, `~/.hermes/config.yaml` |
| In-place edits | `sed -i`, `perl -i`, `ruby -i` on sensitive paths |
| Git destructive | `git reset --hard`, `git push --force`, `git clean -f`, `git branch -D` |
| Script execution | `curl \| sh`, `python -c`, `bash -c`, heredoc, `chmod +x && ./` |
| Process mgmt | `systemctl stop/restart`, `kill -9`, `pkill -9`, `killall` |
| Docker lifecycle | `docker stop/restart/kill`, `docker compose down` |
| Self-protection | `hermes gateway stop/restart`, `pkill hermes`, `kill $(pgrep hermes)` |
| File ops | `cp/mv/install` to sensitive paths |
| Sudo flags | `sudo -S/-s/-A` (privilege escalation) |

## Command Normalization

`_normalize_command_for_detection()` (`approval.py:557-589`) applies before
pattern matching:

1. Strip ANSI escape sequences (CSI, OSC, DCS)
2. Strip null bytes
3. NFKC normalization (defeats fullwidth-character bypass)
4. Strip backslash escapes (`\r\m` → `rm`)
5. Strip empty-string literals (`r''m` → `rm`)
6. Rewrite absolute `$HOME` path to `~/`
7. Rewrite absolute `$HERMES_HOME` path to `~/.hermes/`

## Three Approval Modes

Config key: `approvals.mode` in `config.yaml`. Read by `_get_approval_mode()`
(`approval.py:1024-1027`). Default: `manual`.

**YAML gotcha**: YAML 1.1 parses bare `off` as boolean `False`.
`_normalize_approval_mode()` (`approval.py:998-1010`) corrects this:
`isinstance(mode, bool) and mode is False → "off"`.

### manual (default)

Every dangerous command triggers an interactive prompt.

- **CLI**: `prompt_dangerous_approval()` (`approval.py:883`) — shows command +
  description, accepts `o(once)` / `s(session)` / `a(always)` / other=deny
- **Gateway**: `_await_gateway_decision()` (`approval.py:1233`) — sends request
  to user, blocks agent thread until response (default 5min timeout)
- **Cron**: controlled by `approvals.cron_mode` (separate from `mode`), default `deny`

User choices:
- **once**: allow this single execution
- **session**: remember for this session (in `_session_approved` dict)
- **always**: write to `config.yaml` → `command_allowlist` (permanent)
- **deny** / timeout: agent gets explicit "do NOT retry" message

### smart

Auxiliary LLM pre-screens before manual prompt. `_smart_approve()`
(`approval.py:1051-1095`).

Flow in `check_all_command_guards()` (`approval.py:1443-1463`):
1. Build combined description from all warnings
2. Call `_smart_approve(command, combined_desc)`
3. LLM prompt: "You are a security reviewer... Assess ACTUAL risk"
4. Response: APPROVE → auto-approve + session-scope remember
5. Response: DENY → hard block
6. Response: ESCALATE → fall through to manual prompt

Uses `agent/auxiliary_client.py::call_llm(task="approval", temperature=0,
max_tokens=16)`. The auxiliary LLM can be a smaller/cheaper model.

Design origin: OpenAI Codex's Smart Approvals guardian subagent
(`openai/codex#13860`).

### off

Equivalent to `--yolo`. `approval.py:1370`:
```python
if _YOLO_MODE_FROZEN or is_current_session_yolo_enabled() or approval_mode == "off":
    return {"approved": True, "message": None}
```

YOLO is frozen at module import time (`approval.py:29`) to prevent
prompt-injection bypass (scripts can't set `HERMES_YOLO_MODE` mid-process).

Still subject to HARDLINE_PATTERNS — `rm -rf /` always blocked.

## Session State

Per-session approval tracking (`approval.py:673-677`):
- `_session_approved: dict[str, set]` — patterns approved for this session
- `_session_yolo: set[str]` — sessions with yolo enabled
- `_permanent_approved: set` — from `command_allowlist` in config.yaml

Gateway blocking queue (`approval.py:688-698`):
- `_ApprovalEntry` with `threading.Event` — blocks agent thread
- `resolve_gateway_approval()` — `/approve` or `/deny` unblocks
- FIFO ordering, `resolve_all=True` for `/approve all`

## Container Backend Bypass

`approval.py:1113` and `1344`: commands in Docker/Singularity/Modal/Daytona
backends skip ALL checks — containerized environments can't touch the host.

## Permanent Allowlist

`approval.py:850-876` — loaded from `config.yaml` → `command_allowlist` on
module import. User's "always" choice calls `save_permanent_allowlist()` which
writes the pattern key (human-readable description string) to config.

Pattern key aliasing (`approval.py:530-550`): new approvals use the
human-readable description; older entries may have regex-derived keys.
`_PATTERN_KEY_ALIASES` maps both forms to the same canonical key.

## Combined Guard (tirith + dangerous command)

`check_all_command_guards()` (`approval.py:1334`) is the main entry point. It
also runs `tools/tirith_security.py::check_command_security()` for
content-level security scanning. Both findings are presented as a single
combined approval prompt to prevent bypass via force=True replay.

`check_execute_code_guard()` (`approval.py:1631`) — analogous guard for
`execute_code` tool, since its Python code can call `subprocess` outside
terminal() approval scope.
