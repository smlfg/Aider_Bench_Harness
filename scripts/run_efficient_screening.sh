#!/usr/bin/env bash
# =============================================================================
# run_efficient_screening.sh
# Führt 25 Runs aus: 5 Tasks × 5 Conditions (1 Run pro Zelle)
#
# Usage: bash scripts/run_efficient_screening.sh [parallel=5]
#
# Bedingungen:
#   1 = baseline_v0              (CONVENTIONS.baseline.md)
#   2 = karpathy_rule_1          (CONVENTIONS.R01.md)
#   3 = karpathy_rule_2          (CONVENTIONS.R02.md)
#   4 = karpathy_rule_3          (CONVENTIONS.R03.md)
#   5 = karpathy_rule_4          (CONVENTIONS.R04.md)
#
# Tasks:
#   django__django-10924
#   django__django-12113
#   sympy__sympy-23117
#   astropy__astropy-14365        (fehlende 2 Tasks — ANPASSEN)
#   astropy__astropy-14182        (fehlende 2 Tasks — ANPASSEN)
#
# Output: results/experiment.db (SQLite), results/<run_id>/
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

PARALLEL="${1:-5}"
TASK_FILE="data/screening_tasks.json"
AGENT_TIMEOUT=600
EVAL_TIMEOUT=600

# --- Farben ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# --- Bedingungs-Mapping ---
# condition_id -> conventions file
declare -A COND_MAP=(
    ["baseline_v0"]="harness/CONVENTIONS.baseline.md"
    ["karpathy_rule_1"]="harness/CONVENTIONS.R01.md"
    ["karpathy_rule_2"]="harness/CONVENTIONS.R02.md"
    ["karpathy_rule_3"]="harness/CONVENTIONS.R03.md"
    ["karpathy_rule_4"]="harness/CONVENTIONS.R04.md"
)

# --- Tasks aus TASK_FILE laden ---
read_tasks_from_file() {
    uv run python -c "
import json, sys
with open('$TASK_FILE') as f:
    tasks = json.load(f)
# Unterstütze sowohl [{}] als auch {'tasks': [{}]}
if isinstance(tasks, list):
    ids = [t['instance_id'] for t in tasks]
elif isinstance(tasks, dict) and 'tasks' in tasks:
    ids = [t['instance_id'] for t in tasks['tasks']]
else:
    ids = [t['instance_id'] for t in tasks]
sys.stdout.write('|' + '|'.join(ids) + '|')
"
}

TASKS_STR=$(read_tasks_from_file)
# Parse: |task1|task2|... → Array
IFS='|' read -ra TASKS <<< "$TASKS_STR"
# Erstes Element ist leer (vor erstem |), daher shift
TASKS=("${TASKS[@]:1}")

# --- Run starten ---
run_one() {
    local task_id="$1"
    local condition_id="$2"
    local conventions_path="${COND_MAP[$condition_id]}"
    local run_id="efficient_screening__${task_id}__${condition_id}"

    log "Starte: task=${task_id} condition=${condition_id} run_id=${run_id}"

    # Prüfe ob Conventions-File existiert
    if [[ ! -f "$conventions_path" ]]; then
        error "Conventions nicht gefunden: $conventions_path"
        return 1
    fi

    # Prüfe ob Task im Task-File existiert
    if ! uv run python -c "
import json
with open('$TASK_FILE') as f:
    tasks = json.load(f)['tasks']
ids = [t['instance_id'] for t in tasks]
if '$task_id' not in ids:
    raise SystemExit(1)
" 2>/dev/null; then
        warn "Task nicht in $TASK_FILE: $task_id — überspringe"
        return 0
    fi

    # Eigentlicher Run
    uv run harness-run-once \
        --task-id "$task_id" \
        --task-file "$TASK_FILE" \
        --condition "$condition_id" \
        --run-id "$run_id" \
        --conventions-path "$conventions_path" \
        --agent-timeout "$AGENT_TIMEOUT" \
        --eval-timeout "$EVAL_TIMEOUT"

    local exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        log "OK: $run_id"
    else
        error "FAIL: $run_id (exit=$exit_code)"
    fi

    return $exit_code
}

# --- Queue + Worker ---
declare -a QUEUE=()

# Queue aufbauen: alle 5×5 = 25 Kombinationen
for condition_id in "${!COND_MAP[@]}"; do
    for task_id in "${TASKS[@]}"; do
        QUEUE+=("$task_id|$condition_id")
    done
done

TOTAL=${#QUEUE[@]}
log "Queue: $TOTAL Runs (${#TASKS[@]} Tasks × ${#COND_MAP[@]} Conditions)"
log "Parallel: $PARALLEL"

# --- Parallel ausführen ---
COMPLETED=0
FAILED=0
PIDS=()

run_next() {
    while true; do
        # Freien Slot finden
        while [[ ${#PIDS[@]} -ge $PARALLEL ]]; do
            sleep 5
            # Check welche PIDs fertig sind
            NEW_PIDS=()
            for pid in "${PIDS[@]}"; do
                if kill -0 "$pid" 2>/dev/null; then
                    NEW_PIDS+=("$pid")
                else
                    wait "$pid" || FAILED=$((FAILED + 1))
                    COMPLETED=$((COMPLETED + 1))
                    echo -ne "\r${GREEN}[$(date +%H:%M:%S)]${NC} Fortschritt: $COMPLETED/$TOTAL (failed=$FAILED)   "
                fi
            done
            PIDS=("${NEW_PIDS[@]}")
            if [[ ${#PIDS[@]} -eq 0 ]] && [[ ${#QUEUE[@]} -eq 0 ]]; then
                break 2
            fi
        done

        # Nächsten Job aus Queue holen
        if [[ ${#QUEUE[@]} -eq 0 ]]; then
            break
        fi

        JOB="${QUEUE[0]}"
        QUEUE=("${QUEUE[@]:1}")

        task_id="${JOB%%|*}"
        condition_id="${JOB#*|}"

        run_one "$task_id" "$condition_id" &
        PID=$!
        PIDS+=("$PID")

        # Kurzer delay damit nicht alle gleichzeitig starten
        sleep 2
    done

    # Warten bis alle PIDs fertig
    for pid in "${PIDS[@]}"; do
        wait "$pid" || FAILED=$((FAILED + 1))
        COMPLETED=$((COMPLETED + 1))
        echo -ne "\r${GREEN}[$(date +%H:%M:%S)]${NC} Fortschritt: $COMPLETED/$TOTAL (failed=$FAILED)   "
    done
}

echo -ne "\r${GREEN}[$(date +%H:%M:%S)]${NC} Starte $TOTAL Runs...   "
run_next
echo ""

log "Fertig: $COMPLETED Runs (failed=$FAILED)"

if [[ $FAILED -gt 0 ]]; then
    warn "$FAILED Runs sind fehlgeschlagen — bitte prüfen"
fi

exit $FAILED
