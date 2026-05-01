# Experiment Rig — Harness Policy Evaluation

## Was

Kleines, reproduzierbares Experimentier-Rig für die Frage:

> Kann eine minimalist Harness-Policy besser performen als eine überladene?

## Struktur

```
experiment_config.json    # Zentrale Config: Tasks, Conditions, Runs
harness/
  CONVENTIONS.baseline.md                  # Baseline: 6 Zeilen (control)
  CONVENTIONS.negative_control_karpathy40.md  # 40 § (negative control)
data/selected_tasks.json   # 3 Tasks (Astropy × Django)
runner/
  experiment_runner.py     # Matrix-Runner
  experiment_summarize.py   # Report + Fail-Fast
```

## Bedingungen

| Condition | Datei | Beschreibung |
|-----------|-------|-------------|
| `baseline_6line` | `CONVENTIONS.baseline.md` | 6-Regel-Policy |
| `negative_control_karpathy40` | `CONVENTIONS.negative_control_karpathy40.md` | 40-§-Policy |

## Wie man startet

```bash
# Iteration 1: dry-run
.venv/bin/python -m runner.experiment_runner --dry-run

# Echter Lauf
.venv/bin/python -m runner.experiment_runner --iteration 1

# Report nach dem Lauf
.venv/bin/python -m runner.experiment_summarize --iteration 1
```

## Result Schema

`run_meta.json` pro Run:

```json
{
  "run_id": "baseline_6line_astropy__astropy-12907_run01",
  "task_id": "astropy__astropy-12907",
  "condition_id": "baseline_6line",
  "task_success": true,
  "tests_passed": 2,
  "tests_total": 2,
  "unrelated_edits_present": false,
  "duration_seconds": 142.3,
  "tokens_in": 8000,
  "tokens_out": 3200,
  "files_changed": 1,
  "lines_added": 12,
  "lines_removed": 3,
  "judge_score": 4
}
```

## Aggregat-Report

```
results/summary/experiment_report.md
```

- Pro Task: Erfolg rate + 95% Wilson CI
- Pro Condition: mean success rate, mean pass rate, mean duration
- Win/Loss vs Baseline
- Fail-Fast status

## Fail-Fast Regel

Wenn `baseline_6line` auf einem Task zu instabil ist (SE > 0.3 oder 0/{n} successes),
reportet `experiment_summarize.py` **FAIL-FAST: ...** — das Experiment ist in der
aktuellen Form nicht aussagekräftig.

## Neue Regel hinzufügen

1. `harness/CONVENTIONS.baseline_plus_rule_XX.md` anlegen (kopiere baseline + neue Zeile)
2. `data/experiment_config.json` erweitern:

```json
{
  "conditions": {
    "baseline_6line": { ... },
    "negative_control_karpathy40": { ... },
    "baseline_plus_rule_01": {
      "conventions_path": "harness/CONVENTIONS.baseline_plus_rule_01.md",
      "description": "Baseline + Rule 01"
    }
  }
}
```

3. Alte DB-Resultate für Iteration 1 zur Seite legen
4. Neuen Lauf starten:

```bash
.venv/bin/python -m runner.experiment_runner --iteration 2
.venv/bin/python -m runner.experiment_summarize --iteration 2 --baseline baseline_6line
```

## Taskwechsel

Tasks in `data/selected_tasks.json` ersetzen. Dann DB leeren oder neue Iteration.

```bash
rm results/experiment.db
```
