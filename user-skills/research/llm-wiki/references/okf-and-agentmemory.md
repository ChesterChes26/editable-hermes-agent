# OKF & agentmemory — LLM Wiki 生态参考

本次会话（2026-06-22）对 LLM Wiki V2 生态的完整调研结果。

## Rohit Ghumare 的 LLM Wiki V2

- Gist: https://gist.github.com/rohitg00/2067ab416f7bbe447c1977edaaa681e2
- 2026-04-06 fork 自 Karpathy 原版
- 19 comments
- 基于构建 [agentmemory](https://github.com/rohitg00/agentmemory) (23K+ stars) 的经验

### V2 的 10 个核心扩展

1. **记忆生命周期** — 置信度评分、取代机制、遗忘曲线、四层记忆管道（工作→情景→语义→程序性）
2. **类型化知识图谱** — `uses/depends on/contradicts/caused/fixed/supersedes`
3. **混合搜索** — BM25 + 向量搜索 + 图遍历，RRF 融合
4. **事件驱动自动化** — 新来源→自动 ingest，会话结束→压缩，写入→矛盾检测
5. **质量自愈** — 内容自评、自动修复孤页/断链/过期声明
6. **结晶化** — 会话结束后自动蒸馏为结构化摘要
7. **多 Agent 协作** — mesh sync、共享/私有范围
8. **隐私治理** — 摄入过滤、审计轨迹
9. **多格式输出** — 对比表、时间线、依赖图、简报
10. **Schema 即产品** — SCHEMA.md 是最重要的文件

### 优缺点（来自本会话分析）

**优点**: 生命周期是真正增量、类型化关系强于 wikilink、混合搜索解决规模问题、自动化切中要害、模块化路径务实。
**缺点**: 置信度评分没有 ground truth（LLM 自评循环论证）、遗忘曲线在知识管理中是双刃剑、知识图谱实现细节完全缺失（实体一致性、关系粒度、存储/查询）、成本未核算（每 ingest 一个来源几十万 token）、LLM 自评质量是自我感觉良好。

## Google Cloud Platform OKF (Open Knowledge Format)

- Repo: https://github.com/GoogleCloudPlatform/knowledge-catalog
- Spec: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
- 版本: v0.1 Draft
- 许可: Apache-2.0

### OKF 核心设计

- 目录 + markdown + YAML frontmatter + 跨文件链接（与 Karpathy/Rohit 模式物理层完全一致）
- 唯一必需字段: `type`
- **明确拒绝类型化关系** — §5.3: "关系类型由周围文字传达，不由链接本身"
- 有 index.md（渐进披露）、log.md（日期分组更新历史）、bundle 结构
- 设计目标: 跨系统互操作、厂商中立、人和 agent 都可消费
- §10 明确承认与 "LLM wiki 仓库" 的关联

### OKF vs Rohit V2 的根本分歧

| 维度 | OKF | Rohit V2 |
|------|-----|----------|
| 目标 | 最小互操作协议 | 最大认知深度 |
| 关系 | 无类型（prose 传达） | 六种类型化边 |
| 生命周期 | 无 | 全套（置信度+衰减+取代+四层管道） |
| 知识图谱 | 无 | 实体提取+类型化边+图遍历 |
| 自动化 | 无（格式规范） | 事件驱动 hooks |

**时间线**: Karpathy gist (2026-04-04) → Rohit V2 fork (2026-04-06) → OKF spec v0.1 (约 2026-05)
OKF 在物理层受 LLM wiki 模式影响（spec §10 自认），但在语义层刻意保持最小化。

### OKF 适用场景

- 企业数据目录的可移植层（BigQuery metadata → OKF bundle）
- 跨组织/跨工具知识交换（不绑定 SDK）
- 合规审计（git 原生 blame/diff/review）
- Agent 的"基础养分"层（结构化领域知识）

### OKF 不适合

- 个人知识库
- Agent 自主积累知识
- 需要类型化关系推理
- 实时查询

## agentmemory（Rohit V2 的实现）

- Repo: https://github.com/rohitg00/agentmemory
- 23K+ stars, TypeScript, npm 包 `@agentmemory/agentmemory`
- 1423+ 测试, 53 MCP tools, 128 REST endpoints, 12 hooks, 15 skills
- 底层: iii-engine (WebSocket, port 49134) + SQLite
- 对外: MCP Server (port 3111) + REST API

### agentmemory 实现了 V2 的哪些

| V2 概念 | 状态 | 证据 |
|---------|------|------|
| 四层记忆管道 | ✓ | 4-tier consolidation |
| 遗忘曲线 + 衰减 | ✓ | decay + auto-forget |
| 混合搜索 | ✓ | BM25 + Vector + Graph (RRF fusion) |
| 事件驱动 hooks | ✓ | 12 hooks |
| 结晶化 | ✓ | `crystallize` 函数 |
| 审计轨迹 | ✓ | `recordAudit()` |
| 多 Agent | ✓ 部分 | 多 agent 共享同一 memory server |
| 知识图谱 | ✓ 部分 | 图搜索在混合搜索里 |
| 置信度评分 | 不确定 | 未在 README 展开 |
| Schema 治理 | ✗ | 无 SCHEMA.md |

### agentmemory 的本质

**不是 agent**，是一个 **memory service**。类比：agent 的海马体。

内部使用 LLM:
- 压缩/摘要（consolidation）— 调用 LLM API，约 $10/次跑分
- 向量 embedding — 本地模型 `all-MiniLM-L6-v2`（~80MB，通过 Transformers.js ONNX，免费）

**完全本地运行** — `npm install` 后 localhost 上起服务，数据在本地 SQLite。

### agentmemory ≠ wiki

| | agentmemory | llm-wiki |
|------|-----------|---------|
| 记什么 | 编码会话里发生的事 | 外部来源的 curated 知识 |
| 来源 | Agent 工具调用自动捕获 | 手动或 agent 辅助 ingest |
| 检索时机 | 下次会话开始时自动注入上下文 | 查询时按需搜索 |
| 存储 | SQLite | Markdown 文件 |

两者不冲突，可以搭配：agentmemory 管会话记忆，llm-wiki 管知识资产管理。

### 向量 embedding 管线（本次会话深入）

**写入时**：
```
原始 session 数据 → LLM 压缩为结构化文本 → 存入 SQLite
                                              │
                                              └→ all-MiniLM-L6-v2 → 384维向量 → 存入 SQLite（索引列）
```

**查询时**：
```
Agent 当前上下文 → all-MiniLM-L6-v2 → 查询向量(50ms CPU)
                                          │
                                          └→ SQLite 余弦相似度排名
                                                   │
                                          Top-K 原文 → 注入 agent context
```

向量的角色：**仅作为索引**，取回的是原文不是向量。向量在检索完成后丢弃。

### 为什么不用写死的函数代替 all-MiniLM-L6-v2

2200 万个参数的本质：从几十 GB 语料中压缩出的语义规律。训练过程是反复拧旋钮（反向传播）让"JWT"和"身份验证"在向量空间中靠近。人无法手写这些映射——同义词不可穷举，规则不可枚举。80MB 存的是 2200 万个训练好的浮点数，不是代码。

### 模型不准怎么办

agentmemory 用三重混合搜索兜底：
- **BM25** — 关键词匹配，兜向量对缩写/专有名词的弱点
- **向量搜索** — 语义匹配，兜 BM25 对同义词的盲区
- **图遍历** — 结构关系，从文件节点沿边走到相关 session

RRF 融合三个排名取调和。能兜住局部不准，兜不住系统性偏差（如英文模型用在中英文混合场景）。

### 什么 agent 需要 agentmemory

**需要**：跨会话有累积上下文的 agent——长线编码项目（Claude Code、Codex、Cursor）、运维 agent（K8s、DB 管理）。
**不需要**：一次性任务 agent（"翻译这篇 PDF"）、每次上下文全量重头提供的 agent、任务间完全独立的 agent。

### 与 llm-wiki 的搭配

- agentmemory：自动记住 "上次 weixin.py 改了哪里"、"A2A curl 链路已验证"
- llm-wiki：存放 "Hermes checkpoint v2 架构"、"Rohit V2 优缺点分析"
- 搭配使用：每次新 session，agentmemory 注入上下文，llm-wiki 提供知识参考

### 衰减机制与长期记忆检索

agentmemory 的衰减是**搜索排名降权**，不是从 SQLite 删除。

**三重检索通道的衰减差异**：
- **向量搜索**：衰减在这里生效，模糊语义查询三个月后可能搜不到
- **BM25**：不衰减。精确关键词永远命中
- **图遍历**：不衰减。结构关系不变

**四层管道的分层衰减**：
- 工作记忆：快（几天）
- 情景记忆：中（几周）
- 语义记忆：慢（几个月）
- 程序性记忆：极慢（几乎不衰减）

Consolidation 把被反复确认的信息往上推，衰减曲线逐步压平。

**根本局限**：consolidation 依赖"被访问次数"往上推，假定"最近被访问 = 重要"。缺失的机制：置信度应该直接压低衰减曲线（三个来源确认过的决策即使半年不访问也应衰减极慢）。

**务实分工**：agentmemory 管近期上下文（自动），wiki 管长期知识（手动、无衰减）。

### Hermes-agentmemory 集成

agentmemory 在 Hermes 上有两层接入：

**Option 1 — MCP only**（零 token 增长）：43 个 MCP 工具，agent 按需调用。
**Option 2 — Plugin**：6-hook MemoryProvider。prefetch 每次注入 ~250-500 tokens。

**关键结论**：两种模式都**不影响现有的 `memory` 工具和 Obsidian wiki**。MemoryProvider 是 Hermes 的独立抽象层，`on_memory_write()` 只在原写入后多镜像一份。唯一代价是 Option 2 的 prefetch 多消耗 token。

### LLM Provider 配置

provider 检测链：`OPENAI_API_KEY → MINIMAX_API_KEY → ANTHROPIC_API_KEY → GEMINI_API_KEY → OPENROUTER_API_KEY → noop`

**DeepSeek 接入**：PR #307 (2026-05-16 已合入) — `OPENAI_BASE_URL=https://api.deepseek.com/v1` + `OPENAI_MODEL=deepseek-chat` 直连。不配 key 则跑 noop 模式（零成本，压缩关闭，搜索正常）。

**Embedding**：默认本地 `all-MiniLM-L6-v2`（80MB，`npm install` 自动下载，CPU 推理免费）。

### Windows 部署

原生 Windows 无法直接运行 agentmemory（缺 iii-engine 二进制）。

**方案 A** — Docker（推荐）：`AGENTMEMORY_USE_DOCKER=1 npx @agentmemory/agentmemory`

**方案 B** — 手动安装 iii.exe：从 https://github.com/iii-hq/iii/releases 下载 `iii-x86_64-pc-windows-msvc.zip`，解压到 `%USERPROFILE%\.local\bin\`。

**方案 C** — MCP-only 模式（无 REST API，无 plugin hooks）：`npx @agentmemory/agentmemory mcp`

Docker 模式下首次启动需等待 iii-engine 就绪（可能超过 30s），之后前台/后台均正常。

### Hermes 凭证保护注意

Hermes 的 credential redaction 在写入 `.env` 类文件时会拦截明文 key。通过 `write_file` 工具写入的 key 会被替换为 `***`。**必须用 shell `cat` heredoc 或用户手动编辑。** 验证 key 正常用 `execute_code` 直接读取文件内容（redaction 只影响工具输出显示层，不影响实际文件内容）。

### 实际运行验证（本次会话）

Windows 10 + Docker + DeepSeek V4 实测通过：
```bash
# ~/.agentmemory/.env
OPENAI_API_KEY=sk-***key
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
EMBEDDING_PROVIDER=local
AGENTMEMORY_AUTO_COMPRESS=true
CONSOLIDATION_ENABLED=true
GRAPH_EXTRACTION_ENABLED=true
```

启动后日志确认：`Provider: openai (deepseek-chat) | Embedding provider: local (384 dims) | REST API: 128 endpoints | Triple-stream (BM25+Vector+Graph) search active`。

## 对 llm-wiki 用户的建议

1. 当前阶段（<50 页）保持 Karpathy 原版足够
2. 不要迁移到 OKF — 它是交换格式，不是知识管理引擎。需要交换时**导出** OKF，不要改成 OKF
3. 不要等待 Rohit V2 实现 — agentmemory 是存在的但它是 session memory，不是 wiki
4. V2 的洞察可逐步引入：置信度标记（利用现有 frontmatter `confidence` 字段）、自动化 lint（cron job）
5. 企业级升级不是换引擎，是给现有引擎加零件：搜索、治理、自动化，按需逐步添加
