# Wiki Guide-Split 审计模式

## Round 1 (2026-06-25, 手动审查)

对 wiki-next/concepts/hermes 下 21 对 guide+ref 的初次审查。

### 发现率

| 问题 | 命中 | 比率 |
|------|------|------|
| frontmatter 缺 tags/confidence | 4/21 | ~19% |
| "机制"段写实现细节 | 1/21 | ~5% |
| 对比表出现在 guide | 1/21 | ~5% |

### 教训

手动逐对检容易漏三类：ref 端 frontmatter、confidence 枚举值非法、小文件的对比表。

---

## Round 2 (2026-06-25, subagent 审查)

用 subagent 加载 wiki-guide-split skill 重新审查同一批 21 对。关键差异：**subagent 多发现 3 类问题**（ref 端 frontmatter、confidence:draft 无效、tool-guardrails 对比表漏判）。

### 修正后的总通过率

| 审查轮次 | 问题文件数 | 总文件数 | 通过率 |
|----------|-----------|---------|--------|
| Round 1 (手动) | 7 | 42 | 83% |
| Round 2 (subagent) | 10 | 42 | 76% |
| 修正后 | 0 | 42 | 100% |

---

## Round 3 (2026-06-25, 三 subagent 并行审计)

将审计拆成三个独立子任务，三 subagent 并行跑：

### Subagent #1: Phase 2b 格式审查（后被替代）
- 范围：29 个 standalone .md（无配对的 .ref.md）
- 焦点：frontmatter、type 合法性、confidence 枚举
- 结果：找到 23 篇 `confidence: draft`（批量迁移残留）
- **被替代原因**：用户在途中纠正——Phase 2b 审计的核心不是 frontmatter 格式，而是约束密度判断

### Subagent #2: Phase 2a 内容审查（主力）
- 范围：21 对 guide+ref
- 焦点：五步构造法 + 第5步自审 5 条 + 六段结构 + 违禁内容
- 发现：2 CRITICAL（artifact残留、双例子）+ 2 MODERATE（漏 bit-perfect 约束、constraint 条目不足）+ 系统性伪代码偏长

### Subagent #3: 约束密度审计（关键）
- 范围：29 个 standalone .md
- 焦点：Phase 1 问题——"有没有可执行约束被验证证据淹没了？"
- 结果：16 篇该拆未拆 (T1:2, T2:10, T3:4)、13 篇不拆判断正确

### 三 subagent 并行模式的工作流

```
用户请求审查 wiki 目录
    │
    ├── subagent #1: Phase 2b 格式 → frontmatter + type
    │    （可选——如果用户只关心约束密度，可以跳过）
    │
    ├── subagent #2: Phase 2a 内容 → 五步构造法 + 自审
    │    context: 加载 skill、21 对路径、全部检查项
    │    toolsets: [skills, file, terminal]
    │
    └── subagent #3: 约束密度 → Phase 1 判断（该拆/不拆）
         context: 加载 skill、29 个独立文件路径、每文件输出结构化判断
         toolsets: [skills, file]
```

### 给每个 subagent 的 context 关键要素

1. **首行必须写** `CRITICAL: Load the skill FIRST with skill_view(name='wiki-guide-split')`
2. **路径写完整绝对路径**，不要用相对路径
3. **检查清单要具体**——不要"检查是否合规"，要列出每一小项（如"grep 源码行号 pattern xxx.py:NNN"）
4. **输出格式预定义**——要求每文件输出固定格式，方便汇总
5. **toolsets**：Phase 2a 审查需要 `[skills, file, terminal]`（terminal 用于 grep 扫描行号/对比表），Phase 1 约束密度审查只需 `[skills, file]`

### 本轮的修复批次

修复优先级来自 subagent 发现的严重度分级：

| 批次 | 内容 | 来源 |
|------|------|------|
| 立即 | 删 artifact、合并双例子、补 bit-perfect 约束、补 guardrails 约束 | #2 CRITICAL + MODERATE |
| 机械 | 23 篇 `confidence: draft`→`medium` | #1 发现 |
| 计划 | 16 篇该拆未拆的拆分 | #3 发现 |

---

## Round 4 (2026-06-25, 概念页 + agentmemory 域审计)

审计 7 对 guide+ref（3 对概念级 + 4 对 agentmemory 域），不通过 subagent，直接逐对审查。首次遇到 **DELETE 而非 REDO** 的决策。

### 结果

| 对 | 决策 | 关键违规 |
|----|------|---------|
| agent-loop-design-philosophies | REDO | 缺 frontmatter |
| agent-loop-vs-evaluation | REDO | 约束是原则非 MUST |
| agent-knowledge-trifecta | REDO | 约束 #3 嵌入部署代码块 |
| agentmemory-memory-layers-pipeline | **DELETE** | type: concept, 无可执行约束, 含源码行号 |
| agentmemory-new-session-fix | REDO | 缺 reference: 字段, 约束埋在叙事中但可提取 |
| agentmemory-worker-bound-session-gap | REDO | ref: 非 reference:, 约束埋在叙事中但可提取 |
| llm-wiki-v2-rohit-ghumare | **DELETE** | 约束是设计原则非可执行 MUST, 约束 #3 含对比表 |

### REDO vs DELETE 决策矩阵（Round 4 新增）

决策顺序：先判断可执行性，再判断格式。

**DELETE 的三个触发条件（满足任一即 DELETE）：**

| 条件 | 标志 | 本轮案例 |
|------|------|---------|
| guide 不是 guide（`type: concept`） | 无可执行约束、无六段结构、含源码行号 | #4 memory-layers-pipeline |
| 约束是设计原则，非 MUST/MUST NOT | 违反不会导致崩溃，只是"应该这样做更好" | #7 llm-wiki-v2 |
| split 不减少认知负荷 | guide 和 ref 结构相似，或 guide 只是缩写版 | — |

**REDO 的两个触发条件（两者都要有约束可提取）：**

| 条件 | 标志 | 本轮案例 |
|------|------|---------|
| 有约束但格式错误 | 原则式表述、缺 frontmatter、嵌入代码/表 | #1, #2, #3 |
| 约束埋在叙事中 | 叙事型 bug fix / 诊断报告，但内部有可执行的 MUST | #5, #6 |

**判断红线**：先问"违反这条会导致系统崩溃或行为错误吗？"→ 能 → 可执行约束，可 REDO。不能 → 设计原则，应 DELETE。

### 本轮新增的格式陷阱

- **`ref:` 不是 `reference:`**：worker-bound-session-gap 用了 `ref` 而非 `reference`，语义相同但规范要求 `reference`
- **非标准 frontmatter 字段**：`wikilinks` 和 `summary` 直接写在 YAML 里不属于规范字段
- **概念页伪装的 guide**：memory-layers-pipeline 标签是 `type: concept` 且有 `ref:`（不是 `reference:`），根本不是 guide+ref 结构
- **DELETE 后的物理删除**：`write_file` 和 `patch` 无法删除文件——需终端 `rm`。先 write ref 内容到 .md（覆盖 guide），再 rm .ref.md

### 实操教训

- **约束密度判断是第一步，不是最后一步。** Round 4 中最先判断 #7：7 条"约束"实际全是设计原则 → 直接 DELETE，不再检查格式细节。反之 #5/#6 虽然格式全错但约束可提取 → REDO。
- **理念型文档（LLM Wiki V2 设计白皮书）不适合 guide+ref 拆分。** 设计原则不是可执行约束——保留 standalone ref 就够了。同理，概念解释页（KV scope 全景图）不该伪装成 guide。
