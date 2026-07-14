# Path Migration Guide

This directory contains hardcoded paths specific to this machine. When migrating to a new machine, use the migration tools to update all paths.

## Files

- `path-map.yaml` — Path mapping configuration (tracked)
- `migrate-paths.py` — Migration script (tracked)
- `PATH_MIGRATION.md` — This file

## Current Machine Setup

On this machine, `path-map.yaml` contains only `key` fields (current paths). The `value` fields are empty.

## Migration Steps

### On the new machine:

1. **Clone/pull the repo**

2. **Edit `path-map.yaml`**
   - Fill in the `value` field for each mapping with the new machine's path
   - Example:
     ```yaml
     - key: "C:\\Users\\chester.chen\\AppData\\Local\\hermes"
       value: "C:\\Users\\newuser\\AppData\\Local\\hermes"
     ```

3. **Run the migration script**
   ```bash
   python customized-junction/migrate-paths.py
   ```

4. **Verify the changes**
   - The script reports which files were modified
   - Check a few files to ensure paths were replaced correctly

5. **Commit the changes**
   ```bash
   git add -A
   git commit -m "chore: update paths for new machine"
   ```

## How It Works

The script:
- Reads `path-map.yaml`
- For each mapping where both `key` and `value` are non-empty
- Replaces all occurrences of `key` with `value` in tracked files under `customized-junction/`
- Skips binary files and the migration files themselves

## Affected Files

The following types of files contain hardcoded paths:

- `skills/*/SKILL.md` — Skill documentation with path examples
- `skills/*/references/*.md` — Reference docs with path examples
- `scripts/agentmemory-watchdog.py` — NPM_PREFIX default path
- `memories/MEMORY.md` — Runtime memory with repo path (ignored, not affected)
- `memories/USER.md` — User preferences with path examples (ignored, not affected)

## Notes

- The migration is **idempotent** — running it multiple times with the same mappings has no additional effect
- After migration, the `key` patterns no longer exist in the files, so re-running won't match anything
- To migrate back, add reverse mappings to `path-map.yaml`
