#!/usr/bin/env python3
"""
Baseline variance measurement: 5 runs per selected task using baseline conventions.
Writes to the `runs` table (not calibration_runs).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from runner.paths import (
    DEFAULT_BASELINE_CONVENTIONS,
    DEFAULT_SELECTED_TASKS_PATH,
)


def run_baseline_task(task_id: str, run_index: int) -> None:
    """Run a single baseline measurement."""
    # Ensure we can import runner modules in subprocess
    env = os.environ.copy()
    env["PYTHONPATH"] = (
        f"{Path(__file__).resolve().parents[1]}:{env.get('PYTHONPATH', '')}"
    )

    cmd = [
        sys.executable,
        "-m",
        "runner.run_once",
        "--task-id",
        task_id,
        "--task-file",
        str(DEFAULT_SELECTED_TASKS_PATH),
        "--condition",
        "baseline",
        "--iteration",
        "1",
        "--run-index",
        str(run_index),
        "--conventions-path",
        str(DEFAULT_BASELINE_CONVENTIONS),
    ]
    print(f"Running: {' '.join(cmd)}")
    proc = subprocess.run(cmd, text=True, check=False, env=env)
    if proc.returncode != 0:
        raise SystemExit(f"Baseline run failed for {task_id} run {run_index}")


def main() -> None:
    """Run baseline measurement for all selected tasks (5 runs each)."""
    if not DEFAULT_SELECTED_TASKS_PATH.exists():
        raise SystemExit(
            f"Selected tasks file not found: {DEFAULT_SELECTED_TASKS_PATH}"
        )

    tasks = json.loads(DEFAULT_SELECTED_TASKS_PATH.read_text(encoding="utf-8"))
    if not tasks:
        raise SystemExit("No tasks found in selected_tasks.json")

    print(f"Found {len(tasks)} tasks: {[t['instance_id'] for t in tasks]}")

    for task in tasks:
        task_id = task["instance_id"]
        print(f"\n=== Starting baseline measurement for {task_id} ===")
        for run_index in range(1, 6):  # 1 through 5
            print(f"  Run {run_index}/5")
            run_baseline_task(task_id, run_index)
        print(f"=== Completed {task_id} ===")

    print("\nBaseline measurement complete.")


if __name__ == "__main__":
    main()
