---
name: hermes-internals
description: "Use when tracing Hermes Agent behavior to source code — answering 'why does Hermes do X?' or 'is this prompt or code?' with file+line evidence."
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, internals, source-code, debugging, behavior-analysis, architecture]
    related_skills: [hermes-agent, systematic-debugging]
---

# Hermes Internals: Tracing Behavior to Source

## Overview

When Hermes exhibits a behavior and you need to determine whether it's driven by code, system prompt, or LLM reasoning — trace it to the exact source file and line. This skill maps the key behavioral control points in the codebase.

## When to Use

- User asks "why does Hermes do X?" and expects code-level evidence
- User asks architectural design questions ("why this pattern over ReAct?", "is this dynamic workflow?")
- Need to distinguish LLM-emergent behavior from hardcoded logic
- Understanding how a constraint or rule is enforced
- Debugging unexpected agent decisions

## Key Files and Their Roles

| File | What it controls |
|------|-----------------|
| `agent/prompt_builder.py` | System prompt blocks — behavioral constraints injected into every session |
| `agent/conversation_loop.py` | Core agent loop — LLM call → tool dispatch → final response |
| `run_agent.py` | Agent class, tool dispatch to handlers |
| `tools/approval.py` | Dangerous command detection & approval — two-tier (HARDLINE + DANGEROUS), three-mode (manual/smart/off), smart approval via auxiliary LLM, gateway blocking queue, permanent allowlist |
| `tools/terminal_tool.py` | Terminal tool handler — calls `check_all_command_guards()` before every command |
| `toolsets.py` | Which tools are available per session |
| `hermes_cli/config.py` | Default config values |
| `model_tools.py` | Tool schema definitions |
| `tools/memory_tool.py` | Built-in file-backed memory (MemoryStore) — frozen snapshot pattern |
| `agent/memory_manager.py` | External memory provider orchestration (MemoryManager) |
| `agent/memory_provider.py` | Abstract base class for pluggable memory providers |
| `agent/tool_executor.py` | Tool dispatch & execution — sequential/concurrent paths, error capture, result normalization |\\n| `agent/display.py` | `_detect_tool_failure` (line 849) — classifies tool results as success/failure for UI/logging |\\n| `agent/prompt_builder.py` | Context file injection — `build_context_files_prompt()`: priority-chain discovery of AGENTS.md/CLAUDE.md/.cursorrules/.hermes.md, security scanning, truncation (see `references/context-file-injection.md`) |
| `agent/prompt_caching.py` | Anthropic `cache_control` breakpoint injection — `apply_anthropic_cache_control` at line 49 |
| `agent/context_compressor.py` | Context compression — `ContextCompressor`: 5-step lossy summarization with anti-thrashing, cooldown, fallback |
| `agent/conversation_compression.py` | Compression orchestrator — `compress_context()`: lock acquisition, session rotation, memory provider notification |
| `plugins/memory/__init__.py` | Memory plugin discovery + loading |

For the full memory subsystem architecture (dual built-in + external design, file locking,
drift detection, injection scanning, background sync, and initialization flow),
see `references/memory-architecture.md`.

For the per-turn memory injection path and its interaction with context files —
including the unbounded `system_prompt_block()` problem, `<memory-context>` fencing,
prefetch_all timing, and context window budget competition —
see `references/memory-context-competition.md`.

For how memory injection and context file injection interact —
the four injection points (context tier + volatile tier + per-turn prefetch + built-in),
why they don't override but DO compete for context window budget,
the unbounded-memory risk (no 20K cap like AGENTS.md), compression blind spot,
and three failure modes (silent exhaustion, attention dilution, pollution loop) —
see `references/memory-vs-context-injection.md`.

For the two-layer prompt caching architecture — Hermes local `messages`
persistence, Anthropic `cache_control` vs DeepSeek implicit KV cache (MLA),
bit-perfect prefix normalization, and why caching is the economic foundation
of the while loop — see `references/prompt-caching-architecture.md`.

For the update-check caching mechanism — `hermes_cli/banner.py` `check_for_updates()`,
6-hour cache in `~/.hermes/.update_check`, stale-after-git-pull pitfall,
and how to force a fresh check — see `references/update-check-cache.md`.

For the context compression subsystem — trigger paths (proactive threshold,
provider error, manual /compress), five-step lossy summarisation algorithm,
10% savings anti-thrashing check with `estimate_messages_tokens_rough`,
compression safeguards (SQLite lock, cooldown, abort, image stripping),
session splitting, and interaction with prefix cache — see
`references/context-compression-architecture.md`.

For the gateway platform lock mechanism — `_acquire_platform_lock` is
machine-local (file-based under `XDG_STATE_HOME`), not distributed.
WeChat uses long-poll, QQ Bot uses WebSocket; the actual single-connection
enforcement happens at the platform server level, not in Hermes. See
`references/gateway-platform-locks.md`.

For the gateway and cron process lifecycle — how `DETACHED_PROCESS` et al.
keep gateway alive after terminal close, the watcher-respawn chain, why cron
is a daemon thread inside gateway not a separate process, and the process-vs-
agent-instance distinction. See `references/gateway-cron-lifecycle.md`.

For the Atropos RL training integration — two-component architecture (Hermes as
environment executor, Atropos as orchestration framework), `hermes rl` command
entry point, trajectory format (ShareGPT-compatible JSONL), batch runner,
GRPO training algorithm, trainer integrations (Axolotl, Tinker), and complete
data flow through the Atropos API server — see
`references/atropos-rl-training.md`.

For the streaming content scrubber pipeline — two stateful scrubbers
(`StreamingThinkScrubber` in `agent/think_scrubber.py` for reasoning tags,
`StreamingContextScrubber` in `agent/memory_manager.py:131` for memory-context
spans) that run in series on every streaming delta to prevent internal XML-like
tags from leaking to the user when split across chunk boundaries. Covers state
machines, block-boundary gating, partial-tag hold-back, cross-scrubber cascade
on flush, and the legacy regex fallback — see
`references/streaming-scrubber-architecture.md`.

For the dangerous command approval system — two-tier detection (HARDLINE
never-bypassed floor + DANGEROUS mode-gated patterns), three approval modes
(manual/smart/off), command normalization (ANSI strip, NFKC, backslash unescape,
home-path rewriting), smart approval via auxiliary LLM, gateway blocking queue
with threading.Event, permanent allowlist persistence, and the
check_all_command_guards/tirith combined guard — see
`references/dangerous-command-approval.md`.

## Key Branch Points

### The only decision in the agent loop

`agent/conversation_loop.py` line 3675 / 4007:

```python
if assistant_message.tool_calls:
    # dispatch tools, append results, continue loop
else:
    # No tool calls — final response, return to user
```

This is the **only** structural branch. There is no "if no tool matches → self-develop" path, and no ReAct-style "Thought → Action → Observation" state machine. The LLM's reasoning is internal to each API call; the code only sees tool_calls or final text.

For a deeper analysis — why Hermes chose this design over ReAct, the "narrow waist" philosophy, the dynamic-workflow-vs-interleaved-thinking/acting distinction, and the multilayer recovery pattern — see `references/agent-loop-architecture.md`.

### System prompt constraint blocks

`agent/prompt_builder.py` lines 257-354:

- `TOOL_USE_ENFORCEMENT_GUIDANCE` (line 257) — "You MUST use your tools to take action"
- `TASK_COMPLETION_GUIDANCE` (line 292) — "deliverable is a working artifact backed by real tool output"
- `OPENAI_MODEL_EXECUTION_GUIDANCE` (line 315) — "NEVER answer these from memory"

Model gating at line 274:
```python
TOOL_USE_ENFORCEMENT_MODELS = ("gpt","codex","gemini","gemma","grok","glm","qwen","deepseek")
```

Models NOT in this list skip the enforcement blocks — useful for verifying whether behavior is LLM-driven.

## Methodology

1. **Identify the behavior** — what exactly is Hermes doing?
2. **Check constraints** — search `prompt_builder.py` for injected text that could drive the behavior
3. **Check dispatch** — look at `conversation_loop.py` for code paths that could trigger it
4. **Check tools** — look at the tool handler in `tools/` for tool-specific logic
5. **Conclude LLM vs Code** — if no code path exists but behavior is consistent, it's LLM emergent from constraints

## Common Pitfalls

1. **Assuming behavior is coded when it's emergent.** The three constraint blocks in `prompt_builder.py` create pressure that makes the LLM choose certain paths — but the choice itself is not code-driven. Verify by checking if the behavior exists in `conversation_loop.py`.

2. **Confusing tool schema descriptions with code logic.** Tool descriptions (the natural language in schema) influence LLM tool selection but are NOT code paths.

3. **Skipping the model gating check.** Some constraints only apply to certain model families (line 274). If the model isn't in the list, the constraint isn't injected.

4. **Not checking whether the agent is in a subagent/cron/internal context.** Different execution contexts may have different toolsets and prompt blocks.

5. **Confusing `state.db` with `MEMORY.md` for memory storage.** `state.db` (SQLite) stores session messages and metadata. Built-in memory entries (from the `memory` tool) live in `$HERMES_HOME/memories/MEMORY.md` (and `USER.md`), delimited by `§`. When asked where memory is stored, always check `references/memory-architecture.md` — do NOT guess `state.db`.

## Verification Checklist

- [ ] Found the exact source file and line for any claimed code path
- [ ] Checked `prompt_builder.py` for relevant constraint blocks
- [ ] Checked `conversation_loop.py` for relevant dispatch logic
- [ ] Verified model gating if constraint-related
- [ ] Distinguished LLM reasoning from code logic explicitly