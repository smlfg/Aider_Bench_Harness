#!/usr/bin/env bash
set -euo pipefail

PROJECT="/home/smlflg/Projekte/FirstRealHarnessEvaluation_KarpathiesMD"
PYTHON="$PROJECT/.venv/bin/python"
TASK_FILE="$PROJECT/data/selected_tasks.json"
ITERATION=4
LOGDIR="$PROJECT/results/kernmessung_33"
mkdir -p "$LOGDIR"

PARALLEL_LIMIT=100
echo "=== Launching 33 runs (3 Tasks × 11 Conditions) ==="
echo "Max parallel: $PARALLEL_LIMIT"

# Clear old results
rm -rf "$PROJECT/results/v0_plus_"* 2>/dev/null || true

run_one() {
    local task="$1"
    local cond="$2"
    local conv="$3"
    local name="${cond}_${task}"
    echo "Launching: $name"
    $PYTHON -m runner.run_once \
        --task-id "$task" --task-file "$TASK_FILE" \
        --condition "$cond" \
        --conventions-path "$conv" \
        --iteration $ITERATION --run-index 1 \
        > "$LOGDIR/${name}.log" 2>&1 &
}

# Conditions
CONDS=(
  "baseline_v0:$PROJECT/harness/CONVENTIONS.B.md"
  "v0_plus_R01:$PROJECT/harness/CONVENTIONS.R01.md"
  "v0_plus_R02:$PROJECT/harness/CONVENTIONS.R02.md"
  "v0_plus_R03:$PROJECT/harness/CONVENTIONS.R03.md"
  "v0_plus_R04:$PROJECT/harness/CONVENTIONS.R04.md"
  "v0_plus_R01_R02:$PROJECT/harness/CONVENTIONS.R01_R02.md"
  "v0_plus_R01_R03:$PROJECT/harness/CONVENTIONS.R01_R03.md"
  "v0_plus_R01_R04:$PROJECT/harness/CONVENTIONS.R01_R04.md"
  "v0_plus_R02_R03:$PROJECT/harness/CONVENTIONS.R02_R03.md"
  "v0_plus_R02_R04:$PROJECT/harness/CONVENTIONS.R02_R04.md"
  "v0_plus_R03_R04:$PROJECT/harness/CONVENTIONS.R03_R04.md"
)

TASKS=(
  "astropy__astropy-12907"
  "astropy__astropy-14182"
  "astropy__astropy-14365"
)

for task in "${TASKS[@]}"; do
    for cond_entry in "${CONDS[@]}"; do
        cond="${cond_entry%%:*}"
        conv="${cond_entry##*:}"
        run_one "$task" "$cond" "$conv"
    done
done

echo "=== 33 launched ==="
sleep 3
RUNNING=$(ps aux | grep "runner.run_once" | grep -v grep | wc -l)
echo "Running: $RUNNING"
echo "Logs: $LOGDIR/"
