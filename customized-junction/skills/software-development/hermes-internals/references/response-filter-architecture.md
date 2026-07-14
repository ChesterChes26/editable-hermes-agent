# Response Filter Architecture: LLM Intent + Program Enforcement

## Core question: who decides?

The gateway response filter is a **two-layer** design:

- **Layer 1 (LLM):** decides *intent* — "does this turn need a reply?"
- **Layer 2 (Program):** enforces *how* — exact marker matching, length cap, failure bypass

The LLM outputs text; the program checks if that text is exactly a silence marker.

## Primary path: `gateway/response_filters.py`

### Flow

```
LLM outputs "NO_REPLY"
  → agent loop completes, final_response = "NO_REPLY"
  → run.py:9621: response = agent_result.get("final_response")
  → run.py:9624: is_intentional_silence_agent_result(agent_result, response)
  → matches marker → suppressed at delivery (line 10012)
  → BUT: still persisted in transcript (line 10007 comment — "delivery decision, not transcript mutation")
```

### Three program-enforced constraints

1. **Whitelist (4 markers only)**: `[SILENT]`, `SILENT`, `NO_REPLY`, `NO REPLY` (line 18-23)
2. **Length cap 64 chars**: prevents `"NO_REPLY because the task is already done..."` from bypassing (line 42-43)
3. **Failed-agent bypass**: if `agent_result.failed` is true, silence marker is ignored — user sees the failure (line 51-52)

### Canonicalization

`_canonical_silence_candidate()` normalizes to uppercase single-space (line 26-27):
```
"no  reply" → "NO REPLY" ✓
```

### Key design principle: "Blank ≠ Silence"

Empty string is NOT intentional silence (line 40-41). Empty output goes to the empty-response failure path, not the silence filter. This distinguishes "agent deliberately stays silent" from "agent broke and produced nothing."

## Secondary path: `gateway/delivery.py`

`_is_silence_narration()` (line 43-55) catches a different category: LLM *narrating* its silence with phrases like "silent", "no response", "no reply" wrapped in markdown formatting. Uses regex matching:

```python
_SILENCE_NARRATION = re.compile(
    r'^[\s*_~`]*\(?\s*(silent|silence|no\s+response|no\s+reply)\s*\.?\)?[\s*_~`]*$'
    r'|^[\s*_~`]*[\U0001F507\.\u2026]+[\s*_~`]*$',
    re.IGNORECASE,
)
```

Also length-guarded at 64 chars (line 53). Anchored to full string — "The deployment ran silently" is NOT flagged.

## Does the LLM know about this capability?

**Depends on context:**

| Context | LLM told about silence markers? | Source |
|---------|-------------------------------|--------|
| Main chat (gateway) | **No** — system prompt has no mention of `NO_REPLY` or `[SILENT]` | `agent/prompt_builder.py`: no match for `SILENT`, `NO_REPLY` |
| Cron jobs | **Yes** — explicit instruction in job prompt | `cron/scheduler.py:1430-1433` |
| Feishu comments | **Yes** — explicit instruction | `plugins/platforms/feishu/feishu_comment.py:880` |

For main chat, the silence capability is an **infrastructure feature** — it would trigger if the LLM happened to output those tokens, but the LLM isn't instructed to do so. It's more of a future-proofing guard than an actively used path.

## Tracing methodology (for future investigations)

When asking "does LLM or code decide behavior X?":

1. Find the **filter/check code** → `response_filters.py` (what checks the behavior)
2. Find the **caller** → `run.py:9621` (where does the checked value come from)
3. Trace the **producer** → `agent_result.get("final_response")` → LLM output
4. Check if LLM is **told** about the behavior → `prompt_builder.py` (system prompt)
5. Check for **secondary paths** → `delivery.py` (other silence checks)
