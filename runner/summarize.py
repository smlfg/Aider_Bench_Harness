from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

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


def stdev_rates(rates: list[float]) -> float:
    if len(rates) < 2:
        return 0.0
    return statistics.stdev(rates)


def variance_report() -> str:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT task_id, COUNT(*) AS n, SUM(task_success) AS successes,
                   SUM(infrastructure_error) AS infra_errors,
                   AVG(1.0 * tests_passed / NULLIF(tests_total, 0)) AS pass_rate,
                   AVG(judge_score) AS judge_score
            FROM runs
            WHERE condition_id = 'baseline' AND infrastructure_error = 0
            GROUP BY task_id
            ORDER BY task_id
            """
        ).fetchall()

    lines = ["# Baseline Variance Report", ""]
    lines.append(
        "| task_id | success | 95% CI | mean tests pass rate | mean judge | infra errors |"
    )
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

    if len(rows) >= 2:
        rates = [
            (int(r["successes"] or 0) / int(r["n"])) for r in rows if int(r["n"]) > 0
        ]
        if len(rates) >= 2:
            mean = statistics.mean(rates)
            stdev = stdev_rates(rates)
            lines += [
                "",
                f"**Aggregate**: mean={mean:.2f}, stdev={stdev:.2f}, CV={stdev / mean if mean else 0:.2f}",
            ]

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
                   AVG(unrelated_edits_present) AS unrelated_rate,
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

    lines = [f"# Iteration {iteration}: Comparison Report", ""]

    condition_ids = sorted(by_condition.keys())
    if not condition_ids:
        lines.append("No data found for this iteration.")
        return "\n".join(lines) + "\n"

    baseline_id = "baseline" if "baseline" in condition_ids else condition_ids[0]
    other_ids = [c for c in condition_ids if c != baseline_id]

    lines.append("## Hard Metrics per Task")
    header = (
        "| task_id | condition | success | tests pass rate | cost | infra | unrelated |"
    )
    lines.append(header)
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    for row in rows:
        lines.append(
            f"| {row['task_id']} | {row['condition_id']} | "
            f"{int(row['successes'] or 0)}/{int(row['n'])} | "
            f"{rate(int(row['tests_passed'] or 0), int(row['tests_total'] or 0)):.2f} | "
            f"{float(row['cost_estimate'] or 0):.4f} | "
            f"{int(row['infra_errors'] or 0)} | "
            f"{float(row['unrelated_rate'] or 0):.2f} |"
        )

    lines += ["", "## Aggregate per Condition"]
    agg_header = "| condition | mean success | stdev | 95% CI | mean pass rate | mean duration | mean diff | total cost |"
    lines.append(agg_header)
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")

    condition_stats: dict[str, dict] = {}
    for condition, condition_rows in by_condition.items():
        run_successes = []
        pass_rates = []
        durations = []
        diff_sizes = []
        total_cost = 0.0
        for row in condition_rows:
            n = int(row["n"])
            run_successes.append((row["successes"] or 0) / n)
            pass_rates.append(
                rate(int(row["tests_passed"] or 0), int(row["tests_total"] or 0))
            )
            durations.append(float(row["duration_seconds"] or 0))
            diff_sizes.append(float(row["diff_size"] or 0))
            total_cost += float(row["cost_estimate"] or 0)

        mean_success = statistics.mean(run_successes) if run_successes else 0.0
        stdev_val = stdev_rates(run_successes)
        successes_list = [int(row["successes"] or 0) for row in condition_rows]
        ns_list = [int(row["n"]) for row in condition_rows]
        total_success = sum(successes_list)
        total_n = sum(ns_list)
        lo, hi = wilson_interval(total_success, total_n)

        condition_stats[condition] = {
            "mean_success": mean_success,
            "stdev": stdev_val,
            "ci": (lo, hi),
            "mean_pass_rate": statistics.mean(pass_rates) if pass_rates else 0.0,
            "mean_duration": statistics.mean(durations) if durations else 0.0,
            "mean_diff": statistics.mean(diff_sizes) if diff_sizes else 0.0,
            "total_cost": total_cost,
        }

        lines.append(
            f"| {condition} | {mean_success:.2f} | {stdev_val:.2f} | [{lo:.2f},{hi:.2f}] | "
            f"{condition_stats[condition]['mean_pass_rate']:.2f} | "
            f"{condition_stats[condition]['mean_duration']:.1f}s | "
            f"{condition_stats[condition]['mean_diff']:.1f} | {total_cost:.4f} |"
        )

    if other_ids and baseline_id in condition_stats:
        lines += ["", "## Win/Loss vs Baseline"]
        win_loss_header = "| task_id | baseline | " + " | ".join(other_ids) + " |"
        lines.append(win_loss_header)
        lines.append("|---|---:|" + "---:|" * len(other_ids))

        tasks_in_rows: dict[str, dict] = {}
        for row in rows:
            tasks_in_rows.setdefault(row["task_id"], {})[row["condition_id"]] = row

        for task_id in sorted(tasks_in_rows.keys()):
            row_vals = [task_id]
            baseline_row = tasks_in_rows[task_id].get(baseline_id, {})
            baseline_n = int(baseline_row.get("n", 0))
            baseline_s = int(baseline_row.get("successes", 0))
            baseline_rate = f"{baseline_s}/{baseline_n}"

            row_vals.append(baseline_rate)
            for cand_id in other_ids:
                cand_row = tasks_in_rows[task_id].get(cand_id, {})
                cand_n = int(cand_row.get("n", 0))
                cand_s = int(cand_row.get("successes", 0))
                delta = (cand_s / cand_n if cand_n else 0) - (
                    baseline_s / baseline_n if baseline_n else 0
                )
                delta_str = f"{cand_s}/{cand_n}"
                if delta > 0:
                    delta_str += " (+)"
                elif delta < 0:
                    delta_str += " (-)"
                row_vals.append(delta_str)
            lines.append("| " + " | ".join(row_vals) + " |")

        lines += ["", "## Condition Win/Loss Summary"]
        summary_header = "| condition | wins | losses | ties | net | verdict |"
        lines.append(summary_header)
        lines.append("|---|---:|---:|---:|---:|---|")

        for cand_id in other_ids:
            wins = losses = ties = 0
            for task_id, task_rows in tasks_in_rows.items():
                baseline_row = task_rows.get(baseline_id, {})
                cand_row = task_rows.get(cand_id, {})

                baseline_n = int(baseline_row.get("n", 0))
                baseline_s = int(baseline_row.get("successes", 0))
                cand_n = int(cand_row.get("n", 0))
                cand_s = int(cand_row.get("successes", 0))

                baseline_rate = baseline_s / baseline_n if baseline_n else 0
                cand_rate = cand_s / cand_n if cand_n else 0

                if cand_rate > baseline_rate:
                    wins += 1
                elif cand_rate < baseline_rate:
                    losses += 1
                else:
                    ties += 1

            net = wins - losses
            if net > 0:
                verdict = "**WIN**"
            elif net < 0:
                verdict = "**LOSS**"
            else:
                verdict = "tie"

            lines.append(
                f"| {cand_id} | {wins} | {losses} | {ties} | {net:+d} | {verdict} |"
            )

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
