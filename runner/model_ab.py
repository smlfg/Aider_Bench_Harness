from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runner.db import connect, init_db
from runner.paths import SUMMARY_DIR, ensure_project_dirs
from runner.scientific_ab import (
    HIGHER_IS_BETTER,
    EffectEstimate,
    _fmt,
    _md,
    _mean,
    _rate,
    _safe_float,
    bootstrap_mean_ci,
    sign_test_p_value,
    slug,
)


@dataclass(frozen=True)
class Cell:
    condition_id: str
    task_id: str

    @property
    def key(self) -> str:
        return f"{self.condition_id}::{self.task_id}"


def load_rows(
    *,
    iteration: int,
    model_name: str,
    condition: str | None,
) -> list[dict[str, Any]]:
    clauses = ["iteration = ?", "model_name = ?"]
    params: list[Any] = [iteration, model_name]
    if condition:
        clauses.append("condition_id = ?")
        params.append(condition)
    where = " AND ".join(clauses)
    with connect() as conn:
        rows = conn.execute(
            f"""
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
            WHERE {where}
            ORDER BY condition_id, task_id, run_id
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def list_available() -> str:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT iteration, model_name, condition_id, COUNT(*) AS n,
                   SUM(CASE WHEN infrastructure_error = 0 AND tests_total > 0 THEN 1 ELSE 0 END)
                     AS valid_hard_metric_runs,
                   COUNT(DISTINCT task_id) AS tasks
            FROM runs
            GROUP BY iteration, model_name, condition_id
            ORDER BY iteration, model_name, condition_id
            """
        ).fetchall()

    lines = ["# Available Model A/B Cells", ""]
    lines.append("| iteration | model | condition | runs | valid hard-metric runs | tasks |")
    lines.append("|---:|---|---|---:|---:|---:|")
    for row in rows:
        lines.append(
            f"| {row['iteration']} | `{_md(row['model_name'])}` | "
            f"`{_md(row['condition_id'])}` | {row['n']} | "
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


def aggregate_by_cell(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        cell = Cell(str(row["condition_id"]), str(row["task_id"]))
        grouped[cell.key].append(row)

    aggregates: dict[str, dict[str, Any]] = {}
    for key, cell_rows in grouped.items():
        condition_id, task_id = key.split("::", 1)
        tests_pass_rates = [
            _rate(row["tests_passed"], row["tests_total"]) for row in cell_rows
        ]
        ftp_rates = [
            _rate(row["fail_to_pass_passed"], row["fail_to_pass_total"])
            for row in cell_rows
        ]
        ptp_rates = [
            _rate(row["pass_to_pass_passed"], row["pass_to_pass_total"])
            for row in cell_rows
        ]
        diff_sizes = [
            int(row.get("lines_added") or 0) + int(row.get("lines_removed") or 0)
            for row in cell_rows
        ]
        costs = [_safe_float(row.get("cost_estimate")) or 0.0 for row in cell_rows]
        failure_kinds = sorted(
            {
                str(row.get("failure_kind") or "unknown")
                for row in cell_rows
                if str(row.get("failure_kind") or "unknown") not in {"", "unknown"}
            }
        )
        aggregates[key] = {
            "condition_id": condition_id,
            "task_id": task_id,
            "n": len(cell_rows),
            "task_success": _mean(
                [float(int(row.get("task_success") or 0)) for row in cell_rows]
            ),
            "tests_pass_rate": _mean(tests_pass_rates),
            "fail_to_pass_rate": _mean(ftp_rates),
            "pass_to_pass_rate": _mean(ptp_rates),
            "unrelated_edits_rate": _mean(
                [
                    float(int(row.get("unrelated_edits_present") or 0))
                    for row in cell_rows
                ]
            ),
            "diff_size_loc": _mean([float(v) for v in diff_sizes]),
            "duration_seconds": _mean(
                [_safe_float(row.get("duration_seconds")) for row in cell_rows]
            ),
            "cost_estimate": sum(costs),
            "scope_adherence": _mean(
                [_safe_float(row.get("judge_scope_adherence")) for row in cell_rows]
            ),
            "minimality": _mean(
                [_safe_float(row.get("judge_minimality")) for row in cell_rows]
            ),
            "diff_clarity": _mean(
                [_safe_float(row.get("judge_diff_clarity")) for row in cell_rows]
            ),
            "failure_kinds": failure_kinds,
            "conventions_hashes": sorted(
                {str(row.get("conventions_hash") or "") for row in cell_rows}
            ),
        }
    return aggregates


def cell_mean(
    aggregates: dict[str, dict[str, Any]], keys: list[str], metric: str
) -> float | None:
    return _mean([aggregates[key].get(metric) for key in keys])


def compare_metric(
    metric: str,
    baseline_aggs: dict[str, dict[str, Any]],
    candidate_aggs: dict[str, dict[str, Any]],
    keys: list[str],
) -> EffectEstimate:
    deltas = []
    wins = losses = ties = 0
    higher_is_better = HIGHER_IS_BETTER[metric]
    for key in keys:
        b = baseline_aggs[key].get(metric)
        c = candidate_aggs[key].get(metric)
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
    baseline = cell_mean(baseline_aggs, keys, metric)
    candidate = cell_mean(candidate_aggs, keys, metric)
    p_value = sign_test_p_value(wins, losses)

    if point is None:
        interpretation = "not_measured"
    elif higher_is_better and lo is not None and lo > 0:
        interpretation = "supports_candidate_model"
    elif higher_is_better and hi is not None and hi < 0:
        interpretation = "supports_baseline_model"
    elif not higher_is_better and hi is not None and hi < 0:
        interpretation = "supports_candidate_model"
    elif not higher_is_better and lo is not None and lo > 0:
        interpretation = "supports_baseline_model"
    elif (point > 0 and higher_is_better) or (point < 0 and not higher_is_better):
        interpretation = "candidate_model_trend"
    elif point == 0:
        interpretation = "tie"
    else:
        interpretation = "baseline_model_trend"

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
    common_keys: list[str],
    min_common_cells: int,
    min_runs_per_cell: int,
    condition_filter: str | None,
) -> list[dict[str, str]]:
    gate: list[dict[str, str]] = []

    def add(check: str, status: str, detail: str) -> None:
        gate.append({"check": check, "status": status, "detail": detail})

    add(
        "models_present",
        "PASS" if baseline_rows and candidate_rows else "FAIL",
        f"baseline_model_runs={len(baseline_rows)}, candidate_model_runs={len(candidate_rows)}",
    )
    add(
        "hard_metric_rows",
        "PASS" if baseline_valid and candidate_valid else "FAIL",
        f"valid_baseline_model={len(baseline_valid)}, valid_candidate_model={len(candidate_valid)}",
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
        "paired_condition_task_cells",
        "PASS"
        if len(common_keys) >= min_common_cells
        else ("WARN" if common_keys else "FAIL"),
        f"common_cells={len(common_keys)}, required={min_common_cells}",
    )

    if not common_keys:
        add("cell_repeats", "WARN", "no common condition/task cells to check")
    else:
        underpowered = []
        for key in common_keys:
            b_n = int(baseline_aggs[key]["n"])
            c_n = int(candidate_aggs[key]["n"])
            if b_n < min_runs_per_cell or c_n < min_runs_per_cell:
                underpowered.append(f"{key}: {b_n}/{c_n}")
        add(
            "cell_repeats",
            "PASS" if not underpowered else "WARN",
            "all common cells satisfy min_runs_per_cell"
            if not underpowered
            else "; ".join(underpowered),
        )

    conditions = sorted(
        {baseline_aggs[key]["condition_id"] for key in common_keys}
        | {candidate_aggs[key]["condition_id"] for key in common_keys}
    )
    if condition_filter:
        condition_status = "PASS" if conditions == [condition_filter] else "FAIL"
        condition_detail = f"condition_filter={condition_filter}, observed={conditions}"
    elif not conditions:
        condition_status = "FAIL"
        condition_detail = "no shared conditions"
    else:
        condition_status = "PASS"
        condition_detail = "paired within condition_id: " + ", ".join(conditions)
    add("policy_control", condition_status, condition_detail)

    hash_mismatches = []
    for key in common_keys:
        b_hashes = set(baseline_aggs[key].get("conventions_hashes") or [])
        c_hashes = set(candidate_aggs[key].get("conventions_hashes") or [])
        if b_hashes and c_hashes and b_hashes != c_hashes:
            hash_mismatches.append(key)
    add(
        "policy_hash_control",
        "PASS" if not hash_mismatches else "WARN",
        "same conventions_hashes in paired cells"
        if not hash_mismatches
        else "hash mismatch in: " + ", ".join(hash_mismatches),
    )

    return gate


def counterexamples(
    baseline_aggs: dict[str, dict[str, Any]],
    candidate_aggs: dict[str, dict[str, Any]],
    keys: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in keys:
        reasons = []
        for metric in (
            "task_success",
            "tests_pass_rate",
            "fail_to_pass_rate",
            "pass_to_pass_rate",
        ):
            b = baseline_aggs[key].get(metric)
            c = candidate_aggs[key].get(metric)
            if b is not None and c is not None and c < b:
                reasons.append(f"{metric}: {_fmt(b)} -> {_fmt(c)}")
        b_unrelated = baseline_aggs[key].get("unrelated_edits_rate")
        c_unrelated = candidate_aggs[key].get("unrelated_edits_rate")
        if (
            b_unrelated is not None
            and c_unrelated is not None
            and c_unrelated > b_unrelated
        ):
            reasons.append(
                f"unrelated_edits_rate: {_fmt(b_unrelated)} -> {_fmt(c_unrelated)}"
            )
        b_failures = set(baseline_aggs[key].get("failure_kinds") or [])
        c_failures = set(candidate_aggs[key].get("failure_kinds") or [])
        new_failures = sorted(c_failures - b_failures)
        if new_failures:
            reasons.append("new_failure_kinds: " + ", ".join(new_failures))
        if reasons:
            rows.append(
                {
                    "cell": key,
                    "condition_id": baseline_aggs[key]["condition_id"],
                    "task_id": baseline_aggs[key]["task_id"],
                    "baseline_n": baseline_aggs[key]["n"],
                    "candidate_n": candidate_aggs[key]["n"],
                    "reasons": reasons,
                }
            )
    return rows


def verdict(
    gate: list[dict[str, str]],
    effects: dict[str, EffectEstimate],
    counters: list[dict[str, Any]],
    common_keys: list[str],
    min_common_cells: int,
) -> dict[str, str]:
    if any(row["status"] == "FAIL" for row in gate):
        trust = "not_decisive"
    elif len(common_keys) < min_common_cells:
        trust = "descriptive_only"
    elif any(row["status"] == "WARN" for row in gate):
        trust = "qualified"
    else:
        trust = "decision_ready"

    strong = (
        "falsified_by_counterexample"
        if counters
        else ("not_testable" if not common_keys else "not_falsified_in_this_sample")
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
        average = "supports_candidate_model_average_effect"
    elif primary.ci_high is not None and primary.ci_high < 0:
        average = "falsifies_candidate_model_average_effect"
    elif primary.delta > 0:
        average = "positive_trend_not_decisive"
    elif primary.delta < 0:
        average = "negative_trend_not_decisive"
    else:
        average = "no_observed_average_delta"

    if not common_keys:
        attribution = "not_testable"
    elif trust == "decision_ready":
        attribution = "model_effect_plausibly_isolated"
    else:
        attribution = "model_effect_confounded_or_underpowered"

    return {
        "trust": trust,
        "strong_model_claim": strong,
        "average_model_claim": average,
        "model_attribution": attribution,
    }


def render_report(
    *,
    iteration: int,
    baseline_model: str,
    candidate_model: str,
    condition_filter: str | None,
    min_common_cells: int,
    min_runs_per_cell: int,
    gate: list[dict[str, str]],
    baseline_excluded: Counter[str],
    candidate_excluded: Counter[str],
    baseline_aggs: dict[str, dict[str, Any]],
    candidate_aggs: dict[str, dict[str, Any]],
    common_keys: list[str],
    missing_from_baseline: list[str],
    missing_from_candidate: list[str],
    effects: dict[str, EffectEstimate],
    counters: list[dict[str, Any]],
    verdicts: dict[str, str],
) -> str:
    lines = [
        f"# Scientific Model A/B Report: {baseline_model} vs {candidate_model}",
        "",
        f"- iteration: `{iteration}`",
        f"- baseline model: `{baseline_model}`",
        f"- candidate model: `{candidate_model}`",
        f"- condition filter: `{condition_filter or 'none'}`",
        f"- common valid condition/task cells: `{len(common_keys)}` (required: `{min_common_cells}`)",
        f"- min runs per cell: `{min_runs_per_cell}`",
        "",
        "## Erkenntnisurteil",
        "",
        "| Claim | Verdict | Meaning |",
        "|---|---|---|",
        f"| Trust in comparison | `{verdicts['trust']}` | Whether the model comparison is strong enough for more than a descriptive reading. |",
        f"| Strong model claim | `{verdicts['strong_model_claim']}` | Tests whether the candidate model is never worse in paired cells. |",
        f"| Average model claim | `{verdicts['average_model_claim']}` | Tests whether the candidate model improves the mean hard-metric effect. |",
        f"| Model attribution | `{verdicts['model_attribution']}` | Whether task and policy were controlled well enough to blame the model. |",
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
        "Delta is candidate model minus baseline model. For `unrelated_edits_rate`, `diff_size_loc`, `duration_seconds`, and `cost_estimate`, lower is better.",
        "",
        "| Metric | Baseline model | Candidate model | Delta | 95% bootstrap CI | W/L/T | sign p | Interpretation |",
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
        "## Paired Model Cells",
        "",
        "| Condition | Task | n A/B | success A -> B | tests A -> B | FTP A -> B | PTP A -> B | unrelated A -> B | diff LOC A -> B |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key in common_keys:
        b = baseline_aggs[key]
        c = candidate_aggs[key]
        lines.append(
            f"| `{_md(b['condition_id'])}` | `{_md(b['task_id'])}` | {b['n']}/{c['n']} | "
            f"{_fmt(b.get('task_success'))} -> {_fmt(c.get('task_success'))} | "
            f"{_fmt(b.get('tests_pass_rate'))} -> {_fmt(c.get('tests_pass_rate'))} | "
            f"{_fmt(b.get('fail_to_pass_rate'))} -> {_fmt(c.get('fail_to_pass_rate'))} | "
            f"{_fmt(b.get('pass_to_pass_rate'))} -> {_fmt(c.get('pass_to_pass_rate'))} | "
            f"{_fmt(b.get('unrelated_edits_rate'))} -> {_fmt(c.get('unrelated_edits_rate'))} | "
            f"{_fmt(b.get('diff_size_loc'))} -> {_fmt(c.get('diff_size_loc'))} |"
        )

    lines += ["", "## Counterexamples To Strong Model Claim", ""]
    if not common_keys:
        lines.append("No common valid condition/task cells were available, so the strong model claim was not tested.")
    elif counters:
        lines += [
            "| Condition | Task | n A/B | Why this is a counterexample |",
            "|---|---|---:|---|",
        ]
        for row in counters:
            lines.append(
                f"| `{_md(row['condition_id'])}` | `{_md(row['task_id'])}` | "
                f"{row['baseline_n']}/{row['candidate_n']} | "
                f"{_md('; '.join(row['reasons']))} |"
            )
    else:
        lines.append("No counterexample to the strong model claim was observed in common valid cells.")

    lines += [
        "",
        "## Missing Or Excluded Evidence",
        "",
        f"- excluded baseline model rows: `{dict(baseline_excluded)}`",
        f"- excluded candidate model rows: `{dict(candidate_excluded)}`",
        f"- cells only in baseline model after filtering: `{missing_from_candidate}`",
        f"- cells only in candidate model after filtering: `{missing_from_baseline}`",
        "",
        "## Scientific Reading",
        "",
        "This report tests a model-cause hypothesis only inside matched condition/task cells. If the same task and policy are not shared, a model verdict would be confounded by task or policy differences.",
    ]
    return "\n".join(lines) + "\n"


def make_payload(
    *,
    iteration: int,
    baseline_model: str,
    candidate_model: str,
    condition_filter: str | None,
    gate: list[dict[str, str]],
    effects: dict[str, EffectEstimate],
    counters: list[dict[str, Any]],
    verdicts: dict[str, str],
    common_keys: list[str],
) -> dict[str, Any]:
    return {
        "iteration": iteration,
        "baseline_model": baseline_model,
        "candidate_model": candidate_model,
        "condition_filter": condition_filter,
        "validity_gate": gate,
        "verdict": verdicts,
        "common_cells": common_keys,
        "effects": {
            name: {
                "metric": estimate.metric,
                "baseline": estimate.baseline,
                "candidate": estimate.candidate,
                "delta": estimate.delta,
                "ci_low": estimate.ci_low,
                "ci_high": estimate.ci_high,
                "n_cells": estimate.n_tasks,
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


def run_model_ab(args: argparse.Namespace) -> tuple[Path, Path, dict[str, Any]]:
    baseline_rows = load_rows(
        iteration=args.iteration,
        model_name=args.baseline_model,
        condition=args.condition,
    )
    candidate_rows = load_rows(
        iteration=args.iteration,
        model_name=args.candidate_model,
        condition=args.condition,
    )
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
    baseline_aggs = aggregate_by_cell(baseline_valid)
    candidate_aggs = aggregate_by_cell(candidate_valid)
    common_keys = sorted(set(baseline_aggs) & set(candidate_aggs))
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
        common_keys=common_keys,
        min_common_cells=args.min_common_cells,
        min_runs_per_cell=args.min_runs_per_cell,
        condition_filter=args.condition,
    )
    effects = {
        metric: compare_metric(metric, baseline_aggs, candidate_aggs, common_keys)
        for metric in HIGHER_IS_BETTER
    }
    counters = counterexamples(baseline_aggs, candidate_aggs, common_keys)
    verdicts = verdict(
        gate=gate,
        effects=effects,
        counters=counters,
        common_keys=common_keys,
        min_common_cells=args.min_common_cells,
    )
    report = render_report(
        iteration=args.iteration,
        baseline_model=args.baseline_model,
        candidate_model=args.candidate_model,
        condition_filter=args.condition,
        min_common_cells=args.min_common_cells,
        min_runs_per_cell=args.min_runs_per_cell,
        gate=gate,
        baseline_excluded=baseline_excluded,
        candidate_excluded=candidate_excluded,
        baseline_aggs=baseline_aggs,
        candidate_aggs=candidate_aggs,
        common_keys=common_keys,
        missing_from_baseline=missing_from_baseline,
        missing_from_candidate=missing_from_candidate,
        effects=effects,
        counters=counters,
        verdicts=verdicts,
    )
    payload = make_payload(
        iteration=args.iteration,
        baseline_model=args.baseline_model,
        candidate_model=args.candidate_model,
        condition_filter=args.condition,
        gate=gate,
        effects=effects,
        counters=counters,
        verdicts=verdicts,
        common_keys=common_keys,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    condition_part = f"_{slug(args.condition)}" if args.condition else ""
    stem = (
        f"model_ab_iteration_{args.iteration}{condition_part}_"
        f"{slug(args.baseline_model)}_vs_{slug(args.candidate_model)}"
    )
    report_path = output_dir / f"{stem}.md"
    json_path = output_dir / f"{stem}.json"
    report_path.write_text(report, encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return report_path, json_path, payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scientific model A/B analysis for harness runs."
    )
    parser.add_argument("--iteration", type=int, default=1)
    parser.add_argument("--baseline-model")
    parser.add_argument("--candidate-model")
    parser.add_argument(
        "--condition",
        help="Optional condition_id filter. Recommended for clean model attribution.",
    )
    parser.add_argument("--min-common-cells", type=int, default=3)
    parser.add_argument("--min-runs-per-cell", type=int, default=3)
    parser.add_argument("--allow-zero-tests", action="store_true")
    parser.add_argument("--include-infra", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=SUMMARY_DIR)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    ensure_project_dirs()
    init_db()

    if args.list:
        print(list_available())
        return
    if not args.baseline_model or not args.candidate_model:
        raise SystemExit("Provide --baseline-model and --candidate-model or use --list.")

    report_path, json_path, payload = run_model_ab(args)
    print(f"Wrote {report_path}")
    print(f"Wrote {json_path}")
    print("Verdict:", json.dumps(payload["verdict"], sort_keys=True))


if __name__ == "__main__":
    main()
