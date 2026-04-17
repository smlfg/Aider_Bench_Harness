from __future__ import annotations

import statistics
from dataclasses import dataclass

from runner.db import connect


@dataclass
class FailFastResult:
    should_abort: bool
    reason: str | None
    details: dict


def check_calibration_fail_fast(calibration_round: int | None = None) -> FailFastResult:
    """
    Check calibration results for fail-fast conditions.

    Called after calibration phase to determine if the experiment setup
    is viable before running the full measurement matrix.
    """
    with connect() as conn:
        if calibration_round is not None:
            rows = conn.execute(
                """
                SELECT task_id, COUNT(*) AS n, SUM(task_success) AS successes,
                       SUM(infrastructure_error) AS infra_errors
                FROM calibration_runs
                WHERE round = ?
                GROUP BY task_id
                """,
                (calibration_round,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT task_id, COUNT(*) AS n, SUM(task_success) AS successes,
                       SUM(infrastructure_error) AS infra_errors
                FROM calibration_runs
                GROUP BY task_id
                """
            ).fetchall()

    if not rows:
        return FailFastResult(
            should_abort=True,
            reason="No calibration runs found",
            details={},
        )

    task_success_rates: list[float] = []
    discriminative_tasks = 0
    too_hard = 0
    too_easy = 0
    infra_errors = 0

    for row in rows:
        n = int(row["n"])
        successes = int(row["successes"] or 0)
        infra = int(row["infra_errors"] or 0)
        infra_errors += infra

        if infra > 0 and successes == 0:
            continue

        rate = successes / n if n > 0 else 0.0
        task_success_rates.append(rate)

        if rate == 0.0 or rate == 1.0:
            continue
        discriminative_tasks += 1

        if rate < 0.33:
            too_hard += 1
        if rate > 0.67:
            too_easy += 1

    if infra_errors > len(rows) * 0.5:
        return FailFastResult(
            should_abort=True,
            reason=f"Too many infrastructure errors: {infra_errors}/{len(rows)} tasks affected",
            details={"infra_errors": infra_errors, "total_tasks": len(rows)},
        )

    if discriminative_tasks < 2:
        return FailFastResult(
            should_abort=True,
            reason=f"Fewer than 2 discriminative tasks: found {discriminative_tasks}",
            details={
                "discriminative_tasks": discriminative_tasks,
                "task_success_rates": task_success_rates,
            },
        )

    if task_success_rates:
        min_rate = min(task_success_rates)
        max_rate = max(task_success_rates)
        rate_range = max_rate - min_rate

        if rate_range > 0.66:
            return FailFastResult(
                should_abort=True,
                reason=f"Task success rate range too large: {rate_range:.2f}",
                details={
                    "min_rate": min_rate,
                    "max_rate": max_rate,
                    "range": rate_range,
                    "task_success_rates": task_success_rates,
                },
            )

    return FailFastResult(
        should_abort=False,
        reason=None,
        details={
            "discriminative_tasks": discriminative_tasks,
            "task_success_rates": task_success_rates,
            "infra_errors": infra_errors,
        },
    )


def check_baseline_fail_fast(
    condition_id: str = "baseline_6line",
    max_stdev: float = 0.35,
    min_discriminative: int = 2,
    max_infra_error_rate: float = 0.30,
) -> FailFastResult:
    """
    Baseline reproducibility gate.

    Abort when baseline is too noisy/unstable to support condition comparisons.
    """
    with connect() as conn:
        total_rows = conn.execute(
            "SELECT COUNT(*) AS n FROM runs WHERE condition_id = ?",
            (condition_id,),
        ).fetchone()
        infra_rows = conn.execute(
            "SELECT COUNT(*) AS n FROM runs WHERE condition_id = ? AND infrastructure_error = 1",
            (condition_id,),
        ).fetchone()
        task_rows = conn.execute(
            """
            SELECT task_id, COUNT(*) AS n, SUM(task_success) AS successes
            FROM runs
            WHERE condition_id = ?
            GROUP BY task_id
            ORDER BY task_id
            """,
            (condition_id,),
        ).fetchall()

    total_runs = int(total_rows["n"] or 0)
    infra_errors = int(infra_rows["n"] or 0)

    if total_runs == 0:
        return FailFastResult(
            should_abort=True,
            reason=f"No runs found for condition {condition_id}",
            details={},
        )

    infra_error_rate = infra_errors / total_runs
    if infra_error_rate > max_infra_error_rate:
        return FailFastResult(
            should_abort=True,
            reason=(
                f"Infrastructure failure rate too high ({infra_error_rate:.2f} > "
                f"{max_infra_error_rate:.2f})"
            ),
            details={
                "total_runs": total_runs,
                "infra_errors": infra_errors,
                "infra_error_rate": infra_error_rate,
            },
        )

    if not task_rows:
        return FailFastResult(
            should_abort=True,
            reason=f"No task-level baseline rows found for condition {condition_id}",
            details={},
        )

    task_success_rates: list[float] = []
    discriminative = 0

    for row in task_rows:
        n = int(row["n"] or 0)
        successes = int(row["successes"] or 0)
        rate = successes / n if n else 0.0
        task_success_rates.append(rate)
        if 0.0 < rate < 1.0:
            discriminative += 1

    if discriminative < min_discriminative:
        return FailFastResult(
            should_abort=True,
            reason=(
                f"Fewer than {min_discriminative} discriminative baseline tasks: "
                f"{discriminative}/{len(task_rows)}"
            ),
            details={
                "discriminative": discriminative,
                "task_count": len(task_rows),
                "task_success_rates": task_success_rates,
            },
        )

    stdev = statistics.pstdev(task_success_rates) if len(task_success_rates) > 1 else 0.0
    if stdev > max_stdev:
        return FailFastResult(
            should_abort=True,
            reason=f"Baseline variance too high (stdev={stdev:.2f} > {max_stdev:.2f})",
            details={
                "stdev": stdev,
                "max_stdev": max_stdev,
                "task_success_rates": task_success_rates,
            },
        )

    return FailFastResult(
        should_abort=False,
        reason=None,
        details={
            "total_runs": total_runs,
            "infra_errors": infra_errors,
            "infra_error_rate": infra_error_rate,
            "discriminative": discriminative,
            "task_success_rates": task_success_rates,
            "stdev": stdev,
        },
    )


def check_iteration_fail_fast(
    iteration: int,
    baseline_id: str = "baseline",
    min_wins: int = 1,
) -> FailFastResult:
    """
    Check iteration comparison results for abort conditions.

    Compares all non-baseline conditions in this iteration against baseline.
    """
    with connect() as conn:
        baseline_rows = conn.execute(
            """
            SELECT task_id, AVG(1.0 * task_success) AS avg_success
            FROM runs
            WHERE condition_id = ? AND iteration = ? AND infrastructure_error = 0
            GROUP BY task_id
            """,
            (baseline_id, iteration),
        ).fetchall()

        candidate_conditions = conn.execute(
            """
            SELECT DISTINCT condition_id
            FROM runs
            WHERE iteration = ? AND condition_id != ?
            """,
            (iteration, baseline_id),
        ).fetchall()

    if not baseline_rows:
        return FailFastResult(
            should_abort=True,
            reason=f"No baseline rows for iteration {iteration}",
            details={},
        )

    baseline_rates = {row["task_id"]: row["avg_success"] for row in baseline_rows}

    for cand_row in candidate_conditions:
        cand_id = cand_row["condition_id"]
        cand_rows = conn.execute(
            """
            SELECT task_id, AVG(1.0 * task_success) AS avg_success
            FROM runs
            WHERE condition_id = ? AND iteration = ? AND infrastructure_error = 0
            GROUP BY task_id
            """,
            (cand_id, iteration),
        ).fetchall()

        cand_rates = {row["task_id"]: row["avg_success"] for row in cand_rows}

        wins = 0
        losses = 0
        for task_id, baseline_val in baseline_rates.items():
            cand_val = cand_rates.get(task_id, 0.0)
            if cand_val > baseline_val:
                wins += 1
            elif cand_val < baseline_val:
                losses += 1

        if losses > 0 and wins == 0:
            return FailFastResult(
                should_abort=True,
                reason=f"Condition {cand_id} loses on all tasks vs baseline",
                details={"wins": wins, "losses": losses, "condition": cand_id},
            )

    return FailFastResult(
        should_abort=False,
        reason=None,
        details={},
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fail-fast checks for experiment")
    parser.add_argument(
        "--check",
        choices=["calibration", "baseline", "iteration"],
        default="baseline",
    )
    parser.add_argument("--round", type=int, default=None)
    parser.add_argument("--iteration", type=int, default=1)
    parser.add_argument("--condition", default="baseline_6line")
    args = parser.parse_args()

    if args.check == "calibration":
        result = check_calibration_fail_fast(args.round)
    elif args.check == "baseline":
        result = check_baseline_fail_fast(args.condition)
    else:
        result = check_iteration_fail_fast(args.iteration)

    print(f"should_abort: {result.should_abort}")
    if result.reason:
        print(f"reason: {result.reason}")
    print(f"details: {result.details}")

    if result.should_abort:
        raise SystemExit(1)
