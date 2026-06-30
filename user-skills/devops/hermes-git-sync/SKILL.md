---
name: hermes-git-sync
description: "Sync Hermes Agent setup (source patches, plugins, skills, config) to a private GitHub fork for portability and version control."
version: 1.0.0
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

## Triggers

- "同步 hermse 到 github" / "能不能把 hermse 配置做成 git 仓库" / "备份 hermse 所有改动"
- "commit and push" / "commit hermes changes" / "当前hermes的改动 commit and push"
- "本机hermes"（区别于 D 盘/workspace 的开发 clone） / "当前hermes需要切到main分支拉取上游最新code"
- "换机器怎么还原 hermse"
- "SETUP.md 更新" / "更新 SETUP"

## What gets tracked

| Layer | In repo? | Location in fork |
|-------|----------|-----------------|
| Source patches (weixin.py, qqbot, agent_init.py) | Yes | Committed directly in modified files |
| Custom plugins (agentmemory, etc.) | Yes | `user-plugins/<name>/` |
| All installed skills | Yes | `user-skills/` (exclude `.hub/`, `.curator_backups/`, `__pycache__/`) |
| `config.yaml` | No | Contains API key references — handle separately |
| `.env` | No | NEVER commit — contains raw API keys |
| `state.db` | No | Session history with user PII |
| `channel_directory.json` | No | WeChat/QQ user openids |
| `auth.json` | No | OAuth tokens |

## Step 1: Fork to GitHub

1. Go to https://github.com/NousResearch/hermes-agent
2. Fork → **Private** repository
3. Clone URL will be `https://github.com/<user>/hermes-agent.git`

## Step 2: Reconfigure remotes

Standard fork workflow: `origin` = your fork, `upstream` = NousResearch.

```bash
cd ~/.hermes/hermes-agent
git remote rename origin upstream
git remote add origin https://github.com/<user>/hermes-agent.git
```

## Step 3: Commit and push source changes

```bash
cd ~/.hermes/hermes-agent
# Create a branch for your modifications (keep main clean for upstream tracking)
git checkout -b <branch-name>

# Stage and commit modified source files
git add agent/agent_init.py gateway/platforms/weixin.py gateway/platforms/qqbot/adapter.py
git commit -m "custom: <description of patches>"
git push origin <branch-name>
```

## Step 4: Add plugins and skills

Custom plugins live at `~/.hermes/plugins/`, skills at `~/.hermes/skills/`.
Copy them into the fork under dedicated directories:

```bash
cd ~/.hermes/hermes-agent

# Plugins
mkdir -p user-plugins
cp -r ~/.hermes/plugins/<plugin-name> user-plugins/<plugin-name>/

# Skills (exclude caches)
cp -r ~/.hermes/skills user-skills/
rm -rf user-skills/.hub user-skills/.curator_backups
find user-skills -name "__pycache__" -type d -exec rm -rf {} +
find user-skills -name "*.pyc" -delete

git add user-plugins/ user-skills/
git commit -m "feat: add user plugins and skills"
git push origin <branch-name>
```

## Step 5: Create SETUP.md

Add a restore guide at repo root. See `references/setup-template.md` for a
ready-to-use template.

## Restore on new machine

```bash
# Install Hermes first, then:
git clone https://github.com/<user>/hermes-agent.git ~/.hermes/hermes-agent
cd ~/.hermes/hermes-agent
git checkout <branch-name>

# Sync all five runtime directories (see incremental sync for rationale):
cd ~/.hermes
mkdir -p plugins
cp -r hermes-agent/user-plugins/* plugins/

rm -rf skills
cp -r hermes-agent/user-skills skills

mkdir -p hooks
cp -r hermes-agent/user-config/hooks/* hooks/

mkdir -p scripts
cp hermes-agent/user-config/scripts/* scripts/

mkdir -p memories
cp hermes-agent/user-config/memories/* memories/

cp hermes-agent/user-config/config.yaml config.yaml
cp hermes-agent/user-config/cron/jobs.json cron/

# Worker profile (if exists)
rm -rf profiles/worker && mkdir -p profiles/worker
cp hermes-agent/user-config/profiles/worker/config.yaml profiles/worker/
cp -r hermes-agent/user-config/profiles/worker/skills profiles/worker/skills

# Manually restore .env (NEVER in git)
```

## Updating from upstream

Full end-to-end workflow — fetch upstream, merge into main and custom branch, rebuild, restart:

```bash
cd ~/AppData/Local/hermes/hermes-agent  # Windows (macOS: ~/.hermes/hermes-agent)

# 1. Ensure clean state on custom branch
git checkout chester && git status    # must be clean

# 2. Fetch upstream and update main
git checkout main
git fetch upstream
git merge upstream/main
git push origin main                  # keep fork's main in sync

# 3. Merge into custom branch (or rebase)
git checkout chester
git merge main -m "merge upstream/main into chester"
# Resolve conflicts if any, then:
git push origin chester

# 4. Verify custom patches survived the merge
#    The user WILL ask "are you sure this merge is safe?" — have evidence.
#    Check at minimum: weixin.py, qqbot adapter, agent_init.py, cli.py.
echo "=== weixin.py custom lines ===" && grep -c "ITEM_NOTE\|ITEM_RECORD\|ITEM_APPMSG" gateway/platforms/weixin.py
echo "=== user files untouched? ===" && git diff HEAD~1..HEAD --stat -- user-skills/ user-plugins/ user-config/
# Should show: grep ≥ 9 hits (3 consts + 6 usages), diff empty for user-* dirs.

# 5. Rebuild venv (upstream may have changed pyproject.toml)
uv sync --directory .

# 6. Restart gateway
hermes gateway stop
hermes gateway start
# Verify:
sleep 3 && curl -s http://127.0.0.1:8642/health
# {"status":"ok","version":"0.x.0"}
```

If you prefer rebase over merge:
```bash
git checkout chester
git rebase main
git push origin chester --force-with-lease
```

Note: `git push origin main` on step 2 is important — if `main` diverges
between fork and local, future fetches may produce confusing diffs.

## Incremental sync (after each session with changes)

Hermes has **five** directory pairs where runtime can diverge from git-tracked.
`skill_manage`/curator edits land in the runtime directory; `git status` only
checks the git-tracked copy → silently reports "clean" even when there are
uncommitted changes. Always run a full cross-directory diff before concluding
"nothing to commit":

```bash
cd ~/AppData/Local/hermes  # Windows (macOS: ~/.hermes)

for pair in \
  "skills:user-skills" \
  "plugins:user-plugins" \
  "hooks:user-config/hooks" \
  "scripts:user-config/scripts" \
  "memories:user-config/memories"
do
  runtime="${pair%%:*}"
  gt="${pair##*:}"
  result=$(diff -rq --exclude=__pycache__ "$runtime/" "hermes-agent/$gt/" 2>&1 \
    | grep -v ".lock\|.hub\|.bundled_manifest\|.curator\|.usage.json" | head -1)
  if [ -n "$result" ]; then
    echo "❌ $runtime: $result"
  else
    echo "✓ $runtime"
  fi
done
```

For directories with diffs, sync with `cp -r` (no rsync on Windows Git Bash):

```bash
# For modified dirs: replace entirely
rm -rf hermes-agent/user-skills/<name>
cp -r skills/<name> hermes-agent/user-skills/<name>

# For new dirs: copy in
cp -r skills/<name> hermes-agent/user-skills/<name>
```

Then commit + push (via proxy if GitHub blocked):
```bash
cd hermes-agent
git add -A
git commit -m "sync: <what changed>"
git config http.proxy http://127.0.0.1:7897   # if needed
git push origin chester
```

**Garbage exclusion**: lock files (`.lock`), skill/plugin caches (`.hub`,
`.bundled_manifest`, `.curator_backups`, `.usage.json`), and Python bytecode
(`__pycache__`) are runtime artifacts — never copy them to git.
After `cp -r memories/ hermes-agent/user-config/memories/`, strip locks:
`rm -f hermes-agent/user-config/memories/*.lock`.

**Note on `skills/computer-use`**: this is an upstream bundled skill that may
appear in runtime `skills/` but not in `user-skills/`. It does NOT need syncing.

## Pitfalls

- **Windows path differs**: On Windows, Hermes data lives at
  `~/AppData/Local/hermes/`, NOT `~/.hermes/`. The repo is at
  `~/AppData/Local/hermes/hermes-agent/`. Always verify the path before
  assuming `~/.hermes/hermes-agent`.
- **Workspace clone ≠ runtime install**: A separate clone at `/d/workspace/hermes-agent`
  (tracking upstream for development) is NOT the same as the runtime install at
  `~/AppData/Local/hermes/hermes-agent/` (the fork with user patches). When the
  user asks to "commit hermes changes", the runtime install is the target — not
  any workspace clones.
- **5-pair diff "Only in" entries are new items, not noise.** `diff -rq` output
  like `Only in plugins/: horizon` means the entire directory exists in runtime
  but not in git → it's a new plugin/skill/script that must be synced with
  `cp -r`. Similarly, `Only in hermes-agent/user-plugins/: X` means an item was
  removed from runtime but still in git — consider `git rm`. Commit ALL diffs
  together, don't cherry-pick individual changed files. Cherry-picking
  (e.g. committing only agentmemory while horizon is also new) means the user
  has to ask "还有什么遗漏" on the next turn.
- **`user-config/config.yaml` is tracked but outside 5-pair scope.** The 5-pair
  diff only covers skills/plugins/hooks/scripts/memories. `user-config/config.yaml`
  (template without API keys) and `user-config/cron/jobs.json` are committed
  directly in the repo root's `user-config/` directory. After syncing all 5
  pairs, always run `git status` in the repo to catch modified config or other
  untracked items.
- **Runtime skills/plugins/hooks/scripts/memories all diverge from git-tracked**:
  Hermes updates all five at runtime. These changes do NOT auto-propagate to
  the git-tracked directories in `hermes-agent/`. After any session with
  `skill_manage`, curator edits, or runtime file modifications, run the full
  five-pair diff above before declaring "nothing to commit". A bare `git status`
  in the repo is insufficient — it only sees `user-*` directories.
- **Source patches are tied to base commit.** Always record `git rev-parse HEAD`
  before major upstream merges. If patches are massive (thousands of lines),
  prefer the fork approach over `git diff > patches.diff` — it survives rebases
  better.
- **`.hub/` cache is huge (~24MB).** Always exclude it before committing skills.
  It gets regenerated by `hermes skills check` on the target machine.
- **agentmemory plugin has binary dep (Docker).** The plugin code syncs fine
  via git, but the agentmemory server (`docker run rohitg00/agentmemory`)
  must be running on the target machine.
- **WeChat/QQ platform patches are the most fragile layer.** These adapters
  change frequently upstream. After `git rebase main`, always check
  `gateway/platforms/weixin.py` and `gateway/platforms/qqbot/adapter.py`
  for merge artifacts.
- **git merge ≠ uv sync.** After merging upstream/main into your branch,
  `pyproject.toml` and `uv.lock` are updated but the venv still has the old
  packages. New dependencies added upstream (e.g. `concurrent-log-handler`
  added 2026-06-17 as Windows-only dep) will cause `ImportError` on next
  `hermes gateway run`. Always run after merge:
  ```bash
  # If venv exists under the repo
  uv sync --directory ~/.hermes/hermes-agent
  # Or with pip if using system Python
  ~/.hermes/hermes-agent/venv/Scripts/pip install -e ~/.hermes/hermes-agent
  ```
  Verify: `hermes --version` should not crash.

- **Git committer identity.** On Windows, git may auto-generate committer
  from AD username. Set explicitly:
  ```bash
  git config user.name "Your Name"
  git config user.email "your@email.com"
  ```
- **Shallow clone breaks `git merge`**: The Hermes installer may create a shallow
  clone (`.git/shallow` present). Shallow grafts mark commits as root nodes,
  cutting the ancestry chain. Symptoms:
  - `git merge-base chester main` returns empty (no common ancestor)
  - `git merge main` fails with \"refusing to merge unrelated histories\"
  - `--allow-unrelated-histories` creates hundreds of false conflicts
  
  Fix before merging upstream:
  ```bash
  # Verify shallow state
  cat .git/shallow 2>/dev/null && echo "SHALLOW — needs fix" || echo "OK"
  
  # Unshallow
  git fetch --unshallow origin
  
  # Verify fix
  git merge-base chester main   # should return a commit hash
  ```
  
  After unshallowing, a normal `git merge main` (or `git rebase main`) works
  without `--allow-unrelated-histories`.
- **GitHub blocked by firewall**: Direct git operations to github.com may fail
  with `Could not connect to server`. Configure proxy:
  ```bash
  git config http.proxy http://127.0.0.1:7897
  ```
