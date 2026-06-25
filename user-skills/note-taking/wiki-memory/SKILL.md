---
name: wiki-memory
description: Load memory from LLM Wiki before responding. Write new memory to wiki files + update built-in index.
version: 1.2.0
author: Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [memory, wiki, obsidian, indexing]
    related_skills: [obsidian]
---

# Wiki Memory

Memory lives in a standalone `memory(记忆)/` directory. Built-in memory holds a compact index (pointers). Full content lives in `D:\obsidian\2026\memory(记忆)/`. Every response must load relevant entries before acting.

## Memory Location

```
D:\obsidian\2026\memory(记忆)/
├── index.md                  # memory-specific index
├── driving(行为)/
│   ├── behavior.md           # behavioral rules
│   ├── corrections.md        # user corrections
│   └── preferences.md        # user preferences
└── technical(技术)/
    ├── environment.md        # OS, paths, tools
    ├── hermes-internals.md   # Hermes config, gateway quirks
    └── solutions.md          # patches, workarounds
```

Separate from `D:\obsidian\2026\wiki/` which is the general knowledge base.

## Memory Loading (MANDATORY — before any tool call)

Before responding to ANY user message:

1. Scan the MEMORY INDEX block in your system prompt
2. For each entry whose summary relates to the current task, load the full file:
   ```
   read_file("D:/obsidian/2026/memory(记忆)/<path>.md")
   ```
3. Apply loaded memory to your response

If uncertain whether an entry applies, LOAD IT. False positive is cheaper than missed memory.

## Memory Writing (when saving new knowledge)

When you need to save durable knowledge:

1. **Choose category**: `driving(行为)/` for behavioral rules/preferences/corrections, `technical(技术)/` for environment facts/solutions/internals
2. **Write full content** to the appropriate file:
   - If file exists: `read_file` first, then `write_file` with appended content
   - If new file: `write_file` to `D:/obsidian/2026/memory(记忆)/<category>/<name>.md`
3. **Update index**: append a summary line to the MEMORY INDEX in built-in memory via `memory(action='add', target='memory', content='...')`
4. **Update memory index**: append the entry to `D:/obsidian/2026/memory(记忆)/index.md`

## Index Format

Each memory index line:
```
→ <one-line summary> | <category>/<filename>
```

Keep summaries telegraphic. Index stays in built-in memory until it hits the 2,200 char limit.

## Category Guidelines

| Category | What goes here |
|----------|---------------|
| `driving(行为)/behavior` | Rules that change how Hermes acts |
| `driving(行为)/corrections` | User corrections (don't do X, never Y) |
| `driving(行为)/preferences` | User identity, style, tool choices |
| `technical(技术)/hermes-internals` | Hermes config, gateway quirks, known bugs |
| `technical(技术)/environment` | OS, Python, paths, external tools |
| `technical(技术)/solutions` | Patches, workarounds, migration procedures |

New categories can be created at any time — the index is self-describing.

## Explanation Style (when presenting wiki/technical content)

When the user asks you to explain a wiki page, concept, or technical document:

- **Default to plain conversational Chinese.** Do NOT lead with structured formal exposition (tables, bullet lists, code blocks, "核心问题/设计决策" headers). Start with a one-sentence summary in spoken Chinese, then flesh out with short paragraphs and everyday analogies.
- **"说人话" is the baseline.** If the user says it, you already failed the first response. The second try should be dramatically more casual — short sentences, 口语, analogies (预制菜, 壳), no markdown tables, no formal section headers.
- **Save the structure for follow-ups.** If the user then asks a deeper technical question, you can reintroduce structure. But the default opening explanation should sound like you're talking to a colleague over coffee, not presenting slides.

## Pitfalls

1. **Forgetting to load**: the MEMORY INDEX is short and easily overlooked. Check it BEFORE every response.
2. **Loading too late**: load memory BEFORE making tool calls, not after.
3. **Writing only pointer**: when saving new memory, write FULL content to memory file first, THEN update pointer in index.
4. **Index mismatch**: memory index.md and built-in memory index must stay in sync.
5. **CLI sessions do NOT auto-load this skill**: `WEIXIN_AUTO_SKILL` and `QQBOT_AUTO_SKILL` inject wiki-memory for gateway platforms only. CLI sessions must explicitly load it via `hermes -s wiki-memory`.
6. **No programmatic auto-load**: Hermes has NO code that parses MEMORY.md index lines and auto-reads memory files. Entire pipeline is LLM-driven.
7. **"图谱" = textual explanation, not visual diagram or code simulation.** When the user asks for a "运行机制图谱" or "机制图" for a wiki concept, they want a structured plain-language writeup to drop into the wiki draft — NOT an SVG diagram, NOT an architecture-diagram HTML file, NOT a live code simulation. Deliver text. Use conversational Chinese with short paragraphs and analogies. ASCII art for flow is fine; external tools (browser, terminal simulations, architecture-diagram skill) are overkill and waste turns.

## Verification

- [ ] Before responding, scanned MEMORY INDEX and loaded relevant entries
- [ ] New memories written to memory file with full content
- [ ] Built-in memory index updated with new pointer
- [ ] Memory index.md updated with new entry

## References

- `references/migration-guide.md` — migration from dense built-in memory to Wiki-indexed memory
- `references/hermes-memory-architecture.md` — source-level trace of the full memory pipeline
- `references/hermes-context-compression.md` — context compression system and memory authority
