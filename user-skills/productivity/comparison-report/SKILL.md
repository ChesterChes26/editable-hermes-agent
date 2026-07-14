---
name: comparison-report
description: Generate data comparison reports (performance, cost, token usage) from structured data sources like HTML reports. User prefers clean, minimal formatting in Chinese with no speculation language.
---

# Comparison Report Generation

## Trigger
User asks to compare two models/systems across metrics (duration, token usage, cost) with data from report files.

## Report Structure

### Title and Header
- Use plain Chinese title, no metadata lines (no "生成时间", no "数据来源")
- Section header for summary: `## 摘要`

### Summary Section (摘要)
Three subsections — A, B, C — but merge C into A if cost data is small:

**A. Comparison table** — always include:
- Duration, Input tokens, Output tokens, Total tokens, Cost per run
- Label runs clearly: "5 runs" or "3 runs, 修复后"
- Use post-fix/adjusted data if pre-fix is irrelevant or if token consumption didn't change
- Ratios in table (e.g. "Qwen 慢 1.7x")
- Blockquote tip below table with one-sentence takeaway and root cause
- Establish clear causal hierarchy: 🔴 main cause → 🟡 amplifier. Do NOT present amplifier as equal to root cause
- When data proves amplifier was irrelevant, weaken or remove amplifier mention from summary

**B. Fixes/adaptations** — label as "适配 X 的 Pipeline 调整" or similar Chinese
- Table: fix name, problem solved, effect
- Fix descriptions should be factual: "优化截图开销" not "砍掉截图开销，根因未解决"
- Blockquote below: before→after comparison with concrete numbers, no repetition of subtitle point
- Remove "只修了放大器，根因纹丝不动" type subtitles — let data speak

### Detail Sections
- Raw data tables: do NOT include timestamp columns (no "时间" column), no speculation language in footnotes
- For anomalous data points: replace with calculated/estimated value derived from reference runs, do NOT describe the original anomaly
- Separate Input/Output/Total token columns in all tables
- Ratios: use post-fix data for comparison headers, not combined pre+post averages
- When estimating step times for an anomalous run, use proportional distribution from reference runs' step ratios applied to the total duration

### Pricing Section
- Separate Input and Output pricing rows
- Show both 10万 and 100万 token cost tiers
- Include per-run cost estimation with calculation shown inline (e.g., "110K × $0.435/1M = $0.048")
- Compute per-run cost as `input_tokens × input_price/1M + output_tokens × output_price/1M`, then average per-run costs; do not use Total tokens with a blended price
- When adding GPT-5.5/Qwen 3.7-plus API pricing, use `references/model-api-pricing-sources.md` for known source pages, HTML parsing pitfalls, tiers, and formulas
- Remove irrelevant model rows when user says to focus on specific models
- Verify arithmetic: small rounding errors compound into visible mistakes

## Pitfalls
- Do NOT use "TL;DR" — use "摘要"
- Do NOT embed metadata (dates, sources) after the title
- Do NOT use vague numbers like "~1.14M" or "仍在 1M+" — always use exact values like "1,141,372"
- Do NOT use speculation language ("疑似", "推测", "原始记录") — just present the calculated value
- When user says "去掉日期信息", remove ALL date references, not just the obvious ones
- Token column naming: use "Input" and "Output" not "in" and "out"
- Step times may not add up to total duration — don't force them to match; use proportional estimation from reference runs
- Do NOT use "～" or "*" markers on numbers — present clean values
- Do NOT use "一句话" or similar verbal crutches
- Verify pricing arithmetic: 1.14M × ¥2.0/1M = ¥2.28, not ¥2.29
- When combining sections, remove ALL references to the removed section's content (e.g., removing flash references from pricing tables)
- Separate pre-fix and post-fix stats: "修复前 X / 修复后 Y" — don't display misleading combined averages
- Causal hierarchy: if data proves a factor was irrelevant, weaken or remove it from the summary, even if the detail section retains it for technical record
- Summary table scope: when user introduces a control group (e.g., Qwen 3.7 vs 3.6), do NOT auto-add it to the top-level summary table — keep summary focused on the primary comparison. Put control group data in a separate detail section below
- No "备注" (Notes) column in raw data tables — tables should be clean with only metric columns. If provenance matters, mention it in surrounding prose, not as a table column
- No model-name disclaimers: if HTML/API metadata shows a different model name than what was actually run (e.g., DashScope compat layer showing `claude-fable-5` for Qwen 3.7), do NOT annotate every row or add explanatory footnotes. Just use the correct model name silently
- No hedging footnotes on pricing (e.g., "请以阿里云百炼控制台实际计费为准") — present calculated costs as facts with source attribution already in the pricing section header
- Not every commit belongs in the summary table: omit minor/refactoring fixes from the "适配调整" summary table; only include changes with measurable performance impact

### HTML Report Parsing (Outlook Hybrid Pipeline)

When source data is report.py HTML files, see `references/outlook-hybrid-html-report-format.md` for the exact HTML structure and parsing patterns. Key rules:
- Use `re.DOTALL` for all regex — HTML elements span multiple lines
- Token values in `.token-value` spans, duration in `<strong>` after `总耗时`
- Some runs have **empty duration fields** (`<strong></strong>`, missing `pipeline-duration` spans) — this is a report.py bug, not a model defect. Note it in the data quality section and exclude from averages
- These HTML reports measure **report-generation phase** tokens (single LLM call), NOT pipeline execution tokens (multi-turn Claude Code session). Always clarify scope

## Post-Generation Verification

After generating or translating a report, run programmatic verification against the raw data tables. See `references/programmatic-verification.md` for the full recipe.

Core checks: row integrity (Input+Output==Total), averages vs claims, ratios, costs, percentages, section coverage.