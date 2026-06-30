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
    goal="Run Horizon full pipeline: hz_run_pipeline(hours=24, languages=['zh'], enrich=True). Report run_id when complete.",
    toolsets=["horizon"],
    context="Use hz_run_pipeline to run the full pipeline. Pipeline takes 10-15 min. Report the run_id from the result."
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
