# Neue Condition (Regel) hinzufügen

## Prinzip

Pro Iteration wird **genau eine** atomare Regeländerung getestet. Nie mehrere gleichzeitig.

## Schritt-für-Schritt

### 1. Basis-Datei kopieren

```bash
cp harness/CONVENTIONS.baseline.md harness/CONVENTIONS.<new_condition>.md
```

### 2. Genau eine atomare Änderung machen

Erlaubt:
- Eine Regel hinzufügen
- Eine Regel entfernen
- Eine Regel umformulieren
- Reihenfolge ändern
- Eine Regel präziser machen

**Nicht erlaubt:**
- Zwei oder mehr unabhängige Regeländerungen
- Neue externe Dateien
- Task-Prompt ändern
- Modell ändern

### 3. Config updaten

In `experiment_config.json` hinzufügen:

```json
"<new_condition>": {
  "conventions_file": "harness/CONVENTIONS.<new_condition>.md",
  "parent": "baseline_6line",
  "mutation_note": "Rule XX: <kurze Beschreibung der Änderung>"
}
```

### 4. In experiment_config.json conditions eintragen

Falls noch nicht vorhanden, neuer eintrag in `conditions`:

```json
"conditions": {
  "baseline_6line": { ... },
  "<new_condition>": {
    "conventions_file": "harness/CONVENTIONS.<new_condition>.md",
    "description": "Beschreibung",
    "parent": "baseline_6line"
  }
}
```

### 5. Matrix-Run ausführen

```bash
python -m runner.run_matrix \
  --baseline-conventions harness/CONVENTIONS.baseline.md \
  --candidate-conventions harness/CONVENTIONS.<new_condition>.md \
  --candidate-condition <new_condition> \
  --runs-per-task 3 \
  --iteration 2
```

### 6. Fail-Fast prüfen

```bash
python -m runner.fail_fast --check baseline --condition baseline_6line
python -m runner.fail_fast --check iteration --iteration 2
```

### 7. Report generieren

```bash
python -m runner.summarize --iteration 2
```

### 8. Ergebnis in `results/summary/iteration_2.md` lesen

## Condition-Namenskonvention

```
baseline_6line              # Die 6-Zeilen Baseline
negative_control_karpathy40 # 40-§ Negativkontrolle
baseline_plus_rule_XX       # Baseline + eine neue Regel
baseline_plus_rule_XX_Y Y   # Kombinationen nur für später, wenn Basis etabliert
```

## Atomare Regeländerung - Beispiele

### Regel hinzufügen

**Baseline:**
```
## Rules
1. State the bug hypothesis before editing.
2. Reproduce or inspect the failing behavior first.
```

**Neu:**
```
## Rules
1. State the bug hypothesis before editing.
2. Reproduce or inspect the failing behavior first.
3. Identify the single most relevant file before editing.
```

### Regel umformulieren

**Baseline:**
```
5. Run the relevant tests before finalizing.
```

**Neu:**
```
5. Run the specific failing test after each change. Run the full relevant test set before finalizing.
```

### Regel entfernen

Nur wenn der Test zeigt, dass die Regel keinen Nutzen hat. Selten in frühen Iterationen.

## Typische Fehler vermeiden

1. **Nicht zu viele Regeln auf einmal** - Wenn eine Änderung nicht hilft, weiß man nicht welche
2. **Nicht die Baseline ändern** - Die Baseline bleibt der Fixpunkt für alle Vergleiche
3. **Nicht Task oder Modell ändern** - Nur die CONVENTIONS.md ändert sich
4. **Nicht voreilig optimieren** - Erst Varianz messen, dann eine Regel ändern

## Wann ist eine Regel erfolgreich?

Eine neue Condition `C` ist erfolgreich wenn:

1. `mean task_success(C) >= mean task_success(baseline)`
2. `mean tests_pass_rate(C) >= mean tests_pass_rate(baseline)`
3. Judge nicht signifikant schlechter
4. Keine massive Kosten- oder Zeitexplosion

## Fail-Fast Schwellenwerte

| Metrik | Threshold | Bedeutung |
|--------|-----------|-----------|
| CV (Variationskoeffizient) | > 0.4 | Baseline zu volatil |
| Diskriminative Tasks | < 2 | Nicht genug Messbarkeit |
| Baseline Pass Rate | < 0.2 oder > 0.8 | Task zu leicht/schwer |
| Infrastructure Errors | > 50% | Setup-Problem |

## Iteration fortlaufend nummerieren

- Iteration 1: Baseline vs Negativkontrolle
- Iteration 2: Baseline + Regel 1 vs Baseline
- Iteration 3: Baseline + Regel 2 vs Baseline
- usw.
