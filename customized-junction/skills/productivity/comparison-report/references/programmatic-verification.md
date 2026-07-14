# Programmatic Report Verification

Use after generating, translating, or editing a data-heavy comparison report. Parse the report's own raw data tables and recompute every derived statistic — don't eyeball it.

## Recipe

1. **Parse raw data tables** from the markdown using regex on table rows:
   ```python
   row_re = re.compile(r'\|\s*(\d+)\s*\|\s*([\dms ]+?)\s*\|\s*([\d,]+)\s*\|\s*([\d,]+)\s*\|\s*([\d,]+)\s*\|')
   ```

2. **Check row integrity**: `Input + Output == Total` for every raw data row.

3. **Recompute averages** from raw data, compare against published averages (allow ±1 rounding tolerance).

4. **Recompute ratios** using precise (unrounded) averages, round to same decimal places as report claims.

5. **Recompute costs**: apply pricing × token counts, then cross-currency rate for cost ratios.

6. **Recompute percentages** (fix effectiveness, version comparisons). Watch for rounding-chain artifacts.

## Pitfalls

### Rounding-chain artifacts
When a report rounds intermediate values before computing percentages, the published percentage may differ by ±1 point from the precise computation. Example:

- Precise: (212.8 - 289.5) / 289.5 = -26.49% → Python `round()` gives -26
- Report: uses rounded 213 and 290 → (213-290)/290 = -26.55% → rounds to -27

Both are defensible. Accept either when the precise value is within 0.06 of a rounding boundary.

### Exchange rate sensitivity
Cross-currency cost ratios (e.g., ¥2.15 / $0.056×7.2) are sensitive to both the token cost rounding AND the exchange rate. A claimed ratio of 5.1x vs computed 5.2x may be a real error or a legitimate rate difference. Flag for review rather than auto-rejecting.

### Wrong rounding precision in verification code
When checking costs, match the precision:
- Dollar costs: `round(v, 3)` for values like 0.056
- RMB costs: `round(v, 2)` for values like 2.15
- Ratios: `round(v, 1)` for values like 5.3

Using `round(v, 2)` on a ratio of 5.306 gives 5.31 ≠ 5.3 — this is a verification-script bug, not a report error.

## Verification Output Convention

Script should print summary like:
```
PASS: 55/55 checks
```
with per-category breakdown. Temp script written to `%TEMP%/hermes-verify-*.py`, executed, and removed.
