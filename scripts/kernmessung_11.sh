#!/usr/bin/env bash
set -euo pipefail

PROJECT="/home/smlflg/Projekte/FirstRealHarnessEvaluation_KarpathiesMD"
PYTHON="$PROJECT/.venv/bin/python"
TASK_FILE="$PROJECT/data/selected_tasks.json"
TASK_ID="astropy__astropy-12907"
ITERATION=3
LOGDIR="$PROJECT/results/kernmessung_11"
mkdir -p "$LOGDIR"

# Clear old results
rm -rf "$PROJECT/results/v0_plus_"* 2>/dev/null || true

PARALLEL_LIMIT=100
echo "=== Launching 11 runs with correct Python (max $PARALLEL_LIMIT parallel) ==="

# Use env PYTHON to override sys.executable in subprocess calls
# And use the venv python as the main interpreter
export PYTHON="$PYTHON"

$PYTHON -m runner.run_once \
  --task-id "$TASK_ID" --task-file "$TASK_FILE" \
  --condition baseline_v0 \
  --conventions-path "$PROJECT/harness/CONVENTIONS.B.md" \
  --iteration $ITERATION --run-index 1 \
  > "$LOGDIR/B.log" 2>&1 &

$PYTHON -m runner.run_once \
  --task-id "$TASK_ID" --task-file "$TASK_FILE" \
  --condition v0_plus_R01 \
  --conventions-path "$PROJECT/harness/CONVENTIONS.R01.md" \
  --iteration $ITERATION --run-index 1 \
  > "$LOGDIR/R01.log" 2>&1 &

$PYTHON -m runner.run_once \
  --task-id "$TASK_ID" --task-file "$TASK_FILE" \
  --condition v0_plus_R02 \
  --conventions-path "$PROJECT/harness/CONVENTIONS.R02.md" \
  --iteration $ITERATION --run-index 1 \
  > "$LOGDIR/R02.log" 2>&1 &

$PYTHON -m runner.run_once \
  --task-id "$TASK_ID" --task-file "$TASK_FILE" \
  --condition v0_plus_R03 \
  --conventions-path "$PROJECT/harness/CONVENTIONS.R03.md" \
  --iteration $ITERATION --run-index 1 \
  > "$LOGDIR/R03.log" 2>&1 &

$PYTHON -m runner.run_once \
  --task-id "$TASK_ID" --task-file "$TASK_FILE" \
  --condition v0_plus_R04 \
  --conventions-path "$PROJECT/harness/CONVENTIONS.R04.md" \
  --iteration $ITERATION --run-index 1 \
  > "$LOGDIR/R04.log" 2>&1 &

$PYTHON -m runner.run_once \
  --task-id "$TASK_ID" --task-file "$TASK_FILE" \
  --condition v0_plus_R01_R02 \
  --conventions-path "$PROJECT/harness/CONVENTIONS.R01_R02.md" \
  --iteration $ITERATION --run-index 1 \
  > "$LOGDIR/R01_R02.log" 2>&1 &

$PYTHON -m runner.run_once \
  --task-id "$TASK_ID" --task-file "$TASK_FILE" \
  --condition v0_plus_R01_R03 \
  --conventions-path "$PROJECT/harness/CONVENTIONS.R01_R03.md" \
  --iteration $ITERATION --run-index 1 \
  > "$LOGDIR/R01_R03.log" 2>&1 &

$PYTHON -m runner.run_once \
  --task-id "$TASK_ID" --task-file "$TASK_FILE" \
  --condition v0_plus_R01_R04 \
  --conventions-path "$PROJECT/harness/CONVENTIONS.R01_R04.md" \
  --iteration $ITERATION --run-index 1 \
  > "$LOGDIR/R01_R04.log" 2>&1 &

$PYTHON -m runner.run_once \
  --task-id "$TASK_ID" --task-file "$TASK_FILE" \
  --condition v0_plus_R02_R03 \
  --conventions-path "$PROJECT/harness/CONVENTIONS.R02_R03.md" \
  --iteration $ITERATION --run-index 1 \
  > "$LOGDIR/R02_R03.log" 2>&1 &

$PYTHON -m runner.run_once \
  --task-id "$TASK_ID" --task-file "$TASK_FILE" \
  --condition v0_plus_R02_R04 \
  --conventions-path "$PROJECT/harness/CONVENTIONS.R02_R04.md" \
  --iteration $ITERATION --run-index 1 \
  > "$LOGDIR/R02_R04.log" 2>&1 &

$PYTHON -m runner.run_once \
  --task-id "$TASK_ID" --task-file "$TASK_FILE" \
  --condition v0_plus_R03_R04 \
  --conventions-path "$PROJECT/harness/CONVENTIONS.R03_R04.md" \
  --iteration $ITERATION --run-index 1 \
  > "$LOGDIR/R03_R04.log" 2>&1 &

echo "=== 11 launched ==="
sleep 3
ps aux | grep "runner.run_once" | grep -v grep | wc -l
echo "Check logs: tail -f $LOGDIR/*.log"
