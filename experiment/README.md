# Harness Policy Evaluation Rig

Kleines, reproduzierbares Experimentier-Rig für Harness-Policy-Evaluation.

## Struktur

```
experiment/
├── config.json           # Zentrale Konfiguration (Modell, Tasks, Conditions, Runs)
├── conditions/           # Eine Subdir pro Condition, darin CONVENTIONS.md
│   ├── baseline_6line/
│   └── negative_control_karpathy40/
├── tasks/
│   └── tasks.json       # Task-Definitionen (instace_id, FAIL_TO_PASS, etc.)
├── results/              # Wird bei der Ausführung befüllt
│   └── report/
│       └── summary.md   # Aggregierter Report
├── runner.py             # Führt das vollständige Matrix-Experiment aus
├── aggregate.py          # Aggregiert Ergebnisse + Fail-Fast-Check
└── README.md
```

## Conditions

| ID | Beschreibung | Zeilen |
|---|---|---|
| `baseline_6line` | Minimaler 6-Zeilen-Policy | 13 |
| `negative_control_karpathy40` | 40-§-Policy als Negativkontrolle | 243 |

## Tasks (3 Astropy-Tasks)

- `astropy__astropy-12907` — separability_matrix Bug in nested CompoundModels
- `astropy__astropy-14182` — RST Writer header_rows Support
- `astropy__astropy-14365` — QDP case-insensitive Commands

Alle Tasks haben `FAIL_TO_PASS` und `PASS_TO_PASS` definiert.

## How to Run

### Vollständiges Experiment

```bash
cd experiment
python runner.py
```

Das startet `3 tasks × 2 conditions × 3 runs = 18` Einzelläufe.

### Trockentest (zeigt was laufen würde)

```bash
python runner.py --dry-run
```

### Einzelne Kombination

```bash
python runner.py --condition baseline_6line --run 1
```

### Ergebnis-Aggregation

```bash
python aggregate.py
```

Generiert `results/report/summary.md` mit Tabellen und Win/Loss gegen Baseline.

## Fail-Fast-Regel

Das Experiment wird als **ungültig verworfen** (Exit Code 2), wenn:

1. **Baseline Task-Success CV > 0.35** — zu hohe Varianz über Tasks hinweg
2. **Baseline Duration CV > 0.60** — Laufzeiten zu instabil

Grund: Wenn die Baseline nicht stabil ist, kann keine Aussage über Treatments getroffen werden.

## Result-JSON Schema

Pro Run wird in `results/<condition>/<task_id>/<run_id>/result.json` gespeichert:

```json
{
  "run_id": "baseline_6line_astropy__astropy-12907_run01",
  "task_id": "astropy__astropy-12907",
  "condition_id": "baseline_6line",
  "run_index": 1,
  "start_ts": "2026-04-17T10:00:00+00:00",
  "end_ts": "2026-04-17T10:05:00+00:00",
  "duration_s": 300.0,
  "exit_code": 0,
  "artifacts_dir": "results/baseline_6line/astropy__astropy-12907/baseline_6line_astropy__astropy-12907_run01"
}
```

Die vollständigen Metriken liegen in `run_meta.json` (Tests, Tokens, Diff-Stats, etc.).

## Neue Regel als neue Condition hinzufügen

1. **Condition definieren**:
   ```bash
   mkdir experiment/conditions/baseline_plus_rule_01
   ```

2. **CONVENTIONS.md schreiben** — basierend auf `baseline_6line`, plus die neue Regel:
   ```markdown
   # CONVENTIONS.md

   ## Goal
   Solve the requested bug with the smallest correct change.

   ## Rules
   1. State the bug hypothesis before editing.
   2. Reproduce or inspect the failing behavior first.
   3. Prefer the smallest fix that makes tests pass.
   4. Do not refactor unrelated code.
   5. Run the relevant tests before finalizing.
   6. In the final message, state what changed and which tests passed.
   7. NEW RULE: Always explain the expected vs actual behavior.
   ```

3. **Config erweitern** in `config.json`:
   ```json
   {
     "conditions": [
       "baseline_6line",
       "negative_control_karpathy40",
       "baseline_plus_rule_01"
     ]
   }
   ```

4. **Regel isoliert testen** — nie mehrere Regeln gleichzeitig hinzufügen.

## Primäre vs Sekundäre Metriken

**Hart (Entscheidend für Verdict):**
- `task_success` — hat der Run den Bug gefixt?
- `tests_passed / tests_total` — wie viele Tests bestehen
- `FAIL_TO_PASS` — haben die ursprünglich fehlschlagenden Tests bestanden

**Sekundär (Kontext / Tiebreaker):**
- `tokens_in`, `tokens_out`, `duration_s`
- `files_changed`, `lines_added`, `lines_removed`
- `unrelated_edits_present`
- Judge-Score (wenn vorhanden)

## Wichtige Regeln

- **Nie mehrere Regeln gleichzeitig testen** — eine atomare Änderung pro Condition
- **Baseline bleibt invariant** — nie baseline modifizieren während des Experiments
- **3 Runs pro Task × Condition** — minimum für Varianzabschätzung
- **Harte Metrik > Judge** — Judge nur als qualitative Begründung, nicht als Entscheidungsgrund