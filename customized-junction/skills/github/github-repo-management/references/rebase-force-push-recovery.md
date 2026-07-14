# Rebase + Force Push Recovery

Recovery pattern for when remote history is force-pushed and local `git pull --rebase` silently drops tracked files.

## Problem

Remote was force-pushed — entire history replaced with a single `init` commit that lacks `.claude/`, `skills/`, etc. Running `git pull --rebase` rebases local commits onto this new bare base. During rebase, files tracked in old history but absent from new base become **untracked** (still on disk but git no longer tracks them). Some files may even be deleted by the rebase process.

## Recovery Steps

### 1. Find the last good commit

```
git reflog -10
```

Look for the commit right before the rebase. The reflog preserves all HEAD movements regardless of branch resets.

### 2. Reset to pre-rebase state

```
git reset --hard <sha>
```

### 3. If master is protected (can't force push)

Push to a new branch and create a Merge Request:

```
git checkout -b restore-<name>
git push origin restore-<name>
```

Then create MR via GitLab/GitHub UI to merge into master. This bypasses the force-push restriction on protected branches.

## Prevention

- Before `git pull --rebase`, check `git fetch && git log origin/master --oneline -3` to spot force pushes
- If remote history looks truncated (single commit where there used to be many), **abort** — ask what happened before rebasing
- Consider `git pull --ff-only` as default to reject non-fast-forward pulls entirely
