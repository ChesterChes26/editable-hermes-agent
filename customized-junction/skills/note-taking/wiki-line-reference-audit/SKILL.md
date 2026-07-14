---
name: wiki-line-reference-audit
description: Audit and fix source code line references, parameter values, term names, and concept categorizations in Obsidian wiki documents for cross-document consistency.
category: note-taking
---

# Wiki Line Reference Audit

Systematically verify and correct source code line references in Obsidian wiki documents against the current codebase. Trigger: after git merges, codebase updates, or when wiki accuracy is questioned.

## When to Use

- After `git merge` or `git pull` from upstream (Hermes codebase evolved)
- User asks to "redo the wiki audit" or "check wiki accuracy"
- Suspicion that wiki line numbers have drifted
- User asks "这两篇对 X 的理解是不是不一致" — two wiki docs may conflict on concept name, parameter value, or framing
- Cross-document consistency check: terminology, numeric parameters, concept categorization

## Workflow (4 Phases)

### Phase 1: Extract All Line References from Wiki

Use `execute_code` with regex to scan wiki documents:

```python
import re, os

ref_pattern = re.compile(r'`?([\w/]+\.(?:py|md|js|mjs))`?\s*[:：L第]\s*(\d+)')
# Scans patterns like: file.py:123, `file.py` 第 123 行, file.py L123
```

Collect all `(file, claimed_line, wiki_doc, match_text)` tuples.

### Phase 2: Verify Against Current Source

For each reference, do **content-based search** (NOT line number comparison):

```python
# DON'T: check if file has that line
# DO: search for the described CONTENT at any line
for i, line in enumerate(lines, 1):
    if re.search(pattern, line):
        actual_line = i
        break
```

Define a search pattern per reference that captures the **described mechanism**, not literal text. Report drift as `actual - claimed`.

Categorize results:
- EXACT: drift = 0
- NEAR: |drift| <= 5
- DRIFT: 6-50
- MAJOR_DRIFT: 50+
- NOT_FOUND: pattern unmatched (file renamed? content removed?)

### Phase 3: Update Wiki Documents

Use `patch` tool with `old_string`/`new_string` to fix line numbers. **One replacement at a time**, using unique surrounding context to avoid ambiguity.

**Pitfall**: Same old line number may appear multiple times in the same document (e.g., in prose AND in a table). Each occurrence needs a separate patch with enough unique context.

**Pitfall**: Code block references (inside triple-backtick blocks) vs prose references have different formatting and may need different patch strings.

### Phase 4: Verify and Clean Up

Run a second extraction pass to confirm no old line numbers remain. Use a whitelist of known-old values and check they don't appear in any wiki document.

## Key Paths

| Path | Purpose |
|------|---------|
| `D:/obsidian/2026/wiki/concepts(概念)/*.md` | Wiki documents |
| `C:/Users/chester.chen/AppData/Local/hermes/hermes-agent/` | Hermes source code |
| `agent/conversation_loop.py` | Most-referenced file (~15 refs) |
| `tools/approval.py` | Second-most-referenced (~20 refs) |
| `agent/context_compressor.py` | Third-most (~10 refs) |

## Pitfalls

1. **Content-based search, not line-based**: Never just check `file[old_line]` — the content may have moved. Search for the described mechanism.

2. **Code block references**: References inside ```python blocks may be stale even when prose references are fixed. Check both.

3. **File renames**: If a file isn't found at the expected path, search recursively with `os.walk`.

4. **Mechanism changes, not just line drift**: Sometimes the described mechanism itself changed (e.g., `trajectory.py` was gutted, `_compute_threshold_tokens` added small-model logic). These need content updates beyond line numbers.

5. **Overlapping patterns**: `file.py:260` and `file.py:260-282` — the shorter one will match inside the longer one. Use specific enough `old_string` context.

6. **Wiki table references**: References in markdown tables (pipe-delimited) may use different formatting than prose references. Handle both.

7. **Batch efficiency**: Use `execute_code` for extraction and mapping generation. Use `patch` for applying fixes. Don't manually type 80+ replacements.

8. **Category-level comparison errors**: When wiki docs compare concepts in side-by-side tables, check that all items are in the same category. Symptom: a table lists "three protocols" but one entry is actually a communication pattern, not a protocol. Fix: split into layered tables (protocol layer vs pattern layer), add explicit "不在同一维度" note. Don't force peer comparison where hierarchy exists.

9. **Coverage-gap audit: never move tiered documents**: When comparing a coverage-gap file against actual wiki documents to check completeness, the correction flows ONE direction: update the gap/audit file to reflect current reality (mark gaps as covered, note tier differences). NEVER move wiki documents that are already organized into tiers to match the gap file's original recommendations — the gap file is a snapshot diagnostic, not the authority on final placement. The wiki directories are the ground truth.

## Cross-Document Parameter Verification

When the same parameter, threshold, or constant appears in **multiple wiki documents**, verify numeric values are consistent. Parameter drift is harder to spot than line drift because both values may be "correct" at different abstraction layers.

### When to Check

- Two wiki docs reference the same parameter/constant with different values
- A draft document (in `_drafts/`) and a concepts document overlap on a shared topic
- User asks "do these two docs conflict?"

### Workflow

1. **Identify the overlap**: Read both docs, extract all numeric parameters (percentages, counts, token budgets, timeouts)

2. **Map to source layers**: Trace each doc's claimed value back to its source. Common layers:
   - **Base class** (e.g., `context_engine.py:64`): default values in abstract interface
   - **Implementation class** (e.g., `context_compressor.py:786`): overridden defaults in `__init__`
   - **Helper function** (e.g., `_compute_threshold_tokens()`): additional logic on top of the parameter

3. **Resolve the override chain**: If doc A says 0.75 and doc B says 0.50, check:
   - Does the implementation class override the base class default?
   - Are there additional guards (floor values, degenerate-case branches) between the parameter and its actual use?

4. **Fix the numbers** with source citations: Don't just pick one value. Document the chain:
   ```
   基类默认 0.75 → ContextCompressor.__init__ 覆盖为 0.50
   → _compute_threshold_tokens 加 64K 硬底线 + 小模型退化分支(85%)
   ```

### 跨文档术语一致性审计

当同一概念在多个 wiki 文档里**名称不一致**（如一个写"Agent Communication Protocol"另一个写"Agent Client Protocol"），追踪到源码找出规范名称。

**触发条件**：
- 两个 wiki 文档对同一个缩写/术语展开为不同全称
- 用户问"这两篇对 X 的理解是不是不一致"
- 对比后发现概念描述一致但命名不同

**流程**：

1. **提取两个文档中的术语**：读两篇文档，列出各自对同一概念使用的名称
2. **追踪源码**：用 `search_files` 在源码中搜索该术语的所有出现，统计各变体的频次 → 哪个是主流名称？官方文档/GitHub 仓库用什么名称？
3. **区分 bug 和合法别名**：源码里一个文件写对了另一个写错了 → 那是源码 bug；官方仓库名是唯一权威来源
4. **修正 wiki**：用 `patch` 统一到规范名称。如有必要注明"源码 `xx.py` 也存在此 typo"

### 概念分类错误检测

当两个 wiki 文档将**不同类别**的概念（如协议 vs 通信模式）并排比较时，属于结构性问题：

- 症状：一张表里把 ACP、MCP、A2A 并列称为"三个协议"——实际 ACP 和 MCP 是协议，A2A 是通信模式
- 修复：拆表分层——协议层（ACP vs MCP） vs 模式层（A2A），明确"不在同一维度不能并列"
- 交叉关系说明：协议和模式可以交叉（如 ACP 协议 + A2A 模式 = agent 间走 ACP 通信），不需要做非此即彼的排他对比

### Boundary Marking

When two wiki docs overlap (not fully redundant, but covering the same system at different abstraction levels), **don't merge them**. Instead:

1. Add a "阅读前须知" section at the top of each doc declaring the division of labor
2. Use concrete metaphors to make the boundary intuitive: "图纸 vs 施工日志", "接口 vs 实现"
3. Add bidirectional wikilinks so readers can navigate between the two views
4. List what's in THIS doc and what's in the OTHER doc — no guessing required

**Pitfall**: Never assume one value is wrong just because two docs differ. Always verify against source code — the inconsistency may reveal an override chain that NEITHER doc fully captured.

## Mechanism Description Updates

When the audit reveals that the described mechanism itself changed (not just line drift), update the wiki content too:

- **Oversimplified code snippets**: Replace with accurate pseudo-code reflecting current logic
- **Refactored abstractions**: Note when inline code was extracted to helper functions
- **Removed features**: Remove references to code/features that no longer exist
