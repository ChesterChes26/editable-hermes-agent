---
name: hermes-git-sync
description: "Sync Hermes Agent setup (source patches, plugins, skills, config) to a private GitHub fork for portability and version control."
version: 2.0.0
author: agent
metadata:
  hermes:
    tags: [hermes, git, github, fork, portability, backup, devops]
    related_skills: [hermes-agent, hermes-a2a, agentmemory-hermes]
---

# Hermes Git Sync

Make your Hermes setup fully version-controlled and machine-portable by forking
hermes-agent to a private GitHub repo and tracking source patches, plugins, and
skills in one place.

## Related references

- `references/claude-to-hermes-adaptation.md` — Claude Code skill → Hermes 适配清单（工具前缀、pid/window_id、路径、token 追踪）
- `references/path-migration.md` — 换机器时批量替换硬编码路径的完整指南
- `references/setup-template.md` — Restore guide template

## Triggers

- "同步 hermes 到 github" / "commit and push" / "备份 hermes 所有改动"
- "换机器怎么还原 hermes"
- "当前 runtime 是不是一个 repo" / "配置都 push 了吗"
- "junction 状态" / "runtime 跟踪状态"

## Architecture: Junction-Based Runtime

All five mutable runtime directories are **junctions** pointing into `customized-junction/` inside the repo:

```text
~/AppData/Local/hermes/
  skills/   → junction → hermes-agent/customized-junction/skills/
  plugins/  → junction → hermes-agent/customized-junction/plugins/
  hooks/    → junction → hermes-agent/customized-junction/hooks/
  memories/ → junction → hermes-agent/customized-junction/memories/
  scripts/  → junction → hermes-agent/customized-junction/scripts/
```

**Single invariant:** `customized-junction/` in the repo IS the truth. `git status` in `hermes-agent/` reflects real runtime state. No sync needed.

### Repo layout

```text
hermes-agent/
  customized-junction/
    skills/          # All installed skills
    plugins/         # Custom plugins (agentmemory, horizon)
    hooks/           # Event hooks
    memories/        # USER.md (tracked), MEMORY.md (ignored)
    scripts/         # Runtime scripts (watchdog etc.)
    path-map.yaml    # Path migration mapping
    migrate-paths.py # Path migration script
    PATH_MIGRATION.md
  user-config/       # Legacy config (worker profile skills etc.)
  .gitignore         # Covers customized-junction/ runtime artifacts
```

## What gets tracked

| Layer | In repo? | Location |
|-------|----------|----------|
| Source patches | Yes | Modified files in repo |
| Plugins | Yes | `customized-junction/plugins/` |
| Skills | Yes | `customized-junction/skills/` |
| Hooks | Yes | `customized-junction/hooks/` |
| Scripts | Yes | `customized-junction/scripts/` |
| USER.md | Yes | `customized-junction/memories/` |
| MEMORY.md | No | Runtime state, gitignored |
| `config.yaml` | No | Contains API keys |
| `.env` | No | Raw API keys |
| `auth.json` | No | OAuth tokens |
| `state.db` | No | Session PII |
| `channel_directory.json` | No | Platform user IDs |
| `SOUL.md` | No | Persona (consider tracking) |
| `cron/jobs.json` | No | Scheduled tasks (consider tracking) |

## Pre-Commit Checklist

With junctions, `git status` in `hermes-agent/` directly reflects runtime state.

### Step 1: Check status

```bash
cd ~/AppData/Local/hermes/hermes-agent
git status --short
git ls-files --others --exclude-standard -- customized-junction/
```

### Step 2: Verify .gitignore covers runtime artifacts

These should be ignored (not committed):

```
.hub/  .bundled_manifest  .curator_backups/  .curator_state
.usage.json  *.lock  __pycache__/  *.pyc
snapshots/  _example_snapshots/  DESCRIPTION.md  MEMORY.md
```

### Step 3: Commit + Push

```bash
git add -A
git commit -m "..."
git push origin chester
```

## Restore on new machine

### Step R1: Clone and checkout

```bash
git clone https://github.com/<user>/hermes-agent.git ~/AppData/Local/hermes/hermes-agent
cd ~/AppData/Local/hermes/hermes-agent
git checkout <branch-name>
```

### Step R2: Recreate junctions

```powershell
$Runtime = 'C:\Users\<newuser>\AppData\Local\hermes'
$Repo = Join-Path $Runtime 'hermes-agent'
$Target = Join-Path $Repo 'customized-junction'

foreach ($name in @('skills','plugins','hooks','memories','scripts')) {
  $runtimePath = Join-Path $Runtime $name
  if (Test-Path -LiteralPath $runtimePath) {
    [System.IO.Directory]::Delete($runtimePath, $false)
  }
  New-Item -ItemType Junction -Path $runtimePath -Target (Join-Path $Target $name) | Out-Null
}
```

### Step R3: Path migration

Skills contain hardcoded paths from the original machine. Fill in `path-map.yaml` and run:

```bash
python customized-junction/migrate-paths.py
```

See `references/path-migration.md` for full guide.

### Step R4: Restore non-tracked runtime files

Manually restore (NEVER in git):
- `.env` (API keys)
- `auth.json` (OAuth tokens)
- `config.yaml` (provider settings, API keys)
- `SOUL.md` (persona)
- `cron/jobs.json` (scheduled tasks)
- `channel_directory.json` (platform channel mappings)

## Updating from upstream

```bash
cd ~/AppData/Local/hermes/hermes-agent

# 1. Ensure clean state
git checkout chester && git status

# 2. Fetch and update main
git checkout main && git fetch upstream && git merge upstream/main && git push origin main

# 3. Merge into custom branch
git checkout chester && git merge main -m "merge upstream/main into chester"

# 4. Verify patches survived
grep -c "ITEM_NOTE\|ITEM_RECORD\|ITEM_APPMSG" gateway/platforms/weixin.py  # should be ≥ 9

# 5. Rebuild venv
uv sync --directory .

# 6. Restart gateway
hermes gateway stop && hermes gateway start
```

## Junction caveats on Windows

- Git tracks junction contents normally — `git add customized-junction/skills/` works
- Junctions require the target to exist before creation
- Some tools (rm -rf + recreate) can replace junction with real dir silently
- `mklink /J <link> <target>` for directories; no admin needed

## Pitfalls

- **Windows path**: `~/AppData/Local/hermes/`, NOT `~/.hermes/`. Repo at `~/AppData/Local/hermes/hermes-agent/`.
- **Workspace clone ≠ runtime install**: `/d/workspace/hermes-agent` (dev) ≠ `~/AppData/Local/hermes/hermes-agent/` (runtime fork).
- **Source patches tied to base commit**: Record `git rev-parse HEAD` before major upstream merges.
- **`.hub/` cache is huge (~24MB)**: Already in `.gitignore`, but verify before committing.
- **agentmemory needs Docker**: Plugin code syncs via git, but `docker run rohitg00/agentmemory` must run on target.
- **WeChat/QQ patches fragile**: After `git rebase main`, check `gateway/platforms/weixin.py` and `qqbot/adapter.py`.
- **git merge ≠ uv sync**: After merge, always `uv sync --directory .` before restart.
- **Shallow clone breaks merge**: `cat .git/shallow` → if present, `git fetch --unshallow origin` first.
- **GitHub blocked**: `git config http.proxy http://127.0.0.1:7897`
