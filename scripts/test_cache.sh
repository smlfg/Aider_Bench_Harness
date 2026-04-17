#!/usr/bin/env bash
set -euo pipefail

PROJECT="/home/smlflg/Projekte/FirstRealHarnessEvaluation_KarpathiesMD"
PYTHON="$PROJECT/.venv/bin/python"
RUNNER="$PYTHON -m runner.run_once"
CACHE="$PROJECT/results/repo_cache"
LOGDIR="$PROJECT/results/test_cache"
mkdir -p "$LOGDIR"

echo "=== Repo Cache Test ==="

# 1. Cold-Start: leere Cache + 1 Run
echo ""
echo "--- Cold-Start (cache cleared) ---"
rm -rf "$CACHE" 2>/dev/null || true

start=$(date +%s.%N)
$RUNNER \
  --task-id astropy__astropy-12907 \
  --task-file "$PROJECT/data/selected_tasks.json" \
  --condition baseline_v0 \
  --conventions-path "$PROJECT/harness/CONVENTIONS.B.md" \
  --iteration 1 --run-index 1 \
  > "$LOGDIR/cold.log" 2>&1
rc=$?
end=$(date +%s.%N)
cold=$(echo "$end - $start" | bc)
echo "Cold: ${cold}s  rc=$rc"
echo "Cached repos: $(ls -d "$CACHE"/*/ 2>/dev/null | wc -l)"

# 2. Warm-Start: gleicher Task, sollte aus Cache kommen
echo ""
echo "--- Warm (from cache) ---"
start=$(date +%s.%N)
$RUNNER \
  --task-id astropy__astropy-12907 \
  --task-file "$PROJECT/data/selected_tasks.json" \
  --condition baseline_v0 \
  --conventions-path "$PROJECT/harness/CONVENTIONS.B.md" \
  --iteration 1 --run-index 2 \
  > "$LOGDIR/warm.log" 2>&1
rc=$?
end=$(date +%s.%N)
warm=$(echo "$end - $start" | bc)
echo "Warm: ${warm}s  rc=$rc"

# Speedup
if command -v bc &>/dev/null; then
  ratio=$(echo "scale=2; $cold / $warm" | bc 2>/dev/null || echo "N/A")
  echo "Speedup: ${ratio}x"
  if (( $(echo "$warm < $cold * 0.7" | bc -l 2>/dev/null) )); then
    echo "✓ Cache working (warm < 70% of cold)"
  else
    echo "⚠ Cache speedup minimal"
  fi
fi

echo ""
echo "=== Logs: $LOGDIR/*.log ==="