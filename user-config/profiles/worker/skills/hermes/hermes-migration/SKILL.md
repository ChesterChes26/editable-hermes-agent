---
name: hermes-migration
description: "Audit, export, and migrate Hermes Agent setups between machines."
version: 1.0.0
author: agent
metadata:
  hermes:
    tags: [hermes, migration, export, backup, portable]
    related_skills: [hermes-agent]
---

# Hermes Migration

Audit what customizations exist in a Hermes installation and export them
losslessly for replication on another machine.

## Triggers

- "导出/迁移/复制 hermes 到另一台机器"
- "有哪些改动可以无损导出"
- "backup/migrate/clone my Hermes setup"

## Step 1: Audit what's been changed

Run these diagnostics in order. Each reveals a different layer of customization.

### Skills: agent-created vs hub-installed vs bundled

Read `~/.hermes/skills/.usage.json` — any entry with `"created_by": "agent"`
is a skill the user created. Cross-reference with `.bundled_manifest`
to distinguish hub-installed skills from the bundled base set.

```bash
# Quick: list agent-created skills
python3 -c "
import json
u = json.load(open('.hermes/skills/.usage.json'))
for k,v in u.items():
    if v.get('created_by') == 'agent':
        print(f'  {k}  (patched {v[\"patch_count\"]}x, used {v[\"use_count\"]}x)')
"
```

### Config: what differs from defaults

Read `~/.hermes/config.yaml`. Focus on sections the user would have changed:
`model.*`, `platform_toolsets.*`, `agent.*`, `memory.*`, `display.language`,
`approvals.mode`.

### Source code patches

The hermes-agent source lives at `~/.hermes/hermes-agent/`. Check for local
modifications:

```bash
cd ~/.hermes/hermes-agent
git diff --stat           # which files are modified
git rev-parse HEAD        # the base commit (NEEDED for clean apply)
```

Gateway platform adapters (`gateway/platforms/weixin.py`,
`gateway/platforms/qqbot/`) are common patch targets.

### Credentials (.env)

Credentials live in `~/.hermes/.env`. This file is protected from `read_file`
— use `terminal` with `grep` to enumerate which env vars are set:

```bash
grep -i "^[A-Z]" ~/.hermes/.env | sed 's/=.*/=***REDACTED***/'
```

### Platform runtime state

`channel_directory.json` — session routing (NOT portable, contains user openids).
`gateway_state.json` — runtime state (NOT portable).

## Step 2: Categorize portability

| Layer | Portable? | Export method |
|-------|-----------|---------------|
| Skills (`skills/`) | Yes | Copy directory or `hermes profile export` |
| `config.yaml` | Yes | Copy file (no machine-specific paths) |
| `.env` credentials | Yes | Copy file (contains secrets — transport securely) |
| Source patches | Conditional | `git diff > patches.diff` + record commit SHA |
| `memory/` (profile memories) | Conditional | Contains machine-specific paths sometimes |
| `state.db` (sessions) | No | Session history, bound to machine |
| `channel_directory.json` | No | Contains user-specific chat IDs |
| `gateway_state.json` | No | Runtime PID/connection state |
| `logs/`, `cache/` | No | Local artifacts |

## Step 3: Export

### Method A: Profile export (skills + config + memory + cron + .env)

```bash
hermes profile export default --output hermes-export.tar.gz
```

This does NOT include source patches.

### Method B: Source patches (separate step)

```bash
cd ~/.hermes/hermes-agent
git rev-parse HEAD > HERMES_COMMIT.txt
git diff > hermes-patches.diff
```

### Method C: Full manual bundle

For maximum control, manually collect:
- `skills/` directory
- `config.yaml`
- `.env`
- `hermes-patches.diff` + `HERMES_COMMIT.txt`
- Any custom plugins in `plugins/` (check `config.yaml` `plugins.enabled`)

## Step 4: Restore on target machine

1. Install same hermes-agent version
2. `hermes profile import hermes-export.tar.gz`
3. `cd ~/.hermes/hermes-agent && git checkout <commit> && git apply hermes-patches.diff`
4. Restart gateway: `hermes gateway restart`

## Pre-Upgrade Impact Assessment

Before running `hermes update` or `git pull`, check whether upstream changes
will collide with local patches. This is the `git log` + `git diff`
cross-reference that answers "will my modifications break?"

```bash
cd ~/.hermes/hermes-agent

# 1. How far behind?
git rev-parse HEAD                    # your commit
git rev-parse origin/main             # upstream target
git log --oneline HEAD..origin/main | wc -l   # commit count

# 2. What files did you modify?
git diff --stat                       # which files, how many lines

# 3. Do any upstream commits touch YOUR modified files?
git log --oneline HEAD..origin/main -- <file1> <file2> ...
# EMPTY output = zero conflict for those files.
```

Decision matrix:

| Upstream touches your file? | You modified it? | Result |
|------------------------------|------------------|--------|
| No | Yes | Safe — no merge conflict |
| Yes | No | Safe — clean apply |
| Yes | Yes | CONFLICT — manual resolution needed |

Filtering tip: categorize upstream commits by scope first (`feat(desktop):`,
`fix(telegram):`, `test(...)` etc.) to focus only on CLI-relevant ones before
drilling into conflict checks. Desktop/gateway/test-only commits are noise
for CLI users.

## Pitfalls

- Source patches only apply cleanly to the exact git commit they were made from.
  If the target has a different hermes-agent version, patches will fail.
  Always record `git rev-parse HEAD`.
- `.env` contains API keys — transport securely.
- `channel_directory.json` contains WeChat openids — if the target machine
  uses different accounts, do NOT copy this file.
- Platform adapter patches (weixin.py, qqbot/adapter.py) are the most
  fragile layer. Consider upstreaming patches or maintaining a fork if
  they're substantial.
- Upstream commits that touch files adjacent to your patches (same module,
  different function) can still cause semantic conflicts even without git
  merge conflicts. Review the upstream diff for changed function signatures
  or refactored imports in patched files.
