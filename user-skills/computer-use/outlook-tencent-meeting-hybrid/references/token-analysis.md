# Token 消耗分析 — Qwen vs DeepSeek

## Qwen 3.6-plus Token 暴涨根因

Qwen 通过阿里 DashScope 的 **Anthropic 兼容层** 接入，非原生 API：

```json
"ANTHROPIC_BASE_URL": "https://dashscope.aliyuncs.com/apps/anthropic"
"ANTHROPIC_MODEL": "qwen3.6-plus"
```

### 问题链条

Claude Code 发送 `anthropic-beta: prompt-caching-2024-07-31` header：

1. DashScope 兼容层**接受** caching header，创建缓存（cache_creation 从 3K → 158K）
2. 流式续片（6-token pieces）能读缓存（cache_read 正常）
3. **主 prompt 永远不读缓存** — 兼容层对主 prompt 的 `cache_control` block 处理有问题

结果：每次调用重新发送完整 system prompt + skill 内容（~150K tokens）。

### 实测数据（7.6-7.8）

| 模型 | 平均 Token | 平均耗时 | 缓存状态 |
|------|-----------|---------|---------|
| deepseek-v4-pro | 119,895 | 2m 6s | 100% 生效 |
| qwen3.6-plus | 1,011,662 | 4m 50s | 仅流式续片命中 |
| glm-5-turbo | 160,713 | 2m 10s | 波动大 |

Qwen Token 消耗是 DeepSeek 的 **8.4 倍**。

### 改进方向

1. **换接入方式** — 走 Qwen 原生 API，不用 Anthropic 兼容层。但原生 API 不一定支持 Anthropic 风格 prompt caching
2. **换模型** — DeepSeek 同场景缓存 100% 生效
3. **查 DashScope 文档** — 可能有参数/header 修复缓存行为

## 根因 vs 放大器（分析框架）

Qwen Token 暴涨有**两层原因，必须区分主次**：

| 层级 | 原因 | 每次浪费 | 性质 | 修复方式 |
|------|------|---------|------|---------|
| 🔴 **主因** | DashScope Anthropic 兼容层 prompt caching 对主 prompt 失效 | ~150K/次 | 结构性问题，DashScope bug | 换接入方式/换模型 |
| 🟡 **放大器** | Qwen 默认 capture mode 是 SOM（DeepSeek 默认 AX） | ~130K/次 | 默认配置差异 | `capture_mode="ax"` |

**分析时必须将两者分开陈述**，不能混为一谈。修复放大器不会改善主因——7月9日修复后验证数据证明了这一点。

## Capture Mode 默认行为差异

不同模型在 cua-driver 的 `get_window_state` 中**默认 capture mode 不同**：

| 模型 | 默认 mode | Token/次 | 备注 |
|------|----------|---------|------|
| deepseek-v4-pro | `ax` | ~10K | 仅 UIA 树，无截图 |
| qwen3.6-plus | `som` | ~130K | 截图 + UIA 树叠加 |

**教训：切换模型时必须显式指定 `capture_mode="ax"`，不要依赖默认值。** 默认值因模型而异，且 `include_screenshot=false` 是无效参数（cua-driver MCP 中不存在），会导致静默回退到 daemon 默认。

## Token 预算优化（7月8日实施）

- Iron Rule #7: 截图 PNG 仅用于报告，禁止 Read；验证用 `get_window_state(capture_mode="ax")` 省 ~100K+ tokens/次
- Pitfall #24: 默认 get_window_state 含 base64 截图 ~130K tokens，验证时用 ax 模式
- 参数修正: `include_screenshot=false`（无效）→ `capture_mode="ax"`（正式参数）

## 修复效果验证（7月9日，3 runs）

| 指标 | 修复前 (2 runs) | 修复后 (3 runs) | 说明 |
|------|----------------|-----------------|------|
| 平均耗时 | 290s (4m50s) | 217s (3m37s) | -25%（截图开销消除） |
| 平均 Input | 1,009,361 | 1,141,372 | 无改善（根因未触及） |
| 平均 Total | 1,011,662 | 1,143,744 | 无改善（根因未触及） |

> **Input token 不降反升——证实 DashScope 缓存失效才是主因，capture mode 只是放大器。**

## 成本参照（2026-07 当前）

| 模型 | Input 单价 | Output 单价 | 来源 |
|------|-----------|------------|------|
| deepseek-v4-pro | $0.435/1M | $0.87/1M | api.deepseek.com |
| deepseek-v4-flash | $0.14/1M | $0.28/1M | api.deepseek.com |
| qwen3.6-flash (百炼) | ¥2.0/1M | ¥6.0/1M | help.aliyun.com |

单次 Pipeline 参考：DeepSeek v4-pro ~¥0.40 vs Qwen ~¥2.28（缓存失效致 input 膨胀 9.8x，即使 Qwen 单价更低总成本仍高 5.7x）。计算时注意 input/output 分开算，不要混用 total。
