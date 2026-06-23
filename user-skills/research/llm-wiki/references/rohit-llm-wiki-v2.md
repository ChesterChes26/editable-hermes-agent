# Rohit Ghumare's LLM Wiki v2 (2026-04)

> Source: https://gist.github.com/rohitg00/2067ab416f7bbe447c1977edaaa681e2
> Extends Karpathy's LLM Wiki with lessons from building agentmemory (20K+ stars).

## What It Adds

Rohit's v2 identifies gaps in the original pattern that surface at scale:

### 1. Memory Lifecycle (the biggest gap)

**Confidence scoring.** Every fact carries a confidence score: how many sources support it, recency of confirmation, whether anything contradicts it. Confidence decays with time (Ebbinghaus forgetting curve), strengthens with reinforcement.

**Supersession.** New info explicitly supersedes old claims — linked, timestamped, old version preserved but marked stale. Version control for knowledge, not just files.

**Forgetting.** Retention curve: facts not accessed/reinforced in months gradually deprioritize. Architecture decisions decay slowly; transient bugs decay fast.

**Consolidation tiers (4-layer pipeline):**
- Working memory → recent observations, not yet processed
- Episodic memory → session summaries, compressed from raw observations
- Semantic memory → cross-session facts, consolidated from episodes
- Procedural memory → workflows and patterns, extracted from repeated semantics

Each tier is more compressed, more confident, longer-lived than the one below.

### 2. Knowledge Graph (beyond flat pages)

- **Entity extraction**: people, projects, libraries, concepts, files, decisions — each with type, attributes, relationships.
- **Typed relationships**: "uses", "depends on", "contradicts", "caused", "fixed", "supersedes" — different semantic weight.
- **Graph traversal for queries**: start at a node, walk outward through typed edges to find downstream impacts.

### 3. Hybrid Search (scales past ~100 pages)

Three streams fused with reciprocal rank fusion:
- BM25 (keyword matching with stemming + synonym expansion)
- Vector search (semantic similarity via embeddings)
- Graph traversal (entity-aware relationship walking)

### 4. Event-Driven Automation

Hooks that fire automatically: on new source (auto-ingest), on session start (load context), on session end (compress into observations), on memory write (check contradictions), on schedule (periodic lint/consolidation/decay).

### 5. Quality & Self-Healing

- Score every piece of content the LLM writes. Below threshold → flag or rewrite.
- Lint should auto-fix what it can: orphan pages get linked, stale claims marked, broken cross-references repaired.

### 6. Crystallization

Taking a completed work chain (research thread, debugging session, analysis) and distilling it into a structured digest. What was the question? What did we find? What files/entities involved? What lessons emerged? The exploration itself becomes a first-class source.

### 7. Multi-Agent & Collaboration

- **Mesh sync**: multiple agents merge observations into shared wiki (last-write-wins, timestamp resolution for conflicts).
- **Shared vs. private**: personal preferences private, project architecture shared.
- **Lightweight coordination**: who's working on what, what's blocked.

### 8. Privacy & Governance

- Auto-filter sensitive data on ingest (API keys, passwords, PII).
- Audit trail: every operation logged with timestamp + what changed + why.
- Bulk operations audited and reversible.

## Implementation Spectrum (modular)

| Level | What |
|-------|------|
| MVP | raw sources + wiki pages + index.md + schema (Karpathy original) |
| +Lifecycle | confidence scoring, supersession, basic retention decay |
| +Structure | entity extraction, typed relationships, knowledge graph |
| +Automation | hooks for auto-ingest, auto-lint, context injection |
| +Scale | hybrid search, consolidation tiers, quality scoring |
| +Collaboration | mesh sync, shared/private scoping, work coordination |

## Key Quote

> "The Memex is finally buildable. Not because we have better documents or better search, but because we have librarians that actually do the work."
