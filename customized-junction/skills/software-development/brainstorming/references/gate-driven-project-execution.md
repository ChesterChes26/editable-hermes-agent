# Gate-Driven Project Execution

When the user wants end-to-end execution but says it feels uncontrollable, do NOT collapse into a single approval. Use a staged gate structure:

## Pattern

```
Gate 0 (spec)  ──→  Gate 1 (freeze)  ──→  Gate 2 (tasks)  ──→  Gate 3 (evidence)  ──→  Gate 4 (proposal+adopt)
```

Each gate:
- **Inputs** — what must exist before opening
- **Artifacts** — concrete files produced
- **Verification checklist** — `- [ ]` items, all checked before advancing
- **Stop conditions** — when to abort without advancing
- **User approval** — explicit user "go" before next gate

## Key Rules

1. **Never skip a gate even if "it was already done in a previous session."** Re-execute clean and present fresh evidence. The user asked for gate-driven control — stale artifacts are not control.

2. **Each gate produces a wiki review page** (see obsidian skill reference). The review page records: what was done, what was verified, what the user asked/answered during review, and the approval decision.

3. **Contamination isolation** — if the project has a "do NOT leak X knowledge into Y environment" constraint, every gate must include an explicit check for contamination. Gate 1 is the freeze point that proves cleanliness before any execution begins.

4. **Don't over-narrate** when the evidence speaks. Present the checklist, mark items `[x]`, and ask for review. Don't explain why each item passed unless the user asks.

## Pitfalls

- **Skipping "redundant" gates**: User says "we already did that." Re-do it anyway. They chose gate-driven for auditability — stale snapshots break the chain.
- **One-shot all gates**: Never propose running all gates in sequence without per-gate approval stops. The user explicitly chose gate-driven over "just do C."
- **No wiki trail**: If there's an Obsidian vault available, create per-gate review pages. Otherwise the user has no record of why they approved each step.
