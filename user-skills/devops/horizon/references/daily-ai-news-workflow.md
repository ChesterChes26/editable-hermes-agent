# Daily AI News Workflow (每日AI资讯工作流)

## Trigger
User asks for daily AI news / 每日AI资讯 / Horizon summary / 获取最新AI动态.

## Design Decision

**Primary: subagent with `toolsets=['horizon']`.** Subagent runs `hz_run_pipeline` in background; main thread monitors with read tools. Fix applied 2026-06-30 to `tools/delegate_tool.py` (see `references/delegate-plugin-toolset-recovery.md`) — subagents can now use plugin toolsets like `horizon` that aren't in the static `TOOLSETS` dict.

**Fallback: individual stage tools from main thread.** If subagent stalls or `horizon` toolset unavailable, run stages one-by-one. Each stage <10min, within PER_TOOL_TIMEOUT=900s. Total blocking ~19min but reliable and transparent.

NEVER call `hz_run_pipeline` from main thread — the combined pipeline (~20min) exceeds PER_TOOL_TIMEOUT (15min).

## Primary Workflow (subagent + monitor)

### Step 1: Check for existing runs

```
hz_list_runs(limit=3)
```

If a run for today already exists with all stages complete → skip to Step 4 (copy). If a partial run exists, decide: resume manually or run new pipeline.

### Step 2: Dispatch subagent

```
delegate_task(
    goal="Run Horizon full pipeline: hz_run_pipeline(hours=24, languages=['zh'], enrich=True, save_to_horizon_data=true). Report run_id when complete.",
    toolsets=["horizon"],
    context="Use hz_run_pipeline to run the full pipeline. Pipeline takes 10-15 min. IMPORTANT: pass save_to_horizon_data=true so summary is published to data/summaries/. Report the run_id from the result."
)
```

Subagent runs in background. Main thread is not blocked.

### Step 3: Monitor from main thread (every 2-3 min)

Use read tools — they bypass `_proc_lock`, always instant:

```
hz_list_runs(limit=3)              # Watch for new run
hz_get_run_meta(run_id=<id>)       # Check stage progression
```

Stage progression: `raw(30s) → scored(10min) → filtered(30s) → enriched(9min) → summary(30s)`

When meta shows `summary_generated_at` present → pipeline complete. Wait for subagent result confirmation, then proceed to Step 4.

### Step 4: Copy summary to wiki

```bash
cp "D:/workspace/AI-research/Horizon/data/summaries/horizon-YYYY-MM-DD-zh.md" \
   "D:/obsidian/2026/AI-report/horizon-YYYY-MM-DD-zh.md"
```

### Step 5: Present highlights to user

Read first ~100 lines of the summary and present key items (⭐9.0 and notable ⭐8.0) with a one-line description each.

## Fallback Workflow (individual stages from main thread)

Use when: subagent fails, `horizon` toolset unavailable, or subagent stalls at filter stage.

### Step F1: Run stages individually

```
hz_fetch_items(hours=24)                              # ~30s
hz_score_items(run_id=<id>)                            # ~10min
hz_filter_items(run_id=<id>)                           # ~30s
hz_enrich_items(run_id=<id>)                           # ~9min
hz_generate_summary(run_id=<id>, language="zh",        # ~30s
    save_to_horizon_data=true)
```

Use `hz_get_run_meta(run_id)` between stages to report counts. Then proceed to copy (Step 4).

## Anti-patterns

- DO NOT call `hz_run_pipeline` from main thread — exceeds timeout
- DO NOT skip copy-to-wiki step — it's part of the deliverable
- DO NOT use `delegate_task(toolsets=['terminal'])` — subagent can't call hz_* without the `horizon` toolset

## Parallel Web Research (while pipeline runs)

Pipeline takes 10-15 min. User may ask for additional research (e.g., "搜一下 SAG 代替 RAG 的新闻") during the wait. Use the gap productively:

**Safe sources (fast, no firewall risk):**
- GitHub API: `api.github.com/search/repositories`
- arXiv API: `export.arxiv.org/api/query`
- HN Algolia: `hn.algolia.com/api/v1/search`

**Firewall-sensitive (use sparingly, sequential only):**
- Web search engines (Google/Bing/DDG) — all block automated queries; don't bother
- Reddit API — often times out or blocks
- Nitter — unreliable

**CRITICAL — rate limiting:** 3+ parallel `curl` calls via proxy `127.0.0.1:7897` to external APIs trigger corporate firewall alerts. Sequential single-source searches are safe. Never fire multiple DDG/Google/Reddit calls simultaneously.

**When nothing found:** User accepts and prefers honest "not found" over fabrication. If a concept (e.g., user-defined SAG) has zero results across all channels, report clearly: which channels were searched and that nothing was found. Don't invent or substitute.

**PITFALL — user knows the source, just didn't share it:** When the user describes a named concept (e.g., "SAG 以时间地点人物 story 形式存入向量库") that doesn't appear in any search channel after 2-3 attempts, STOP searching and ask: "这个信息是从哪看到的？链接或 repo 名？" The user often has the exact URL/repo name (e.g., `Zleap-AI/SAG`) but assumed you'd find it. Exhausting 10+ channels before asking wastes tools and triggers firewall alarms (2026-07-09 session: GitHub→arXiv→HN→Google→Bing→DDG→Reddit→Nitter→Brave, all for a repo the user knew by name).

## Known Patterns

### Weekend volume drop

Weekend runs (Sat/Sun) fetch 40-50 items vs 600+ on weekdays. This is expected — GitHub/HN/RSS activity drops significantly on weekends. The pipeline still works correctly; just set expectations: "周末效应，内容偏少" is the right framing. Don't flag low volume as a pipeline issue.

### Missing summary_published_path

If `save_to_horizon_data=true` was not passed to `hz_run_pipeline`, the summary only exists in `data/mcp-runs/<run_id>/summary-zh.md`. Fallback copy:

```bash
cp "D:/workspace/AI-research/Horizon/data/mcp-runs/<run_id>/summary-zh.md" \
   "D:/obsidian/2026/AI-report/horizon-YYYY-MM-DD-zh.md"
```
