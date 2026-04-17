#!/usr/bin/env bash
set -euo pipefail

PROJECT="/home/smlflg/Projekte/FirstRealHarnessEvaluation_KarpathiesMD"
PYTHON="$PROJECT/.venv/bin/python"
TASK_FILE="$PROJECT/data/selected_tasks.json"
TASK_ID="astropy__astropy-12907"
ITERATION=3

# Clear old results directories
for d in B R01 R02 R03 R04 R01_R02 R01_R03 R01_R04 R02_R03 R02_R04 R03_R04; do
  rm -rf "$PROJECT/results/v0_plus_${d}" 2>/dev/null || true
done

# Launch in background with proper disown
launch() {
  local cid="$1"
  local cond="$2"
  local conv="$3"
  
  echo "Launching: $cid"
  $PYTHON -m runner.run_once \
    --task-id "$TASK_ID" \
    --task-file "$TASK_FILE" \
    --condition "$cond" \
    --conventions-path "$conv" \
    --iteration "$ITERATION" \
    --run-index 1 \
    > "$PROJECT/results/${cid}_${TASK_ID}.log" 2>&1 &
}

launch "baseline_v0" "baseline_v0" "$PROJECT/harness/CONVENTIONS.B.md"
launch "v0_plus_R01" "v0_plus_R01" "$PROJECT/harness/CONVENTIONS.R01.md"
launch "v0_plus_R02" "v0_plus_R02" "$PROJECT/harness/CONVENTIONS.R02.md"
launch "v0_plus_R03" "v0_plus_R03" "$PROJECT/harness/CONVENTIONS.R03.md"
launch "v0_plus_R04" "v0_plus_R04" "$PROJECT/harness/CONVENTIONS.R04.md"
launch "v0_plus_R01_R02" "v0_plus_R01_R02" "$PROJECT/harness/CONVENTIONS.R01_R02.md"
launch "v0_plus_R01_R03" "v0_plus_R01_R03" "$PROJECT/harness/CONVENTIONS.R01_R03.md"
launch "v0_plus_R01_R04" "v0_plus_R01_R04" "$PROJECT/harness/CONVENTIONS.R01_R04.md"
launch "v0_plus_R02_R03" "v0_plus_R02_R03" "$PROJECT/harness/CONVENTIONS.R02_R03.md"
launch "v0_plus_R02_R04" "v0_plus_R02_R04" "$PROJECT/harness/CONVENTIONS.R02_R04.md"
launch "v0_plus_R03_R04" "v0_plus_R03_R04" "$PROJECT/harness/CONVENTIONS.R03_R04.md"

echo "=== 11 runs launched ==="
echo "Check status: ps aux | grep runner.run_once"
