# Model API Pricing Source Notes

Use this when adding API cost comparisons to model/run reports.

## Azure OpenAI pricing page

Source: `https://azure.microsoft.com/en-us/pricing/details/azure-openai/`

Pitfall: the visible HTML may show `$-` inside `<span class='price-value'>`; the real numeric price is embedded in the sibling `data-amount` JSON on `<span class='price-data'>`.

For GPT-5.5 Global standard processing, the page has:
- Input: `$5.00 / 1M tokens`
- Cached Input: `$0.50 / 1M tokens`
- Output: `$30.00 / 1M tokens`
- Priority Processing: Input `$12.50`, Cached Input `$1.25`, Output `$75.00` per 1M tokens

For standard API cost comparisons, use standard processing unless the user explicitly asks for Priority Processing.

## Alibaba Cloud Model Studio pricing page

Source: `https://www.alibabacloud.com/help/en/model-studio/model-pricing`

For `qwen3.7-plus` International pricing:
- `0<Token≤256K`: Input `$0.40 / 1M tokens`; Output `$1.60 / 1M tokens` in both Non-Thinking and Thinking modes
- `256K<Token≤1M`: Input `$1.20 / 1M tokens`; Output `$4.80 / 1M tokens` in both modes

Choose the tier from the request's input-token count. For report-generation runs whose input is below 256K, use the 0<Token≤256K tier.

## Cost formula

Compute per-run API cost from raw rows, then average the costs:

```text
cost = input_tokens × input_price_per_1M / 1,000,000
     + output_tokens × output_price_per_1M / 1,000,000
```

Do not compute cost from Total tokens with a single blended price. Input and Output prices differ.

Recommended report additions:
- Summary table row: `平均 API cost / run`
- Pricing section with Input/Output price rows, 100K token cost, 1M token cost
- Average cost table showing inline formula
- Per-run cost table when raw run rows are present
