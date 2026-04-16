#!/usr/bin/env bash
set -euo pipefail
DB="${1:-results/experiment.db}"
if ! command -v datasette &>/dev/null; then
  echo "datasette not found. Install with: pip install datasette datasette-vega"
  exit 1
fi
if [ ! -f "$DB" ]; then
  echo "Database not found: $DB"
  exit 1
fi
exec datasette "$DB" --open --metadata web/metadata.yml "${@:2}"