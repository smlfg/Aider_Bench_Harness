#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from runner.fail_fast import check_baseline_fail_fast
from runner.paths import PROJECT_ROOT


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_config(cfg: dict) -> None:
    conditions = cfg.get("conditions", {})
    required = {"baseline_6line", "negative_control_karpathy40"}
    missing = required - set(conditions.keys())
    if missing:
        raise SystemExit(f"Missing required conditions: {', '.join(sorted(missing))}")

    for cid, cond in conditions.items():
        conv_path = PROJECT_ROOT / cond["conventions_path"]
        if not conv_path.exists():
            raise SystemExit(
                f"Condition '{cid}' conventions file missing: {conv_path}"
            )


def run_once(
    *,
    task_id: str,
    task_file: Path,
    condition: str,
    conventions_path: Path,
    iteration: int,
    run_index: int,
    model_name: str | None,
    skip_agent: bool,
    skip_eval: bool,
    agent_timeout: int,
    eval_timeout: int,
) -> int:
    cmd = [
        sys.executable,
        "-m",
        "runner.run_once",
        "--task-id",
        task_id,
        "--task-file",
        str(task_file),
        "--condition",
        condition,
        "--conventions-path",
        str(conventions_path),
        "--iteration",
        str(iteration),
        "--run-index",
        str(run_index),
        "--agent-timeout",
        str(agent_timeout),
        "--eval-timeout",
        str(eval_timeout),
    ]
    if model_name:
        cmd += ["--model-name", model_name]
    if skip_agent:
        cmd.append("--skip-agent")
    if skip_eval:
        cmd.append("--skip-eval")
    proc = subprocess.run(cmd, text=True, check=False)
    return proc.returncode


def build_condition_order(cfg: dict, phase: str, baseline_first: bool) -> list[str]:
    all_conditions = list(cfg["conditions"].keys())
    baseline_id = "baseline_6line"

    if phase == "baseline":
        return [baseline_id]

    if baseline_first:
        return [baseline_id] + [cid for cid in all_conditions if cid != baseline_id]
    return all_conditions


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the experiment matrix.")
    parser.add_argument(
        "--config", type=Path, default=PROJECT_ROOT / "data" / "experiment_config.json"
    )
    parser.add_argument("--iteration", type=int, default=1)
    parser.add_argument("--model-name")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--runs-per-task", type=int)
    parser.add_argument("--skip-agent", action="store_true")
    parser.add_argument("--skip-eval", action="store_true")
    parser.add_argument("--phase", choices=["all", "baseline"], default="all")
    parser.add_argument("--baseline-first", action="store_true", default=True)
    parser.add_argument("--no-baseline-first", action="store_false", dest="baseline_first")
    parser.add_argument("--no-fail-fast", action="store_false", dest="fail_fast")
    args = parser.parse_args()

    cfg = load_config(args.config)
    validate_config(cfg)

    exp = cfg["experiment"]
    tasks_path = PROJECT_ROOT / cfg["tasks"]["file"]
    tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
    runs_per_task = (
        args.runs_per_task
        if args.runs_per_task is not None
        else cfg["runs_per_condition_per_task"]
    )

    model_name = args.model_name or cfg.get("model_name")
    agent_timeout = int(cfg.get("agent_timeout_seconds", 1800))
    eval_timeout = int(cfg.get("eval_timeout_seconds", 7200))

    condition_order = build_condition_order(cfg, args.phase, args.baseline_first)

    print(f"=== Experiment: {exp['name']} | iteration {args.iteration} ===")
    print(
        f"Tasks: {len(tasks)} | Conditions: {len(condition_order)} | Runs: {runs_per_task}"
    )
    print(f"Task file: {tasks_path}")
    print(f"Model: {model_name or '(runner default)'}")
    print(f"Agent timeout: {agent_timeout}s | Eval timeout: {eval_timeout}s")
    print()

    total_runs = len(tasks) * len(condition_order) * runs_per_task
    print(f"Total runs: {total_runs}")
    print()

    if args.dry_run:
        print("DRY RUN — would execute:")
        for task in tasks:
            for cond_id in condition_order:
                for r in range(1, runs_per_task + 1):
                    print(f"  {cond_id} | {task['instance_id']} | run {r}")
        return

    results: list[dict] = []
    start_total = time.monotonic()

    baseline_id = "baseline_6line"

    for cond_id in condition_order:
        cond = cfg["conditions"][cond_id]
        conv_path = PROJECT_ROOT / cond["conventions_path"]
        print(f"--- Condition: {cond_id} ({cond['description']}) ---")

        for task in tasks:
            task_id = task["instance_id"]
            for r in range(1, runs_per_task + 1):
                label = f"{cond_id}_{task_id}_run{r:02d}"
                print(f"  [{label}] ", end="", flush=True)
                t0 = time.monotonic()
                rc = run_once(
                    task_id=task_id,
                    task_file=tasks_path,
                    condition=cond_id,
                    conventions_path=conv_path,
                    iteration=args.iteration,
                    run_index=r,
                    model_name=model_name,
                    skip_agent=args.skip_agent,
                    skip_eval=args.skip_eval,
                    agent_timeout=agent_timeout,
                    eval_timeout=eval_timeout,
                )
                dt = time.monotonic() - t0
                status = "OK" if rc == 0 else f"FAIL({rc})"
                print(f"{status} ({dt:.0f}s)")
                results.append(
                    {
                        "condition": cond_id,
                        "task_id": task_id,
                        "run": r,
                        "rc": rc,
                        "duration_s": round(dt, 1),
                    }
                )

        if args.fail_fast and cond_id == baseline_id and args.phase == "all":
            ff = check_baseline_fail_fast(condition_id=baseline_id)
            if ff.should_abort:
                print(f"\nFAIL-FAST TRIGGERED: {ff.reason}")
                dt_total = time.monotonic() - start_total
                n_fail = sum(1 for row in results if row["rc"] != 0)
                print(
                    f"=== ABORTED: {len(results)} runs in {dt_total:.0f}s | {n_fail} failed ==="
                )
                log_path = PROJECT_ROOT / "results" / "experiment_runs.json"
                log_path.parent.mkdir(exist_ok=True)
                log_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
                raise SystemExit(1)
            print(f"  [baseline fail-fast check: {ff.reason or 'ok'}]")

        print()

    dt_total = time.monotonic() - start_total
    n_fail = sum(1 for row in results if row["rc"] != 0)
    print(f"=== Done: {len(results)} runs in {dt_total:.0f}s | {n_fail} failed ===")

    log_path = PROJECT_ROOT / "results" / "experiment_runs.json"
    log_path.parent.mkdir(exist_ok=True)
    log_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Run log: {log_path}")


if __name__ == "__main__":
    main()
