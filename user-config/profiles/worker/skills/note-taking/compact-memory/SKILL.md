---
name: compact-memory
description: "Use when writing to memory or when memory is near/at capacity — enforce telegraphic style, auto-archive stale entries to Obsidian before reclaiming space."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [memory, maintenance, obsidian, archiving]
---

# Compact Memory Management

## Telegraphic Style (Mandatory)

Every memory entry MUST be telegraphic. Drop articles, copulas, and filler. Use abbreviations.

| Bad (full sentence) | Good (telegraphic) |
|---|---|
| The Obsidian vault is located at D:\obsidian\2026 | Obsidian vault: D:\obsidian\2026 |
| WeChat uses pairing mode for DM authorization | WeChat DM: pairing mode |
| Reasonix is installed at ~/AppData/Roaming/npm/reasonix | Reasonix at ~/AppData/Roaming/npm/reasonix |
| It supports ACP mode for delegation | ACP delegation via delegate_task(...) |

Rules:
- No "is", "are", "was", "The", "A", "An" unless essential for meaning
- Colons instead of "is located at" / "uses"
- Semicolons to chain related facts
- Abbreviations: msgs, dir, cfg, env, pkg, w/ (with), b/c (because)

## Capacity Monitoring

When memory usage reaches **75%+** or an add is rejected:

### Step 1: Identify archivable entries

Read current entries. Flag entries that are:
- Oldest (least recently relevant)
- Longest (highest char count, likely uncompressed)
- Stale (project-specific facts from completed work, one-off configs)

### Step 2: Archive to Obsidian

Save flagged entries to Obsidian archive:
```
D:\obsidian\2026\hermes-memory\{YYYY-MM-DD}.md
```

Format:
```markdown
# Hermes Memory Archive — {YYYY-MM-DD}

Archived from Hermes memory store to free capacity.

| # | Content |
|---|---------|
| 1 | entry text |
| 2 | entry text |
```

### Step 3: Remove from Hermes memory

Use `memory(action='remove', target='memory', old_text='...')` for each archived entry.

### Step 4: Add new entry

Now retry the add that was blocked.

## Pre-Archive Compression (First Resort)

Before archiving, ALWAYS try compressing existing entries first — many entries can be halved in size:

```
memory(action='replace', target='memory', old_text='...', content='telegraphic version')
```

Only archive entries that are genuinely stale or cannot be compressed further.

## Obsidian Vault Path

Archive root: `D:\obsidian\2026\hermes-memory\`
Create the directory if it doesn't exist.
