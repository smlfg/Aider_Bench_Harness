#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

TASKS=(
  django__django-10924
  django__django-12113
  django__django-16046
  mwaskom__seaborn-3010
  sphinx-doc__sphinx-8595
  sympy__sympy-13043
  sympy__sympy-23117
  sympy__sympy-24909
)

for TASK in "${TASKS[@]}"; do
  RUN_ID="calib1_${TASK}_run01"
  ARTIFACTS="results/calibration/${TASK}/${RUN_ID}"

  if [ -d "$ARTIFACTS" ] && [ -f "$ARTIFACTS/.phase" ]; then
    PHASE=$(cat "$ARTIFACTS/.phase")
    if [ "$PHASE" = "done" ] || [ "$PHASE" = "error" ]; then
      echo "=== SKIP $TASK (phase=$PHASE) ==="
      continue
    fi
  fi

  echo "=== Starting $TASK ==="
  date

  uv run python -m runner.run_once \
    --task-id "$TASK" \
    --task-file data/swebench_lite_candidates.json \
    --condition calibration \
    --iteration 0 \
    --run-index 1 \
    --run-id "$RUN_ID" \
    --conventions-path harness/CONVENTIONS.baseline.md \
    --calibration-round 1 \
    || echo "=== FAILED $TASK ==="

  echo "=== Finished $TASK ==="
  date
  echo ""
done

echo "=== ALL CALIBRATION RUNS COMPLETE ==="
date