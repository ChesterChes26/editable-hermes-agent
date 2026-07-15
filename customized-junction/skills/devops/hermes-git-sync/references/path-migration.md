# Path Migration Guide

Skills contain hardcoded paths specific to the machine where they were created. When migrating to a new machine, use the migration tools to update all paths.

## Files

```
customized-junction/
  path-map.yaml          # Path mapping configuration (tracked)
  migrate-paths.py       # Migration script (tracked)
```

## How It Works

The script:
- Reads `path-map.yaml`
- For each mapping where both `key` and `value` are non-empty
- Replaces all occurrences of `key` with `value` in tracked files under `customized-junction/`
- Skips binary files and the migration files themselves
- Is idempotent — running multiple times with same mappings has no additional effect

## Migration Steps

### On the new machine:

1. **Clone/pull the repo**

2. **Edit `customized-junction/path-map.yaml`**
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

## Affected Files

The following types of files contain hardcoded paths:

- `skills/*/SKILL.md` — Skill documentation with path examples
- `skills/*/references/*.md` — Reference docs with path examples
- `scripts/agentmemory-watchdog.py` — NPM_PREFIX default path
- `memories/MEMORY.md` — Runtime memory with repo path (ignored, not affected)
- `memories/USER.md` — User preferences with path examples (ignored, not affected)

## Common Path Patterns

Typical mappings needed:

```yaml
mappings:
  # Hermes runtime
  - key: "C:\\Users\\olduser\\AppData\\Local\\hermes"
    value: "C:\\Users\\newuser\\AppData\\Local\\hermes"
  
  - key: "C:/Users/olduser/AppData/Local/hermes"
    value: "C:/Users/newuser/AppData/Local/hermes"
  
  # MSYS2 style paths
  - key: "/c/Users/olduser/AppData/Local/hermes"
    value: "/c/Users/newuser/AppData/Local/hermes"
  
  # Obsidian vault (if applicable)
  - key: "D:\\obsidian\\2026"
    value: "E:\\obsidian\\2026"
  
  # Workspace
  - key: "D:\\workspace"
    value: "C:\\workspace"
```

## Notes

- After migration, the `key` patterns no longer exist in the files, so re-running won't match anything
- To migrate back, add reverse mappings to `path-map.yaml`
- The script covers both tracked and ignored files (`.hub/`, `memories/MEMORY.md`, etc.) — this is correct behavior for full migration
