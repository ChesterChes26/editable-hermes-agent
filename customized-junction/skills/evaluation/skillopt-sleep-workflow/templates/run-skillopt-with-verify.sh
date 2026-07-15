#!/usr/bin/env bash
# SkillOpt-Sleep execution wrapper
# Bundles baseline verification + env setup + SkillOpt invocation
# Usage: ./run-skillopt-with-verify.sh [extra-args...]
#
# Customize these variables for your project before first use.

set -e

# ── Project paths (edit per project) ─────────────────────────────────────────
PROJECT_ROOT="D:/workspace/outlook-tencent-metting"
EXP_DIR="$PROJECT_ROOT/.skillopt-exp/outlook-tencent-meeting-hybrid-en"
TARGET_SKILL="$PROJECT_ROOT/.claude/skills/computer-use/outlook-tencent-meeting-hybrid-en/SKILL.md"
TASKS_FILE="$EXP_DIR/tasks/tasks.v2.json"
CLAUDE_HOME="$EXP_DIR/claude-home"
SKILLOPT_SRC="D:/workspace/SkillOpt"  # where `python -m skillopt_sleep` lives

# ── Baseline verification ────────────────────────────────────────────────────
BASELINE_HEAD_FILE="$EXP_DIR/baseline/git-head.txt"

echo "=== 验证 baseline ==="

if [ ! -f "$BASELINE_HEAD_FILE" ]; then
  echo "ERROR: baseline git-head.txt not found"
  echo "  Expected: $BASELINE_HEAD_FILE"
  echo "  Run stage ① first to fix baseline"
  exit 1
fi

baseline_head=$(cat "$BASELINE_HEAD_FILE")
current_head=$(cd "$PROJECT_ROOT" && git rev-parse HEAD)

echo "Baseline HEAD: $baseline_head"
echo "Current HEAD:  $current_head"

if [ "$baseline_head" != "$current_head" ]; then
  echo ""
  echo "ERROR: baseline is stale"
  echo "  baseline: $baseline_head"
  echo "  current:  $current_head"
  echo ""
  echo "SkillOpt would optimize old code, not current code."
  echo "Re-run stage ① to fix baseline with current HEAD:"
  echo ""
  echo "  cd $PROJECT_ROOT"
  echo "  git rev-parse HEAD > $BASELINE_HEAD_FILE"
  echo "  cp $TARGET_SKILL $EXP_DIR/baseline/SKILL.baseline.md"
  echo "  sha256sum $TARGET_SKILL > $EXP_DIR/baseline/SKILL.baseline.sha256"
  exit 1
fi

echo "PASS: baseline matches current HEAD"
echo ""

# ── Run SkillOpt ─────────────────────────────────────────────────────────────
echo "=== 执行 SkillOpt (claude backend, edit-budget 4) ==="
cd "$SKILLOPT_SRC"

ANTHROPIC_API_KEY=placeholder python -m skillopt_sleep run \
  --project "$PROJECT_ROOT" \
  --claude-home "$CLAUDE_HOME" \
  --target-skill-path "$TARGET_SKILL" \
  --tasks-file "$TASKS_FILE" \
  --backend claude \
  --max-tasks 20 \
  --edit-budget 4 \
  --progress \
  --json "$@"
