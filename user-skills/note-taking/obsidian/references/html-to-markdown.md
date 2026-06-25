# HTML-to-Markdown Conversion for Wiki Import

Convert visually-rich HTML documents (CSS-class-structured, card/grid layouts, tables) to Markdown for Obsidian wiki storage. Use `execute_code` for the conversion script.

## When to use

- HTML files with rich visual structure (cards, comparison tables, flow diagrams, decision trees)
- Documents where generic `html2text` loses too much structure
- Batch import into wiki `concepts(概念)/` or `raw(源材料)/`

## Dependencies

```bash
pip install beautifulsoup4 html2text
```

`html2text` is installed but NOT used for the conversion — use BeautifulSoup directly with a semantic class-aware converter.

## execute_code Sandbox Pitfalls

### 1. read_file() returns dedup responses

`hermes_tools.read_file()` in execute_code returns `{'status': 'unchanged', 'dedup': True, 'content_returned': False}` when the file was already read in the main conversation. The sandbox has separate context but the dedup layer still fires.

**Fix:** Use Python's built-in `open()` to read files directly:

```python
def read_file_raw(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()
```

### 2. BeautifulSoup children() includes NavigableString nodes

`el.children` yields both `Tag` and `NavigableString` objects. Calling `.get('class')` on a NavigableString raises `AttributeError`.

**Fix:** Always filter children for Tag instances:

```python
from bs4 import Tag

def children(el, selector=None):
    result = []
    for c in el.children:
        if isinstance(c, Tag):
            if selector is None or c.name == selector:
                result.append(c)
    return result
```

### 3. soupsieve rejects ':scope > div' CSS selector

BeautifulSoup's CSS selector engine (soupsieve) doesn't support `:scope > div` syntax. Use the `children()` helper above instead of `el.select(':scope > div')`.

### 4. HTML header may be sibling of `<main>`, not child

Some HTML documents place `<header>` as a direct child of `<body>`, not nested inside `<main>`. When searching for the header:

```python
body = soup.find('body')
main = soup.find('main') or body
header = main.find('header') or (body.find('header') if body else None)
```

## Conversion Script Architecture

### Core pattern: semantic class-based converter

The converter walks `<main>` children and dispatches based on CSS class patterns:

```
convert_element(el):
  if 'cmp-table' in cls → build Markdown table from direct div children
  if 'design-grid' in cls → iterate .design-card, extract .card-header + .card-body
  if 'walkthrough' in cls → iterate .step-card, split .step-orch / .step-eval
  if 'key-insight' in cls → extract .insight-principle + .insight-grid
  if 'arch-diagram' in cls → extract .arch-col titles + .layer items
  if 'output-showcase' in cls → extract .output-panel headers + .output-panel-body
  ...
  else → recurse into children(el)
```

### Content extraction rules

1. **Strip noise first**: Remove `<style>`, `<script>`, and `.noise` / `.noise-overlay` divs
2. **Use `.stripped_strings`**: Yields all text nodes without whitespace padding
3. **Tables**: Count columns from header cells (`hdr`/`cg-header` class), build Markdown `| col | col |` tables
4. **Code blocks**: Extract from `<code>` tags or `.code-snippet` divs, wrap in ` ``` `
5. **Structure preservation**: Headings stay as `#`/`##`/`###`, lists as `- `, blockquotes as `> `

### CSS class patterns and their Markdown mapping

| CSS class | HTML structure | Markdown output |
|---|---|---|
| `.section` | Container for a major section | Process children recursively |
| `.section-title` | Section heading, may contain `.num` span | `## N. Title` |
| `.spectrum` | Horizontal bar chart with `.spectrum-bar` items | `- item — description` list |
| `.two-layer` | Two `.layer-card` with `.layer-bad`/`.layer-good` inside | `### title` + `**h4**` + code block + paragraph |
| `.design-grid` | Grid of `.design-card` (`.card-header` + `.card-body`) | `### header` + code block + insight bullets |
| `.card-grid.colsN` | Grid of `.card` divs (first string = title) | `**title**` + rest on next line |
| `.cmp-table` / `.compare-grid` | Direct `<div>` children forming rows | Markdown table `\| col \| col \|` |
| `.decision-tree` | `.dt-node` questions + `.dt-branch` choices | `**Q**` + bullet options |
| `.key-insight` | `.insight-principle` + `.insight-grid` items | Bold summary + `>` sub-detail |
| `.arch-diagram` | `.arch-col` columns with `.layer` items | `### title` + `- **name**` items |
| `.walkthrough` | `.step-card` with `.step-orch`/`.step-eval` split | `**步骤 N — label**` + code blocks |
| `.output-showcase` | Two `.output-panel` (bad vs good) with `.output-panel-body` | `**header**` + code fence |
| `.principles-grid` | `.principle-card` with icon + h4 + p | `### icon title` + paragraph |
| `.strategy-split` | Two `.strategy-col` (`.left`/`.right`) with `.does`/`.doesnt` | `### h3` + subtitle + bullet lists + `> bet` |
| `.key-box` | `h3` title + `.key-grid` divs + closing text | `## title` + bullet items |
| `.subtitle` | Subtitle div inside `.strategy-col` | Italic text |
| `.cmp-title` | Table section title | `### title` |

### Special handling: `.does` / `.doesnt` blocks

These appear inside `.strategy-col` and have a nested structure:
```html
<div class="does">
  <h5>✅ 选择做的</h5>
  <ul>
    <li>item 1</li>
    <li>item 2</li>
  </ul>
</div>
```
Extract: `h5.get_text()` → bold heading, `ul.find_all('li')` → bullet list items.

### Section numbering cleanup

HTML section titles often lack proper spacing (e.g., "1ADK ..." or "2核心贡献"). Fix with regex after conversion:
```python
text = re.sub(r'^## (\d)([A-Z\u4e00-\u9fff])', r'## \1. \2', text, flags=re.MULTILINE)
```

### Empty table header fix

Some comparison tables have an empty first header cell. Detect and fix:
```python
if not hdr[0].strip():
    hdr[0] = "维度"
```

### Output cleaning

```python
md_text = re.sub(r'\n{4,}', '\n\n\n', md_text)  # collapse excessive blank lines
```

## Wiki target directories

- Architecture/design concepts → `wiki/concepts(概念)/`
- Raw source materials → `wiki/raw(源材料)/articles(文章)/`
- Comparison documents → `wiki/comparisons(对比)/`

## Example: full conversion call

```python
html_to_md(
    "D:/workspace/project/docs/diagrams/some-diagram.html",
    "D:/obsidian/2026/wiki/concepts(概念)/some-diagram.md"
)
```

The converter should be written inside `execute_code` using Python's `open()` for file I/O and BeautifulSoup for parsing. The script is self-contained — no external converter libraries needed beyond bs4.
