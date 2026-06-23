# LLM Wiki Integration Reference

## Wiki Location

```
D:\obsidian\2026\wiki\
├── SCHEMA.md              # tag taxonomy, conventions, page thresholds
├── index.md               # content catalog (alphabetical by type)
├── log.md                 # append-only chronological log
├── entities(实体)/         # one page per entity (tools, models, services)
├── concepts(概念)/         # one page per concept (patterns, decisions)
├── comparisons(对比)/      # side-by-side analyses
├── queries(问答)/          # valuable Q&A outcomes
└── raw(源材料)/            # external source material (immutable)
    ├── articles(文章)/
    ├── papers(论文)/
    ├── transcripts(记录)/
    └── assets(素材)/
```

Memory is stored separately at `D:\obsidian\2026\memory(记忆)/` (independent of wiki).

## Frontmatter Template

```yaml
---
title: Page Title
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: entity | concept | comparison | query
tags: [from SCHEMA.md taxonomy]
sources: [raw(源材料)/xxx.md]
confidence: high | medium | low
---
```

## Numbered-Selection to Wiki Page Workflow

When the user replies with numbers (e.g. "1,3"):

1. Parse: "1,3" → items 1 and 3. "全部" → all items.
2. For 2+ items, synthesize into coherent wiki pages (don't create 1 page per number).
3. Determine the best type for each page:
   - entity → `entities(实体)/`
   - concept → `concepts(概念)/`
   - comparison → `comparisons(对比)/`
   - query → `queries(问答)/`
4. Write the page with full frontmatter + at least 2 `[[wikilinks]]`.
5. Update `wiki/index.md` (add entry + bump total count).
6. Append to `wiki/log.md` with files created/updated.
7. Confirm to user: what was saved and where.

## Tag Taxonomy (Domain: AI Agent Architecture)

- Architecture: agent-arch, tool-design, provider, gateway, session
- Integration: wechat, qqbot, obsidian, mcp, api
- Knowledge: wiki, knowledge-base, inbox, archival, memory
- Patterns: design-decision, tradeoff, workflow, pitfall
- Meta: schema, index, reference, deprecated
