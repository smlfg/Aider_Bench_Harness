from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from runner.db import connect, init_db
from runner.paths import (
    DEFAULT_BASELINE_CONVENTIONS,
    DEFAULT_CANDIDATES_PATH,
    DEFAULT_SELECTED_TASKS_PATH,
    ensure_project_dirs,
)
from runner.swebench_data import load_task_file, write_candidates


def run_calibration_task(args: argparse.Namespace, task_id: str, round_index: int) -> None:
    for run_index in range(1, 4):
        cmd = [
            sys.executable,
            "-m",
            "runner.run_once",
            "--task-id",
            task_id,
            "--task-file",
            str(args.candidates_file),
            "--condition",
            "calibration",
            "--iteration",
            "0",
            "--run-index",
            str(run_index),
            "--calibration-round",
            str(round_index),
            "--run-id",
            f"calibration_r{round_index}_{task_id}_run{run_index:02d}",
            "--conventions-path",
            str(args.conventions_path),
        ]
        if args.model_name:
            cmd += ["--model-name", args.model_name]
        if args.skip_agent:
            cmd.append("--skip-agent")
        if args.skip_eval:
            cmd.append("--skip-eval")
        if args.synthetic_tests_json:
            cmd += ["--synthetic-tests-json", args.synthetic_tests_json]
        proc = subprocess.run(cmd, text=True, check=False)
        if proc.returncode != 0:
            raise SystemExit(f"Calibration run failed for {task_id} run {run_index}")


def classify(round_index: int) -> dict[str, int]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT task_id, SUM(task_success) AS successes
            FROM calibration_runs
            WHERE round = ?
            GROUP BY task_id
            """,
            (round_index,),
        ).fetchall()
    return {row["task_id"]: int(row["successes"] or 0) for row in rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate SWE-bench Lite tasks.")
    parser.add_argument("--candidates-file", type=Path, default=DEFAULT_CANDIDATES_PATH)
    parser.add_argument("--selected-output", type=Path, default=DEFAULT_SELECTED_TASKS_PATH)
    parser.add_argument("--conventions-path", type=Path, default=DEFAULT_BASELINE_CONVENTIONS)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--model-name")
    parser.add_argument("--skip-agent", action="store_true")
    parser.add_argument("--skip-eval", action="store_true")
    parser.add_argument("--synthetic-tests-json")
    args = parser.parse_args()

    ensure_project_dirs()
    init_db()
    if not args.candidates_file.exists():
        write_candidates(args.candidates_file)
    candidates = load_task_file(args.candidates_file)
    selected: list[dict] = []
    offset = 0
    for round_index in range(1, args.rounds + 1):
        batch = candidates[offset : offset + args.batch_size]
        offset += args.batch_size
        if not batch:
            break
        for task in batch:
            run_calibration_task(args, task["instance_id"], round_index)
        successes = classify(round_index)
        keep_ids = {task_id for task_id, count in successes.items() if count in (1, 2)}
        selected.extend(task for task in batch if task["instance_id"] in keep_ids)
        if len(selected) >= 3:
            args.selected_output.write_text(
                json.dumps(selected[:3], indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"Selected 3 tasks in {args.selected_output}")
            return
    raise SystemExit("Calibration failed: fewer than 3 discriminatory tasks after two rounds")


if __name__ == "__main__":
    main()

