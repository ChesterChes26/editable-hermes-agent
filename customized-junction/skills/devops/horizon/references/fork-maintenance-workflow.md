# Horizon Fork Maintenance Workflow

**Fork:** ChesterChes26/Horizon
**Upstream:** Thysrael/Horizon
**Local clone:** D:/workspace/AI-research/Horizon
**Git proxy:** http://127.0.0.1:7897 (required — direct GitHub access triggers firewall)

## Remote Setup

```bash
cd D:/workspace/AI-research/Horizon
git remote add fork https://github.com/ChesterChes26/Horizon.git
# origin already points to Thysrael/Horizon
```

## Workflow: Rebase + Push Feature Branch

```bash
# 0. Check current state
git status --short                 # any uncommitted changes?
git remote -v                      # verify remotes

# 1. Fetch upstream
git fetch origin main

# 2. Check what's new upstream
git log --oneline main..origin/main

# 3. Stash local changes, rebase, pop
git stash push -m "local changes"
git rebase origin/main
git stash pop

# 4. Verify no conflicts — diff file sets should be disjoint
git diff --stat origin/main~N..origin/main   # upstream changes
git diff --stat origin/main..                # your changes

# 5. Create feature branch (NEVER push to main)
git checkout -b <branch-name>
git add <files>
git commit -m "..."

# 6. Push via proxy
git -c http.proxy=http://127.0.0.1:7897 push fork <branch-name>
```

## Key Rules

- **Never push to main** — always use feature branches (e.g., `chester-edit`)
- **git via proxy 127.0.0.1:7897** — never use curl/browser for GitHub (triggers firewall)
- **Verify file overlap before rebase** — upstream and local diffs should touch disjoint files
- **Untracked runtime artifacts** (e.g., `data/pipeline_output.txt`) stay out of commits
