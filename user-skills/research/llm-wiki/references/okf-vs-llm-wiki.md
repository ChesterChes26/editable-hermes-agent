# OKF vs LLM Wiki 模式对比

Google Cloud Platform 的 Open Knowledge Format (OKF) v0.1 与
Karpathy/Rohit 的 LLM Wiki 模式在设计上的对比分析。

## OKF 来源

- Repo: https://github.com/GoogleCloudPlatform/knowledge-catalog
- Spec: `okf/SPEC.md`
- 设计目标: 通用、厂商中立的**数据交换格式**
- 物理层: 目录 + markdown + YAML frontmatter（与 LLM Wiki 完全一致）

## 核心分歧

### 要不要类型化关系

| | OKF | Rohit V2 |
|---|-----|----------|
| 链接语义 | 无类型 — §5.3: "关系类型由周围文字传达，不由链接本身" | 六种类型化边: uses/depends on/contradicts/caused/fixed/supersedes |
| 设计理由 | 交换格式不需要规定关系语义，留给消费者解释 | 图遍历查询需要类型化边，否则无法做精确推理 |

### 要不要知识生命周期

OKF 完全没有置信度、衰减、取代、记忆管道。因为它只是格式规范，不管内容如何演化。
Rohit V2 的核心创新就是生命周期管理。

### 设计目标

- OKF: "最小可互操作子集" — 只规定 type 这一个必需 frontmatter 字段
- Rohit V2: "最大认知深度" — 完整置信度+图谱+自动化+质量自愈

## 共享的设计（都继承自 Karpathy 原版）

- Markdown 文件 + YAML frontmatter
- 目录层级组织
- index.md + log.md
- 跨文件链接
- raw/ 源材料目录（OKF 无，但有 references/）

## 时间线

- Karpathy LLM Wiki gist: 2026-04-04
- Rohit V2 fork: 2026-04-06
- OKF spec v0.1: ~2026-05（示例中最早 timestamp 为 2026-05-28）

OKF spec §10 明确承认受到 LLM wiki 仓库模式影响。

## 一句话

OKF 和 Rohit V2 跑在同一个物理介质上（markdown + frontmatter + 目录），但往相反方向走：
OKF 追求最小互操作协议（数据交换），Rohit V2 追求最大认知深度（agent 内部推理）。
