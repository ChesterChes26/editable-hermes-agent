# Update Check Cache Mechanism

## Source

`hermes_cli/banner.py` — `check_for_updates()` at line 266.

## How it works

`hermes --version` calls `check_for_updates()` which runs `git rev-list --count HEAD..origin/main` to count commits behind. Result is cached to avoid repeated `git fetch` on every invocation.

## Cache file

- **Path**: `~/.hermes/.update_check` (or `%LOCALAPPDATA%\hermes\.update_check` on Windows)
- **Format**: JSON
  ```json
  {"ts": 1781681029.666, "behind": 68, "rev": null, "ver": "0.16.0"}
  ```

## Cache validity rules (line 306-316)

Cache is valid (reused) when ALL three conditions hold:
1. Age < `_UPDATE_CHECK_CACHE_SECONDS` (6 hours)
2. `cached.rev == embedded_rev` (both None for non-nix installs)
3. `cached.ver == VERSION` (e.g., "0.16.0")

If any condition fails, a fresh check runs.

## Pitfall: stale after git pull

After `git pull` updates HEAD but the version string (`VERSION`) doesn't change (patch-level update, not a version bump), the cache remains valid and continues reporting the old "behind" count — for up to 6 hours.

Example: pulled 76 commits, HEAD moved from `2dbc3bd` to `f9c8d95e`, but cache still says "68 commits behind" because `ver` is still `"0.16.0"`.

## Fix

Delete the cache file to force a fresh check:

```bash
rm ~/AppData/Local/hermes/.update_check   # Windows
rm ~/.hermes/.update_check                # macOS/Linux
```

Then `hermes --version` will re-run `git fetch` + `git rev-list --count` and report the correct count.

## Two-step check paths (line 266-320)

1. **Nix builds** (`HERMES_REVISION` env set): compare against upstream via `git ls-remote`
2. **Local git checkout**: `git fetch origin` then `git rev-list --count HEAD..origin/main`
3. **Docker**: short-circuits to `None` (no `.git` directory)
4. **PyPI fallback**: `check_via_pypi()` compares `VERSION` against PyPI latest — returns 1 (behind) or 0 (current), not a count
