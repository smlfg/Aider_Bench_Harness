#!/usr/bin/env python3
"""Minimal experiment runner.

Runs: condition × task × run combinations, stores artifacts under experiment/results/.

Usage:
    python runner.py                    # runs full matrix from config.json
    python runner.py --dry-run         # prints what would run without executing
    python runner.py --condition baseline_6line --run 1  # single combination
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = EXPERIMENT_ROOT.parent
CONFIG_PATH = EXPERIMENT_ROOT / "config.json"
TASKS_FILE = EXPERIMENT_ROOT / "tasks" / "tasks.json"
CONDITIONS_DIR = EXPERIMENT_ROOT / "conditions"
RESULTS_DIR = EXPERIMENT_ROOT / "results"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def load_tasks() -> list[dict]:
    return json.loads(TASKS_FILE.read_text(encoding="utf-8"))


def condition_path(condition_id: str) -> Path:
    return CONDITIONS_DIR / condition_id / "CONVENTIONS.md"


def build_run_id(condition_id: str, task_id: str, run_index: int) -> str:
    clean_task = task_id.replace("/", "__")
    return f"{condition_id}_{clean_task}_run{run_index:02d}"


def run_single(
    condition_id: str,
    task_id: str,
    run_index: int,
    model: str,
    agent_timeout: int,
    eval_timeout: int,
) -> dict:
    conventions = condition_path(condition_id)
    run_id = build_run_id(condition_id, task_id, run_index)
    artifacts = RESULTS_DIR / condition_id / task_id / run_id
    artifacts.mkdir(parents=True, exist_ok=True)

    start = utc_now()
    t0 = time.monotonic()

    cmd = [
        sys.executable,
        "-m",
        "runner.run_once",
        "--task-id",
        task_id,
        "--task-file",
        str(TASKS_FILE),
        "--condition",
        condition_id,
        "--iteration",
        "1",
        "--run-index",
        str(run_index),
        "--run-id",
        run_id,
        "--model-name",
        model,
        "--conventions-path",
        str(conventions),
        "--agent-timeout",
        str(agent_timeout),
        "--eval-timeout",
        str(eval_timeout),
    ]

    proc = subprocess.run(cmd, text=True, check=False, cwd=PROJECT_ROOT)
    duration = time.monotonic() - t0

    result = {
        "run_id": run_id,
        "task_id": task_id,
        "condition_id": condition_id,
        "run_index": run_index,
        "start_ts": start,
        "end_ts": utc_now(),
        "duration_s": round(duration, 2),
        "exit_code": proc.returncode,
        "artifacts_dir": str(artifacts),
    }

    (artifacts / "result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return result


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    single_condition = None
    single_run = None

    if "--condition" in sys.argv and "--run" in sys.argv:
        ci = sys.argv.index("--condition")
        ri = sys.argv.index("--run")
        single_condition = sys.argv[ci + 1]
        single_run = int(sys.argv[ri + 1])

    config = load_config()
    tasks = load_tasks()
    conditions = config["conditions"]
    runs_per = config.get("runs_per_condition", 3)
    model = config.get("model", "MiniMax-M2.7-highspeed")
    agent_timeout = config.get("agent_timeout_s", 1800)
    eval_timeout = config.get("eval_timeout_s", 7200)

    total = 0
    for condition in conditions:
        for task in tasks:
            n = runs_per if single_condition is None else (single_run or 1)
            total += n

    print(
        f"[runner] {len(tasks)} tasks × {len(conditions)} conditions × {runs_per} runs = {total} total runs"
    )
    if dry_run:
        print("[runner] dry-run mode, printing commands only")
        for condition in conditions:
            for task in tasks:
                for r in range(1, runs_per + 1):
                    run_id = build_run_id(condition, task["task_id"], r)
                    conventions = condition_path(condition)
                    print(f"  {run_id}: --conventions {conventions}")
        return

    results = []
    for condition in conditions:
        for task in tasks:
            task_id = task["task_id"]
            for r in range(1, runs_per + 1):
                print(f"[runner] {condition} / {task_id} / run{r}", flush=True)
                try:
                    res = run_single(
                        condition, task_id, r, model, agent_timeout, eval_timeout
                    )
                    results.append(res)
                except Exception as exc:
                    print(f"[runner] ERROR: {exc}", flush=True)
                    results.append(
                        {
                            "condition_id": condition,
                            "task_id": task_id,
                            "run_index": r,
                            "error": str(exc),
                        }
                    )

    print(f"[runner] done. {len(results)} runs completed.")
    summary_path = RESULTS_DIR / "run_summary.json"
    summary_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[runner] summary written to {summary_path}")


if __name__ == "__main__":
    main()
