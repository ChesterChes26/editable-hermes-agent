# Wiki 浅/深分离（Guide / Reference Split）

> 完整方法论参考。基于 2026-06-25 对话深度讨论。

## 问题

wiki 文档信息密度过高时，agent 读取会产生两个问题：

1. **context window 注意力分散**：关键执行约束（"system prompt 不能改"）和历史背景（"ReAct 发明于 2022"）被平等对待，agent 可能错过关键约束
2. **agentmemory 向量检索精度下降**：当 wiki 内容以 session 观测形式进入 agentmemory 时，高密度文档的 embedding 包含过多维度，稀释了关键信号的精度

## 理论基础：记忆模型类比

受人类记忆中枢启发——短期/长期 × 浅/深的四象限模型，对应 agentmemory 和 wiki 的压缩链完全对称：

```
人类记忆           agentmemory（短记忆）      wiki（长记忆）
─────────          ──────────────────        ────────────
短/深（全量）      observations               raw/ 源材料
    ↓ 压缩             ↓ 压缩                    ↓ 提取
短/浅（摘要）      episodic                   技术版（深/长）← 有源码引用和对比表
    ↓ 巩固             ↓ 巩固                    ↓ 压缩
长/浅（规则）      semantic / procedural      指南版（浅/长）← 纯约束 + 因果链
```

核心洞察：**大脑不会每次回忆都激活全部相关神经元——先激活稀疏的 summary 模式，不够用时才向下递归。** wiki 应遵循同一策略。

## 两层定义

### 指南版（前身为"人话版"）

**本质**：可执行的约束，不是通俗化翻译。

**内容**：
- 所有 MUST / MUST NOT 约束（遗漏会直接导致执行失败）
- 每条约束的最小必要因果链（为什么是 MUST / MUST NOT，边界在哪）
- 一个典型例子把约束串起来

**不应包含**：
- 历史背景（"ReAct 发明于 2022"）——不影响执行，占注意力
- 计费计算（"节省 ~95%"）——验证证据，不是操作约束
- 源码行号（"conversation_loop.py:589"）——需要时去技术版查
- 对比表（"Anthropic vs DeepSeek"）——需要时去技术版查

**预期压缩率**：技术版 200 行 → 指南版 40-60 行（约 70% 压缩率）

**质量标准**：一个没读过技术版的人，读完指南版后，能否准确预测 agent 在 80% 场景下的行为？

### 技术版（前身为"技术版"）

**本质**：可验证的证据，保留完整的溯源链。

**内容**：源码引用、计费计算、对比表、历史背景、边界情况的详细分析——所有指南版不包含的验证材料。

**和指南版的关系**：技术版 → 指南版是**可审计的映射**，不是两篇独立文章。指南版的每条约束都能在技术版里找到对应的源码引用做证据。

## 四步构造法（自下而上）

从技术版（已有）出发，构造指南版：

### 第 1 步：提取所有 MUST / MUST NOT 约束

从技术版中提取所有能写成规则的执行约束。不是总结内容，是提取命令式规则：

```
从 hermes-loop-and-cache 技术版提取：
- MUST NOT 修改 system prompt（缓存全废）
- MUST 把 memory 注入塞进 user message，不能动 system prompt
- MUST 只追加 messages，不修改旧条目
- MUST 用 api_messages（深拷贝）调 API，不污染持久化 messages
```

### 第 2 步：补充最小必要因果链

对每条约束，给出一句话因果解释 + 边界说明：

```
- MUST NOT 修改 system prompt
  原因：改一次 → LLM 服务端缓存全废 → 后续每轮重新计费
  边界：这是硬约束。没有例外。改一个字后果一样。
```

### 第 3 步：用一个典型例子串起来

展示约束在真实场景中长什么样：

```
场景：agent 需要把 memory 内容注入到对话中

错误做法：直接拼到 system prompt 后面
  → system prompt 变了 → 缓存命中率归零

正确做法：塞进 user message 的 <agentmemory-context> 块里
  → system prompt 不变 → 缓存不受影响
```

### 第 4 步：交叉验证

回到技术版，逐条核对：指南版有没有漏掉任何会导致执行失败的约束？漏了就补，不是"差不多就行"。

## 渐进式读取策略

agent 按以下顺序消费 wiki 文档：

```
阶段 1（执行）：读指南版 → 基于约束行动
阶段 2（eval）：agent 自审 + 用户 review → 判断结果对不对
阶段 3（纠正）：不对 → 读技术版深入理解 → 修正
```

**回退触发条件**（不是 LLM 自检——Hermes 的 Loop 没有 eval 分支）：
- 工具返回 error / 空结果
- 用户中途纠正
- 同一操作连续重试 3+ 次

## wiki-next 目录结构

在现有 wiki 同层创建 `wiki-next/`，采用顶层分叉 + 拍平 T0-T3：

```
wiki-next/
├── sulan(速览)/           ← 指南版（可执行约束）
│   ├── concepts/
│   │   ├── hermes/
│   │   │   ├── hermes-loop-and-cache.md
│   │   │   ├── hermes-cron-scheduler.md
│   │   │   └── ...
│   │   └── agentmemory/
│   ├── comparisons/
│   └── queries/
├── xiangjie(详解)/        ← 技术版（可验证证据，路径后缀与 sulan 完全一致）
│   ├── concepts/
│   │   ├── hermes/
│   │   │   ├── hermes-loop-and-cache.md
│   │   │   └── ...
│   │   └── agentmemory/
│   └── comparisons/
├── raw/                   ← 共享，不拆分
├── SCHEMA.md
├── index.md
└── log.md
```

**设计理由**：
- 顶层分叉让 agent 检索路径最直接：`sulan/concepts/hermes/X.md` → `../xiangjie/concepts/hermes/X.md`
- 拍平 T0-T3 因为两层分层（深度 + 基础性）对 agent 太复杂
- `sulan/xiangjie` 和 `concepts` 一样走拼音 + 中文风格
- `raw/` 不拆——源材料没有浅/深之分，它本身就是最底层

**命名备选**：`sulan(速览)/xiangjie(详解)` 是当前推荐。备选方案：
- `guide(指南)/reference(参考)` —— 英文前缀，自解释最强但与拼音风格不一致
- `guize(规则)/yiju(依据)` —— 描述内容本质，但"规则/依据"不是公认术语对
- `keyong(可用)/kekao(可靠)` —— 状态隐喻，抽象，自解释性弱

## 迁移策略

渐进式，从 wiki 逐篇迁移到 wiki-next：
1. 技术版先照搬现有 wiki 文档（深度不变）
2. 指南版逐步编写（新写，不是压缩）
3. 不需要一次性完成全量拆分
4. 试验阶段不 commit / push
