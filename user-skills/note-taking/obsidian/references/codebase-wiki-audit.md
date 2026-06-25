# Codebase → Wiki Coverage Audit

Systematic technique for comparing a codebase's modules against existing wiki documentation, identifying uncovered subsystems, and producing a tiered gap report.

## When to Use

- User asks "what does the wiki miss about this codebase?"
- After major codebase updates — check if new modules need wiki coverage
- As a planning step before a documentation sprint
- When evaluating whether existing docs are complete enough

## Audit Workflow

### Phase 1: Build Codebase Inventory

Use `execute_code` to walk the codebase directory tree, excluding noise directories (venv, node_modules, tests, __pycache__, .git):

```python
import os

EXCLUDE = {'venv', 'node_modules', 'tests', '__pycache__', '.git', 'optional-skills'}

def collect_source(root):
    result = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in EXCLUDE]
        for f in files:
            if f.endswith('.py') and f != '__init__.py':
                rel = os.path.relpath(os.path.join(dirpath, f), root)
                result.append(rel)
    return result
```

Group modules by top-level directory (agent/, gateway/, tools/, cron/, etc.) for the first-pass overview.

### Phase 2: Read Module Headers

For each key module, read the first 5-8 lines to extract the docstring — this tells you the module's purpose without reading the full file. Batch this in `execute_code`:

```python
for f in key_files[:50]:  # batch reasonable chunks
    with open(os.path.join(root, f), 'r', encoding='utf-8', errors='replace') as fh:
        lines = fh.readlines()[:8]
    print(f"=== {f} ===\n  {''.join(lines[:5]).rstrip()}\n")
```

Focus on the `agent/` directory first—it contains the core mechanisms.

### Phase 3: Map Wiki Coverage

Read the wiki index to understand what's already documented:

```python
read_file("D:/obsidian/2026/wiki-next/index.md")
```

Also check the old wiki/ for legacy coverage:
```python
read_file("D:/obsidian/2026/wiki/index.md")
```

Extract all existing wiki pages relevant to the codebase. For Hermes, these are the `hermes-*` entries under `concepts(概念)/` in both wiki/ and wiki-next/.

Optionally skim the first paragraph of each wiki doc to confirm what each covers.

### Phase 4: Cross-Reference

For each codebase module, determine:
- **Covered**: wiki page exists that explains this module's mechanism
- **Partial**: module is mentioned in passing but not as the main topic
- **Uncovered**: no wiki page addresses this module at all

Pay special attention to:
- `agent/` modules — these are the core agent mechanisms (error recovery, credential management, self-review)
- `gateway/` modules — streaming pipeline, event hooks, delivery routing
- `tools/` modules — individual tools like tool_search (progressive disclosure)

### Phase 5: Classify into Tiers

Use a 3-tier classification:

| Tier | Criteria | Examples |
|------|----------|---------|
| Tier 1 — Core Gaps | Runs on every turn; understanding agent behavior requires it | secret redaction, credential pool, error classifier, retry state machine |
| Tier 2 — Important Gaps | Independent subsystem, significant design choice | computer use, LSP integration, shell hooks, gateway relay |
| Tier 3 — Edge Gaps | Auxiliary/support modules; nice to have | billing view, i18n, channel directory, runtime footer |

Tier assignment rationale:
- **Tier 1**: If someone reads all wiki docs and still can't explain what happens when an API call fails, it's Tier 1.
- **Tier 2**: Self-contained features that don't affect understanding of the core loop.
- **Tier 3**: Infrastructure that's important for operators but not for understanding the design.

### Phase 6: Output the Report

Save as a wiki concept page via `wiki-guide-split` skill (wiki-import-markdown is deprecated):

1. YAML frontmatter with `type: concept`, appropriate tags, `confidence: high`
2. Brief summary blockquote explaining the report's purpose
3. "已覆盖" section listing existing docs with wikilinks
4. Three tier sections, each with numbered entries containing: module name, source files, what it does, key design decisions, why it matters
5. Summary table with counts per tier
6. Coverage pattern analysis — what the wiki covers well vs what it systematically misses

## Gap Closure (Post-Audit Follow-Up)

When gaps identified in the audit report have been filled:

1. **Re-scan the wiki** to map each gap to its new document.
2. **Update the coverage-gaps report** with a "全部补齐" section containing:
   - Completion status and date
   - Final file count (before/after)
   - Tier alignment differences table (if final placement differs from report recommendation)
3. **Update frontmatter**: `tags` from `todo` → `completed`, add review source line.
4. **Do NOT move files** that are already organized into tiers just because the report recommended a different tier. The report is a snapshot; the actual tier assignments reflect later decisions. Document the differences in the report's alignment table instead.
5. **Git commit & push** the updated report.

## Pitfalls

1. **Don't skip the agent/ directory**. It's the most important and most likely to contain uncovered mechanisms.
2. **Read module headers, not full files**. Reading full files for 100+ modules is impractical. The docstring tells you the purpose.
3. **Batch the header reads in execute_code**. Don't make 50 separate read_file calls — batch in one Python script.
4. **The tier system must be justifiable**. Don't just list uncovered modules — explain WHY each tier assignment.
5. **Include the "coverage pattern analysis" section**. It's the most valuable part — tells the reader what kind of knowledge they're missing systematically, not just a flat list.
6. **Don't claim coverage where it doesn't exist**. A wiki doc mentioning prompt caching in passing is NOT the same as a dedicated doc on prompt_caching.py.
7. **NEVER move already-tiered wiki files to match report recommendations**. The tier assignments in the report are suggestions at audit time; the actual placement reflects editorial decisions made during document creation. Moving files to match the report breaks existing wikilinks and erases editorial intent. Instead, document tier differences in the report's alignment table.
