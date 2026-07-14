# Wiki Project Review Pages

For multi-gate projects, create a dedicated directory under the active wiki (typically `wiki-next/`) to record each gate's review Q&A.

## Directory Structure

```
wiki-next/<project-name>(中文名)/
├── index.md                    # project overview + gate progress table
├── gate-0-<name>(中文).md      # per-gate review records
├── gate-1-<name>(中文).md
├── ...
```

## index.md Template

```markdown
---
tags: [<project-tag>]
created: YYYY-MM-DD
---

# Project Title

> One-line summary.

## 项目文件

- **Spec:** absolute path
- **Source plan:** absolute path
- **Target:** absolute path

## Gate 进度

| Gate | 名称 | 状态 | Review 记录 |
|------|------|------|------------|
| 0 | Spec Gate | ✅ 完成 | [[gate-0-xxx]] |
| 1 | Baseline Freeze | 🔄 等待 Review | [[gate-1-xxx]] |
| ... | ... | ⏳ 待开始 | ... |

## 核心约束

- constraint 1
- constraint 2
```

## Per-Gate Page Template

```markdown
---
tags: [<project-tag>, gate-N, <gate-name>]
created: YYYY-MM-DD
parent: [[index]]
---

# Gate N — Name (中文)

> One-line purpose.

## Review 记录

### YYYY-MM-DD: topic

**问题:** what user asked

**回答要点:**
- point 1
- point 2

### YYYY-MM-DD: topic

...

## 状态

🔄 等待用户 Review / ✅ 已批准

## 产出物

- file paths or directory tree
```

## Rules

1. **Append, don't replace.** Each review Q&A is a timestamped subsection. Don't rewrite the page for each new question.
2. **Status line at bottom.** Always show current state: `🔄 等待用户 Review` or `✅ 已批准 → 进入 Gate N+1`.
3. **Update index progress table** when a gate status changes.
4. **Update wiki-next log.md** when creating new pages.
5. **Don't over-narrate in wiki pages.** Record what happened, what was asked, what was answered. The wiki is the audit trail, not a tutorial.
6. **Use [[wikilinks]]** for all cross-references between gate pages and the index.

## When to Create

- Any project with 3+ distinct phases/stages/gates
- User says "I want to record the review process"
- User asks "put this in the wiki"
