# Wissenschaftliches Auswertungsprotokoll

Dieses Projekt soll nicht beweisen, dass `Karpathy.md` allgemein "gut" ist.
Es soll pruefen, ob eine klar benannte Markdown-Policy in einem eng benannten
Harness-Scope messbar anderes Agentenverhalten erzeugt als eine Baseline.

## Erkenntnistheoretischer Kern

Die richtige Form ist kein globales Werturteil, sondern ein falsifizierbarer
A/B-Satz:

> Bei kleinen Coding-Tasks reduziert Condition B bestimmtes Fehlverhalten
> gegenueber Condition A, unter gleichem Modell, gleicher Task-Auswahl und
> gleicher Messpipeline.

Darauf folgen drei getrennte Claims:

| Claim | Bedeutung | Falsifikation |
|---|---|---|
| `H_strong` | Candidate ist in keinem gueltigen Run schlechter als Baseline. | Ein valider Gegenlauf reicht. |
| `H_avg` | Candidate verbessert den durchschnittlichen Treatment-Effekt. | Mittlerer Effekt <= 0 oder CI zeigt klar in die falsche Richtung. |
| `H_safety` | Candidate erzeugt keine neuen Fehlerarten. | Neue Regressionen, unrelated edits, Scope-Verletzungen oder neue Failure-Klassen. |

Ein einzelnes Gegenbeispiel zerstoert also nur die starke Universalbehauptung.
Es zerstoert nicht automatisch die schwaechere statistische Behauptung, dass
der Candidate im Erwartungswert hilft.

## Was als gueltiger A/B-Vergleich zaehlt

Ein Run darf nur in die wissenschaftliche Auswertung, wenn:

- `infrastructure_error = 0`
- `tests_total > 0`
- Baseline und Candidate dieselbe `iteration` verwenden
- Baseline und Candidate mindestens einen gemeinsamen `task_id` haben
- das Modell zwischen den verglichenen Bedingungen nicht gewechselt wurde
- eine `condition_id` nicht mehrere verschiedene `conventions_hash`-Identitaeten mischt

Runs mit `--skip-eval`, Docker-/Auth-Problemen oder `tests_total = 0` sind
wertvoll fuer Debugging, aber keine harte Evidenz fuer den Treatment-Effekt.

## Primaere und sekundaere Outcomes

Primaer, weil direkt an der Aufgabe:

- `task_success`
- `tests_pass_rate`
- `fail_to_pass_rate`
- `pass_to_pass_rate`

Sekundaer, weil sie Verhalten erklaeren:

- `unrelated_edits_present`
- `diff_size_loc`
- `duration_seconds`
- `cost_estimate`
- Judge-Rubriken: `scope_adherence`, `minimality`, `diff_clarity`

Der Judge ist ein Tiebreaker und Diagnoseinstrument, aber nicht das primaere
Erfolgskriterium.

## CLI: wissenschaftlicher A/B-Report

Verfuegbare Conditions anzeigen:

```bash
uv run harness-science-ab --list
```

Beispiel fuer Baseline gegen Candidate:

```bash
uv run harness-science-ab \
  --iteration 1 \
  --baseline baseline_6line \
  --candidate negative_control_karpathy40
```

Strengerer Report mit mindestens 5 gemeinsamen Tasks und 5 Repeats pro Zelle:

```bash
uv run harness-science-ab \
  --iteration 7 \
  --baseline baseline_6line \
  --candidate karpathy_v1 \
  --min-common-tasks 5 \
  --min-runs-per-task 5
```

Der Report landet in:

```text
results/summary/scientific_ab_iteration_<N>_<baseline>_vs_<candidate>.md
results/summary/scientific_ab_iteration_<N>_<baseline>_vs_<candidate>.json
```

## CLI: Modellursache testen

Wenn die Frage lautet "liegt es am Modell?", muss die Policy konstant bleiben.
Der Modellvergleich paart deshalb nach `condition_id` und `task_id`.

Verfuegbare Modellzellen anzeigen:

```bash
uv run harness-model-ab --list
```

GPT 5.5 gegen MiniMax M2.7 innerhalb einer festen Condition:

```bash
uv run harness-model-ab \
  --iteration 7 \
  --condition baseline_6line \
  --baseline-model openai/MiniMax-M2.7 \
  --candidate-model openai/gpt-5.5 \
  --min-common-cells 5 \
  --min-runs-per-cell 5
```

MiniMax M2.7 gegen M2.5:

```bash
uv run harness-model-ab \
  --iteration 8 \
  --condition baseline_6line \
  --baseline-model openai/MiniMax-M2.7 \
  --candidate-model openai/MiniMax-M2.5 \
  --min-common-cells 5 \
  --min-runs-per-cell 5
```

Ohne gemeinsame `condition_id`/`task_id`-Zellen ist die Modellhypothese nicht
entscheidbar. Dann koennte der Unterschied am Task, an der Policy, an Infra oder
am Modell liegen.

## Entscheidungslogik

| Befund | Wissenschaftliche Lesart |
|---|---|
| Validity Gate hat `FAIL` | Nicht entscheidbar; erst Messdesign reparieren. |
| Validity Gate hat `WARN` | Nur qualifizierte/deskriptive Aussage. |
| Gegenbeispiele vorhanden | `H_strong` ist falsifiziert. |
| `tests_pass_rate`-Delta > 0, aber CI umfasst 0 | Positiver Trend, noch kein belastbarer Effekt. |
| `tests_pass_rate`-CI voll > 0 | Candidate unterstuetzt `H_avg` im gemessenen Scope. |
| `tests_pass_rate`-CI voll < 0 | Candidate widerlegt die Verbesserungsbehauptung im gemessenen Scope. |
| `pass_to_pass_rate` sinkt oder unrelated edits steigen | Safety-Claim geschwaecht oder falsifiziert. |

## Minimaler sauberer Versuchsplan

Fuer erste belastbare Erkenntnisse:

```text
5 kleine Tasks
x 5 Wiederholungen
x 2 Conditions: Baseline und Candidate
= 50 Runs
```

Besser:

```text
10 kleine Tasks
x 5 Wiederholungen
x 2 Conditions
= 100 Runs
```

Wenn einzelne Regeln isoliert werden sollen:

```text
Baseline + R01 + R02 + R03 + R04
x 10 Tasks
x 5 Wiederholungen
= 250 Runs
```

Erst danach lohnt sich ein faktorielles Design fuer Interaktionen.

## Praktische Regel

Wenn der Report sagt `not_decisive`, dann ist das kein schlechtes Ergebnis.
Es ist eine erfolgreiche Trennung von Rohdaten und Erkenntnis. Das Projekt sagt
dann sauber: "Diese Daten reichen noch nicht, um diese Behauptung zu tragen."
