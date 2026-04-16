from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
HARNESS_DIR = PROJECT_ROOT / "harness"
RESULTS_DIR = PROJECT_ROOT / "results"
SUMMARY_DIR = RESULTS_DIR / "summary"
DB_PATH = RESULTS_DIR / "experiment.db"
DEFAULT_CANDIDATES_PATH = DATA_DIR / "swebench_lite_candidates.json"
DEFAULT_SELECTED_TASKS_PATH = DATA_DIR / "selected_tasks.json"
DEFAULT_BASELINE_CONVENTIONS = HARNESS_DIR / "CONVENTIONS.baseline.md"


def ensure_project_dirs() -> None:
    for path in (DATA_DIR, HARNESS_DIR, RESULTS_DIR, SUMMARY_DIR):
        path.mkdir(parents=True, exist_ok=True)

