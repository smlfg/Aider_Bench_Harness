#!/usr/bin/env bash
set -euo pipefail

PROJECT="/home/smlflg/Projekte/FirstRealHarnessEvaluation_KarpathiesMD"
PYTHON="$PROJECT/.venv/bin/python"
RUNNER="$PYTHON -m runner.run_once"
TASK_FILE="data/selected_tasks.json"
ITERATION=2
JOBS="${1:-10}"
LOGDIR="$PROJECT/results/run_75_logs"
mkdir -p "$LOGDIR"

TASKS=(
  astropy__astropy-12907
  astropy__astropy-14182
  astropy__astropy-14365
)

declare -A COND_NAME
declare -A COND_PATH

COND_NAME[C0]="baseline_v0"
COND_PATH[C0]="harness/CONVENTIONS.baseline.md"

COND_NAME[C1]="v0_plus_R01"
COND_PATH[C1]="harness/CONVENTIONS.v0_plus_R01.md"

COND_NAME[C2]="v0_plus_R02"
COND_PATH[C2]="harness/CONVENTIONS.v0_plus_R02.md"

COND_NAME[C3]="v0_plus_R03"
COND_PATH[C3]="harness/CONVENTIONS.v0_plus_R03.md"

COND_NAME[C4]="v0_plus_R04"
COND_PATH[C4]="harness/CONVENTIONS.v0_plus_R04.md"

CMDS_FILE="$LOGDIR/all_commands.txt"
> "$CMDS_FILE"

for cid in C0 C1 C2 C3 C4; do
  cond="${COND_NAME[$cid]}"
  conv="${COND_PATH[$cid]}"
  for task in "${TASKS[@]}"; do
    for idx in 1 2 3 4 5; do
      run_id="${cond}_${task}_run${idx}"
      logfile="$LOGDIR/${run_id}.log"
      echo "$RUNNER --task-id $task --task-file $TASK_FILE --condition $cond --conventions-path $conv --iteration $ITERATION --run-index $idx > '$logfile' 2>&1; echo \"EXIT=\$? run_id=$run_id\" >> '$logfile'" >> "$CMDS_FILE"
    done
  done
done

TOTAL=$(wc -l < "$CMDS_FILE")
echo "=== 75-Run Batch ==="
echo "Commands: $TOTAL"
echo "Parallel: $JOBS"
echo "Logs:     $LOGDIR/"
echo "Starting in 3s ... Ctrl+C to abort"
sleep 3

cd "$PROJECT"
xargs -P "$JOBS" -I {} bash -c "{}" < "$CMDS_FILE"

echo "=== All runs submitted ==="
echo "Check logs: ls $LOGDIR/*.log"
