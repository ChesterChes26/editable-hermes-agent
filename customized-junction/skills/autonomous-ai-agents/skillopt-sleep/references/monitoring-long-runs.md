# Monitoring Progress During Long SkillOpt-Sleep Runs

When running SkillOpt-Sleep with `--max-tasks 20` or similar, the consolidate phase can take 15-60+ minutes. Use these indicators to track progress without interrupting the process.

## Progress Indicators

### 1. Staging Directories (Primary Indicator)
```bash
ls -lt <project>/.skillopt-sleep/staging/ | head -5
```
- New timestamped directories appear during consolidate phase (e.g., `20260715-062104`)
- Multiple directories per run = multiple consolidation cycles
- Directory creation timestamps show active progress

### 2. State File
```bash
python -c "import json; d=json.load(open('<project>/.skillopt-sleep/state.json')); print('night:', d.get('night')); print('task_archive:', len(d.get('task_archive',[]))); print('history:', len(d.get('history',[])))"
```
- `night`: Current night number (increments each cycle)
- `task_archive`: Total tasks processed across all nights
- `history`: Night completion records

### 3. Log Files
```bash
tail -50 <project>/.skillopt-exp/<experiment>/logs/skillopt-run-v2.log
```
- Shows recent edits and consolidation output
- JSON structure with `staging_dir`, `adopted`, `tasks_reviewed` fields

## Expected Timing

- **Consolidate phase**: 10-20+ minutes of LLM calls with minimal stdout output
- **Task execution phase**: Faster, visible task-by-task progress
- **Total runtime**: 30-60 minutes for `--max-tasks 20`

## Monitoring Workflow

1. Start process with `background=true, notify_on_complete=true`
2. Check staging directories every 5-10 minutes for new timestamps
3. Review state.json for night/task_archive growth
4. Wait for process completion notification
5. Final output shows: staging_dir path, baseline_score, candidate_score, gate decision

## Signs of Healthy Progress

- ✅ New staging directories appearing (timestamps progressing)
- ✅ state.json `last_harvest` updating
- ✅ Process still running (no exit code)
- ✅ No error output in logs

## Signs of Problems

- ❌ No new staging directories for 20+ minutes
- ❌ Process exited unexpectedly
- ❌ Error messages in log files
- ❌ state.json not updating
