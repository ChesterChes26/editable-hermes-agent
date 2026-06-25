---
name: wiki-guide-split
description: "Wiki 归档入口：LLM 生成原始文档 → 约束密度判断 → 拆(guide+ref)或留(单文件) → review 循环。"
version: 2.1.0
---

# Wiki 归档

将一次对话总结或文章阅读沉淀为 wiki 文档。不是机械搬运——先判断信息是否有提取价值，有就拆成 guide（可执行约束）+ reference（完整证据），没有就保留原始文档。

旧 wiki 根目录（`D:/obsidian/2026/wiki/`）即将废弃，之后所有 wiki 存档都走这个流程。

## 触发条件

用户说「把这个存到 wiki」「总结一下写入 wiki」「读这篇然后归档」等意图。

## 工作流

### Phase 0：生成原始文档

LLM 根据用户要求产出原始材料：
- 如果是会话总结 → 提取关键决策、设计权衡、踩坑记录
- 如果是文章阅读 → 提取核心观点、论据、可操作结论

原始文档直接写入目标路径，作为后续判断的底板。**不要在这个阶段做拆分——先完整记录，再判断。**

### Phase 1：约束密度判断

读完原始文档，回答一个问题：

> 这篇文档里，有没有可执行约束（MUST/MUST NOT）被验证证据（源码引用、对比表、历史背景、计费数据）淹没了？

- **拆** → 进入 Phase 2a。文档同时包含可执行约束 AND 验证证据，两者混杂。
- **不拆** → 进入 Phase 2b。文档已经是纯约束或纯背景，拆分不产生增量价值。

判断标准不是行数。90 行的纯约束文档不需要拆，200 行的纯叙事文档拆了也没用。

辅助问题：违反这条规则会导致系统崩溃或行为错误吗？能 → 可执行约束，需要提取。只是改策略但系统还能跑 → 算法内部行为，不需要提取。

### Phase 2a：拆分路径（guide + reference）

1. 写 reference（`xxx.ref.md`）：原始文档整理后作为证据卷宗。type: reference，guide 字段指向配对的 `.md`。
2. 用五步构造法从 reference 提取 guide（`xxx.md`）。type: guide，reference 字段指向配对的 `.ref.md`。
3. **Review 循环**：按第 5 步自我审查逐条验证。5 条全部通过 → 写入 wiki。任何一条不通过 → 回到第 2 步重写 guide，直到全部通过。

guide 和 reference 同目录，后缀配对。`.ref.md` 只在有配对的 guide 时才存在。

### Phase 2b：单文件路径

直接写入原始文档，不创建 `.ref.md`，不拆分。文件保持 `xxx.md` 单文件。

**审计已有单文件**：当审查已有 standalone 文档是否该拆时，不要看 frontmatter 格式——frontmatter 修正是机械操作。核心问题是 Phase 1 的约束密度判断：这篇文档里有没有可执行约束被验证证据淹没了？有 → 该拆；纯背景/纯叙事/约束已经很突出 → 不拆。判断时追问：\"违反这条规则会导致系统崩溃或行为错误吗？能 → 可执行约束，需要提取。\"

## 五步构造法

### 第 1 步：提取约束清单

通读原始文档，提取所有可写成 MUST/MUST NOT 的规则。

```
正确提取：
  - MUST NOT 修改 system prompt
  - MUST 把动态上下文塞进 user message

不是约束，不提取：
  - "ReAct 发明于 2022"（历史背景）
  - "conversation_loop.py:589"（源码引用）
```

### 第 2 步：补充最小因果链

每条约束加一句话原因 + 边界。只给操作所需的最小因果——不需要完整原理推导。

```
✅ MUST NOT 修改 system prompt
   → 原因：system prompt 是缓存的锚点。改一次 → 缓存全废
   → 边界：硬约束，没有例外

❌ [从 cache_control 断点策略讲到 MLA 前缀匹配...]
```

### 第 3 步：用典型例子串约束

一个最常见的操作场景，展示 ❌ 错误 vs ✅ 正确。一个例子够了。

**什么是\"一个\"**：一个连贯场景。可以在这个场景里展示正常/异常两条路径（如正常 silence + 同一 filter 下 failed 绕过），但不能拆成两个带独立标题的例子块。如果发现自己写了「场景 1 ... 场景 2 ...」→ 合并成单场景内的双路径。

### 第 4 步：交叉验证

逐条回到原始文档：有没有漏掉会导致执行失败的 MUST/MUST NOT？不漏源码行号，只查约束。漏了 → 补上。

**关键**：原始文档可能通过 wikilink 引用其他文档来承载约束细节。比如 `loop-and-cache.ref.md` 把 bit-perfect 归一化的实现细节委托给了 `[[context-compression]]`。交叉验证时遇到 wikilink 引用 → 必须追过去读，确认被引用的文档里有没有本 guide 漏掉的硬约束。

### 第 5 步：自我审查（强制，写入前最后一步）

逐条回答以下 5 题。**每条必须带证据，不能只写"通过"。**

| # | 验证项 | 需求 | 回答格式 |
|---|--------|------|----------|
| 1 | 约束无遗漏 | guide 包含所有会导致执行失败的约束 | 列 guide 每条约束 + 对应原始文档段落。反问：原始文档还有未覆盖的约束吗？ |
| 2 | 约束可执行 | agent 读完知道具体做什么 | 抄第一条约束原文：agent 读完知道该做什么、不该做什么吗？ |
| 3 | 认知减负 | guide 比原始文档明显更快 | guide 行数超过原始文档 40% → 不通过 |
| 4 | 无禁止内容 | 无源码行号/计费数据/对比表/历史年份/多例子 | grep 扫描：`源码行号:0, 计费:0, 对比表:0, 历史年份:0` |
| 5 | 不像缩写版 | guide 和 reference 结构根本不同 | 列两边的段序。相似 → 重写 |

5 条全部通过 → 写入。任何一条不通过 → 回到 Phase 2a 第 2 步重写 guide，再审查，直到全部通过。

## Guide 页面结构

```markdown
## 这东西解决什么问题
（必须。1-2 句话。）

## 核心约束
（必须。编号列表。MUST/MUST NOT + 原因 + 边界。）

## 一个例子
（按需。❌ 错误 + ✅ 正确。）

## 循环/机制怎么运转
（按需。3-5 行伪代码。）

## 出错了怎么办
（按需。信号 → 去 reference 看什么。）

## 核心就一句话
（必须。口语化总结。）
```

## 什么不进 guide

| 内容 | 不进 | 理由 |
|------|------|------|
| 历史背景 | ✗ | 不影响执行 |
| 源码行号 | ✗ | 不是代码导航 |
| 计费/性能数据 | ✗ | 验证证据 |
| 对比表 | ✗ | 去 reference 查 |
| 超过一个的例子 | ✗ | 一个锚定足够 |
| 学术引用 | ✗ | 不是论文 |

## 命名与路径规范

- 目录和文件：`英文(中文)` 格式。英文必须是实义词（`concepts(概念)`），不是拼音。
- 文件名全小写，连字符分隔。
- 拆的文档：`xxx.md`（guide）+ `xxx.ref.md`（reference），同目录。
- 不拆的文档：`xxx.md` 单文件。
- 目标根路径：`D:/obsidian/2026/wiki-next/`。根据内容分入对应子目录：`concepts(概念)/`、`comparisons(对比)/`、`entities(实体)/`、`queries(问答)/`、`raw(源材料)/`。hermes 相关内容按 T0-T3 层级放入 `concepts(概念)/hermes/Tx(层级)/`。
- **`raw(源材料)/` 目录不进入任何归档流程。** 此目录下的文档是原始材料（会话记录、文章原文），不拆 guide+ref，不做约束密度判断，不修改。只有 `concepts/`、`comparisons/`、`entities/`、`queries/` 下的文档走此流程。

## Frontmatter 规范

每篇 wiki 文档必须包含 YAML frontmatter：

```yaml
---
title: <口语化中文标题>
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: guide | reference | concept | comparison | entity | raw
tags: [<来自 SCHEMA taxonomy>]
confidence: high | medium | low
---
```

拆分文档额外字段：
- guide 的 `reference: xxx.ref.md`（相对路径）
- reference 的 `guide: xxx.md`（相对路径）

## 写入管线

所有 wiki 文件通过此管线写入，**不走 obsidian skill 的 wiki-import-markdown**。

### 1. 分类

根据内容判断归属子目录。有疑问时参考 `D:/obsidian/2026/wiki-next/SCHEMA.md`。

### 2. 写文件

用 `write_file` 写入目标路径。guide+ref 配对时，先写 reference 再写 guide（guide 从 reference 提取）。

### 3. Wikilink

每个新页面至少 2 个 `[[wikilink]]` 交叉引用已有页面。

### 4. 更新 index.md

```bash
# 更新总页数
# 在对应分类下插入新条目，按字母序
- [[相对路径|显示标题]] — 一句话摘要
```

### 5. 追加 log.md

```markdown
## [YYYY-MM-DD] create | <标题>
- 类型: guide+reference | concept | comparison | entity | raw
- 文件: [[相对路径]]
- 内容: <一句话摘要>
```

### 6. Git commit & push

```bash
cd /d/obsidian/2026
git add wiki-next/
git commit -m "wiki-next: <描述>"
git -c http.proxy=http://127.0.0.1:7897 push
```

## 维护规则

- 修改 reference 后，检查 guide 是否需同步。
- guide 约束被推翻 → 立即修正。
- guide 永远从 reference 派生，不要反过来。

## Pitfalls

- **不要无底板写 guide。** 先有原始文档，再判断，再提取。
- **不要预判 Phase 1 结果而跳过 Phase 0。** 即使你 99% 确定这篇文档是 Phase 2b（不拆），也必须先把原始底板写入磁盘，再进入 Phase 1 正式判断。Phase 0 的产物是纯叙事底板——不加 frontmatter、不加 wikilink、不做约束提取、不设「核心约束」「一个例子」「机制怎么运转」等 guide 式章节。这些是 Phase 2b 最后一步才加的东西。违反后果：产出的不是底板而是成品，Phase 1 判断失去意义。
- **不要混淆聊天输出和 Phase 0 底板。** Phase 0 的交付物是磁盘上的一个文件（用 `write_file` 写入目标路径），不是对话里的 summary 文字。对话里总结一段话 ≠ Phase 0 完成。必须看到文件落盘、确认路径，才算 Phase 0 结束。
- **不要追求 100% 覆盖。** Guide 定位 80% 够用，剩下靠"出错了怎么办"表兜底。
- **不要把 guide 写成缩写版。** 提取约束 ≠ 缩短原文。段序相似 → 判不合格。
- **不要漏硬约束。** 违反后系统崩溃的 → 必须进 guide。只影响理解的 → 不进。
- **"出错了怎么办"不是摆设。** 盲区必须映射到 reference 具体段落。
- **不要用行数做判断。** 只看约束密度。
- **不要跳过第 5 步。** 猜自己没漏和实际没漏是两回事。
- **Review 不通过就重写，不要修修补补凑合。** 结构性不合格 → 从头来。
- **不要漏 frontmatter 字段。** guide 必须有 `tags` + `confidence` + `reference`，reference 必须有 `guide` 字段——四篇里就有一篇漏。修改后 grep 确认：`tags:`、`confidence:`、`reference:`（guide）/ `guide:`（ref）全部存在。
- **DELETE guide 时，保留的 standalone 必须是完整原始内容，不是 ref 子集。** 当判断 guide 没价值而删除时，正确的操作是：从旧 wiki 底板恢复原始完整文档 → 更新 wikilink 路径 → 写入 standalone。错误的操作是：直接把 ref 内容覆盖到 .md 上——ref 只是原始文档的子集（证据卷宗），删掉 guide 后 ref 代替不了完整的原始文档。判断标准：恢复后的 standalone 必须能和 wiki(已废弃) 的对应文件 diff 一致（排除 wikilink 路径和 frontmatter 日期差异后）。
- **批量操作后必须对比验证。** 任何涉及文件覆盖的操作（迁移、拆分、DELETE 提升）完成后，用 `diff <(sed '1,/^---$/d' new) <(sed '1,/^---$/d' old)` 对比 body 内容。排除 wikilink 路径（`wiki(已废弃)` ↔ `wiki-next`）后，差异应为零。非零 → 内容被意外修改，需从旧 wiki 恢复。
- **`ref:` 不是 `reference:`。** guide 用 `ref:` 是常见错误（语义相同但规范要求全写 `reference:`）。同理 reference 端字段是 `guide:` 不是 `ref:`。审计时 grep 两边的字段名。
- **理念型/设计白皮书文档不适合 guide+ref 拆分。** LLM Wiki V2 设计文档、架构对比分析这类纯原则性内容——"约束"是可选的 best practice 而非不遵守就会崩溃的硬规则。Phase 1 判断时问"违反这条会导致系统崩溃吗？"→ 不会 → 这 7 条"约束"实际是设计原则 → DELETE，保留 standalone ref。
- **概念页（type: concept）伪装成 guide。** 文件有配对 `.ref.md` 但 frontmatter 写 `type: concept`，且内容无核心约束/无一个例子/无出错了怎么办——说明写的人就没打算让它当 guide。审计时判断是否真 guide，不要因为有配对的 ref 就假定它是。
- **`confidence: draft` 不是合法值。** 批量迁移时旧 wiki 的 `confidence: draft` 会被原样复制到 wiki-next 的 ref。只有 `high | medium | low` 三个合法值。涉及 3 个 ref（credential-pool、gateway-stream-pipeline、secret-redaction）。发现后改为 `medium`（内容完整但有待验证的 TODO）。
- **批量修 frontmatter 时慎用 `replace_all=true`。** 修 `updated: 2026-06-24` → `2026-06-25` 用了 replace_all，误伤了 body 中的同字符串和 `created` 字段（两者共享日期子串）。修复：给 old_string 加足够上下文作唯一匹配。
- **"机制怎么运转"段不要写实现细节。** 3-5 行伪代码就够了——不要写类名、方法名、参数列表、调用链。发现自己在写 `PairingStore.generate_code()` 或步骤列表超 5 行 → 停，这是在写 reference 不是 guide。
- 对比表不进 guide。哪怕是"三层防线递进"这种机制概览表，只要是表格比较（触发点/检查逻辑/行为），一律放进 reference。guide 的"机制"段用伪代码流，不用表格。
- **用一个例子里的双路径替代两个独立例子。** gateway-response-filters 的"一个例子"拆成了 [场景1 正常 silence] + [场景2 失败绕过] 两个独立块，各占 15+ 行。合并为单场景内的双路径（正常路径/异常路径），一个 code block 搞定。
- **约束密度大于格式审查。** 审计 Phase 2b 文档时，核心问题是"该不该拆"（Phase 1 约束密度判断），不是 frontmatter 是否缺字段。frontmatter 修正是机械操作，约束密度是判断操作——先判断，后修正。
- **大规模合规审查用三 subagent 并行。** 详见 `references/audit-patterns.md`。要点：Phase 2a（guide 内容）、Phase 2b 约束密度、格式审查拆成独立 subagent，各配 skills toolset。

## 批量迁移（按需）

大规模迁移（20+ 篇）时，每篇一个 subagent，并发 3 个。

> 详细工作流见 `references/batch-split-workflow.md` — 包含 subagent 配置、context 模板、完成后 review 清单。
给每个 subagent 配 `skills` toolset，让它直接加载 wiki-guide-split skill。

- 每个 subagent 独立处理一篇，互不干扰
- PATH 必须写完整绝对路径，goal 和 context 首行各写一次
- subagent 完成的 summary 不可全信——全部派完后逐路径验证
- 约束密度判断由批量派发者逐篇做，不要交给 subagent
