# 深度参考

## OKF (Open Knowledge Format) v0.1

Google Cloud Platform 的知识交换格式规范。仓库: https://github.com/GoogleCloudPlatform/knowledge-catalog

核心设计:
- 目录 + markdown + YAML frontmatter
- 必需字段: 只有 `type`
- 链接: 标准 markdown link，无权类型化
- 目标: 最小互操作协议，跨系统交换

与 Rohit V2 的核心分歧: OKF 说链接语义由 prose 传达（"The specific kind of relationship is conveyed by the surrounding prose, not by the link itself"），Rohit V2 说链接必须有类型（uses/depends on/contradicts 等）。

不构成升级链——OKF 是交换格式，agentmemory 是 session 记忆，llm-wiki 是 curated 知识库。

## agentmemory PR #307

- 链接: https://github.com/rohitg00/agentmemory/pull/307
- 状态: 已合入 (2026-05-16)
- 作者: fatinghenji
- 内容: 让 OpenAI provider 通道从"只能 embedding"变成"也能 chat completion"
- 顺带支持: DeepSeek, SiliconFlow, vLLM, LM Studio, Ollama (via /v1 协议)

配置:
```bash
OPENAI_API_KEY=***
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-v4-flash
```

## DeepSeek 定价 (2026-06-22)

| 模型 | 输入 cache hit | 输入 cache miss | 输出 |
|------|---------------|----------------|------|
| deepseek-v4-flash | $0.0028/M | $0.14/M | $0.28/M |
| deepseek-v4-pro | $0.003625/M | $0.435/M | $0.87/M |

注意: `deepseek-chat` 和 `deepseek-reasoner` 将于 2026/07/24 废弃，映射到 flash 的非思考/思考模式。

## 相关 wiki 页面

- concepts(概念)/agent-knowledge-trifecta-wiki-v2-okf-agentmemory.md — 三者对比与选型分析
- concepts(概念)/llm-wiki-v2-rohit-ghumare.md — V2 原文分析
- raw(源材料)/transcripts/2026-06-22-llm-wiki-v2-okf-agentmemory.md — 对话源材料
