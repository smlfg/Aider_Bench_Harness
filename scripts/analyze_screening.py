#!/usr/bin/env python3
"""
analyze_screening.py

Liest results/experiment.db und erzeugt eine deskriptive Analyse
der 25 Runs aus efficient_screening.

Output: Text-Tabelle + Delta-Übersicht

Usage:
    uv run python scripts/analyze_screening.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("results/experiment.db")

CONDITIONS = [
    "baseline_v0",
    "karpathy_rule_1",
    "karpathy_rule_2",
    "karpathy_rule_3",
    "karpathy_rule_4",
]

RULE_LABELS = {
    "karpathy_rule_1": "Rule 1",
    "karpathy_rule_2": "Rule 2",
    "karpathy_rule_3": "Rule 3",
    "karpathy_rule_4": "Rule 4",
}


def load_data() -> dict:
    """Lädt alle efficient_screening Runs aus der DB."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    query = """
    SELECT
        run_id,
        task_id,
        condition_id,
        tests_passed,
        tests_total,
        judge_report_status,
        failure_kind,
        agent_duration_seconds,
        tokens_used
    FROM runs
    WHERE run_id LIKE 'efficient_screening__%'
    ORDER BY task_id, condition_id
    """

    rows = cur.execute(query).fetchall()
    conn.close()

    # {(task_id, condition_id): {...}}
    data = {}
    for r in rows:
        key = (r["task_id"], r["condition_id"])
        pass_rate = r["tests_passed"] / r["tests_total"] if r["tests_total"] and r["tests_total"] > 0 else None
        data[key] = {
            "run_id": r["run_id"],
            "tests_passed": r["tests_passed"],
            "tests_total": r["tests_total"],
            "pass_rate": pass_rate,
            "status": r["judge_report_status"],
            "failure_kind": r["failure_kind"],
            "duration": r["agent_duration_seconds"],
            "tokens": r["tokens_used"],
        }
    return data


def print_table(data: dict):
    """Druckt Task × Condition Tabelle."""
    # Alle Tasks sammeln
    tasks = sorted(set(k[0] for k in data.keys()))
    conditions = CONDITIONS

    # Header
    print("\n" + "=" * 90)
    print("SCREENING ERGEBNISSE")
    print("=" * 90)

    header = f"{'Task':<35}" + "".join(f"{c.replace('baseline_v0','baseline').replace('karpathy_rule_','R'):>12}" for c in conditions)
    print(header)
    print("-" * 90)

    for task in tasks:
        row = f"{task:<35}"
        for cond in conditions:
            val = data.get((task, cond))
            if val is None:
                row += f"{'—':>12}"
            elif val["pass_rate"] is None:
                row += f"{'ERR':>12}"
            else:
                pr = val["pass_rate"]
                total = val["tests_total"]
                passed = val["tests_passed"]
                # Farbe im String (funktioniert in Terminal)
                if val["failure_kind"] in ("task_failure",):
                    row += f"\033[92m{passed}/{total}\033[0m{'':>4}"
                elif val["failure_kind"] in ("agent_timeout", "agent_import_error"):
                    row += f"\033[91m{passed}/{total}\033[0m{'':>4}"
                else:
                    row += f"{passed}/{total}{'':>5}"
        print(row)

    print("-" * 90)


def print_deltas(data: dict):
    """Druckt Delta vs Baseline aggregiert."""
    print("\n" + "=" * 70)
    print("DELTA vs BASELINE (Rule - Baseline)")
    print("=" * 70)

    tasks = sorted(set(k[0] for k in data.keys()))

    print(f"\n{'Regel':<20} {'mean Δ':>10} {'win/total':>12} {'Trend':>15}")
    print("-" * 70)

    for rule in CONDITIONS:
        if rule == "baseline_v0":
            continue

        deltas = []
        wins = 0
        losses = 0
        no_baseline = 0

        for task in tasks:
            b = data.get((task, "baseline_v0"))
            r = data.get((task, rule))

            if b is None or r is None:
                continue
            if b["pass_rate"] is None or r["pass_rate"] is None:
                no_baseline += 1
                continue

            delta = r["pass_rate"] - b["pass_rate"]
            deltas.append(delta)
            if delta > 0:
                wins += 1
            elif delta < 0:
                losses += 1

        if not deltas:
            print(f"{RULE_LABELS.get(rule, rule):<20} {'N/A':>10} {'—':>12} {'N/A':>15}")
            continue

        mean_delta = sum(deltas) / len(deltas)

        if wins >= 4:
            trend = "\033[92m✔ stark positiv\033[0m"
        elif losses >= 4:
            trend = "\033[91m✘ stark negativ\033[0m"
        elif wins > losses:
            trend = "\033[93m~ tendenziell +\033[0m"
        elif losses > wins:
            trend = "\033[93m~ tendenziell -\033[0m"
        else:
            trend = "\033[90m~ gemischt\033[0m"

        print(f"{RULE_LABELS.get(rule, rule):<20} {mean_delta:>+10.3f} {wins}/{len(deltas)}:{losses}   {trend}")

    print()


def print_summary(data: dict):
    """Aggregierte Statistik pro Bedingung."""
    print("=" * 70)
    print("ZUSAMMENFASSUNG PRO BEDINGUNG")
    print("=" * 70)

    for cond in CONDITIONS:
        vals = [v["pass_rate"] for v in data.values() if v[0] == cond and v["pass_rate"] is not None] if False else [v["pass_rate"] for k, v in data.items() if k[1] == cond and v["pass_rate"] is not None]
        # Re-run properly
        vals = []
        for k, v in data.items():
            if k[1] == cond and v["pass_rate"] is not None:
                vals.append(v["pass_rate"])

        label = RULE_LABELS.get(cond, cond)

        if vals:
            mean_pr = sum(vals) / len(vals)
            print(f"  {label:<20}: mean_pass_rate={mean_pr:.3f} (n={len(vals)})")
        else:
            print(f"  {label:<20}: keine Daten")


def main():
    if not DB_PATH.exists():
        print(f"[ERROR] DB nicht gefunden: {DB_PATH}")
        print("Bitte erst scripts/run_efficient_screening.sh ausführen.")
        return

    data = load_data()

    if not data:
        print("[ERROR] Keine efficient_screening Runs in DB gefunden.")
        print("Bitte erst scripts/run_efficient_screening.sh ausführen.")
        return

    tasks = sorted(set(k[0] for k in data.keys()))
    print(f"\n[tasks={len(tasks)}, conditions={len(CONDITIONS)}, total_runs={len(data)}]")

    print_table(data)
    print_deltas(data)
    print_summary(data)

    print("\nInterpretation:")
    print("  mean Δ > 0  → Regel tendenziell hilfreich")
    print("  mean Δ < 0  → Regel tendenziell schädlich")
    print("  win/total   → wie oft besser vs schlechter als Baseline")
    print("  ≥ 4/5 wins  → starker Trend — Phase 2 lohnt sich")
    print("  ≤ 1/5 wins  → starker negativer Trend — meiden")


if __name__ == "__main__":
    main()
