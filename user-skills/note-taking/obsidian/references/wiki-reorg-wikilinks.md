# Vault Reorganization: Moving Files + Updating Wikilinks

When bulk-moving files within the vault and updating cross-references, use execute_code with Python scripts. Do NOT use shell find/sed — the wikilink syntax has edge cases that regex in sed is too fragile for.

## Three Wikilink Patterns to Handle

When updating `[[old_path]]` → `[[new_path]]`:

### 1. Bare links: `[[path]]`
```python
re.compile(rf'\[\[{re.escape(old_path)}\]\]')
```

### 2. Normal pipe: `[[path|display]]`
```python
re.compile(rf'\[\[{re.escape(old_path)}\|([^\]]+)\]\]')
```

### 3. Escaped pipe in markdown tables: `[[path\|display]]`
This happens when wikilinks appear inside markdown table cells — the pipe between path and display text must be escaped with backslash to not break the table layout.

```python
re.compile(rf'\[\[{re.escape(old_path)}\\\|([^\]]+)\]\]')
```

**Pitfall**: If you only handle patterns 1 and 2, you'll miss all wikilinks inside markdown tables. Always run a scan pass after updates to catch remaining old links.

## Two-Pass Strategy

**Pass 1**: Handle all three `[[...]]` wikilink patterns. Move files + update links in one script.

**Pass 2**: Scan for remaining old path references. Common sources of missed links:
- Escaped-pipe wikilinks (pattern 3 above)
- Bare paths in YAML frontmatter `wikilinks:` fields (not in `[[...]]` brackets)
- Paths inside code blocks (usually false positives, can be left)

## Bare YAML Frontmatter Paths

Some Obsidian notes use custom YAML frontmatter fields like:
```yaml
wikilinks:
  - concepts(概念)/some-page
  - concepts(概念)/another-page
```

These are plain text (not `[[...]]`), so wikilink regex won't match them. Use simple string replacement.

## Verification

After all passes, run a final scan:
```python
for md_file in vault.rglob("*.md"):
    for old_path in old_paths:
        if old_path in content:
            print(f"Remaining: {file} → {old_path}")
```

If any remain, inspect them — they might be in code blocks (leave) or missed formats (fix).
