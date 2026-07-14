---
name: hermes-github-backup
description: "Backup a full Hermes Agent setup (source patches, plugins, skills, config) to a private GitHub fork for cross-machine portability."
version: 1.0.0
author: agent
metadata:
  hermes:
    tags: [hermes, github, backup, fork, portable, migration]
    related_skills: [hermes-agent, hermes-a2a, agentmemory-hermes]
---

# Hermes GitHub Backup

Sync a complete Hermes Agent setup — source code modifications, custom plugins,
all installed skills, and runtime configuration — to a private GitHub fork for
lossless cross-machine reproduction.

## Triggers

- "同步 hermes 到 github"
- "备份 hermes 到私人仓库"
- "fork hermes-agent 保存我的改动"
- "导出 hermes 配置到 github"

## What Gets Synced

| Layer | Source path | Repo target | Notes |
|-------|------------|-------------|-------|
| Source patches | `hermes-agent/` (git diff) | Root of fork | Branch `chester` for custom changes |
| Custom plugins | `~/.hermes/plugins/<name>/` | `user-plugins/<name>/` | e.g. agentmemory |
| Skills (default) | `~/.hermes/skills/` | `user-skills/` | Exclude `.hub/`, `.curator_backups/`, `__pycache__/` |
| Skills (worker) | `~/.hermes/profiles/worker/skills/` | `user-config/profiles/worker/skills/` | Same cache exclusions |
| Config | `~/.hermes/config.yaml` | `user-config/config.yaml` | Verify no real API keys |
| Hooks | `~/.hermes/hooks/` | `user-config/hooks/` | Gateway event hooks |
| Cron jobs | `~/.hermes/cron/jobs.json` | `user-config/cron/` | Timed tasks |
| Scripts | `~/.hermes/scripts/` | `user-config/scripts/` | Custom scripts (watchdog, etc.) |
| Memories | `~/.hermes/memories/` | `user-config/memories/` | MEMORY.md + USER.md |
| Worker config | `~/.hermes/profiles/worker/config.yaml` | `user-config/profiles/worker/` | A2A worker profile |

## What NEVER Goes to GitHub

- `~/.hermes/.env` — API keys
- `~/.hermes/auth.json` — OAuth tokens
- `~/.hermes/state.db` — Session history with user IDs
- `~/.hermes/channel_directory.json` — WeChat/QQ openids
- `~/.hermes/gateway_state.json` — Runtime PID/connection state
- `~/.hermes/logs/`, `cache/` — Local artifacts

## Step 1: Fork on GitHub

1. Fork `https://github.com/NousResearch/hermes-agent` on GitHub (private repo recommended)
2. Note the fork URL: `https://github.com/<user>/hermes-agent.git`

## Step 2: Configure Git Remotes

Standard fork workflow — origin is YOUR fork, upstream is NousResearch:

```bash
cd ~/.hermes/hermes-agent
git remote rename origin upstream
git remote add origin https://github.com/<user>/hermes-agent.git
git remote -v  # verify: origin→your fork, upstream→NousResearch
```

## Step 3: Commit and Push Source Changes

```bash
cd ~/.hermes/hermes-agent
git checkout -b chester                    # create branch for custom changes
git add -A                                 # stage all modified files
git commit -m "custom: <description>"      # commit
git push origin chester                    # push to fork
```

## Step 4: Add user-plugins, user-skills, user-config

Copy everything into the repo, excluding caches:

```bash
cd ~/.hermes/hermes-agent

# Plugins
mkdir -p user-plugins/<name>
cp ~/.hermes/plugins/<name>/*.{py,yaml} user-plugins/<name>/
# never copy __pycache__/

# Skills (default profile)
mkdir -p user-skills
cp -r ~/.hermes/skills/* user-skills/
rm -rf user-skills/.hub user-skills/.curator_backups
find user-skills -name "__pycache__" -type d -exec rm -rf {} +

# Runtime config
mkdir -p user-config/{hooks,cron,scripts,profiles/worker,memories}
cp ~/.hermes/config.yaml user-config/
cp -r ~/.hermes/hooks/* user-config/hooks/
cp ~/.hermes/cron/jobs.json user-config/cron/
cp ~/.hermes/scripts/*.py user-config/scripts/
cp ~/.hermes/memories/*.md user-config/memories/

# Worker profile
cp ~/.hermes/profiles/worker/config.yaml user-config/profiles/worker/
cp -r ~/.hermes/profiles/worker/skills user-config/profiles/worker/skills
# same cache cleanup as above

# Verify no secrets in config
grep -n "sk-\|AKID\|AIza\|xai-\|hf_\|dsk-" user-config/config.yaml \
  user-config/profiles/worker/config.yaml || echo "safe"

# Commit and push
git add user-plugins/ user-skills/ user-config/
git commit -m "feat: add plugins, skills, and runtime config"
git push origin chester
```

## Step 5: Create SETUP.md

Add a restore guide at the repo root. See `references/SETUP-template.md`.

## Step 6: Restore on New Machine

```bash
git clone https://github.com/<user>/hermes-agent.git ~/.hermes/hermes-agent
cd ~/.hermes/hermes-agent
git checkout chester

# Link plugins
cp -r user-plugins/* ~/.hermes/plugins/

# Link skills
rm -rf ~/.hermes/skills
cp -r user-skills ~/.hermes/skills

# Link config
cp user-config/config.yaml ~/.hermes/
cp -r user-config/hooks/* ~/.hermes/hooks/
cp user-config/cron/jobs.json ~/.hermes/cron/
cp user-config/scripts/* ~/.hermes/scripts/
cp user-config/memories/* ~/.hermes/memories/

# Worker profile
rm -rf ~/.hermes/profiles/worker
mkdir -p ~/.hermes/profiles/worker
cp user-config/profiles/worker/config.yaml ~/.hermes/profiles/worker/
cp -r user-config/profiles/worker/skills ~/.hermes/profiles/worker/skills

# MANUAL: fill in ~/.hermes/.env with API keys
# MANUAL: start agentmemory docker if needed
```

## Keeping Up with Upstream

```bash
cd ~/.hermes/hermes-agent
git fetch upstream
git checkout main
git merge upstream/main          # fast-forward to latest NousResearch
git checkout chester
git rebase main                  # replay your changes on top
# resolve conflicts if any, then:
git push origin chester --force-with-lease
```

## Step 4b: Incremental skill sync (ongoing)

After the initial backup, Hermes updates skills at runtime (via `skill_manage`,
curator, or agent-initiated edits). These runtime changes live in
`~/AppData/Local/hermes/skills/` (Windows) or `~/.hermes/skills/` (macOS/Linux)
and MUST be synced back to the git-tracked `user-skills/` before committing.

**Workflow for incremental sync:**

```bash
cd <hermes-agent-repo>   # ~/AppData/Local/hermes/hermes-agent on Windows

# Diff runtime vs tracked — find what changed
for skill in $(ls ~/AppData/Local/hermes/skills/); do
  diff -rq ~/AppData/Local/hermes/skills/$skill user-skills/$skill 2>/dev/null \
    && echo "  $skill: unchanged" \
    || echo "  $skill: CHANGED"
done

# Sync only changed skills
cp -r ~/AppData/Local/hermes/skills/<skill-name> user-skills/<skill-name>/

# For NEW skills (runtime but not tracked):
cp -r ~/AppData/Local/hermes/skills/<new-skill> user-skills/<new-skill>/

git add user-skills/
git commit -m "feat: sync updated skills — <list names>"
```

**When this is needed:** Any session that used `skill_manage` to create/patch
skills, or any session where `skill_view` led to agent-initiated skill edits.
A session with skill changes left uncommitted is a silent divergence —
next `hermes-git-sync` won't know what changed.

## Pitfalls

- **Windows path differs**: On Windows, the Hermes data lives at
  `~/AppData/Local/hermes/`, NOT `~/.hermes/`. The repo is at
  `~/AppData/Local/hermes/hermes-agent/`. On macOS/Linux it's `~/.hermes/hermes-agent/`.
  Always verify with `ls ~/.hermes ~/AppData/Local/hermes 2>/dev/null` before
  assuming the path.
- **Runtime skills diverge from git**: Skills are updated by Hermes at runtime
  in `~/AppData/Local/hermes/skills/` (or `~/.hermes/skills/`). These changes
  do NOT auto-propagate to `user-skills/` in the git repo. After sessions with
  skill changes, you MUST run Step 4b before `git commit`.
- **Config has API keys**: Always grep for key patterns before committing config.yaml.
  All api_key values should be empty strings `''` — real keys live in `.env`.
- **Skills include .hub cache**: The `.hub/index-cache/` directory can be 20MB+.
  Always exclude it.
- **Worker profile duplicates skills**: Worker profile has its own independent skills
  directory. It must be synced separately from the default profile skills.
- **Git identity**: On first commit, git may auto-generate committer from system
  username. Set `git config user.name/email` if you care about attribution.
- **Force push after rebase**: When rebasing chester onto updated main, you need
  `--force-with-lease` since chester history diverges.
- **Large diffs in weixin/qqbot**: These platform adapters have 4800+ line diffs.
  Upstream changes to the same files will almost certainly conflict. Consider
  extracting your changes into hooks or plugins to reduce merge pain long-term.
- **GitHub blocked by firewall**: Direct `git push` to github.com may fail with
  `Could not connect to server`. Configure proxy before pushing:
  ```bash
  git config http.proxy http://127.0.0.1:7897
  ```
  After successful push, verify the proxy setting persists in `.git/config`.
  This is per-repo — each new clone needs it set.
