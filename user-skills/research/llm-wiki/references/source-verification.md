# Wiki Source Verification (源码交叉验证)

When a wiki page claims facts about source code (w/r/d/u counts, function lists, index
mappings), verify by extracting ground truth from the actual source.

## Pattern

```
wiki claim → grep source for operation patterns → aggregate → diff → report delta
```

## Recipe: KV scope operation counts from minified JS

The agentmemory `dist/index.mjs` (22K lines, minified) contains all KV operations as
`kv.set/get/list/delete/update(KV.scopeName, ...)`. The scope names are string literals.

### Step 1: Find all unique scope names

```bash
grep -oP 'KV\.\w+' dist/index.mjs | sort | uniq -c | sort -rn
```

This gives a frequency count of KV scope references (not just operations — includes
passing `KV.scope` as a parameter, etc.).

### Step 2: Extract per-scope operation counts

```bash
grep -oP 'kv\.(set|get|list|delete|update)\(KV\.\w+' dist/index.mjs \
  | sort | uniq -c | sort -rn
```

This extracts lines like `17 kv.set(KV.actions` — count per (operation, scope) pair.

### Step 3: Aggregate in Python

```python
from collections import defaultdict
counts = defaultdict(lambda: {"w": 0, "r": 0, "d": 0, "u": 0})

for line in grep_output.split("\n"):
    # parse "17 kv.set(KV.actions" → op="set", scope="actions", num=17
    ...
    if op == "set": counts[scope]["w"] += num
    elif op in ("get", "list"): counts[scope]["r"] += num
    elif op == "delete": counts[scope]["d"] += num
    elif op == "update": counts[scope]["u"] += num
```

### Step 4: Diff against wiki

For each scope in the wiki table, compare w/r/d/u against the aggregated counts.
Flag any mismatch.

### Pitfalls

- **Dynamic scope names**: `KV.observations(sessionId)` — the grep pattern `KV\.\w+`
  captures just `observations` (stops at the paren). This is correct behavior — the
  scope base name is what matters for counting.
- **Minified code noise**: functions named `kvSet`, `kvGet` etc. may be internal
  wrappers. Focus on calls with the literal `KV.<scopeName>` pattern.
- **Multiple source copies**: npm caches may have multiple versions. Check file
  timestamps and use `wc -c` to confirm they're identical. If they differ, use the
  newest.

## Recipe: Trace consumption paths (is data actually used?)

To verify whether data stored in a scope is actually consumed (vs. write-only dead data),
trace the read paths:

### Step 1: Find all reads of the scope

```bash
grep -n 'kv\.\(get\|list\)(KV\.<scope>' dist/index.mjs
```

### Step 2: Classify each read by consumption context

Read the surrounding code (~20 lines) for each hit and categorize:

| Pattern | Meaning |
|---------|---------|
| Inside `mem::context` or context assembly | Injected into LLM prompt every turn — highly useful |
| Inside `mem::search` or search index | Searchable via BM25/Vector |
| Inside `mem::consolidate` or consolidate-pipeline | Self-consumption in memory pipeline |
| Inside `mem::export` | Only for dump/viewer — low value |
| Inside mesh sync (delta/merge) | Multi-instance sync — situational |
| Inside a REST/MCP handler get-by-ID | API-accessible on demand |
| No reads found at all | Truly dead data |

### Step 3: Build the consumption map

For each LLM-generated scope, trace what actually happens to the data:

Example from agentmemory audit (2026-06-22):

```
profiles    → mem::context (L5118): injected into every LLM turn ✅
lessons     → mem::context (L5119): top 10 by confidence, every turn ✅
summaries   → mem::context (L5163): prior session summaries, every turn ✅
slots       → mem::context (L5117): pinned context, every turn ✅
semantic    → consolidate-pipeline (L8456): read-merge-write cycle ⚠️
procedural  → consolidate-pipeline (L8538): read-merge-write cycle ⚠️
sketches    → sketch-read API (L10966): get-by-ID ✅
insights    → export only (L7228): listed, never in reasoning path ❌
crystals    → export only (L7225): listed, never in reasoning path ❌
enrichedChunks → NO reads found: 1 write, 0 reads ❌☠️
```

### Pitfall: "不进搜索 = 白算"

A scope not in BM25+Vector index may still be heavily consumed via context injection.
Always verify ALL consumption paths before calling data "wasted."

Wiki at `D:/obsidian/2026/wiki/concepts(概念)/agentmemory-47-kv-scopes.md`.
Source at `~/.npm/_npx/<hash>/node_modules/@agentmemory/agentmemory/dist/index.mjs`.

### Findings

**w/r/d/u errors (3 scopes):**

| Scope | Wiki | Source | Issue |
|-------|------|--------|-------|
| enrichedChunks | 0/0/0/0 | 1/0/0/0 | wiki has "LLM: ✅ enrich" but counts say 0 — contradictory |
| teamProfile | 0/0/0/0 | 1/0/0/0 | 1 `kv.set` exists |
| teamShared | 0/0/0/0 | 1/3/0/0 | 1 set + 3 list calls exist |

**Summary table errors:**

- 记忆/知识层 "有 LLM 参与": wiki says 8, actual is 10 (all 10 with ✅ marks in detail)
- 汇总 "总计 9 个": wiki says 9 but detail table + actual counts suggest ≥12 scope-LLM pairs
- "LLM 参与的 9 个函数": line says 9 but lists 10 names, omits `temporal-graph-extract`

**Confirmed accurate:**

- All 47 scope names — no missing, no extra
- Four-tier classification (13+7+8+19) correct
- Index mapping (BM25+Vector: observations+memories; Graph: 7 scopes) correct
- LLM function attribution per scope correct
- Trigger mechanism (auto/manual) correct
