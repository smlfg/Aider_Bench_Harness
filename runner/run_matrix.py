from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from runner.paths import DEFAULT_BASELINE_CONVENTIONS, DEFAULT_SELECTED_TASKS_PATH
from runner.swebench_data import load_task_file


def call_run_once(args: argparse.Namespace, task_id: str, condition: str, run_index: int) -> int:
    cmd = [
        sys.executable,
        "-m",
        "runner.run_once",
        "--task-id",
        task_id,
        "--task-file",
        str(args.task_file),
        "--condition",
        condition,
        "--iteration",
        str(args.iteration),
        "--run-index",
        str(run_index),
        "--conventions-path",
        str(args.candidate_conventions if condition.startswith("candidate") else args.baseline_conventions),
    ]
    if args.model_name:
        cmd += ["--model-name", args.model_name]
    if args.mutation_note and condition.startswith("candidate"):
        cmd += ["--mutation-note", args.mutation_note]
    if args.skip_agent:
        cmd.append("--skip-agent")
    if args.skip_eval:
        cmd.append("--skip-eval")
    if args.synthetic_tests_json:
        cmd += ["--synthetic-tests-json", args.synthetic_tests_json]
    proc = subprocess.run(cmd, text=True, check=False)
    return proc.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the symmetric 3 x 5 x 2 matrix.")
    parser.add_argument("--task-file", type=Path, default=DEFAULT_SELECTED_TASKS_PATH)
    parser.add_argument("--iteration", type=int, default=1)
    parser.add_argument("--baseline-conventions", type=Path, default=DEFAULT_BASELINE_CONVENTIONS)
    parser.add_argument("--candidate-conventions", type=Path, required=True)
    parser.add_argument("--candidate-condition", default="candidate_v1")
    parser.add_argument("--model-name")
    parser.add_argument("--mutation-note")
    parser.add_argument("--runs-per-task", type=int, default=5)
    parser.add_argument("--skip-agent", action="store_true")
    parser.add_argument("--skip-eval", action="store_true")
    parser.add_argument("--synthetic-tests-json")
    args = parser.parse_args()

    tasks = load_task_file(args.task_file)
    if len(tasks) != 3:
        raise SystemExit(f"Expected exactly 3 selected tasks, got {len(tasks)}")
    conditions = ["baseline", args.candidate_condition]
    failures = 0
    for condition in conditions:
        for task in tasks:
            task_id = task.get("task_id") or task["instance_id"]
            for run_index in range(1, args.runs_per_task + 1):
                failures += int(call_run_once(args, task_id, condition, run_index) != 0)
    if failures:
        raise SystemExit(f"{failures} run_once subprocesses failed")


if __name__ == "__main__":
    main()

