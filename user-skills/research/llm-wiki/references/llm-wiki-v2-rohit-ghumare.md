# LLM Wiki V2 — Rohit Ghumare (2026-04-06)

> Source: https://gist.github.com/rohitg00/2067ab416f7bbe447c1977edaaa681e2
> Extends: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f (Karpathy's original)

## Summary

Rohit Ghumare's V2 extends Karpathy's LLM Wiki pattern with lessons from building agentmemory (20K+ stars on GitHub). The core insight: the original wiki is a static file cabinet — V2 adds a knowledge lifecycle so the wiki becomes a living model rather than a flat collection of equally-weighted pages.

## Ten Extensions

1. **Memory Lifecycle** — confidence scoring, supersession (knowledge version control), Ebbinghaus forgetting curve, four-tier consolidation pipeline (working → episodic → semantic → procedural)

2. **Typed Knowledge Graph** — entity extraction + typed relationships (uses, depends on, contradicts, caused, fixed, supersedes) layered on top of wiki pages

3. **Hybrid Search** — BM25 + vector search + graph traversal fused via reciprocal rank fusion. Replaces index.md as primary search beyond ~100 pages.

4. **Event-Driven Automation** — hooks for: on-new-source, on-session-start, on-session-end, on-memory-write, on-schedule (lint/consolidation/decay)

5. **Quality Self-Healing** — auto-scoring every LLM-written piece, auto-fix for orphan pages/stale claims/broken cross-refs, contradiction resolution proposals

6. **Crystallization** — treating completed work chains (debug sessions, research threads) as first-class sources, auto-distilling into structured digests

7. **Multi-Agent Collaboration** — mesh sync, shared vs. private scoping, lightweight work coordination

8. **Privacy & Governance** — auto-filter on ingest (API keys, PII), audit trail, auditable bulk operations

9. **Multi-Format Output** — comparison tables, timeline viz, dependency graphs, slide decks, JSON/CSV exports

10. **Schema as Product** — CLAUDE.md/AGENTS.md co-evolved with LLM, encodes domain model, transferable across projects

## Implementation Spectrum (Modular)

| Level | Components | When |
|-------|-----------|------|
| MVP | raw + pages + index.md + schema | 10-50 pages (Karpathy original) |
| +Lifecycle | confidence, supersession, decay | content starts going stale |
| +Structure | entities, typed relationships, graph | wikilinks insufficient |
| +Automation | hooks | manual maintenance burden |
| +Scale | hybrid search, consolidation tiers, quality scoring | 200+ pages |
| +Collaboration | mesh sync, shared/private scoping | multi-agent/team |

## Critical Weaknesses (Analysis from 2026-06-22 session)

1. **Confidence scoring lacks ground truth.** Scores come from LLM self-evaluation — different models/prompts/invocations can vary by 20 percentage points. Without human calibration, confidence numbers are unreliable. This undermines the entire "self-correcting" premise.

2. **Forgetting curve is a double-edged sword.** Ebbinghaus describes biological memory constraints. In a knowledge base, "not accessed recently" ≠ "unimportant." A Redis config you haven't touched in 6 months may be critical during a migration. Auto-deprioritization trades discoverability for an unverified "freshness" signal.

3. **LLM self-evaluation is circular.** Having the same LLM score its own output ("is this well-structured?") is not quality assessment — it's self-assessment with no external feedback loop. Real quality signals (query count, citation count, modification frequency, human feedback) are absent from the proposal.

4. **Knowledge graph implementation is unspecified.** Entity dedup (React vs react vs React.js), relationship granularity, storage, query engine, page-graph sync — all left as hand-waving. This section is closer to a wishlist than a design.

5. **Cost not accounted for.** Per-source ingest: write page + extract entities + update graph + score confidence + check contradictions + maybe self-score quality. A 5000-word article could burn hundreds of thousands of tokens. Viable for personal wikis, economically questionable for team wikis with dozens of daily sources.

6. **Multi-agent merge is hand-wavy.** "Last-write-wins for most cases" ignores the real problems: two agents editing different paragraphs of the same page, one deleting an entity another just created. No CRDTs, no version vectors, no merge strategy beyond "timestamp + manual override."

7. **Privacy filtering underestimates difficulty.** Regex for API keys misses Base64-encoded secrets, embedded env vars, sharded storage. Real PII detection requires entity recognition (names, emails, ID numbers) — another LLM call per source.

## Bottom Line

V2's diagnosis is accurate — the original wiki lacks lifecycle, structured search, and automation. But the treatment is overweight: a full cognitive architecture where most use cases need only ~30% of the components. **The fatal flaw is that confidence and quality assessment both rely entirely on LLM self-evaluation with no external feedback loop — the whole "self-correcting" system is built on sand.**
