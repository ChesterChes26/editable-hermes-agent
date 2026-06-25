# Wiki Concept Page Template

## YAML Frontmatter (required)

```yaml
---
title: <口语化中文问句标题>
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: concept
tags: [agent-arch, <domain-tag>]
sources:
  - 源码: <relative-path-in-hermes-agent-repo>
confidence: draft
status: pending-review
---
```

## Body Structure

### Section 1: 这东西解决什么问题
口语化中文，解释动机、触发场景、没有它会出什么问题。

### Section 2: 怎么做
源码级追踪核心逻辑。引用具体文件和关键函数/类名。用流程图或步骤列表。代码块只放关键片段。

### Section 3: 关键设计决策
Tradeoff、边界条件、特殊处理。不确定原因标注 `<!-- TODO: 确认原因 -->`

### Section 4: 与其他模块的关系
Wikilink 列表。格式：`[[concepts(概念)/hermes-xxx|页面名]]`

## Hard Rules

1. 标题用口语化中文问句
2. 不要写 "if user says X then Y" 规则
3. 不要用价值判断词（简单、高级、笨拙）— 客观描述差异
4. 代码路径使用正斜杠：`agent/redact.py:42`
5. 200-400 行，不要注水
6. TODO 标记不确定的设计决策：`<!-- TODO: 确认原因 -->`
7. Wikilinks 格式：`[[concepts(概念)/hermes-xxx|display-name]]`
8. Tags 必须包含 `agent-arch` 和 `design-decision`

## Source-Code-Level Evidence (preference order)

1. Direct line reference: `agent/redact.py:343`
2. Function/class name: `_mask_token()`, `CredentialPool`
3. Config key path: `curator.interval_hours`
4. Named constants: `DEAD_MANUAL_PRUNE_TTL_SECONDS`
5. Inline code snippet (only for key logic, 5-10 lines max)
