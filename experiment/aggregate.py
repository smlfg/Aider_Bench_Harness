#!/usr/bin/env python3
"""Aggregate experiment results and check Fail-Fast condition.

Reads run_meta.json from all experiment/results/ condition/task/run/ directories.
Computes per-condition stats and checks baseline stability.

Fail-Fast: If baseline variance is too high, report INVALID and exit with code 2.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parent
RESULTS_DIR = EXPERIMENT_ROOT / "results"
CONFIG_PATH = EXPERIMENT_ROOT / "config.json"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def load_run_meta(artifacts_dir: Path) -> dict | None:
    path = artifacts_dir / "run_meta.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def collect_results() -> dict[str, list[dict]]:
    results: dict[str, list[dict]] = defaultdict(list)
    if not RESULTS_DIR.exists():
        return results
    for condition_dir in RESULTS_DIR.iterdir():
        if not condition_dir.is_dir():
            continue
        condition_id = condition_dir.name
        for task_dir in condition_dir.iterdir():
            if not task_dir.is_dir():
                continue
            task_id = task_dir.name
            for run_dir in task_dir.iterdir():
                if not run_dir.is_dir():
                    continue
                meta = load_run_meta(run_dir)
                if meta is None:
                    continue
                meta["_condition_dir"] = str(condition_dir)
                meta["_task_id"] = task_id
                results[condition_id].append(meta)
    return results


def mean(lst: list[float]) -> float:
    return statistics.mean(lst) if lst else 0.0


def stdev(lst: list[float]) -> float:
    return statistics.stdev(lst) if len(lst) > 1 else 0.0


def coefficient_of_variation(lst: list[float]) -> float:
    m = mean(lst)
    if m == 0:
        return 0.0
    return stdev(lst) / m


def task_success_rate(runs: list[dict]) -> float:
    if not runs:
        return 0.0
    return sum(1 for r in runs if r.get("task_success", False)) / len(runs)


def tests_pass_rate(runs: list[dict]) -> float:
    totals = [r.get("tests_total", 0) for r in runs]
    passed = [r.get("tests_passed", 0) for r in runs]
    total_sum = sum(totals)
    if total_sum == 0:
        return 0.0
    return sum(passed) / total_sum


def fail_to_pass_rate(runs: list[dict]) -> float:
    """Fraction of FAIL_TO_PASS tests that passed."""
    total = sum(len(r.get("FAIL_TO_PASS", []) or []) for r in runs)
    if total == 0:
        return 0.0
    return 0.0


def pass_to_pass_rate(runs: list[dict]) -> float:
    return 0.0


def unrelated_edits_rate(runs: list[dict]) -> float:
    if not runs:
        return 0.0
    count = sum(1 for r in runs if r.get("unrelated_edits_present", False))
    return count / len(runs)


def compute_condition_stats(results: dict[str, list[dict]], condition_id: str) -> dict:
    runs = results.get(condition_id, [])
    if not runs:
        return {"n_runs": 0}

    task_ids = sorted(set(r["task_id"] for r in runs))
    task_success_rates = []
    task_durations = []

    for task_id in task_ids:
        task_runs = [r for r in runs if r["task_id"] == task_id]
        task_success_rates.append(task_success_rate(task_runs))
        durations = [
            r.get("duration_seconds", 0) for r in task_runs if r.get("duration_seconds")
        ]
        if durations:
            task_durations.append(mean(durations))

    overall_success = task_success_rate(runs)
    overall_tests_pass = tests_pass_rate(runs)
    success_stdev = stdev(task_success_rates) if task_success_rates else 0.0
    duration_cv = coefficient_of_variation(task_durations) if task_durations else 0.0

    return {
        "n_runs": len(runs),
        "n_tasks": len(task_ids),
        "task_success_rate": round(overall_success, 3),
        "tests_pass_rate": round(overall_tests_pass, 3),
        "success_stdev_across_tasks": round(success_stdev, 3),
        "duration_cv": round(duration_cv, 3),
        "mean_duration_s": round(mean(task_durations), 1) if task_durations else 0,
        "infrastructure_errors": sum(
            1 for r in runs if r.get("infrastructure_error", False)
        ),
    }


def check_fail_fast(baseline_stats: dict) -> tuple[bool, str]:
    """Check if baseline variance exceeds thresholds.

    Returns (is_invalid, reason).
    """
    success_cv = baseline_stats.get("success_stdev_across_tasks", 0)
    if success_cv > 0.35:
        return (
            True,
            f"BASELINE_STABILITY_FAILURE: success CV={success_cv:.3f} > 0.35 (too much variance across tasks)",
        )

    duration_cv = baseline_stats.get("duration_cv", 0)
    if duration_cv > 0.6:
        return (
            True,
            f"BASELINE_STABILITY_FAILURE: duration CV={duration_cv:.3f} > 0.6 (runs too variable)",
        )

    return False, ""


def format_markdown_table(results: dict[str, list[dict]], config: dict) -> str:
    conditions = config["conditions"]
    lines = []
    lines.append("# Experiment Results\n")
    lines.append(
        f"| condition | tasks | runs | task_success | tests_pass_rate | success_std | duration_cv | infra_err |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|")

    baseline_stats = None
    for condition_id in conditions:
        stats = compute_condition_stats(results, condition_id)
        if condition_id == "baseline_6line":
            baseline_stats = stats
        lines.append(
            f"| {condition_id} | "
            f"{stats.get('n_tasks', '?')} | "
            f"{stats.get('n_runs', 0)} | "
            f"{stats.get('task_success_rate', 0):.3f} | "
            f"{stats.get('tests_pass_rate', 0):.3f} | "
            f"{stats.get('success_stdev_across_tasks', 0):.3f} | "
            f"{stats.get('duration_cv', 0):.3f} | "
            f"{stats.get('infrastructure_errors', 0)} |"
        )

    lines.append("")

    if baseline_stats:
        is_invalid, reason = check_fail_fast(baseline_stats)
        if is_invalid:
            lines.append(f"## FAIL-FAST: {reason}\n")
        else:
            lines.append(
                f"## Baseline stability: OK (success CV={baseline_stats.get('success_stdev_across_tasks', 0):.3f}, duration CV={baseline_stats.get('duration_cv', 0):.3f})\n"
            )

        baseline_rate = baseline_stats.get("task_success_rate", 0)
        for condition_id in conditions:
            if condition_id == "baseline_6line":
                continue
            stats = compute_condition_stats(results, condition_id)
            candidate_rate = stats.get("task_success_rate", 0)
            if candidate_rate > baseline_rate:
                verdict = f"WIN: +{(candidate_rate - baseline_rate):.3f}"
            elif candidate_rate < baseline_rate:
                verdict = f"LOSS: {(candidate_rate - baseline_rate):.3f}"
            else:
                verdict = "TIE"
            lines.append(f"- **{condition_id}** vs baseline: {verdict}\n")

    return "\n".join(lines)


def main() -> None:
    config = load_config()
    results = collect_results()

    report_dir = RESULTS_DIR / "report"
    report_dir.mkdir(parents=True, exist_ok=True)

    md_report = format_markdown_table(results, config)
    (report_dir / "summary.md").write_text(md_report, encoding="utf-8")

    baseline_stats = compute_condition_stats(results, "baseline_6line")
    is_invalid, reason = check_fail_fast(baseline_stats)

    print(md_report)
    print(f"[aggregate] Report written to {report_dir / 'summary.md'}")

    if is_invalid:
        print(f"[aggregate] FAIL-FAST: {reason}", file=sys.stderr)
        sys.exit(2)

    print("[aggregate] Done.")


if __name__ == "__main__":
    main()
