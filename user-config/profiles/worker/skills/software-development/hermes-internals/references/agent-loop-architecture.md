# Agent Loop Architecture

## The While Loop

`agent/conversation_loop.py:526`:

```python
while (api_call_count < agent.max_iterations and
       agent.iteration_budget.remaining > 0) or agent._budget_grace_call:
```

The only structural branch is at `conversation_loop.py:3675`:

```python
if assistant_message.tool_calls:
    # dispatch tools → messages ← results → continue
else:
    # no tool_calls → final response → return
```

There is no ReAct-style "Thought → Action → Observation" state machine. The code does not see how the LLM reasoned — it only sees tool_calls or text.

## Dynamic Workflow (Not ReAct)

Hermes delegates workflow orchestration to the LLM. The code provides a stable while loop + tool dispatch + recovery; the LLM provides the dynamic decision-making.

Evidence:

| Layer | Where | What |
|-------|-------|------|
| Skills orchestration | `prompt_builder.py:1127` `build_skills_system_prompt()` | LLM chooses which skills to load and in what order |
| Behavioral constraints | `prompt_builder.py:257-270` `TOOL_USE_ENFORCEMENT_GUIDANCE` | "Every response should either contain tool calls or deliver a final result" |
| Task completion rules | `prompt_builder.py:292-305` `TASK_COMPLETION_GUIDANCE` | "deliverable is a working artifact backed by real tool output" |
| Error recovery | `agent/tool_executor.py:1147-1148`, `conversation_loop.py:4103` | LLM self-corrects; code only injects error messages into context |

**Core philosophy** (`AGENTS.md:24-27`): "The core is a narrow waist; capability lives at the edges."

## Contrast with ReAct

| | ReAct | Hermes |
|---|---|---|
| Reasoning carrier | Explicit "Thought: ..." text in message history | Implicit thinking tokens (model-internal) |
| Action granularity | One Action per step | N tool_calls per API call (batch dispatch) |
| Who decides to continue | Prompt pattern "Thought: do I know the answer?" | `if assistant_message.tool_calls` (code check) |
| Message overhead | +50% from explicit Thought steps | Only tool_calls + results |

The extra 50% message volume in ReAct also hurts prompt caching (Anthropic's 4 breakpoints cover less useful history).

## Context Passing: The `messages` List

A single Python `list` carries all context between iterations:

```
while iteration:
  1. Build api_messages from messages (deep copy + system prompt prefix)
  2. Call LLM
  3. Assistant message (with tool_calls) → messages.append(...)
  4. Tool results → messages.append(...)
  5. continue → goto step 1 with updated messages
```

- `messages` is append-only — old entries are NEVER modified (preserves cache prefix)
- `conversation_loop.py:3837-3892` appends assistant message
- `agent/tool_executor.py:1379` (sequential) or `:748` (concurrent) appends tool results
- `conversation_loop.py:675-718` builds `api_messages` for each API call

## Error Recovery (Multilayer)

| Recovery | Location | Mechanism |
|----------|----------|-----------|
| Invalid tool name | `conversation_loop.py:3695-3732` | Return error to LLM, let it self-correct (up to 3 retries) |
| Invalid JSON args | `conversation_loop.py:3756-3824` | Return error or inject recovery results |
| Post-tool empty response | `conversation_loop.py:4103-4134` | Inject nudge: "You just executed tool calls but returned empty" |
| Thinking-only response | `conversation_loop.py:4151-4168` | Prefill mechanism to continue (up to 2 retries) |
| Tool execution exception | `agent/tool_executor.py:1147-1148` | `except Exception: result = "Error executing tool: ..."` — becomes LLM context |
| Tool returned failure | `agent/display.py:849-896` `_detect_tool_failure` | Classifies for UI/logging only — loop continues regardless |

Errors never crash the loop. They become text in `messages`, and the LLM decides the next move.
