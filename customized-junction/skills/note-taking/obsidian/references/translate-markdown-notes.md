# Translating Structured Markdown Notes

When translating large Obsidian markdown notes (e.g., bilingual reports), use this approach to ensure structure preservation and verifiable completeness.

## Workflow

1. **Read source in chunks** — Large files (>500 lines) must be read via `read_file` with `offset` and `limit`. Read 200-line chunks in parallel for efficiency.

2. **Plan translations before writing** — Scan all item titles and craft natural target-language equivalents mentally before committing. Titles should be **descriptive translations**, not literal word-for-word.

3. **Write the entire file in one `write_file` call** — This avoids patch ordering bugs and ensures atomic output. Use the full source structure as a template.

## Structure Preservation Checklist

Every translated markdown note MUST preserve:

| Element | Rule |
|---------|------|
| Headers (`#`, `##`) | Translate text, keep hierarchy |
| TOC with anchor links | `[Title](#item-N)` — translate title, keep anchor ID |
| Item numbering | `1.`, `2.`, … unchanged |
| Scores | `⭐️ X.X/10` — keep numeric values |
| URLs | All `http(s)://` links unchanged |
| Source attribution lines | e.g., `hackernews · user · Jun 25, 14:19` — keep dates, translate labels if needed |
| Collapsible sections | `<details><summary>…</summary>` — translate summary label, keep HTML structure |
| Tags | `#tag1`, `#tag2` … unchanged |
| Blockquotes | `>` — translate content |

## Section Header Translations

Standard Obsidian note section headers (English → Chinese):

| English | Chinese |
|---------|---------|
| `**Background**` | `**背景**` |
| `**Discussion**` | `**讨论**` |
| `**Tags**` | `**标签**` |
| `References` (inside `<summary>`) | `参考来源` |

## Verification

After translation, verify with a Python script that cross-references source and target files:

```python
import re

def scan(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return {
        "items":     len(re.findall(r'<a id="item-\d+"></a>', text)),
        "headings":  len(re.findall(r"^## \[", text, re.MULTILINE)),
        "toc":       len(re.findall(r"^\d+\. \[", text, re.MULTILINE)),
        "scores":    re.findall(r"⭐️ (\d+\.\d+)/10", text),
        "details":   len(re.findall(r"<details>", text)),
        "urls":      len(re.findall(r"https?://", text)),
        "tags":      len(re.findall(r"\*\*(Tags|标签)\*\*", text)),
        "bg":        len(re.findall(r"\*\*(Background|背景)\*\*", text)),
        "disc":      len(re.findall(r"\*\*(Discussion|讨论)\*\*", text)),
        "lines":     len(text.splitlines()),
    }

en = scan("source-en.md")
zh = scan("target-zh.md")

for field in ["items", "headings", "toc", "details", "tags", "bg", "disc"]:
    assert zh[field] == en[field], f"Mismatch: {field}"

assert len(zh["scores"]) == len(en["scores"])
assert sum(float(s) for s in zh["scores"]) == sum(float(s) for s in en["scores"])

# Verify no English headers leaked into Chinese output
for tag in ["**Background**", "**Discussion**", "**Tags**"]:
    assert tag not in open("target-zh.md", encoding="utf-8").read(), f"Leaked: {tag}"

print("PASS")
```

The script checks: item counts, heading counts, TOC entries, `<details>` blocks, URL count, tag blocks, background blocks, discussion blocks, score sums, and English header leakage.

## Pitfalls

- **Don't translate anchor IDs** — `#item-1` must stay as-is for TOC links to work
- **Don't translate inside HTML tags** — `<a id="item-1"></a>`, `<details>`, `<summary>` stay in English
- **Don't translate tag values** — `#AI`, `#machine learning` stay in English (they're metadata keys)
- **Don't translate URLs** — obvious but easy to fat-finger during bulk editing
- **One `write_file` call** — don't split translations across multiple writes; it invites drift
