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

## Compaction Workflow

When memory usage reaches **75%+** or an add is rejected, follow this order:

### Phase 1: Compress All Entries In-Place (Always First)

Before deciding what to archive, compress EVERY entry to telegraphic style.
Most entries can be halved in size without losing information:

```
memory(action='replace', target='memory', old_text='<current full entry>', content='<telegraphic version>')
```

Also merge overlapping entries (e.g. two entries about the same system) into one.

After this phase, usage should drop significantly — often from 90%+ to 60-65%.
If that frees enough space, skip to Phase 4 (log). Only proceed to Phase 2 if still tight.

### Phase 2: Identify Stale Entries

Now with compressed entries, flag only those that are genuinely stale:
- Project-specific facts from completed work
- One-off configs no longer relevant
- Oldest entries that haven't been referenced in sessions

Do NOT archive entries that are still actively used — compression alone should handle those.

### Phase 3: Archive and Remove Stale Entries

For each stale entry:

1. Save to Obsidian: `D:\obsidian\2026\hermes-memory\{YYYY-MM-DD}.md`
2. Remove from Hermes: `memory(action='remove', target='memory', old_text='...')`

Archive format:
```markdown
# Hermes Memory Archive — {YYYY-MM-DD}

Archived from Hermes memory store to free capacity.

| # | Original | Compressed |
|---|----------|------------|
| 1 | entry text | telegraphic version |
```

### Phase 4: Document the Pass (Always)

EVERY compact pass MUST leave a record, even if nothing was archived (pure compression):

Create or append to `D:\obsidian\2026\hermes-memory\{YYYY-MM-DD}.md` with:

```markdown
# Hermes Memory Compact — {YYYY-MM-DD}

## Stats
| Metric | Before | After |
|---|---|---|
| Entries | N | N |
| Usage | X% | Y% |
| Freed | — | Z chars |

## Operations
| Action | Entry | Notes |
|---|---|---|
| Compress | <name> | <what changed> |
| Merge | <name1>+<name2> | <reason> |
| Archive | <name> | stale, moved to Obsidian |
```

If this was triggered by a rejected add, retry the add after logging.

## Pitfalls

### Not loading the skill before acting

Agent must call `skill_view('compact-memory')` BEFORE executing any compaction. Acting from memory alone leads to skipped phases and wrong log formats. The user expects the Obsidian log to match the prescribed Phase 4 table structure exactly — no extra prose, no missing columns.

### Skipping the Obsidian log

User expects every compact pass to leave a trace in Obsidian, even when no entries were archived. A pure-compression pass still creates `hermes-memory/{date}.md` documenting the before/after stats and operations. Missing this log makes the pass invisible to the user — they'll ask "where did the memory go?"

### Premature archiving

Don't archive entries that are still actively needed just because the limit is tight. Compress first, merge overlapping entries, THEN check if archiving is still necessary. In the common case compression alone is enough — e.g. 96%→59% saves 38% without losing any information.

## Design Rationale

Why not modify `memory_tool.py` to remove the 2,200 char limit or proxy to Obsidian? See `references/memory-capacity-approaches.md` for the trade-off analysis. The short answer: zero-source-modification beats perpetual upgrade conflicts; 2,200 chars is enough for active working memory when stale entries are regularly pruned.

## Obsidian Vault Path

Archive root: `D:\obsidian\2026\hermes-memory\`
Create the directory if it doesn't exist.
