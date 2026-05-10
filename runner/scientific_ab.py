from __future__ import annotations

import argparse
import json
import math
import random
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runner.db import connect, init_db
from runner.paths import SUMMARY_DIR, ensure_project_dirs


HIGHER_IS_BETTER = {
    "task_success": True,
    "tests_pass_rate": True,
    "fail_to_pass_rate": True,
    "pass_to_pass_rate": True,
    "scope_adherence": True,
    "minimality": True,
    "diff_clarity": True,
    "unrelated_edits_rate": False,
    "diff_size_loc": False,
    "duration_seconds": False,
    "cost_estimate": False,
}


@dataclass(frozen=True)
class EffectEstimate:
    metric: str
    baseline: float | None
    candidate: float | None
    delta: float | None
    ci_low: float | None
    ci_high: float | None
    n_tasks: int
    wins: int
    losses: int
    ties: int
    sign_p_value: float | None
    interpretation: str


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mean(values: list[float | None]) -> float | None:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return float(statistics.mean(clean))


def _rate(passed: Any, total: Any) -> float | None:
    total_int = int(total or 0)
    if total_int <= 0:
        return None
    return int(passed or 0) / total_int


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    pos = (len(ordered) - 1) * p
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    weight = pos - lo
    return ordered[lo] * (1 - weight) + ordered[hi] * weight


def bootstrap_mean_ci(
    values: list[float],
    *,
    resamples: int = 5000,
    seed: int = 17,
    ci: float = 0.95,
) -> tuple[float | None, float | None, float | None]:
    if not values:
        return None, None, None
    point = float(statistics.mean(values))
    if len(values) < 2:
        return point, point, point
    rng = random.Random(seed)
    means = []
    for _ in range(resamples):
        sample = [values[rng.randrange(len(values))] for _ in values]
        means.append(float(statistics.mean(sample)))
    alpha = (1 - ci) / 2
    return point, _percentile(means, alpha), _percentile(means, 1 - alpha)


def sign_test_p_value(wins: int, losses: int) -> float | None:
    n = wins + losses
    if n == 0:
        return None
    k = min(wins, losses)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2**n)
    return min(1.0, 2 * tail)


def load_rows(iteration: int, condition: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT run_id, task_id, condition_id, iteration, model_name,
                   conventions_hash, conventions_path, duration_seconds,
                   infrastructure_error, failure_kind, tokens_in, tokens_out,
                   cost_estimate, tests_total, tests_passed, task_success,
                   fail_to_pass_total, fail_to_pass_passed,
                   pass_to_pass_total, pass_to_pass_passed,
                   files_changed, lines_added, lines_removed,
                   unrelated_edits_present, judge_score,
                   judge_scope_adherence, judge_minimality, judge_diff_clarity
            FROM runs
            WHERE iteration = ? AND condition_id = ?
            ORDER BY task_id, run_id
            """,
            (iteration, condition),
        ).fetchall()
    return [dict(row) for row in rows]


def list_available() -> str:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT iteration, condition_id, COUNT(*) AS n,
                   SUM(CASE WHEN infrastructure_error = 0 AND tests_total > 0 THEN 1 ELSE 0 END)
                     AS valid_hard_metric_runs,
                   COUNT(DISTINCT task_id) AS tasks
            FROM runs
            GROUP BY iteration, condition_id
            ORDER BY iteration, condition_id
            """
        ).fetchall()

    lines = ["# Available A/B Conditions", ""]
    lines.append("| iteration | condition | runs | valid hard-metric runs | tasks |")
    lines.append("|---:|---|---:|---:|---:|")
    for row in rows:
        lines.append(
            f"| {row['iteration']} | {_md(row['condition_id'])} | {row['n']} | "
            f"{row['valid_hard_metric_runs'] or 0} | {row['tasks']} |"
        )
    return "\n".join(lines) + "\n"


def split_valid_rows(
    rows: list[dict[str, Any]],
    *,
    include_infra: bool,
    allow_zero_tests: bool,
) -> tuple[list[dict[str, Any]], Counter[str]]:
    valid = []
    excluded: Counter[str] = Counter()
    for row in rows:
        if not include_infra and int(row.get("infrastructure_error") or 0):
            excluded["infrastructure_error"] += 1
            continue
        if not allow_zero_tests and int(row.get("tests_total") or 0) <= 0:
            excluded["zero_tests"] += 1
            continue
        valid.append(row)
    return valid, excluded


def aggregate_by_task(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["task_id"])].append(row)

    aggregates: dict[str, dict[str, Any]] = {}
    for task_id, task_rows in grouped.items():
        tests_pass_rates = [
            _rate(row["tests_passed"], row["tests_total"]) for row in task_rows
        ]
        ftp_rates = [
            _rate(row["fail_to_pass_passed"], row["fail_to_pass_total"])
            for row in task_rows
        ]
        ptp_rates = [
            _rate(row["pass_to_pass_passed"], row["pass_to_pass_total"])
            for row in task_rows
        ]
        diff_sizes = [
            int(row.get("lines_added") or 0) + int(row.get("lines_removed") or 0)
            for row in task_rows
        ]
        costs = [_safe_float(row.get("cost_estimate")) or 0.0 for row in task_rows]
        failure_kinds = sorted(
            {
                str(row.get("failure_kind") or "unknown")
                for row in task_rows
                if str(row.get("failure_kind") or "unknown") not in {"", "unknown"}
            }
        )
        aggregates[task_id] = {
            "n": len(task_rows),
            "task_success": _mean(
                [float(int(row.get("task_success") or 0)) for row in task_rows]
            ),
            "tests_pass_rate": _mean(tests_pass_rates),
            "fail_to_pass_rate": _mean(ftp_rates),
            "pass_to_pass_rate": _mean(ptp_rates),
            "unrelated_edits_rate": _mean(
                [
                    float(int(row.get("unrelated_edits_present") or 0))
                    for row in task_rows
                ]
            ),
            "diff_size_loc": _mean([float(v) for v in diff_sizes]),
            "duration_seconds": _mean(
                [_safe_float(row.get("duration_seconds")) for row in task_rows]
            ),
            "cost_estimate": sum(costs),
            "scope_adherence": _mean(
                [_safe_float(row.get("judge_scope_adherence")) for row in task_rows]
            ),
            "minimality": _mean(
                [_safe_float(row.get("judge_minimality")) for row in task_rows]
            ),
            "diff_clarity": _mean(
                [_safe_float(row.get("judge_diff_clarity")) for row in task_rows]
            ),
            "failure_kinds": failure_kinds,
            "models": sorted({str(row.get("model_name") or "") for row in task_rows}),
            "conventions_hashes": sorted(
                {str(row.get("conventions_hash") or "") for row in task_rows}
            ),
        }
    return aggregates


def condition_mean(
    task_aggs: dict[str, dict[str, Any]], tasks: list[str], metric: str
) -> float | None:
    return _mean([task_aggs[task].get(metric) for task in tasks])


def compare_metric(
    metric: str,
    baseline_aggs: dict[str, dict[str, Any]],
    candidate_aggs: dict[str, dict[str, Any]],
    tasks: list[str],
) -> EffectEstimate:
    deltas = []
    wins = losses = ties = 0
    higher_is_better = HIGHER_IS_BETTER[metric]
    for task in tasks:
        b = baseline_aggs[task].get(metric)
        c = candidate_aggs[task].get(metric)
        if b is None or c is None:
            continue
        delta = float(c) - float(b)
        deltas.append(delta)
        if abs(delta) < 1e-12:
            ties += 1
        elif (delta > 0 and higher_is_better) or (delta < 0 and not higher_is_better):
            wins += 1
        else:
            losses += 1

    point, lo, hi = bootstrap_mean_ci(deltas)
    baseline = condition_mean(baseline_aggs, tasks, metric)
    candidate = condition_mean(candidate_aggs, tasks, metric)
    p_value = sign_test_p_value(wins, losses)

    if point is None:
        interpretation = "not_measured"
    else:
        supports = point > 0 if higher_is_better else point < 0
        if lo is not None and hi is not None:
            if higher_is_better and lo > 0:
                interpretation = "supports_candidate"
            elif higher_is_better and hi < 0:
                interpretation = "supports_baseline"
            elif not higher_is_better and hi < 0:
                interpretation = "supports_candidate"
            elif not higher_is_better and lo > 0:
                interpretation = "supports_baseline"
            elif supports:
                interpretation = "candidate_trend"
            elif point == 0:
                interpretation = "tie"
            else:
                interpretation = "baseline_trend"
        else:
            interpretation = "candidate_trend" if supports else "baseline_trend"

    return EffectEstimate(
        metric=metric,
        baseline=baseline,
        candidate=candidate,
        delta=point,
        ci_low=lo,
        ci_high=hi,
        n_tasks=len(deltas),
        wins=wins,
        losses=losses,
        ties=ties,
        sign_p_value=p_value,
        interpretation=interpretation,
    )


def make_gate(
    *,
    baseline_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    baseline_valid: list[dict[str, Any]],
    candidate_valid: list[dict[str, Any]],
    baseline_excluded: Counter[str],
    candidate_excluded: Counter[str],
    baseline_aggs: dict[str, dict[str, Any]],
    candidate_aggs: dict[str, dict[str, Any]],
    common_tasks: list[str],
    min_common_tasks: int,
    min_runs_per_task: int,
) -> list[dict[str, str]]:
    gate: list[dict[str, str]] = []

    def add(check: str, status: str, detail: str) -> None:
        gate.append({"check": check, "status": status, "detail": detail})

    add(
        "conditions_present",
        "PASS" if baseline_rows and candidate_rows else "FAIL",
        f"baseline_runs={len(baseline_rows)}, candidate_runs={len(candidate_rows)}",
    )
    add(
        "hard_metric_rows",
        "PASS" if baseline_valid and candidate_valid else "FAIL",
        f"valid_baseline={len(baseline_valid)}, valid_candidate={len(candidate_valid)}",
    )
    add(
        "excluded_rows",
        "WARN" if baseline_excluded or candidate_excluded else "PASS",
        "baseline="
        + dict(baseline_excluded).__repr__()
        + ", candidate="
        + dict(candidate_excluded).__repr__(),
    )
    add(
        "task_overlap",
        "PASS" if len(common_tasks) >= min_common_tasks else ("WARN" if common_tasks else "FAIL"),
        f"common_tasks={len(common_tasks)}, required={min_common_tasks}",
    )

    if not common_tasks:
        add("cell_repeats", "WARN", "no common task cells to check")
    else:
        underpowered = []
        for task in common_tasks:
            b_n = int(baseline_aggs[task]["n"])
            c_n = int(candidate_aggs[task]["n"])
            if b_n < min_runs_per_task or c_n < min_runs_per_task:
                underpowered.append(f"{task}: {b_n}/{c_n}")
        add(
            "cell_repeats",
            "PASS" if not underpowered else "WARN",
            "all common task cells satisfy min_runs_per_task"
            if not underpowered
            else "; ".join(underpowered),
        )

    models = {
        str(row.get("model_name") or "")
        for row in baseline_valid + candidate_valid
        if row.get("model_name")
    }
    add(
        "model_control",
        "PASS" if len(models) <= 1 else "WARN",
        ", ".join(sorted(models)) if models else "no model names recorded",
    )

    ambiguous_conditions = []
    for label, rows in (("baseline", baseline_valid), ("candidate", candidate_valid)):
        by_condition_hashes = {
            str(row.get("conventions_hash") or "") for row in rows if row.get("conventions_hash")
        }
        if len(by_condition_hashes) > 1:
            ambiguous_conditions.append(f"{label} has {len(by_condition_hashes)} hashes")
    add(
        "condition_identity",
        "PASS" if not ambiguous_conditions else "WARN",
        "one conventions hash per condition"
        if not ambiguous_conditions
        else "; ".join(ambiguous_conditions),
    )

    baseline_rates = [
        baseline_aggs[task].get("tests_pass_rate")
        for task in common_tasks
        if baseline_aggs[task].get("tests_pass_rate") is not None
    ]
    if len(baseline_rates) < 2:
        task_status = "WARN"
        detail = "too few baseline task rates to estimate task difficulty"
    elif all(abs(rate - baseline_rates[0]) < 1e-12 for rate in baseline_rates):
        task_status = "WARN"
        detail = "baseline task rates have no observed variation"
    else:
        task_status = "PASS"
        detail = "baseline task rates vary across tasks"
    add("task_discrimination", task_status, detail)

    return gate


def counterexamples(
    baseline_aggs: dict[str, dict[str, Any]],
    candidate_aggs: dict[str, dict[str, Any]],
    tasks: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for task in tasks:
        reasons = []
        for metric in (
            "task_success",
            "tests_pass_rate",
            "fail_to_pass_rate",
            "pass_to_pass_rate",
        ):
            b = baseline_aggs[task].get(metric)
            c = candidate_aggs[task].get(metric)
            if b is not None and c is not None and c < b:
                reasons.append(f"{metric}: {_fmt(b)} -> {_fmt(c)}")
        b_unrelated = baseline_aggs[task].get("unrelated_edits_rate")
        c_unrelated = candidate_aggs[task].get("unrelated_edits_rate")
        if (
            b_unrelated is not None
            and c_unrelated is not None
            and c_unrelated > b_unrelated
        ):
            reasons.append(
                f"unrelated_edits_rate: {_fmt(b_unrelated)} -> {_fmt(c_unrelated)}"
            )
        b_failures = set(baseline_aggs[task].get("failure_kinds") or [])
        c_failures = set(candidate_aggs[task].get("failure_kinds") or [])
        new_failures = sorted(c_failures - b_failures)
        if new_failures:
            reasons.append("new_failure_kinds: " + ", ".join(new_failures))
        if reasons:
            rows.append(
                {
                    "task_id": task,
                    "baseline_n": baseline_aggs[task]["n"],
                    "candidate_n": candidate_aggs[task]["n"],
                    "reasons": reasons,
                }
            )
    return rows


def verdict(
    gate: list[dict[str, str]],
    effects: dict[str, EffectEstimate],
    counters: list[dict[str, Any]],
    common_tasks: list[str],
    min_common_tasks: int,
) -> dict[str, str]:
    if any(row["status"] == "FAIL" for row in gate):
        trust = "not_decisive"
    elif len(common_tasks) < min_common_tasks:
        trust = "descriptive_only"
    elif any(row["status"] == "WARN" for row in gate):
        trust = "qualified"
    else:
        trust = "decision_ready"

    strong = (
        "falsified_by_counterexample"
        if counters
        else ("not_testable" if not common_tasks else "not_falsified_in_this_sample")
    )

    primary = effects["tests_pass_rate"]
    if trust == "not_decisive" or primary.delta is None:
        average = "not_testable"
    elif trust != "decision_ready":
        if primary.delta > 0:
            average = "positive_trend_not_decisive"
        elif primary.delta < 0:
            average = "negative_trend_not_decisive"
        else:
            average = "no_observed_average_delta"
    elif primary.ci_low is not None and primary.ci_low > 0:
        average = "supports_candidate_average_effect"
    elif primary.ci_high is not None and primary.ci_high < 0:
        average = "falsifies_candidate_average_effect"
    elif primary.delta > 0:
        average = "positive_trend_not_decisive"
    elif primary.delta < 0:
        average = "negative_trend_not_decisive"
    else:
        average = "no_observed_average_delta"

    if not common_tasks:
        safety = "not_testable"
    else:
        safety_metrics = [
            effects["pass_to_pass_rate"],
            effects["unrelated_edits_rate"],
            effects["diff_size_loc"],
        ]
        safety_bad = any(
            metric.interpretation in {"supports_baseline", "baseline_trend"}
            for metric in safety_metrics
            if metric.delta is not None
        )
        safety = (
            "safety_regression_observed"
            if counters or safety_bad
            else "no_safety_regression_observed"
        )

    return {
        "trust": trust,
        "strong_claim": strong,
        "average_claim": average,
        "safety_claim": safety,
    }


def render_report(
    *,
    iteration: int,
    baseline: str,
    candidate: str,
    min_common_tasks: int,
    min_runs_per_task: int,
    gate: list[dict[str, str]],
    baseline_excluded: Counter[str],
    candidate_excluded: Counter[str],
    baseline_aggs: dict[str, dict[str, Any]],
    candidate_aggs: dict[str, dict[str, Any]],
    common_tasks: list[str],
    missing_from_baseline: list[str],
    missing_from_candidate: list[str],
    effects: dict[str, EffectEstimate],
    counters: list[dict[str, Any]],
    verdicts: dict[str, str],
) -> str:
    lines = [
        f"# Scientific A/B Report: {baseline} vs {candidate}",
        "",
        f"- iteration: `{iteration}`",
        f"- baseline: `{baseline}`",
        f"- candidate: `{candidate}`",
        f"- common valid tasks: `{len(common_tasks)}` (required: `{min_common_tasks}`)",
        f"- min runs per task cell: `{min_runs_per_task}`",
        "",
        "## Erkenntnisurteil",
        "",
        "| Claim | Verdict | Meaning |",
        "|---|---|---|",
        f"| Trust in comparison | `{verdicts['trust']}` | Whether the data are strong enough for more than a descriptive reading. |",
        f"| Strong universal claim | `{verdicts['strong_claim']}` | Tests whether the candidate is never worse than baseline in this sample. |",
        f"| Average treatment claim | `{verdicts['average_claim']}` | Tests whether the candidate improves the mean hard-metric effect. |",
        f"| Safety claim | `{verdicts['safety_claim']}` | Checks new regressions, unrelated edits, and cost/diff regressions. |",
        "",
        "## Validity Gate",
        "",
        "| Check | Status | Detail |",
        "|---|---|---|",
    ]
    for row in gate:
        lines.append(
            f"| {_md(row['check'])} | `{row['status']}` | {_md(row['detail'])} |"
        )

    lines += [
        "",
        "## Effect Estimates",
        "",
        "Delta is candidate minus baseline. For `unrelated_edits_rate`, `diff_size_loc`, `duration_seconds`, and `cost_estimate`, lower is better.",
        "",
        "| Metric | Baseline | Candidate | Delta | 95% bootstrap CI | W/L/T | sign p | Interpretation |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for metric in (
        "task_success",
        "tests_pass_rate",
        "fail_to_pass_rate",
        "pass_to_pass_rate",
        "unrelated_edits_rate",
        "diff_size_loc",
        "duration_seconds",
        "cost_estimate",
        "scope_adherence",
        "minimality",
        "diff_clarity",
    ):
        estimate = effects[metric]
        ci = f"[{_fmt(estimate.ci_low)}, {_fmt(estimate.ci_high)}]"
        wlt = f"{estimate.wins}/{estimate.losses}/{estimate.ties}"
        lines.append(
            f"| `{metric}` | {_fmt(estimate.baseline)} | {_fmt(estimate.candidate)} | "
            f"{_fmt(estimate.delta)} | {ci} | {wlt} | {_fmt(estimate.sign_p_value)} | "
            f"`{estimate.interpretation}` |"
        )

    lines += [
        "",
        "## Task-Level Pairing",
        "",
        "| Task | n A/B | success A -> B | tests A -> B | FTP A -> B | PTP A -> B | unrelated A -> B | diff LOC A -> B |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for task in common_tasks:
        b = baseline_aggs[task]
        c = candidate_aggs[task]
        lines.append(
            f"| `{_md(task)}` | {b['n']}/{c['n']} | "
            f"{_fmt(b.get('task_success'))} -> {_fmt(c.get('task_success'))} | "
            f"{_fmt(b.get('tests_pass_rate'))} -> {_fmt(c.get('tests_pass_rate'))} | "
            f"{_fmt(b.get('fail_to_pass_rate'))} -> {_fmt(c.get('fail_to_pass_rate'))} | "
            f"{_fmt(b.get('pass_to_pass_rate'))} -> {_fmt(c.get('pass_to_pass_rate'))} | "
            f"{_fmt(b.get('unrelated_edits_rate'))} -> {_fmt(c.get('unrelated_edits_rate'))} | "
            f"{_fmt(b.get('diff_size_loc'))} -> {_fmt(c.get('diff_size_loc'))} |"
        )

    lines += ["", "## Counterexamples To Strong Claim", ""]
    if not common_tasks:
        lines.append("No common valid tasks were available, so the strong claim was not tested.")
    elif counters:
        lines += [
            "| Task | n A/B | Why this is a counterexample |",
            "|---|---:|---|",
        ]
        for row in counters:
            lines.append(
                f"| `{_md(row['task_id'])}` | {row['baseline_n']}/{row['candidate_n']} | "
                f"{_md('; '.join(row['reasons']))} |"
            )
    else:
        lines.append("No counterexample to the strong claim was observed in common valid tasks.")

    lines += [
        "",
        "## Missing Or Excluded Evidence",
        "",
        f"- excluded baseline rows: `{dict(baseline_excluded)}`",
        f"- excluded candidate rows: `{dict(candidate_excluded)}`",
        f"- tasks only in baseline after filtering: `{missing_from_candidate}`",
        f"- tasks only in candidate after filtering: `{missing_from_baseline}`",
        "",
        "## Scientific Reading",
        "",
        "This report does not ask whether the Markdown policy is generally good. It asks whether this candidate condition changes measurable behavior against this baseline inside the declared harness scope. Counterexamples falsify the strong universal claim. Mean deltas and confidence intervals address the weaker treatment-effect claim.",
    ]
    return "\n".join(lines) + "\n"


def make_payload(
    *,
    iteration: int,
    baseline: str,
    candidate: str,
    gate: list[dict[str, str]],
    effects: dict[str, EffectEstimate],
    counters: list[dict[str, Any]],
    verdicts: dict[str, str],
    common_tasks: list[str],
) -> dict[str, Any]:
    return {
        "iteration": iteration,
        "baseline": baseline,
        "candidate": candidate,
        "validity_gate": gate,
        "verdict": verdicts,
        "common_tasks": common_tasks,
        "effects": {
            name: {
                "metric": estimate.metric,
                "baseline": estimate.baseline,
                "candidate": estimate.candidate,
                "delta": estimate.delta,
                "ci_low": estimate.ci_low,
                "ci_high": estimate.ci_high,
                "n_tasks": estimate.n_tasks,
                "wins": estimate.wins,
                "losses": estimate.losses,
                "ties": estimate.ties,
                "sign_p_value": estimate.sign_p_value,
                "interpretation": estimate.interpretation,
            }
            for name, estimate in effects.items()
        },
        "counterexamples": counters,
    }


def slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "condition"


def run_scientific_ab(args: argparse.Namespace) -> tuple[Path, Path, dict[str, Any]]:
    baseline_rows = load_rows(args.iteration, args.baseline)
    candidate_rows = load_rows(args.iteration, args.candidate)
    baseline_valid, baseline_excluded = split_valid_rows(
        baseline_rows,
        include_infra=args.include_infra,
        allow_zero_tests=args.allow_zero_tests,
    )
    candidate_valid, candidate_excluded = split_valid_rows(
        candidate_rows,
        include_infra=args.include_infra,
        allow_zero_tests=args.allow_zero_tests,
    )
    baseline_aggs = aggregate_by_task(baseline_valid)
    candidate_aggs = aggregate_by_task(candidate_valid)
    common_tasks = sorted(set(baseline_aggs) & set(candidate_aggs))
    missing_from_baseline = sorted(set(candidate_aggs) - set(baseline_aggs))
    missing_from_candidate = sorted(set(baseline_aggs) - set(candidate_aggs))

    gate = make_gate(
        baseline_rows=baseline_rows,
        candidate_rows=candidate_rows,
        baseline_valid=baseline_valid,
        candidate_valid=candidate_valid,
        baseline_excluded=baseline_excluded,
        candidate_excluded=candidate_excluded,
        baseline_aggs=baseline_aggs,
        candidate_aggs=candidate_aggs,
        common_tasks=common_tasks,
        min_common_tasks=args.min_common_tasks,
        min_runs_per_task=args.min_runs_per_task,
    )

    effects = {
        metric: compare_metric(metric, baseline_aggs, candidate_aggs, common_tasks)
        for metric in HIGHER_IS_BETTER
    }
    counters = counterexamples(baseline_aggs, candidate_aggs, common_tasks)
    verdicts = verdict(
        gate=gate,
        effects=effects,
        counters=counters,
        common_tasks=common_tasks,
        min_common_tasks=args.min_common_tasks,
    )
    report = render_report(
        iteration=args.iteration,
        baseline=args.baseline,
        candidate=args.candidate,
        min_common_tasks=args.min_common_tasks,
        min_runs_per_task=args.min_runs_per_task,
        gate=gate,
        baseline_excluded=baseline_excluded,
        candidate_excluded=candidate_excluded,
        baseline_aggs=baseline_aggs,
        candidate_aggs=candidate_aggs,
        common_tasks=common_tasks,
        missing_from_baseline=missing_from_baseline,
        missing_from_candidate=missing_from_candidate,
        effects=effects,
        counters=counters,
        verdicts=verdicts,
    )
    payload = make_payload(
        iteration=args.iteration,
        baseline=args.baseline,
        candidate=args.candidate,
        gate=gate,
        effects=effects,
        counters=counters,
        verdicts=verdicts,
        common_tasks=common_tasks,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"scientific_ab_iteration_{args.iteration}_{slug(args.baseline)}_vs_{slug(args.candidate)}"
    report_path = output_dir / f"{stem}.md"
    json_path = output_dir / f"{stem}.json"
    report_path.write_text(report, encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return report_path, json_path, payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scientific A/B analysis for harness policy runs."
    )
    parser.add_argument("--iteration", type=int, default=1)
    parser.add_argument("--baseline", default="baseline")
    parser.add_argument("--candidate")
    parser.add_argument("--min-common-tasks", type=int, default=3)
    parser.add_argument("--min-runs-per-task", type=int, default=3)
    parser.add_argument("--allow-zero-tests", action="store_true")
    parser.add_argument("--include-infra", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=SUMMARY_DIR)
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available conditions and exit.",
    )
    args = parser.parse_args()

    ensure_project_dirs()
    init_db()

    if args.list:
        print(list_available())
        return
    if not args.candidate:
        raise SystemExit("Provide --candidate or use --list.")

    report_path, json_path, payload = run_scientific_ab(args)
    print(f"Wrote {report_path}")
    print(f"Wrote {json_path}")
    print("Verdict:", json.dumps(payload["verdict"], sort_keys=True))


if __name__ == "__main__":
    main()
