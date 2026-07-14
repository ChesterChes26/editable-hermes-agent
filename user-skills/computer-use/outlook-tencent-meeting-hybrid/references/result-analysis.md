# 从 report.html 提取运行指标

## 场景

需要分析 snapshots 目录下多次运行的耗时、Token、模型差异。

## HTML 结构

report.html 的关键数据位于文件尾部（~900行之后）：

```html
<div class="model-info">LLM Model: <strong>deepseek-v4-pro</strong></div>

<div class="card">
  <div class="card-title">Token Usage</div>
  <div class="token-grid">
    <div class="token-value">161,518</div>  <!-- Input -->
    <div class="token-value">10,350</div>   <!-- Output -->
    <div class="token-value">171,868</div>  <!-- Total -->
  </div>
  <div class="meta-bar">
    <span>Duration</span>
    <strong>2m 29s</strong>
  </div>
</div>

<!-- Per-step durations -->
<span class="pipeline-step-name">Step 1</span>
<span class="pipeline-duration">&lt;1s</span>

<span class="pipeline-step-name">Step 2</span>
<span class="pipeline-duration">41s</span>
```

## 提取正则

```python
model   = re.search(r'LLM Model:\s*<strong>([^<]+)</strong>', html)
dur     = re.search(r'<span>Duration</span>\s*<strong>([^<]+)</strong>', html)
input_t = re.search(r'Input</div>\s*<div class="token-value">([\d,]+)</div>', html)
output_t= re.search(r'Output</div>\s*<div class="token-value">([\d,]+)</div>', html)
total_t = re.search(r'Total</div>\s*<div class="token-value">([\d,]+)</div>', html)
steps   = re.findall(r'<span class="pipeline-step-name">(Step \d+)</span>.*?<span class="pipeline-duration">([^<]+)</span>', html, re.DOTALL)
```

## 按模型分组统计

按 modification time >= 目标日期过滤 snapshots 子目录，遍历 report.html，按 model 字段分组计算平均值。

## 注意事项

- 报告用 **Total** tokens，但分析时建议同时提取 Input/Output 分列——Input/Output 比值暴露问题本质（如缓存失效时 Input 远大于 Output）
- Duration 格式 `2m 29s` 或 `<1s`，需 parse 为秒数再做统计
- 早期 snapshot（7.6 之前）可能缺少 model-info 字段
- 修改日期用文件夹 mtime，非 report.html mtime
- `_temp/` 目录也可能包含补充的 report.html（通过 git pull 获取），解析时合并两个来源

## Git 改动分析

```bash
# 提取指定日期范围的 commits（注意 UTC 时区问题）
git log --all --oneline --format="%h %ad %an %s" --date=short --after="YYYY-MM-DD" --before="YYYY-MM-DD+1"

# 用本地时间格式避免 UTC 偏移
git log --all --oneline --format="%h %ad %an %s" --date=format:"%m-%d %H:%M" -30

# 区间 diff 统计
git diff <base>..<head> --stat
```

commit 分类规则：
- **通用 fix**（如 duration 计算修正）→ 标注 `属通用 fix，非 XX 相关`
- **问题特定 fix** → 只列与当前分析直接相关的部分
- 每个 fix 必须附带原因说明

## 分析方法论

### 根因 vs 放大器

分析性能问题时，**必须区分根因和放大器**，不能混为一谈：

- **根因**：导致问题的结构性原因，修复它问题解决
- **放大器**：加重问题的因素，修复它只能缓解症状

在报告中应明确标注每个发现属于哪一层，并验证：修复放大器后根因指标是否变化？（如果不变化，说明确实是根因 vs 放大器关系。）

### 原因驱动叙事

每个 fix/change 必须附带 **"原因"** 栏，解释为什么需要这个修改。不要只列"做了什么"，要列"为什么做"。格式：

```
> **原因:** <为什么这个改动是必要的>
```

### 归因纪律

- **通用 fix**（如 duration 计算修正）标注为通用，不要归入特定问题的修复列表
- **问题特定 fix** 只列出与当前分析问题直接相关的部分
- 如果一个 commit 包含多种改动，分开陈述，不要一股脑全列

### 摘要结构

分析报告应在顶部放置可扫描的摘要（用中文 `## 摘要`，不用 `TL;DR`），每条摘要配 **一句话点睛**：
- A. 数据对比（数字 + 比值）
- B. 修复总结（做了什么 + 效果 + 局限）
- C. 成本/定价（单价 + 实际消耗 + 对比）

详细数据在下方保持不变。

### 报告撰写注意事项

1. **中文优先**：标题用中文（`摘要` 而非 `TL;DR`），用户面向中文读者
2. **精确数字**：避免模糊引用如 `~1.14M`，使用具体值如 `1,141,372`。模糊数只在首次概述时用一次
3. **因果链前置**：根因放在放大器前面，表格中主因行在前
4. **文件名有意义**：如 `DeepSeek-Qwen_Compare_Summary.md`，不用 `DURATION_AND_PRICING_REPORT.md`
5. **每个 fix 附原因**：格式 `> **原因:** <为什么需要这个修改>`，不要只列做了什么
6. **通用 fix 标注**：非问题特定的修复标注为 `属通用 fix，非 XX 相关`
7. **成本并入对比表**：定价信息不要单独成节（避免 C 节独立），在对比摘要表中加一行 `单次 Pipeline 成本` 即可
8. **去掉无关模型**：如果某模型不在分析范围内（如 deepseek-v4-flash 未参与对比测试），全文移除其引用，保持报告聚焦
9. **弱化被证伪的因子**：修复后数据证明某因子影响不大时（如 SOM→AX 修复后 Input token 不变），摘要中应弱化该因子，将叙事聚焦到被数据证实的根因上。不要保留已被数据推翻的"双重叠加"叙事
10. **标题去噪**：去掉括号内的日期、路径等辅助信息（如 `(07-09, \`_temp/\`)`），标题保持简洁。技术性 workflow 步骤名改为可读描述（如 `Step 0c COM 注册` → `要求使用 COM 注册`）
11. **Review 后验证**：报告完成后 spawn subagent 做 final review，检查数据一致性、定价计算、残留引用、因果链完整性。review 发现的错误必须修正后再交付

### 成本计算

```python
# DeepSeek (USD, per 1M tokens)
# 来源: https://api-docs.deepseek.com/quick_start/pricing
cost = input_tokens / 1_000_000 * input_price + output_tokens / 1_000_000 * output_price
# deepseek-v4-pro: input=$0.435/1M, output=$0.87/1M

# Qwen (CNY, per 1M tokens)
# 来源: https://help.aliyun.com/zh/model-studio/models (百炼 Model Studio)
cost = input_tokens / 1_000_000 * input_price + output_tokens / 1_000_000 * output_price
# qwen3.6-flash: input=¥2.0/1M, output=¥6.0/1M
```

> 注意：Qwen 通过 DashScope Anthropic 兼容层接入时，output token 极少（~2K），成本几乎全来自 input。验证计算时用精确值，不用约数叠加导致偏差（如 ¥2.28 + ¥0.01 ≠ ¥2.29 而是 ¥2.28 + ¥0.0144 ≈ ¥2.29，取决于舍入策略）。

## 异常数据处理

### 单步耗时异常

当某个 step 的耗时明显异常时（如 Step 4 记录为 44m56s 而其他 run 仅 55-59s），不要保留异常值或添加冗长的推测脚注：

1. 用同组其他 run 的**比例**推算正常值（如取相邻 run 的 step/总时长比例，应用到当前 run 的总时长）
2. 直接在表格中填入推算值，**不加脚注、不加 `~`、不加 `*` 标记**
3. 如果计算值落在合理范围内，它就是正常值——不需要解释"为什么改了"

### 总 duration 不可用时

如果总 duration 与 step 耗时之和差距过大（步骤耗时无法简单相加），优先用总 duration 反推各 step。例：

```
# Run 总 229s，Steps 2/4/5 取相邻 run 比例推算后，Step 3 = 总 - 其余
# 如果结果为负，取 <1s（下限）
```

## 表格格式

- 去掉独立的"时间"列（日期信息分散读者注意力，且不影响性能对比）
- 用"备注"列标注修复前/后，而非在标题或脚注中说明
- 中英文版本数据完全一致，仅翻译标签和说明文字

## 双语输出

完整报告生成后，在根目录生成一份英文版（`*_EN.md`），结构、数据与中文版完全一致，仅翻译所有标签、标题和说明文字。英文版中：
- 技术名词保留原文（SOM、AX、ROT、COM 等）
- 货币符号不变（¥、$）
- commit message 保留原文
