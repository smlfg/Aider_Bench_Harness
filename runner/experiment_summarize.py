from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any

from runner.db import connect, init_db
from runner.fail_fast import check_baseline_fail_fast
from runner.paths import PROJECT_ROOT, SUMMARY_DIR, ensure_project_dirs


PRIMARY_METRICS = (
    "task_success",
    "tests_pass_rate",
    "fail_to_pass_rate",
    "pass_to_pass_rate",
)


def safe_rate(num: int, den: int) -> float:
    return num / den if den else 0.0


def mean(values: list[float]) -> float:
    return statistics.mean(values) if values else 0.0


def variance(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return statistics.pvariance(values)


def fetch_condition_task_rows(iteration: int, condition_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
              task_id,
              COUNT(*) AS n,
              SUM(task_success) AS successes,
              SUM(tests_passed) AS tests_passed,
              SUM(tests_total) AS tests_total,
              SUM(fail_to_pass_passed) AS ftp_passed,
              SUM(fail_to_pass_total) AS ftp_total,
              SUM(pass_to_pass_passed) AS ptp_passed,
              SUM(pass_to_pass_total) AS ptp_total,
              AVG(duration_seconds) AS duration_mean,
              AVG(tokens_in) AS tokens_in_mean,
              AVG(tokens_out) AS tokens_out_mean,
              AVG(files_changed) AS files_changed_mean,
              AVG(lines_added) AS lines_added_mean,
              AVG(lines_removed) AS lines_removed_mean,
              AVG(unrelated_edits_present) AS unrelated_edits_rate,
              AVG(COALESCE(judge_score, 0)) AS judge_score_mean
            FROM runs
            WHERE iteration = ? AND condition_id = ?
            GROUP BY task_id
            ORDER BY task_id
            """,
            (iteration, condition_id),
        ).fetchall()

    out: list[dict[str, Any]] = []
    for row in rows:
        successes = int(row["successes"] or 0)
        n = int(row["n"] or 0)
        tests_passed = int(row["tests_passed"] or 0)
        tests_total = int(row["tests_total"] or 0)
        ftp_passed = int(row["ftp_passed"] or 0)
        ftp_total = int(row["ftp_total"] or 0)
        ptp_passed = int(row["ptp_passed"] or 0)
        ptp_total = int(row["ptp_total"] or 0)

        out.append(
            {
                "task_id": row["task_id"],
                "n": n,
                "successes": successes,
                "task_success": safe_rate(successes, n),
                "tests_pass_rate": safe_rate(tests_passed, tests_total),
                "fail_to_pass_rate": safe_rate(ftp_passed, ftp_total),
                "pass_to_pass_rate": safe_rate(ptp_passed, ptp_total),
                "duration_s_mean": float(row["duration_mean"] or 0.0),
                "tokens_in_mean": float(row["tokens_in_mean"] or 0.0),
                "tokens_out_mean": float(row["tokens_out_mean"] or 0.0),
                "files_changed_mean": float(row["files_changed_mean"] or 0.0),
                "lines_added_mean": float(row["lines_added_mean"] or 0.0),
                "lines_removed_mean": float(row["lines_removed_mean"] or 0.0),
                "unrelated_edits_rate": float(row["unrelated_edits_rate"] or 0.0),
                "judge_score_mean": float(row["judge_score_mean"] or 0.0),
            }
        )
    return out


def aggregate_condition(tasks: list[dict[str, Any]]) -> dict[str, float]:
    if not tasks:
        return {
            "task_success_mean": 0.0,
            "task_success_var": 0.0,
            "tests_pass_rate_mean": 0.0,
            "tests_pass_rate_var": 0.0,
            "fail_to_pass_rate_mean": 0.0,
            "fail_to_pass_rate_var": 0.0,
            "pass_to_pass_rate_mean": 0.0,
            "pass_to_pass_rate_var": 0.0,
            "duration_s_mean": 0.0,
            "tokens_in_mean": 0.0,
            "tokens_out_mean": 0.0,
            "judge_score_mean": 0.0,
        }

    return {
        "task_success_mean": mean([t["task_success"] for t in tasks]),
        "task_success_var": variance([t["task_success"] for t in tasks]),
        "tests_pass_rate_mean": mean([t["tests_pass_rate"] for t in tasks]),
        "tests_pass_rate_var": variance([t["tests_pass_rate"] for t in tasks]),
        "fail_to_pass_rate_mean": mean([t["fail_to_pass_rate"] for t in tasks]),
        "fail_to_pass_rate_var": variance([t["fail_to_pass_rate"] for t in tasks]),
        "pass_to_pass_rate_mean": mean([t["pass_to_pass_rate"] for t in tasks]),
        "pass_to_pass_rate_var": variance([t["pass_to_pass_rate"] for t in tasks]),
        "duration_s_mean": mean([t["duration_s_mean"] for t in tasks]),
        "tokens_in_mean": mean([t["tokens_in_mean"] for t in tasks]),
        "tokens_out_mean": mean([t["tokens_out_mean"] for t in tasks]),
        "judge_score_mean": mean([t["judge_score_mean"] for t in tasks]),
    }


def fetch_conditions(iteration: int) -> list[str]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT condition_id FROM runs WHERE iteration = ? ORDER BY condition_id",
            (iteration,),
        ).fetchall()
    return [r["condition_id"] for r in rows]


def win_loss_vs_baseline(
    baseline_tasks: list[dict[str, Any]], candidate_tasks: list[dict[str, Any]]
) -> tuple[int, int, int]:
    by_task = {t["task_id"]: t for t in candidate_tasks}
    wins = 0
    losses = 0
    ties = 0
    for b in baseline_tasks:
        c = by_task.get(b["task_id"])
        if not c:
            losses += 1
            continue
        if c["task_success"] > b["task_success"]:
            wins += 1
        elif c["task_success"] < b["task_success"]:
            losses += 1
        else:
            ties += 1
    return wins, losses, ties


def experiment_report(iteration: int = 1, baseline: str = "baseline_6line") -> tuple[str, dict[str, Any]]:
    conditions = fetch_conditions(iteration)
    summaries: dict[str, dict[str, Any]] = {}

    for cid in conditions:
        tasks = fetch_condition_task_rows(iteration, cid)
        summaries[cid] = {
            "condition": cid,
            "tasks": tasks,
            "aggregate": aggregate_condition(tasks),
        }

    ff = check_baseline_fail_fast(condition_id=baseline)

    lines: list[str] = [f"# Experiment Report — Iteration {iteration}", ""]
    lines.append("## Fail-Fast")
    lines.append(
        f"- status: {'TRIGGERED' if ff.should_abort else 'ok'}"
    )
    lines.append(f"- reason: {ff.reason or 'none'}")
    lines.append(f"- details: `{json.dumps(ff.details, ensure_ascii=False)}`")
    lines.append("")

    lines.append("## Hard Metrics per Task")
    lines.append(
        "| task_id | condition | success | tests_pass_rate | ftp_rate | ptp_rate | avg_dur_s |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    for cid in conditions:
        for t in summaries[cid]["tasks"]:
            lines.append(
                f"| {t['task_id']} | {cid} | {t['successes']}/{t['n']} "
                f"({t['task_success']:.2f}) | {t['tests_pass_rate']:.2f} | {t['fail_to_pass_rate']:.2f} "
                f"| {t['pass_to_pass_rate']:.2f} | {t['duration_s_mean']:.0f} |"
            )
    lines.append("")

    lines.append("## Aggregate (Primary)")
    lines.append(
        "| condition | success_mean | success_var | tests_pass_mean | tests_pass_var | ftp_mean | ptp_mean |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for cid in conditions:
        a = summaries[cid]["aggregate"]
        lines.append(
            f"| {cid} | {a['task_success_mean']:.2f} | {a['task_success_var']:.4f} | "
            f"{a['tests_pass_rate_mean']:.2f} | {a['tests_pass_rate_var']:.4f} | "
            f"{a['fail_to_pass_rate_mean']:.2f} | {a['pass_to_pass_rate_mean']:.2f} |"
        )
    lines.append("")

    lines.append("## Win/Loss vs Baseline")
    lines.append("| condition | wins | losses | ties | verdict |")
    lines.append("|---|---:|---:|---:|---|")
    baseline_tasks = summaries.get(baseline, {}).get("tasks", [])
    for cid in conditions:
        if cid == baseline:
            continue
        wins, losses, ties = win_loss_vs_baseline(baseline_tasks, summaries[cid]["tasks"])
        if wins > losses:
            verdict = "win"
        elif losses > wins:
            verdict = "loss"
        else:
            verdict = "mixed"
        lines.append(f"| {cid} | {wins} | {losses} | {ties} | {verdict} |")
    lines.append("")

    lines.append("## Secondary (Judge)")
    lines.append("| condition | judge_score_mean |")
    lines.append("|---|---:|")
    for cid in conditions:
        lines.append(
            f"| {cid} | {summaries[cid]['aggregate']['judge_score_mean']:.2f} |"
        )
    lines.append("")

    return "\n".join(lines) + "\n", {
        "iteration": iteration,
        "baseline": baseline,
        "fail_fast": {
            "triggered": ff.should_abort,
            "reason": ff.reason,
            "details": ff.details,
        },
        "conditions": summaries,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Summarize experiment results.")
    parser.add_argument("--iteration", type=int, default=1)
    parser.add_argument("--baseline", default="baseline_6line")
    args = parser.parse_args()

    ensure_project_dirs()
    init_db()
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

    report_md, report_json = experiment_report(
        iteration=args.iteration,
        baseline=args.baseline,
    )

    out_md = SUMMARY_DIR / "experiment_report.md"
    out_json = SUMMARY_DIR / "experiment_report.json"
    out_md.write_text(report_md, encoding="utf-8")
    out_json.write_text(json.dumps(report_json, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote: {out_md}")
    print(f"Wrote: {out_json}")
    print()
    print(report_md)


if __name__ == "__main__":
    main()
