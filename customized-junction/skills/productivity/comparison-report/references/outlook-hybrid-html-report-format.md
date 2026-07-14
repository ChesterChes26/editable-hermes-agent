# Outlook Hybrid Pipeline HTML Report Format

The pipeline's `report.py` generates HTML reports under `snapshots/<run-id>/report.html`.

## HTML Structure

### Token Values
```html
<div class="token-card token-card--input">
    <div class="token-value">75,335</div>   <!-- Input tokens -->
</div>
<div class="token-card token-card--output">
    <div class="token-value">9,252</div>    <!-- Output tokens -->
</div>
<div class="token-card token-card--total">
    <div class="token-value">84,587</div>   <!-- Total tokens -->
</div>
```

### Total Duration
```html
<span>总耗时</span>
<strong>4m 9s</strong>    <!-- May be EMPTY: <strong></strong> -->
```

### Step Durations
```html
<span class="pipeline-step-name">Step 2</span>
<span class="pipeline-duration">23s</span>    <!-- May be MISSING entirely -->
```

### Model Name
```html
<div class="model-info">
    运行模型: <strong>deepseek-v4-pro</strong>
</div>
```

## Parsing Patterns

Python regex with `re.DOTALL` flag required because HTML elements span multiple lines:

```python
import re

# Tokens: find all in order (input, output, total)
token_vals = re.findall(r'token-value[^>]*>\s*([\d,]+)\s*<', content)
inp = int(token_vals[0].replace(',',''))

# Duration (DOTALL needed)
dur_m = re.search(r'总耗时.*?<strong>(.*?)</strong>', content, re.DOTALL)

# Steps (DOTALL needed)
steps = re.findall(r'Step\s*(\d+).*?pipeline-duration[^>]*>\s*(.*?)\s*</span>', content, re.DOTALL)
```

## Known Data Quality Issues

### Empty/Missing Duration Fields

`report.py` has a bug where some runs produce:
- Empty `<strong></strong>` for total duration
- Missing `pipeline-duration` spans entirely for some steps
- Steps marked PASS but no timing data

This is a **report.py bug** (likely snapshot data incompleteness), NOT a model defect. When encountered:
1. Note the missing data in the report's data quality section
2. Exclude affected runs from duration averages
3. Do NOT attribute missing durations to model performance differences

### Token Scope Confusion

These HTML reports capture **report-generation phase** tokens (report.py's single LLM call), NOT the full pipeline execution tokens (Claude Code multi-turn session). The two differ by orders of magnitude:
- Pipeline execution (Claude Code session): ~100K–1M tokens
- Report generation (report.py): ~60K–250K tokens

Always clarify which phase is being measured.
