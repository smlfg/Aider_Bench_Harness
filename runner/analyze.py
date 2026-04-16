from __future__ import annotations

import argparse
import math
import warnings
from dataclasses import dataclass

import numpy as np
from scipy import stats as sp_stats

from runner.db import connect, init_db
from runner.paths import RESULTS_DIR, ensure_project_dirs

ANALYSIS_SCHEMA = """
CREATE TABLE IF NOT EXISTS analysis (
  iteration INTEGER NOT NULL,
  condition TEXT NOT NULL,
  metric TEXT NOT NULL,
  n INTEGER NOT NULL,
  point_estimate REAL NOT NULL,
  ci_low REAL,
  ci_high REAL,
  method TEXT NOT NULL,
  PRIMARY KEY (iteration, condition, metric)
);

CREATE TABLE IF NOT EXISTS comparisons (
  iteration INTEGER NOT NULL,
  metric TEXT NOT NULL,
  baseline_estimate REAL,
  candidate_estimate REAL,
  delta REAL,
  test_name TEXT NOT NULL,
  p_value REAL,
  effect_size REAL,
  composite REAL,
  PRIMARY KEY (iteration, metric)
);

CREATE TABLE IF NOT EXISTS trajectory (
  iteration INTEGER PRIMARY KEY,
  conventions_hash TEXT,
  mutation_note TEXT,
  parent_hash TEXT,
  cumulative_success_rate REAL,
  cumulative_diff_size_loc_mean REAL,
  pareto_dominated INTEGER NOT NULL DEFAULT 0
);
"""


def wilson_interval(
    successes: int, n: int, z: float = 1.96
) -> tuple[float, float, float]:
    if n == 0:
        return 0.0, 0.0, 1.0
    p_hat = successes / n
    center = (successes + z * z / 2) / (n + z * z)
    margin = z * math.sqrt((successes * (n - successes) / n) + z * z / 4) / (n + z * z)
    return p_hat, max(0.0, center - margin), min(1.0, center + margin)


def bootstrap_ci(
    data: list[float], n_resamples: int = 10_000, ci: float = 0.95, stat_fn=np.mean
) -> tuple[float, float, float]:
    if len(data) == 0:
        return 0.0, 0.0, 0.0
    arr = np.array(data)
    point = float(stat_fn(arr))
    if len(data) < 2:
        return point, point, point
    boot = np.array(
        [
            stat_fn(np.random.choice(arr, size=len(arr), replace=True))
            for _ in range(n_resamples)
        ]
    )
    lo = float(np.percentile(boot, (1 - ci) / 2 * 100))
    hi = float(np.percentile(boot, (1 + ci) / 2 * 100))
    return point, lo, hi


def bootstrap_median_ci(
    data: list[float], n_resamples: int = 10_000, ci: float = 0.95
) -> tuple[float, float, float]:
    return bootstrap_ci(data, n_resamples=n_resamples, ci=ci, stat_fn=np.median)


def cliffs_delta(a: list[float], b: list[float]) -> tuple[float, str]:
    n_a = len(a)
    n_b = len(b)
    if n_a == 0 or n_b == 0:
        return 0.0, "negligible"
    more = 0
    less = 0
    for x in a:
        for y in b:
            if x > y:
                more += 1
            elif x < y:
                less += 1
    d = (more - less) / (n_a * n_b)
    abs_d = abs(d)
    if abs_d < 0.147:
        magnitude = "negligible"
    elif abs_d < 0.33:
        magnitude = "small"
    elif abs_d < 0.474:
        magnitude = "medium"
    else:
        magnitude = "large"
    return d, magnitude


@dataclass
class ConditionData:
    task_successes: list[int]
    tests_pass_rates: list[float]
    diff_size_locs: list[int]
    files_changed: list[int]
    durations: list[float]
    judge_scores: list[float]


def extract_diff_size_loc(row: dict) -> int:
    return int(row["lines_added"]) + int(row["lines_removed"])


def load_runs_for_iteration(conn, iteration: int) -> dict[str, ConditionData]:
    rows = conn.execute(
        """
        SELECT condition_id, task_success, tests_passed, tests_total,
               lines_added, lines_removed, files_changed,
               duration_seconds, judge_score
        FROM runs
        WHERE iteration = ? AND infrastructure_error = 0
        ORDER BY condition_id, run_id
        """,
        (iteration,),
    ).fetchall()

    by_condition: dict[str, ConditionData] = {}
    for row in rows:
        cond = row["condition_id"]
        if cond not in by_condition:
            by_condition[cond] = ConditionData(
                task_successes=[],
                tests_pass_rates=[],
                diff_size_locs=[],
                files_changed=[],
                durations=[],
                judge_scores=[],
            )
        cd = by_condition[cond]
        cd.task_successes.append(int(row["task_success"]))
        total = int(row["tests_total"]) if row["tests_total"] else 0
        passed = int(row["tests_passed"]) if row["tests_passed"] else 0
        cd.tests_pass_rates.append(passed / total if total > 0 else 0.0)
        cd.diff_size_locs.append(int(row["lines_added"]) + int(row["lines_removed"]))
        cd.files_changed.append(int(row["files_changed"]))
        cd.durations.append(float(row["duration_seconds"]))
        if row["judge_score"] is not None:
            cd.judge_scores.append(float(row["judge_score"]))
    return by_condition


def compute_analysis(
    conn, iteration: int, condition: str, cd: ConditionData
) -> list[dict]:
    rows: list[dict] = []
    n = len(cd.task_successes)
    if n == 0:
        warnings.warn(f"No runs for iteration={iteration} condition={condition}")
        return rows

    successes = sum(cd.task_successes)
    point, lo, hi = wilson_interval(successes, n)
    rows.append(
        {
            "iteration": iteration,
            "condition": condition,
            "metric": "task_success",
            "n": n,
            "point_estimate": point,
            "ci_low": lo,
            "ci_hi": hi,
            "method": "wilson",
        }
    )

    point, lo, hi = bootstrap_ci(cd.tests_pass_rates)
    rows.append(
        {
            "iteration": iteration,
            "condition": condition,
            "metric": "tests_pass_rate",
            "n": n,
            "point_estimate": point,
            "ci_low": lo,
            "ci_hi": hi,
            "method": "bootstrap_mean",
        }
    )

    point, lo, hi = bootstrap_ci([float(x) for x in cd.diff_size_locs])
    rows.append(
        {
            "iteration": iteration,
            "condition": condition,
            "metric": "diff_size_loc",
            "n": n,
            "point_estimate": point,
            "ci_low": lo,
            "ci_hi": hi,
            "method": "bootstrap_mean",
        }
    )

    point, lo, hi = bootstrap_ci([float(x) for x in cd.files_changed])
    rows.append(
        {
            "iteration": iteration,
            "condition": condition,
            "metric": "files_changed",
            "n": n,
            "point_estimate": point,
            "ci_low": lo,
            "ci_hi": hi,
            "method": "bootstrap_mean",
        }
    )

    point, lo, hi = bootstrap_ci(cd.durations)
    rows.append(
        {
            "iteration": iteration,
            "condition": condition,
            "metric": "duration_seconds",
            "n": n,
            "point_estimate": point,
            "ci_low": lo,
            "ci_hi": hi,
            "method": "bootstrap_mean",
        }
    )

    if cd.judge_scores:
        point, lo, hi = bootstrap_median_ci(cd.judge_scores)
        rows.append(
            {
                "iteration": iteration,
                "condition": condition,
                "metric": "judge_score",
                "n": len(cd.judge_scores),
                "point_estimate": point,
                "ci_low": lo,
                "ci_hi": hi,
                "method": "bootstrap_median",
            }
        )

    for r in rows:
        if r["n"] < 5:
            warnings.warn(
                f"Small n={r['n']} for iteration={iteration} condition={condition} "
                f"metric={r['metric']}: CIs unstable"
            )
    return rows


def compute_comparisons(
    iteration: int,
    baseline: ConditionData,
    candidate: ConditionData,
) -> list[dict]:
    rows: list[dict] = []

    b_successes = sum(baseline.task_successes)
    c_successes = sum(candidate.task_successes)
    b_n = len(baseline.task_successes)
    c_n = len(candidate.task_successes)
    b_rate = b_successes / b_n if b_n else 0.0
    c_rate = c_successes / c_n if c_n else 0.0

    if b_n > 0 and c_n > 0:
        table = [[b_successes, b_n - b_successes], [c_successes, c_n - c_successes]]
        try:
            _, p_value = sp_stats.fisher_exact(table)
        except ValueError:
            p_value = None
        rows.append(
            {
                "iteration": iteration,
                "metric": "task_success",
                "baseline_estimate": b_rate,
                "candidate_estimate": c_rate,
                "delta": c_rate - b_rate,
                "test_name": "fisher_exact",
                "p_value": p_value,
                "effect_size": None,
                "composite": None,
            }
        )

    for metric_name, b_data, c_data in [
        ("tests_pass_rate", baseline.tests_pass_rates, candidate.tests_pass_rates),
        (
            "diff_size_loc",
            [float(x) for x in baseline.diff_size_locs],
            [float(x) for x in candidate.diff_size_locs],
        ),
        (
            "files_changed",
            [float(x) for x in baseline.files_changed],
            [float(x) for x in candidate.files_changed],
        ),
        ("duration_seconds", baseline.durations, candidate.durations),
    ]:
        if len(b_data) < 2 or len(c_data) < 2:
            continue
        b_mean = float(np.mean(b_data))
        c_mean = float(np.mean(c_data))
        try:
            stat, p_value = sp_stats.mannwhitneyu(
                b_data, c_data, alternative="two-sided"
            )
        except ValueError:
            continue
        d, _ = cliffs_delta(b_data, c_data)
        rows.append(
            {
                "iteration": iteration,
                "metric": metric_name,
                "baseline_estimate": b_mean,
                "candidate_estimate": c_mean,
                "delta": c_mean - b_mean,
                "test_name": "mann_whitney_u",
                "p_value": p_value,
                "effect_size": d,
                "composite": None,
            }
        )

    if baseline.judge_scores and candidate.judge_scores:
        b_med = float(np.median(baseline.judge_scores))
        c_med = float(np.median(candidate.judge_scores))
        try:
            _, p_value = sp_stats.mannwhitneyu(
                baseline.judge_scores, candidate.judge_scores, alternative="two-sided"
            )
        except ValueError:
            p_value = None
        d, _ = cliffs_delta(baseline.judge_scores, candidate.judge_scores)
        rows.append(
            {
                "iteration": iteration,
                "metric": "judge_score",
                "baseline_estimate": b_med,
                "candidate_estimate": c_med,
                "delta": c_med - b_med,
                "test_name": "mann_whitney_u",
                "p_value": p_value,
                "effect_size": d,
                "composite": None,
            }
        )

    composite = None
    if b_rate > 0 and any(r["metric"] == "diff_size_loc" for r in rows):
        ds_row = next(r for r in rows if r["metric"] == "diff_size_loc")
        baseline_ds = ds_row["baseline_estimate"]
        if baseline_ds is not None and baseline_ds > 0:
            composite = c_rate * math.exp(-ds_row["candidate_estimate"] / baseline_ds)
    for r in rows:
        if r["metric"] == "task_success":
            r["composite"] = composite

    return rows


def compute_trajectory(conn) -> list[dict]:
    rows = conn.execute(
        """
        SELECT r.iteration, r.conventions_hash, c.mutation_note, c.parent_hash,
               AVG(r.task_success) AS mean_success,
               AVG(r.lines_added + r.lines_removed) AS mean_diff_size_loc
        FROM runs r
        LEFT JOIN conventions c ON r.conventions_hash = c.conventions_hash
        WHERE r.infrastructure_error = 0
        GROUP BY r.iteration, r.conventions_hash
        ORDER BY r.iteration
        """
    ).fetchall()

    best_success = -1.0
    best_diff_size = float("inf")
    frontier: list[dict] = []

    for row in rows:
        entry = {
            "iteration": int(row["iteration"]),
            "conventions_hash": row["conventions_hash"] or "",
            "mutation_note": row["mutation_note"] or "",
            "parent_hash": row["parent_hash"] or "",
            "cumulative_success_rate": float(row["mean_success"] or 0),
            "cumulative_diff_size_loc_mean": float(row["mean_diff_size_loc"] or 0),
            "pareto_dominated": 0,
        }
        frontier.append(entry)

    improved = True
    while improved:
        improved = False
        for i, entry in enumerate(frontier):
            if entry["pareto_dominated"] == 1:
                continue
            for j, other in enumerate(frontier):
                if i == j or other["pareto_dominated"] == 1:
                    continue
                if (
                    other["cumulative_success_rate"] >= entry["cumulative_success_rate"]
                    and other["cumulative_diff_size_loc_mean"]
                    <= entry["cumulative_diff_size_loc_mean"]
                    and (
                        other["cumulative_success_rate"]
                        > entry["cumulative_success_rate"]
                        or other["cumulative_diff_size_loc_mean"]
                        < entry["cumulative_diff_size_loc_mean"]
                    )
                ):
                    entry["pareto_dominated"] = 1
                    improved = True
                    break

    return frontier


def write_analysis(conn, all_analysis: list[dict]) -> None:
    conn.execute("DELETE FROM analysis")
    for row in all_analysis:
        conn.execute(
            """
            INSERT INTO analysis (iteration, condition, metric, n, point_estimate,
                                  ci_low, ci_high, method)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["iteration"],
                row["condition"],
                row["metric"],
                row["n"],
                row["point_estimate"],
                row["ci_low"],
                row["ci_hi"],
                row["method"],
            ),
        )


def write_comparisons(conn, all_comparisons: list[dict]) -> None:
    conn.execute("DELETE FROM comparisons")
    for row in all_comparisons:
        conn.execute(
            """
            INSERT INTO comparisons (iteration, metric, baseline_estimate,
                                     candidate_estimate, delta, test_name,
                                     p_value, effect_size, composite)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["iteration"],
                row["metric"],
                row["baseline_estimate"],
                row["candidate_estimate"],
                row["delta"],
                row["test_name"],
                row["p_value"],
                row["effect_size"],
                row["composite"],
            ),
        )


def write_trajectory(conn, trajectory: list[dict]) -> None:
    conn.execute("DELETE FROM trajectory")
    for row in trajectory:
        conn.execute(
            """
            INSERT INTO trajectory (iteration, conventions_hash, mutation_note,
                                    parent_hash, cumulative_success_rate,
                                    cumulative_diff_size_loc_mean, pareto_dominated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["iteration"],
                row["conventions_hash"],
                row["mutation_note"],
                row["parent_hash"],
                row["cumulative_success_rate"],
                row["cumulative_diff_size_loc_mean"],
                row["pareto_dominated"],
            ),
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute statistical analysis tables from experiment.db"
    )
    parser.add_argument(
        "--iteration",
        type=int,
        default=None,
        help="Specific iteration to analyze (default: all)",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Path to experiment.db (default: auto-detect)",
    )
    args = parser.parse_args()

    ensure_project_dirs()
    init_db()
    db_path = RESULTS_DIR / "experiment.db" if args.db is None else args.Path(args.db)

    conn = connect(db_path)
    conn.executescript(ANALYSIS_SCHEMA)

    iterations_row = conn.execute(
        "SELECT DISTINCT iteration FROM runs ORDER BY iteration"
    ).fetchall()
    all_iterations = [int(r["iteration"]) for r in iterations_row]

    if args.iteration is not None:
        all_iterations = [i for i in all_iterations if i == args.iteration]

    if not all_iterations:
        warnings.warn("No iterations found in runs table. Nothing to analyze.")
        conn.close()
        return

    all_analysis: list[dict] = []
    all_comparisons: list[dict] = []

    for iteration in all_iterations:
        by_condition = load_runs_for_iteration(conn, iteration)

        for cond, cd in by_condition.items():
            all_analysis.extend(compute_analysis(conn, iteration, cond, cd))

        baseline = by_condition.get("baseline")
        candidate_names = [c for c in by_condition if c != "baseline"]

        if baseline is None:
            warnings.warn(
                f"Iteration {iteration}: no baseline condition, skipping comparison"
            )
            continue
        if not candidate_names:
            warnings.warn(
                f"Iteration {iteration}: no candidate condition, skipping comparison"
            )
            continue

        for cand_name in candidate_names:
            all_comparisons.extend(
                compute_comparisons(iteration, baseline, by_condition[cand_name])
            )

    write_analysis(conn, all_analysis)
    write_comparisons(conn, all_comparisons)

    trajectory = compute_trajectory(conn)
    write_trajectory(conn, trajectory)

    conn.commit()
    conn.close()

    print(
        f"Analysis complete: {len(all_analysis)} analysis rows, "
        f"{len(all_comparisons)} comparison rows, "
        f"{len(trajectory)} trajectory rows"
    )


if __name__ == "__main__":
    main()
