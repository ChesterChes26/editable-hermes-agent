# 批量拆分工作流

大规模将 standalone 文档拆为 guide+ref 对时使用。

## 触发条件

审查发现 10+ 篇独立文档「该拆未拆」时触发。

## 分流

将文档均分为 3 批（每批 ≤5 篇），每批一个 subagent。不超 3 个并发——subagent 之间互不干扰，多了反而管理混乱。

## Subagent 配置

每个 subagent 必须：
- `toolsets: ["skills", "file"]` — 需要 skills 加载 wiki-guide-split + file 读写
- context 中写明每篇的完整绝对路径
- 明确要求加载 skill: `skill_view(name='wiki-guide-split')`
- 明确要求走 Phase 0→2a 完整流程

## Context 模板

```
You are executing wiki-guide-split Phase 2a. CRITICAL: load the skill FIRST with skill_view(name='wiki-guide-split').

Files: [列出绝对路径]

For EACH file:
Step 1 — Read original .md (Phase 0 raw document)
Step 2 — Write .ref.md (organized reference, type:reference, guide:xxx.md)
Step 3 — 五步构造法 extract guide (.md, type:guide, reference:xxx.ref.md)
Step 4 — Self-review (5 items from skill step 5)
Step 5 — ALL pass → write. Any fail → iterate.

Respond with per-file: guide/ref line counts, constraint count, self-review result.
```

## 完成后 Review

派发者必须逐对验证：
1. `grep` 六段结构是否齐全
2. guide frontmatter: `type: guide` + `reference:` 指向正确 .ref.md
3. ref frontmatter: `type: reference` + `guide:` 指向正确 .md
4. 认知减负比 guide_lines / ref_lines ≤ 140%
5. 抽查 1-2 篇 guide 内容质量（约束是否可执行、例子是否只有一个）

## 常见问题

- credits-billing 类短文档比例可能接近 100%——合规但紧贴线，属原文本身约束密集
- profile-a2a 类长文档比例可能低至 25%——说明原文叙事占比大，拆分效果好
- 不要信任 subagent 的 self-report——必须逐对验证
