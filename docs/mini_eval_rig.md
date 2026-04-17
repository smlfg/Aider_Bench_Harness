# Mini Eval Rig (Harness Policy)

Ziel
- Kleines, reproduzierbares Experiment-Rig für Policy-Vergleich.
- Primär: harte Test-Metriken, nicht Judge.

## Conditions
- `baseline_6line` (Control)
- `negative_control_karpathy40` (Negativkontrolle)

Neue Condition hinzufügen:
1. Kopiere baseline policy in neue Datei unter `harness/`.
2. Füge **genau eine** atomare Regeländerung hinzu.
3. Trage neue Condition in `data/experiment_config.json` ein.
4. Keine Multi-Regel-Änderungen in einer Condition.

## Config
Zentrale Datei: `data/experiment_config.json`
- model_name
- tasks.file
- conditions
- runs_per_condition_per_task
- timeouts

Task-Liste (V0):
- `data/tasks_astropy_small.json` (3 Astropy-Bugfix-Tasks)

## Commands
Dry-run (nur Plan):
- `python -m runner.experiment_runner --config data/experiment_config.json --dry-run`

Baseline-only:
- `python -m runner.experiment_runner --config data/experiment_config.json --phase baseline`

Voller Run (baseline-first + fail-fast):
- `python -m runner.experiment_runner --config data/experiment_config.json`

Summary:
- `python -m runner.experiment_summarize --iteration 1 --baseline baseline_6line`

## Fail-Fast
Nach Baseline wird abgebrochen, wenn z. B.:
- Infra-Fehlerquote zu hoch
- zu wenige diskriminative Tasks
- Baseline-Varianz zu hoch

Das wird explizit als Grund gemeldet (non-zero exit).

## Outputs
Pro Run (`run_meta.json`) u. a.:
- task_success / success
- fail_to_pass_total/passed
- pass_to_pass_total/passed
- tests_passed/tests_total
- duration, tokens, diff stats
- unrelated_edits_present
- target_file(s)

Aggregate (`results/summary/experiment_report.*`):
- Mittelwerte + Varianz (harte Metriken)
- Win/Loss vs Baseline
- Fail-fast Statusblock
- Judge nur sekundär
