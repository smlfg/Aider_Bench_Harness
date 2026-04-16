from __future__ import annotations

import argparse
import math
import statistics
from collections import defaultdict

from runner.db import connect, init_db
from runner.paths import SUMMARY_DIR, ensure_project_dirs


def rate(passed: int, total: int) -> float:
    return passed / total if total else 0.0


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    center = (successes + z * z / 2) / (n + z * z)
    margin = z * math.sqrt((successes * (n - successes) / n) + z * z / 4) / (n + z * z)
    return max(0.0, center - margin), min(1.0, center + margin)


def variance_report() -> str:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT task_id, COUNT(*) AS n, SUM(task_success) AS successes,
                   SUM(infrastructure_error) AS infra_errors,
                   AVG(tests_passed * 1.0 / NULLIF(tests_total, 0)) AS pass_rate,
                   AVG(judge_score) AS judge_score
            FROM runs
            WHERE condition_id = 'baseline' AND infrastructure_error = 0
            GROUP BY task_id
            ORDER BY task_id
            """
        ).fetchall()
    lines = ["# Baseline Variance Report", ""]
    lines.append("| task_id | success | 95% CI | mean tests pass rate | mean judge | infra errors |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for row in rows:
        n = int(row["n"])
        successes = int(row["successes"] or 0)
        lo, hi = wilson_interval(successes, n)
        lines.append(
            f"| {row['task_id']} | {successes}/{n} | {lo:.2f}-{hi:.2f} | "
            f"{(row['pass_rate'] or 0):.2f} | {(row['judge_score'] or 0):.2f} | "
            f"{int(row['infra_errors'] or 0)} |"
        )
    return "\n".join(lines) + "\n"


def iteration_report(iteration: int) -> str:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT condition_id, task_id, COUNT(*) AS n, SUM(task_success) AS successes,
                   SUM(infrastructure_error) AS infra_errors,
                   SUM(tests_passed) AS tests_passed, SUM(tests_total) AS tests_total,
                   AVG(duration_seconds) AS duration_seconds,
                   AVG(files_changed + lines_added + lines_removed) AS diff_size,
                   AVG(judge_score) AS judge_score,
                   SUM(COALESCE(cost_estimate, 0)) AS cost_estimate
            FROM runs
            WHERE iteration = ? AND infrastructure_error = 0
            GROUP BY condition_id, task_id
            ORDER BY task_id, condition_id
            """,
            (iteration,),
        ).fetchall()
    by_condition: dict[str, list] = defaultdict(list)
    for row in rows:
        by_condition[row["condition_id"]].append(row)

    lines = [f"# Iteration {iteration}: Baseline vs Candidate", ""]
    lines.append("## Harte Metriken pro Task")
    lines.append("| task_id | condition | success | tests pass rate | cost estimate | infra errors |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for row in rows:
        lines.append(
            f"| {row['task_id']} | {row['condition_id']} | "
            f"{int(row['successes'] or 0)}/{int(row['n'])} | "
            f"{rate(int(row['tests_passed'] or 0), int(row['tests_total'] or 0)):.2f} | "
            f"{float(row['cost_estimate'] or 0):.4f} | "
            f"{int(row['infra_errors'] or 0)} |"
        )

    lines += ["", "## Aggregat"]
    lines.append("| condition | mean task_success | mean tests_pass_rate | mean duration | mean diff_size | total cost |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    condition_success: dict[str, float] = {}
    for condition, condition_rows in by_condition.items():
        run_successes = []
        pass_rates = []
        durations = []
        diff_sizes = []
        total_cost = 0.0
        for row in condition_rows:
            n = int(row["n"])
            run_successes.append((row["successes"] or 0) / n)
            pass_rates.append(rate(int(row["tests_passed"] or 0), int(row["tests_total"] or 0)))
            durations.append(float(row["duration_seconds"] or 0))
            diff_sizes.append(float(row["diff_size"] or 0))
            total_cost += float(row["cost_estimate"] or 0)
        condition_success[condition] = statistics.mean(run_successes) if run_successes else 0.0
        lines.append(
            f"| {condition} | {condition_success[condition]:.2f} | "
            f"{statistics.mean(pass_rates or [0]):.2f} | "
            f"{statistics.mean(durations or [0]):.1f}s | "
            f"{statistics.mean(diff_sizes or [0]):.1f} | {total_cost:.4f} |"
        )

    candidate_names = [name for name in by_condition if name != "baseline"]
    verdict = "no decision"
    if candidate_names and "baseline" in condition_success:
        candidate = candidate_names[0]
        if condition_success[candidate] > condition_success["baseline"]:
            verdict = "candidate wins"
        elif condition_success[candidate] < condition_success["baseline"]:
            verdict = "candidate loses"
    lines += ["", "## Verdict", "", verdict]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize SQLite experiment results.")
    parser.add_argument("--iteration", type=int, default=1)
    args = parser.parse_args()
    ensure_project_dirs()
    init_db()
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    (SUMMARY_DIR / "variance_report.md").write_text(variance_report(), encoding="utf-8")
    (SUMMARY_DIR / f"iteration_{args.iteration}.md").write_text(
        iteration_report(args.iteration),
        encoding="utf-8",
    )
    print(f"Wrote summaries to {SUMMARY_DIR}")


if __name__ == "__main__":
    main()
