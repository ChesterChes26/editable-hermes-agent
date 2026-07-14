# Subagent Prompt Template for Batch Wiki Draft Creation

When dispatching subagents to create wiki drafts in parallel, use this structure.

## Per-Subagent Context Template

```
You are creating draft wiki pages for the Hermes Agent wiki.
Output directory: D:/obsidian/2026/wiki/_drafts/

TEMPLATE: Read D:/obsidian/2026/wiki/_drafts/_TEMPLATE.md first.
SOURCE CODE BASE: C:/Users/chester.chen/AppData/Local/hermes/hermes-agent/

Topics to cover:

### Topic N: <Name>
- Slug: hermes-<slug>
- Source: <relative path>
- What it does: <one paragraph explaining the mechanism>
- Why important: <one sentence on why this matters>

[Repeat for each topic]

WIKI CONVENTIONS:
- Title must be a colloquial Chinese question (口语化中文问句)
- Use wikilinks like [[concepts(概念)/hermes-xxx|page name]]
- Tags: at least [agent-arch, design-decision]
- No value judgments (简单, 高级, 笨拙) — describe differences objectively
- Source code paths use forward slashes
- If source doesn't reveal something, mark with <!-- TODO -->

For each topic, read the actual source code to understand the mechanism, then write the draft.
```

## Goal Template

```
Create N draft wiki concept pages (Tier X topics A-B) in D:/obsidian/2026/wiki/_drafts/.
Read the template at D:/obsidian/2026/wiki/_drafts/_TEMPLATE.md first and follow it exactly.
```

## Toolsets

Use `["terminal", "file"]` — subagents need to read source files and write drafts. They don't need web access or browser tools.

## Tier-Specific Notes

- **Tier 1**: Full 200-400 lines. Deep source analysis expected. Critical mechanisms.
- **Tier 2**: 150-300 lines. Independent subsystems.
- **Tier 3**: 100-200 lines. Auxiliary modules. Tell subagents "shorter drafts OK."
