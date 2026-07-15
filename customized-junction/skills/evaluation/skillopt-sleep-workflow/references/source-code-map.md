# SkillOpt-Sleep Source Code Reference

Verified against `D:\workspace\SkillOpt` (microsoft/SkillOpt repo).
git pull failed 2026-07-14 (network), code was already local.

## Cycle Orchestration — cycle.py

`run_sleep_cycle()` (line 91) is the main entry point.

Flow:
```
1. Load state, begin night
2. Resolve live_skill_path + live_memory_path
3. If seed_tasks provided: skip harvest+mine, use them directly
4. Else: harvest_for_config() -> mine() -> TaskRecord[]
5. dream_consolidate() -> replay + gate + edits
6. write_staging() -> proposed_SKILL.md + report + manifest
7. If auto_adopt and accepted: adopt_staging()
```

Key: `seed_tasks` bypasses harvest+mine entirely. When `--tasks-file` is passed,
`__main__.py:143-152` loads it and passes as `seed_tasks`. This is how externally
designed tasks enter the cycle.

## TaskRecord Schema — types.py:45-86

```python
@dataclass
class TaskRecord:
    id: str
    project: str
    intent: str                    # what the user wanted
    context_excerpt: str = ""      # minimal context
    system: str = ""               # optional system framing
    attempted_solution: str = ""   # what agent produced before
    outcome: str = "unknown"       # success | fail | mixed | unknown
    reference_kind: str = "none"   # exact | rubric | rule | none
    reference: str = ""            # exact answer or rubric text
    judge: Dict = {}               # gbrain-style rule judge
    tags: List[str] = []
    source_sessions: List[str] = []
    split: str = "train"           # train | val | test
    origin: str = "real"           # real | dream
    derived_from: str = ""         # for dream tasks
```

## reviewed Gate — __main__.py:153-159

```python
if cfg.get("backend", "mock") != "mock" and task_meta.get("reviewed") is not True:
    print("[sleep] refusing real-backend replay from an unreviewed tasks file; ...")
    return 2
```

Real backend (claude/codex/copilot/handoff) REQUIRES `reviewed: true`.

## Staging — staging.py

`write_staging()` (line 95) creates:
- `proposed_SKILL.md` (if has_skill)
- `proposed_CLAUDE.md` (if has_memory)
- `report.json` (SleepReport.to_dict())
- `report.md` (rendered by `_render_report_md` in cycle.py:59-88)
- `manifest.json` (live paths, accepted flag)
- `diagnostics.json` (written by cycle.py:291-307, redacted)

`adopt()` (line 137) copies staged files over live, with backup to `staging_dir/backup/`.

## SleepReport — types.py:124-146

```python
@dataclass
class SleepReport:
    night: int
    project: str
    baseline_score: float = 0.0
    candidate_score: float = 0.0
    accepted: bool = False
    gate_action: str = ""
    no_edits_reason: str = ""
    edits: List[EditRecord] = []
    rejected_edits: List[EditRecord] = []
    tokens_used: int = 0
    notes: List[str] = []
```

## Handoff Backend — handoff_backend.py

Writes PROMPTS.md + pending.json when LLM calls are needed.
Exit code 3 = pending answers required.
Answers go to `answers/<sha256[:16]>.md`.
Re-run same command to resume.

## CLI Commands

```
run        full cycle: harvest->mine->replay->gate->stage->optional adopt
dry-run    same but report only, no staging/adopt
status     show state + latest staged proposal
adopt      apply latest staged proposal (with backup)
harvest    debug: show mined tasks
schedule   install nightly cron
unschedule remove nightly cron
```

## Config Resolution — __main__.py:97-137

`_cfg_from_args()` maps CLI args to config overrides:
- `--project` -> `invoked_project` + `projects: invoked`
- `--backend` -> `backend`
- `--claude-home` -> `claude_home` (isolates state)
- `--target-skill-path` -> resolved to absolute path
- `--tasks-file` -> loaded separately, `reviewed` checked
