# Pipeline Stage Timing Baseline

Measured on 2026-06-30 from three complete runs. 24h window, 5 sources (GitHub, HackerNews, RSS, Reddit, Telegram), 445-447 items after dedup, 38 items after filter. DeepSeek API for scoring.

## Individual Run Data

| Stage | Run 1 (manual) | Run 2 (terminal subagent) | Run 3 (horizon subagent) | Baseline |
|-------|---------------|--------------------------|--------------------------|----------|
| Fetch | 6s | 6s | 6s | ~30s |
| Score (445 items) | ~10min | ~10min | 9m44s | ~10min |
| Filter | ~30s | ~30s | 27s | ~30s |
| Enrich (38 items) | 8m51s (531s) | ~9min | 6m51s (411s) | ~7-9min |
| Summarize | ~30s | ~30s | embedded | ~30s |
| **Total** | **~20min** | **~21min** | **17m8s** | **15-20min** |

## Key Observations

- **Fetch**: Consistently 6s across all runs. Faster than the ~30s baseline — likely improved in Horizon 1.26.0.
- **Score**: ~1.3s/item, very stable. Dominant time sink (60% of total).
- **Filter**: Sub-30s, negligible.
- **Enrich**: Most variable — 6m51s to 8m51s. Depends on DeepSeek API latency and web research speed. 38 items × ~11-14s per item.
- **Total**: 17-21 minutes. Within PER_TOOL_TIMEOUT=900s (15min) only if individual stages are used; `hz_run_pipeline` combined exceeds timeout.

## Subagent Overhead

`delegate_task(toolsets=['horizon'])` with `hz_run_pipeline`: subagent startup adds ~30s.
Individual stage tools from main thread: no overhead but blocks main thread for ~19min total.
Subagent + main-thread monitoring: ideal pattern — no blocking, full visibility via read tools.
