---
name: hermes-wiki-concept-page
description: Create Hermes wiki concept pages from source code — read template, deep-read source, write drafts to D:/obsidian/2026/wiki/_drafts/.
version: 1.0.0
tags: [wiki, obsidian, hermes-internals, concept-page]
related_skills: [obsidian, wiki-line-reference-audit]
---

# Hermes Wiki Concept Page

Create draft concept pages for the Hermes wiki. Each page explains one Hermes subsystem at source-code level, following a strict template.

## When to Use

- User asks to "create a wiki page for X"
- User asks to "write a concept page for the Hermes wiki"
- User mentions `D:/obsidian/2026/wiki/_drafts/` or the `_TEMPLATE.md`
- User asks you to analyze a Hermes subsystem and produce documentation

## Prerequisites

- Hermes source code at `C:/Users/chester.chen/AppData/Local/hermes/hermes-agent/`
- Template at `D:/obsidian/2026/wiki/_drafts/_TEMPLATE.md`
- Output directory exists: `D:/obsidian/2026/wiki/_drafts/`

## Workflow

### Phase 1: Read the Template (ALWAYS first)

```
read_file("D:/obsidian/2026/wiki/_drafts/_TEMPLATE.md")
```

The template defines the exact structure required. Do not deviate.

### Phase 2: Deep-Read Source Files

For each topic assigned, identify the relevant source files from the Hermes repo. Read them **deeply** — do not just scan the first 100 lines. For large files (2000+ lines), read the key sections:

- Module docstring + constants/config (first ~100 lines)
- Core data structures / dataclasses
- Main entry point functions
- Key selection/dispatch/loop logic (search for `def <key_function_name>`)
- State machine transitions (status constants, if/elif chains)

**Pitfall**: Reading only the first 500 lines of a 2200-line file misses the critical `_select_unlocked()`, `mark_exhausted_and_rotate()`, and `load_pool()` functions. Use `read_file` with `offset` to jump to known function locations, and `search_files` with `pattern="def <function_name>"` to find them.

**Source paths for each topic are listed in the user's prompt** under `sources:`. Read every file listed.

### Phase 3: Write the Draft

Template structure (from `_TEMPLATE.md`):

```
---
title: <口语化中文问句标题>
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: concept
tags: [agent-arch, <domain-tag>]
sources:
  - 源码: <relative-path>
confidence: draft
status: pending-review
---

# <Same Chinese question title>

## 这东西解决什么问题
口语化中文，解释动机、触发场景、没有它会出什么问题。

## 怎么做
源码级追踪核心逻辑。引用具体文件和关键函数/类名。
用流程图或步骤列表。代码块只放关键片段。

## 关键设计决策
Tradeoff、边界条件、特殊处理。
不要猜测原因 → 标注 <!-- TODO: 确认原因 -->

## 与其他模块的关系
Wikilink 列表。格式：[[concepts(概念)/hermes-xxx|页面名]]
```

#### Hard Rules

1. **标题用口语化中文问句** — "Hermes 怎么防止 API Key 泄漏到日志和工具输出里？" ✅
2. **不要写 "if user says X then Y" 规则** — 这是概念页，不是行为手册
3. **不要用价值判断词**（"简单"、"高级"、"笨拙"）— 客观描述差异
4. **代码路径使用正斜杠**：`agent/redact.py:42`
5. **200-400 行，不要注水** — 每条信息都要有出处
6. **TODO 标记不确定的设计决策**：`<!-- TODO: 确认原因 -->`
7. **Wikilinks 格式**：`[[concepts(概念)/hermes-xxx|display-name]]`
8. **Tags**：必须包含 `agent-arch` 和 `design-decision`，再加领域 tag

#### Source-Code-Level Analysis

Every claim should be traceable to a line number or function name. Types of evidence, in order of preference:
1. Direct line reference: `agent/redact.py:343`
2. Function/class name: `_mask_token()`, `CredentialPool`
3. Config key path: `curator.interval_hours`
4. Named constants: `DEAD_MANUAL_PRUNE_TTL_SECONDS`
5. Inline code snippet (only for key logic, 5-10 lines max)

### Phase 4: Expand to Minimum Line Count

After the first write, check line count with `wc -l`. If below 200, add more source-level detail:

- **Expand regex/pattern analysis**: Explain how each regex is compiled, what pre-checks gate it, what corner cases it handles
- **Add sub-workflows**: Break down complex flows into numbered lists (loading → seeding → merging, or backup → rollback → restore)
- **Add data structure walkthroughs**: Show key dataclass fields and how they flow through the pipeline
- **Add cross-process/threading details**: Lock usage, contextvar propagation, thread safety notes
- **Add configuration surface**: List all config keys with defaults, explain each one

Use `patch` to insert expansions **before** existing sections (use the section heading as the `old_string` anchor point) — this preserves the structure while adding content.

### Phase 5: Verify

```bash
wc -l D:/obsidian/2026/wiki/_drafts/hermes-<slug>.md
```

Confirm all files are 200-400 lines. Confirm YAML frontmatter has all required fields. Confirm wikilinks use correct paths.

## Batch Creation via Delegation

When there are many topics (10+), do NOT create them one-by-one in the main agent. Use `delegate_task` with batch mode to parallelize:

### Step 1: Create the template (if not exists)

```bash
mkdir -p D:/obsidian/2026/wiki/_drafts/
# Write _TEMPLATE.md with YAML frontmatter + section structure
```

### Step 2: Split topics into batches

Group topics by tier, then split into chunks of 3-7 per subagent. Max 3 subagents per `delegate_task` call, but you can dispatch multiple rounds.

### Step 3: Craft subagent prompts

Each subagent needs:
- **goal**: "Create N draft wiki concept pages in D:/obsidian/2026/wiki/_drafts/. Read template first."
- **context**: Topic details (slug, source file, "what it does", "why important"), wiki conventions, template path
- **toolsets**: `["terminal", "file", "web"]` — they need to read source and write files

Critical context fields per topic:
```
### Topic N: <Name>
- Slug: hermes-<slug>
- Source: <relative path in hermes-agent repo>
- What it does: <one paragraph>
- Why important: <one sentence>
```

### Step 4: Dispatch in rounds

Round 1 → Tier 1 (9 topics, 3 subagents × 3 each)
Round 2 → Tier 2 (11 topics, 3 subagents × 4/4/3)
Round 3 → Tier 3 (20 topics, 3 subagents × 7/7/6)

Each round is one `delegate_task(tasks=[...])` call. The subagents' results re-enter the conversation as async messages when done.

### Step 5: Verify

After all rounds complete, verify file count:
```bash
ls D:/obsidian/2026/wiki/_drafts/hermes-*.md | wc -l
```

### Pitfalls specific to batch delegation

- **Subagents cannot read the template if you don't tell them where it is.** Always include "Read D:/obsidian/2026/wiki/_drafts/_TEMPLATE.md first" in the context.
- **Subagents have no memory of the main conversation.** Pass ALL wiki conventions in the context — don't assume they know Chinese question titles or `concepts(概念)/` paths.
- **Subagents write with `write_file`** — they don't need the `obsidian` skill. Give them `terminal` + `file` toolsets.
- **Tier 3 topics can be shorter** — tell subagents "100-200 lines OK for Tier 3" to avoid padding.

---

## Pitfalls

1. **Reading source files too shallowly**: Files like `credential_pool.py` (2208 lines) and `curator.py` (1916 lines) have critical functions at offsets 800-1400+. Use `search_files` to locate key functions, then `read_file` with `offset` to read them.
2. **Missing the title format**: Title MUST be a spoken Chinese question (口语化中文问句). Not a declarative statement. Not English.
3. **Under the line minimum**: First drafts often land at 130-170 lines. Expand with more source-level detail, not filler sentences.
4. **Over-narrating instead of showing**: Don't write "This is a sophisticated system with many capabilities." Show `agent/redact.py:343 redact_sensitive_text(text, *, force=False, code_file=False)` and trace through it.
5. **Forgetting `code_file=True` significance**: This parameter skips ENV/JSON patterns in source code files — an important boundary case worth documenting.
6. **Template drift**: Always re-read `_TEMPLATE.md` before starting. The template may have been updated.
7. **Wikilink paths**: Concepts live under `concepts(概念)/`. Not under `wiki/` or bare. Use the Chinese directory name.
8. **Tags must include `design-decision`**: Every concept page documents design decisions. If a page has none, it's not a concept page — it's a reference page.

## Verification

- [ ] Template read first
- [ ] All listed source files read (with offsets for large files)
- [ ] YAML frontmatter has title, created, updated, type, tags, sources, confidence, status
- [ ] Title is Chinese question
- [ ] 200-400 lines
- [ ] No value judgments
- [ ] Source line references use forward slashes
- [ ] Wikilinks use `[[concepts(概念)/hermes-xxx|name]]` format
- [ ] TODO markers used for uncertain design decisions
- [ ] `wc -l` confirmed on all output files

## Key Paths

| Path | Purpose |
|------|---------|
| `D:/obsidian/2026/wiki/_drafts/_TEMPLATE.md` | Page template (on-disk copy) |
| `D:/obsidian/2026/wiki/_drafts/` | Output directory for drafts |
| `D:/obsidian/2026/wiki/concepts(概念)/` | Published concept pages (not drafts) |
| `C:/Users/chester.chen/AppData/Local/hermes/hermes-agent/` | Hermes source code root |

## Support Files

- `references/wiki-draft-template.md` — Inline copy of the template rules (subagents can load this instead of reading from disk)
- `references/subagent-context-template.md` — Prompt template for batch delegation subagents
