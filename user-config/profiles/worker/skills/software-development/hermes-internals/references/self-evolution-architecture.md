# Hermes Self-Evolution Architecture

## Quick Summary

Hermes's "self-evolution" (自主开发脚本、创建 skill、改源码) is **LLM-emergent**, not code-driven. There is no `if task_unsolvable: self_develop()` code path.

## The Mechanism

### Layer 1: System Prompt Constraints (prompt_builder.py:257-354)

Three constraint blocks injected into every session:

1. **TOOL_USE_ENFORCEMENT_GUIDANCE** (line 258)
   - "You MUST use your tools to take action"
   - "Never end your turn with a promise of future action"
   - "Every response should either (a) contain tool calls or (b) deliver a final result"

2. **TASK_COMPLETION_GUIDANCE** (line 292)
   - "the deliverable is a working artifact backed by real tool output"
   - "NEVER substitute plausible-looking fabricated output"
   - "Reporting a blocker honestly is always better than inventing a result"

3. **OPENAI_MODEL_EXECUTION_GUIDANCE** (line 315)
   - "Use tools whenever they improve correctness"
   - "Do not stop early when another tool call would materially improve the result"

Model gating: `TOOL_USE_ENFORCEMENT_MODELS` (line 274) includes `"deepseek"`.

### Layer 2: The Only Code Branch (conversation_loop.py:3675/4007)

```python
if assistant_message.tool_calls:
    # dispatch each tool, append result, continue loop
else:
    final_response = assistant_message.content or ""
    # return to user
```

No other structural branches. No "self-develop" path.

### Layer 3: How "Self-Development" Actually Happens

```
Constraint 1: must use tools (can't just describe)
Constraint 2: must deliver working artifact (can't stop at planning)
Constraint 3: can't fabricate results (can't lie)
        ↓
    LLM sees: write_file + terminal + execute_code + patch are available
    LLM reasons: "I can compose these to build the missing capability"
    LLM acts: write_file → terminal → verify → skill_manage to persist
        ↓
    Skill loaded next session → knowledge persists
```

### Layer 4: Persistence (after the fact)

- `skill_manage(action='create')` — saves workflow as reusable skill
- `memory(action='add')` — saves durable facts
- Curator (background) — manages skill lifecycle (stale detection, archiving)

## Verifying LLM vs Code

To prove a behavior is LLM-driven:
1. Check `conversation_loop.py` — is there a code path that triggers it?
2. Check `prompt_builder.py` — are there constraints steering toward it?
3. If (1) is no and (2) is yes → LLM emergent
4. If (1) is yes → code-driven (or hybrid)

## Known Self-Evolution Examples (from this user's setup)

- **WeChat forwarded links**: `patch` to `gateway/platforms/weixin/` adding ITEM_APPMSG=7, ITEM_RECORD=6, ITEM_NOTE=8
- **Obsidian sync**: `skill_manage(action='create')` → `obsidian-sync` skill
- **Reasonix delegation**: discovered tool, tested, saved to memory
- **Hermes vision setup**: created `hermes-vision-setup` skill