# Session 2026-06-24 Audit Results

## Codebase State
- Commit: current HEAD of `chester` branch (upstream NousResearch/hermes-agent merged)
- Model used for audit: deepseek-v4-pro

## Wiki Documents Audited (9 total)
All in `D:/obsidian/2026/wiki/concepts(概念)/`:

| Document | Refs Fixed | Worst Drift |
|----------|-----------|-------------|
| hermes-loop-and-cache.md | 9 | +207 |
| hermes-context-compression.md | 15 | +223 |
| hermes-dangerous-command-approval.md | 21 | -1339 |
| hermes-streaming-context-scrubber.md | 13 | +65 |
| hermes-checkpoint-rollback.md | 17 | +26 |
| hermes-rl-training-atropos.md | 6 | +463 |
| hermes-process-agent-session-lifecycle.md | 8 | +437 |
| hermes-context-files-injection.md | 6 | +194 |
| hermes-memory-vs-context-files-token-budget.md | 4 | +50 |

## Exact Matches (4 refs, 5%)
Only these 4 were at unchanged line positions:
- `AGENTS.md:24` — "core is a narrow waist"
- `checkpoint_manager.py:80` — DEFAULT_EXCLUDES
- `trajectory.py:30` — save_trajectory function
- `gateway.py:649` — launch_detached_gateway_restart

## Mechanism Updates (3)
1. **Compression threshold**: `_compute_threshold_tokens()` now has small-model degradation protection (85% fallback when floor >= window)
2. **Gateway process flags**: Abstracted to `windows_detach_popen_kwargs()` helper
3. **trajectory.py**: Removed "轨迹归一化" claim (tool_call→`<tool_call>` normalization no longer in trajectory.py; now in `run_agent.py:369-385`)

## Key Source Files and Current Lengths
| File | Lines | 
|------|-------|
| agent/conversation_loop.py | 4582 |
| tools/approval.py | 2038 |
| agent/context_compressor.py | 2649 |
| agent/prompt_builder.py | 1888 |
| gateway/run.py | 17845 |
| hermes_cli/main.py | 13191 |
| run_agent.py | 5568 |
| agent/trajectory.py | 56 (gutted — was much larger) |
