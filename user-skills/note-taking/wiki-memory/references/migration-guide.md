# Memory Migration Guide

How to migrate from dense built-in memory to Wiki-indexed memory.

## Pattern

```
Old: 7 entries, 1,832 chars (83% full)
New: 1 index entry, 496 chars (22% full)
Saving: 73% compression
```

## Steps

### 1. Create wiki directory structure

```
D:\\obsidian\\2026\\memory\\
├── index.md                 # Wiki-readable index
├── driving/
│   ├── behavior.md
│   ├── corrections.md
│   └── preferences.md
└── technical/
    ├── hermes-internals.md
    ├── environment.md
    └── solutions.md
```

### 2. Extract each memory entry into a wiki file

For each built-in memory entry:
- Determine category (driving vs technical)
- Write full markdown content to the wiki file
- If file exists, read it first, then append new section

### 3. Build the index

After all files are written, construct the compact MEMORY INDEX:

```
MEMORY INDEX — load via read_file(D:/obsidian/2026/memory/<path>.md):
→ pause before risky ops | driving/behavior
→ don't echo/附和 | driving/corrections
→ user prefs: CN, WeChat/QQ, concise | driving/preferences
→ hermes internals: vision→dashscope, /new broken | technical/hermes-internals
→ env: deepseek-v4-pro, Win10, Obsidian, reasonix | technical/environment
→ patches: WeChat ITEM_APPMSG, migration .zip | technical/solutions
```

Format: `→ <one-line summary> | <category>/<filename>`

### 4. Replace built-in memory

Remove all old entries via `memory(action='remove')` one by one, then add the single index entry via `memory(action='add')`.

### 5. Create the wiki-memory skill

The skill contains:
- Mandatory loading rules (before any tool call, scan index, load relevant files)
- Writing rules (full content to wiki, pointer to index)
- Category guidelines

### 6. Configure auto-loading

For gateway platforms (WeChat, QQBot), add to `.env`:
```
WEIXIN_AUTO_SKILL=obsidian-sync,wiki-memory
QQBOT_AUTO_SKILL=obsidian-sync,wiki-memory
```

For CLI, use `hermes -s wiki-memory` or `hermes --skills wiki-memory`.

## Verification

- [ ] Built-in memory shows only the index (1 entry, <500 chars)
- [ ] All wiki memory files exist with full content
- [ ] `skill_view("wiki-memory")` returns the skill
- [ ] Gateway platforms inject both obsidian-sync and wiki-memory
