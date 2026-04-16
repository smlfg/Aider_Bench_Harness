# Versuchsaufbau.md

## Titel
Minimal-Experiment zur eval-getriebenen Optimierung eines Wegwerf-Harnesses über Markdown-Instruktionen

---

## 1. Ziel des Experiments

Wir wollen **nicht** direkt ein produktives agentisches System optimieren.
Wir wollen zuerst nur die Frage beantworten:

> Kann man den Effekt kleiner Änderungen an einer Markdown-Instruktionsdatei (`AGENTS.md` / `CONVENTIONS.md`) bei einem einfachen Coding-Harness überhaupt belastbar messen?

Dieses Experiment ist absichtlich klein und falsifizierbar.
Es soll klären, ob die Methode lebt oder stirbt.

---

## 2. Kernhypothese

Eine einzelne, klar abgegrenzte Änderung an der zentralen Instruktionsdatei eines einfachen Coding-Harnesses kann die Performance auf einer kleinen, homogenen Task-Klasse messbar verändern.

Wichtig:
- primäres Signal = **harte Metrik**
- sekundäres Signal = **LLM-as-a-judge**
- keine Automatisierung der Optimierung in Phase 1
- Operator = **Mensch** für die ersten 5 Iterationen

---

## 3. Designprinzipien

1. **Wegwerf-Harness statt Produktions-Harness**
   - Das Experiment darf scheitern, ohne bestehende Systeme zu kontaminieren.
   - Keine Kopplung an Sidecar, Hermes-Profile oder bestehende private CLAUDE.md-Ökosysteme.

2. **Nur ein Harness**
   - Keine Cross-Harness-Vergleiche.
   - Ziel ist Messbarkeit, nicht Marktvergleich.

3. **Nur eine Task-Klasse**
   - Kleine Python-Bugfix-Tasks.
   - Gleichartige Aufgaben reduzieren Varianz.

4. **Nur eine Veränderung pro Iteration**
   - Pro Iteration wird genau ein Abschnitt in der Instruktionsdatei geändert.
   - Keine parallelen Änderungen an Modell, Tooling, Repo, Task oder Testsetup.

5. **Harte Metrik vor Judge**
   - `tests_passed` / `tests_total` ist primär.
   - Judge dient nur als Tiebreaker oder Zusatzsignal.

6. **Baseline-Varianz zuerst messen**
   - Bevor optimiert wird, muss gemessen werden, wie stark dasselbe Setup ohnehin streut.
   - Falls die natürliche Varianz größer ist als die erwartete Wirkung kleiner Markdown-Edits, ist die Methode in dieser Form unbrauchbar.

---

## 4. Konkrete Entscheidungen

### 4.1 Modellwahl

**Gewählt: `MiniMax-M2.7-highspeed`**

### Begründung
- Gleiches Qualitätsniveau wie `MiniMax-M2.7`, aber schneller.
- Für ein iteratives Experiment mit mehreren Wiederholungen ist schnellere Laufzeit nützlicher als die langsamere Standardvariante.
- Gegenüber `M2.5` ist `M2.7` die stärkere Wahl, wenn das Ziel ist, die Messmethode zu validieren und nicht absichtlich ein schwächeres Modell zu stressen.
- Ein stärkeres Modell reduziert das Risiko, dass triviale Task-Fehlschläge nur durch unzureichende Grundfähigkeit entstehen.

### Fallback
Falls `M2.7-highspeed` technisch nicht sauber in das gewählte Harness integrierbar ist, nutze `MiniMax-M2.7`.
Nur wenn beides nicht sauber funktioniert, auf `M2.5` zurückfallen.

### Konstanzregel
Für den gesamten ersten Versuch gilt:
- exakt ein Modell
- exakt dieselbe Modellvariante
- exakt dieselben Sampling-Parameter

---

### 4.2 Harness-Wahl

**Gewählt: Aider**

### Begründung
Aider ist für dieses Experiment besser geeignet als schwerere agentische Systeme, weil es:
- terminalbasiert und relativ minimal ist
- modellagnostisch arbeitet
- Git-Repo-nah ist
- klaren Fokus auf Code-Änderungen in lokalen Repositories hat
- Konventionsdateien per Markdown unterstützt
- deutlich weniger bewegliche Teile hat als größere agentische Plattformen

### Warum nicht OpenHands / schwere Agent-Harnesses?
Weil dieses Experiment **nicht** die Qualität eines vollwertigen autonomen Agent-Systems messen soll.
Schwere Harnesses bringen zusätzliche Störfaktoren hinein:
- komplexere Orchestrierung
- Sandbox-/Runtime-Schichten
- zusätzliche Controller-Logik
- mehr interne Zustände
- schwerere Attribution von Verbesserungen

### Warum nicht OpenCode für Version 0?
OpenCode ist gut, aber bereits agentischer und feature-reicher.
Für die erste Validierung ist Aider enger, einfacher und damit methodisch sauberer.

### Konsequenz
In V0 optimieren wir **nicht Skills und Hooks**, sondern genau **eine Markdown-Konventionsdatei**.
Also nicht die ganze Harness-Oberfläche, sondern einen schmalen, kontrollierten Instruktionskanal.

---

### 4.3 Task-Wahl

**Gewählt: 3 kleine Python-Bugfix-Tasks aus SWE-bench Lite**

### Begründung
Python-Bugfix bleibt für das erste Experiment ideal, weil:
- Tests schnell laufen
- Reproduzierbarkeit hoch ist
- Aufgaben klein gehalten werden können
- `tests_passed/tests_total` eine harte Metrik ist
- dieselbe Task-Klasse über reale Repositories hinweg gut vergleichbar ist

Statt eigene Mini-Repos zu bauen, werden die Tasks aus **SWE-bench Lite**
(`princeton-nlp/SWE-bench_Lite`) gezogen.

Das reduziert Eigenbau-Bias in den Aufgaben und nutzt eine bestehende Pass/Fail-
Infrastruktur auf echten GitHub-Issues.

### Harte Metrik

Für SWE-bench Lite bedeutet `tests_passed/tests_total` konkret:
- `FAIL_TO_PASS`: Tests, die durch den Patch von rot auf grün wechseln müssen
- `PASS_TO_PASS`: Tests, die durch den Patch grün bleiben müssen

Ein Run ist erfolgreich, wenn alle relevanten `FAIL_TO_PASS`- und
`PASS_TO_PASS`-Tests bestehen.

### Nicht gewählt
- Greenfield-Feature-Builds: zu offen
- Refactor-only: Erfolg schwerer objektiv messbar
- Frontend/UI: Judge- und Visual-Noise zu hoch
- Multi-file Architekturarbeit: zu viele Freiheitsgrade

### Task-Charakteristika
Jeder Task soll:
- maximal 2-4 Dateien betreffen
- einen klaren, existierenden Bug enthalten
- mindestens einen failing test zu Beginn haben
- unter 2 Minuten Testlaufzeit bleiben
- keinen Netzwerkzugriff benötigen
- keine externen Services brauchen

---

## 5. Was wird optimiert?

### Optimierungsobjekt
Eine Datei:

- `CONVENTIONS.md`

oder alternativ, falls der Coder lieber OpenCode statt Aider aufsetzt:

- `AGENTS.md`

Für V0 gilt aber: **eine Datei, ein Optimierungsobjekt**.

### Nicht Teil der Optimierung in V0
- Modellwechsel
- Tooling-Änderungen
- Hook-Änderungen
- Skill-Systeme
- Prompt-Template außerhalb der Markdown-Datei
- Task-Auswahl
- Judge-Prompt
- Test-Runner

---

## 6. Inspirationsbasis für die erste Baseline-Datei

Als inhaltliche Inspiration kann eine vorsichtige, engineering-zentrierte Datei im Stil von Karpathy/forrestchang dienen.

Aber:
- nicht einfach blind übernehmen
- keine große Universal-CLAUDE.md bauen
- nur 4-6 Regeln aufnehmen
- jede Regel muss auf Bugfix-Tasks einzahlen

### Empfohlene Baseline-Struktur

```md
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
```

Diese Datei ist absichtlich klein.
Nicht „besserer Stil“, sondern **bessere Messbarkeit** ist das Ziel.

---

## 7. Experimentstruktur

## 7.1 Bedingungen

### Condition A — Baseline
- fixes Harness
- fixes Modell
- fixes `CONVENTIONS.md`
- 3 Tasks
- 5 Runs pro Task für die eigentliche Baseline-Varianzmessung

### Condition B — Mutation
- alles identisch zu A
- genau **eine** Änderung in `CONVENTIONS.md`
- wieder 3 Tasks
- 5 Runs pro Task

---

## 7.2 Wiederholungen

Für die Task-Kalibration:
- 6-10 Kandidaten-Tasks
- 3 Runs pro Kandidat als grobe Vorauswahl

Für die Baseline-Varianzmessung:
- 3 finale Tasks
- 5 Runs pro Task
- also 15 Baseline-Runs

Für eine Candidate-Mutation:
- 3 finale Tasks
- 5 Runs pro Task
- also 15 Candidate-Runs

### Begründung
Ein einzelner Run ist zu instabil.
3 Runs pro Task reichen nur als grober Filter.
Für die eigentliche Varianzmessung braucht jeder finale Task mehr Wiederholungen,
sonst sind die Unsicherheitsintervalle zu breit.

Die erste relevante Frage lautet nicht „wurde es besser?“, sondern:

> Wie groß ist die natürliche Streuung desselben Setups?

---

## 7.3 Operator-Regel

Für die ersten **5 Iterationen** ist der Operator **manuell**.

Das heißt:
- kein Optimizer-Agent
- keine automatische Mutationserzeugung
- du entscheidest die Änderung selbst
- nach Sichtung der Baseline-Ergebnisse

### Begründung
Erst muss die Messlogik validiert werden.
Danach kann über Automatisierung nachgedacht werden.

---

## 8. Architektur

```text
experiment/
├─ data/
│  ├─ swebench_lite_candidates.json
│  └─ selected_tasks.json
├─ harness/
│  ├─ CONVENTIONS.baseline.md
│  ├─ CONVENTIONS.candidate.md
│  └─ aider-config.example.yml
├─ runner/
│  ├─ run_once.py
│  ├─ calibrate.py
│  ├─ run_matrix.py
│  ├─ judge.py
│  ├─ summarize.py
│  └─ schemas/
│     ├─ run_result.schema.json
│     └─ judge_result.schema.json
└─ results/
   ├─ baseline/
   ├─ candidate/
   ├─ summary/
   └─ experiment.db
```

SWE-bench Lite liefert Repo, Base-Commit, Problem Statement und relevante Tests.
Der lokale Harness erzeugt daraus pro Run einen frischen Worktree, schreibt die
jeweilige `CONVENTIONS.md`, lässt Aider einen Patch erzeugen und wertet den Patch
über SWE-bench aus.

Rohdaten bleiben als Dateien unter `results/<condition>/<task_id>/<run_id>/`.
Aggregierbare Metadaten werden zusätzlich in `results/experiment.db` gespeichert.

---

## 9. Inputs und Outputs

## 9.1 Inputs

### Statische Inputs
- Modellname
- Harness-Konfiguration
- Markdown-Instruktionsdatei
- SWE-bench-Lite-Instanzen
- SWE-bench-Repo- und Test-Setup
- Judge-Rubric

### Pro Run
- `task_id`
- `run_id`
- `condition_id` (`baseline` oder `candidate`)
- `model_name`
- `conventions_file`
- `instance_id`
- `repo`
- `base_commit`
- `problem_statement`

---

## 9.2 Outputs pro Run

Jeder Run muss mindestens diese Dateien erzeugen:

- `agent_stdout.log`
- `agent_stderr.log`
- `git_diff.patch`
- `tests.json`
- `run_meta.json`
- `judge_input.json`
- `judge_result.json`

### `tests.json`

`tests.json` enthält die SWE-bench-relevanten Testergebnisse:

```json
{
  "FAIL_TO_PASS": {
    "total": 2,
    "passed": 2,
    "failed": []
  },
  "PASS_TO_PASS": {
    "total": 8,
    "passed": 8,
    "failed": []
  }
}
```

---

## 9.3 Pflichtfelder in `run_meta.json`

```json
{
  "run_id": "baseline_django__django-12345_run01",
  "task_id": "django__django-12345",
  "condition_id": "baseline",
  "model_name": "MiniMax-M2.7-highspeed",
  "harness_name": "aider",
  "instruction_file": "CONVENTIONS.baseline.md",
  "start_ts": "...",
  "end_ts": "...",
  "duration_seconds": 0,
  "exit_code": 0,
  "tokens_in": null,
  "tokens_out": null,
  "cost_estimate": null,
  "files_changed": 0,
  "lines_added": 0,
  "lines_removed": 0,
  "tests_total": 0,
  "tests_passed": 0,
  "task_success": false
}
```

Hinweis:
Wenn Token-/Kostendaten nicht sauber extrahierbar sind, in V0 optional lassen.
`tests_passed/tests_total` ist wichtiger.

---

## 9.4 SQLite-Schema

Zusätzlich zu den Rohdateien schreibt der Harness nach
`results/experiment.db`.

### Tabelle `runs`

Eine Zeile pro Haupt-Run:

| Feld | Typ |
|---|---|
| `run_id` | TEXT PRIMARY KEY |
| `task_id` | TEXT |
| `condition_id` | TEXT |
| `iteration` | INTEGER |
| `model_name` | TEXT |
| `conventions_hash` | TEXT |
| `conventions_path` | TEXT |
| `start_ts` | TEXT |
| `end_ts` | TEXT |
| `duration_seconds` | REAL |
| `exit_code` | INTEGER |
| `tokens_in` | INTEGER |
| `tokens_out` | INTEGER |
| `cost_estimate` | REAL |
| `tests_total` | INTEGER |
| `tests_passed` | INTEGER |
| `task_success` | INTEGER |
| `files_changed` | INTEGER |
| `lines_added` | INTEGER |
| `lines_removed` | INTEGER |
| `judge_score` | REAL |
| `artifacts_dir` | TEXT |

### Tabelle `conventions`

Eine Zeile pro verwendeter Markdown-Instruktionsdatei:

| Feld | Typ |
|---|---|
| `conventions_hash` | TEXT PRIMARY KEY |
| `content` | TEXT |
| `parent_hash` | TEXT |
| `mutation_note` | TEXT |

### Tabelle `calibration_runs`

Separater Log der Task-Kalibrationsphase.
Diese Läufe zählen nicht als Baseline-Runs der Hauptauswertung.

| Feld | Typ |
|---|---|
| `calibration_run_id` | TEXT PRIMARY KEY |
| `task_id` | TEXT |
| `round` | INTEGER |
| `run_index` | INTEGER |
| `model_name` | TEXT |
| `conventions_hash` | TEXT |
| `start_ts` | TEXT |
| `end_ts` | TEXT |
| `duration_seconds` | REAL |
| `exit_code` | INTEGER |
| `tests_total` | INTEGER |
| `tests_passed` | INTEGER |
| `task_success` | INTEGER |
| `artifacts_dir` | TEXT |

---

## 10. Primäre Metriken

### Primär
1. `task_success`
2. `tests_passed / tests_total`

### Sekundär
3. `duration_seconds`
4. `files_changed`
5. `lines_added + lines_removed`
6. `judge_score`

### Tertiär / Diagnose
7. `stderr_present`
8. `number_of_retries` (falls extrahierbar)
9. `patch_size`
10. `final_message_length`

---

## 11. Bewertungssystem

## 11.1 Harte Gates zuerst

Ein Run gilt als **hart erfolgreich**, wenn:
- Test-Runner ohne Infrastrukturfehler läuft
- alle relevanten Task-Tests grün sind

Ein Run gilt als **hart fehlgeschlagen**, wenn:
- Test-Runner nicht sauber startet
- relevante Tests scheitern
- kein sinnvoller Patch erzeugt wurde

### Primäre Erfolgsmetrik

```text
task_success = 1, wenn alle relevanten Tests bestehen
sonst 0
```

---

## 11.2 Judge nur als Tiebreaker

Judge darf nie die primäre Metrik überstimmen.

Judge wird nur verwendet, wenn zwei Varianten bei harten Metriken ähnlich sind.

### Judge-Rubric
Skala 1-5 für:
- Scope-Treue
- Minimalität der Änderung
- Verständlichkeit des Diffs

Gesamtscore:

```text
judge_score = Mittelwert der 3 Rubric-Scores
```

### Wichtige Regel
Judge bekommt:
- Original-Prompt
- Diff
- Testresultat
- kurze Task-Beschreibung

Judge bekommt **nicht** die Bedingung `baseline` oder `candidate`.
Der Judge nutzt ein separat konfiguriertes Modell, z. B. `JUDGE_MODEL=claude-sonnet-4.5`
oder `JUDGE_MODEL=gpt-4o`.
Er darf nicht identisch mit dem Agent-Modell sein, damit kein Self-Preference-Bias
in den Tiebreaker eingebaut wird.

---

## 12.0 Task-Kalibration

Vor dem Baseline-Varianz-Test wird der finale Task-Satz kalibriert.

Ziel:
Tasks finden, die für das gewählte Modell und Harness nicht trivial leicht und
nicht praktisch unlösbar sind.

### Prozedur

1. Aus SWE-bench Lite 6-10 Kandidaten-Tasks vorfiltern.
2. Für jeden Kandidaten 3 Baseline-Runs mit fixer `CONVENTIONS.baseline.md`
   fahren.
3. Pro Kandidat klassifizieren:
   - `0/3` erfolgreiche Runs: zu schwer, verwerfen
   - `3/3` erfolgreiche Runs: zu leicht, verwerfen
   - `1/3` oder `2/3` erfolgreiche Runs: diskriminativ, behalten
4. Aus dem diskriminativen Pool 3 Tasks als finalen Task-Satz fixieren.
5. Falls der Pool weniger als 3 Tasks enthält, 4-6 weitere Kandidaten ziehen
   und wiederholen.

### Abbruchregel

Wenn nach zwei Kalibrationsrunden weniger als 3 diskriminative Tasks übrig sind,
wird das Experiment abgebrochen.

Dann ist SWE-bench Lite für dieses Modell/Harness in dieser Form nicht der
richtige Schwierigkeitsgrad.

### Wichtige Trennung

Kalibrationsläufe werden in `calibration_runs` gespeichert.
Sie zählen **nicht** als Baseline-Runs der Hauptauswertung.

Die `1/3`- und `2/3`-Regel ist nur eine grobe Vorauswahl.
Bei `n=3` sind die Konfidenzintervalle zu breit, um echte
Task-Schwierigkeit belastbar zu schätzen.
Darum werden die finalen 3 Tasks anschließend mit je 5 Baseline-Runs gemessen.

---

## 12. Baseline-Varianz-Test

Vor jeder Optimierung zuerst:
- 3 Tasks
- 5 Runs je Task
- identische Baseline-Bedingung
- also 15 Baseline-Runs

Dann pro Task berechnen:
- Mittelwert `task_success`
- Mittelwert `tests_pass_rate`
- Mittelwert `judge_score`
- Standardabweichung / Spannweite der Scores
- grobe Unsicherheitsintervalle für `task_success`

### Abbruchregel
Falls die Baseline-Varianz so hoch ist, dass kleine Markdown-Änderungen plausibel darin untergehen, wird das Experiment in dieser Form gestoppt.

Pragmatische Faustregel:
- wenn die Judge-Streuung groß ist, aber `tests_passed` stabil ist → weitermachen
- wenn schon `tests_passed` stark streut → Methode in dieser Form unbrauchbar

---

## 13. Mutationsregel

Für jede Iteration ist genau **eine** Mutation erlaubt.

### Erlaubt
- eine Regel hinzufügen
- eine Regel entfernen
- eine Regel umformulieren
- Reihenfolge von Regeln ändern
- eine Regel präziser machen

### Nicht erlaubt
- zwei oder mehr unabhängige Regeländerungen
- neue externe Dateien
- Task-Prompt ändern
- Modell ändern
- Testsetup ändern
- Repo ändern

### Beispiel für eine gültige Mutation
Baseline-Regel:
- `Run the relevant tests before finalizing.`

Candidate-Regel:
- `Before editing, identify the smallest relevant test target. Run it after each meaningful change and run the full relevant test set before finalizing.`

Das ist eine **einzelne** präzisierende Mutation am Testverhalten.

---

## 14. Vergleichslogik

Verglichen wird immer konditionsweise:

```text
baseline vs candidate
```

für dieselben 3 finalen Tasks.

Die Baseline-Varianzmessung nutzt 5 Runs pro Task.
Eine Candidate-Mutation nutzt von Anfang an ebenfalls 5 Runs pro Task.
Es gibt kein nachträgliches Top-up, weil eine adaptive Erweiterung der
Run-Anzahl Information aus dem Zwischenergebnis leaken würde.

### Candidate gewinnt nur, wenn:
1. mittlere `task_success` nicht schlechter ist
2. mittlere `tests_pass_rate` nicht schlechter ist
3. Judge nicht klar schlechter ist
4. keine massive Kosten-/Zeitexplosion entsteht

### Empfehlung für V0
Primär nur auf diese beiden Fragen schauen:
- mehr harte Erfolge?
- gleiche harte Erfolge bei geringerem Änderungsumfang / besserem Judge?

---

## 15. Was der Coder konkret bauen soll

## 15.1 Muss gebaut werden

1. **Task-Runner**
   - zieht Repo und Test-Setup aus SWE-bench Lite
   - checkt den SWE-bench-`base_commit` in einem frischen Arbeitsverzeichnis aus
   - schreibt die gewünschte `CONVENTIONS.md`
   - ruft Aider mit festem Modell auf
   - gibt das SWE-bench-`problem_statement` hinein
   - speichert Logs
   - exportiert Git-Diff
   - evaluiert den Patch über SWE-bench `FAIL_TO_PASS` und `PASS_TO_PASS`
   - speichert Testresultate strukturiert in `tests.json`
   - schreibt `run_meta.json`
   - schreibt eine Zeile in `results/experiment.db`

2. **Kalibrations-Runner**
   - nimmt 6-10 SWE-bench-Lite-Kandidaten
   - fährt 3 Baseline-Runs pro Kandidat
   - schreibt alle Läufe in `calibration_runs`
   - filtert `0/3` und `3/3` aus
   - fixiert 3 Tasks mit `1/3` oder `2/3` als finalen Task-Satz

3. **Matrix-Runner**
   - läuft alle nötigen Kombinationen aus
     - 3 finale Tasks
     - 5 Baseline-Runs pro Task für die Varianzmessung
     - 5 Candidate-Runs pro Task
   - erzeugt stabile Ordnerstruktur

4. **Result-Parser**
   - extrahiert SWE-bench-Testresultate
   - zählt Dateien/Diff-Größe
   - schreibt `run_meta.json`
   - aktualisiert die SQLite-Tabelle `runs`

5. **Judge-Skript**
   - nimmt Prompt + Diff + Testresultat
   - ruft ein separates Judge-Modell mit fixem Prompt auf
   - schreibt JSON mit Rubric-Scores
   - aktualisiert `runs.judge_score`

6. **Summary-Skript**
   - liest `results/experiment.db`
   - aggregiert Ergebnisse pro Task und pro Condition
   - berechnet Mittelwerte und Streuung
   - erstellt `results/summary/variance_report.md`
   - erstellt pro Iteration `results/summary/iteration_<n>.md`
   - schreibt in `iteration_<n>.md` ein Verdict nach §14

---

## 15.2 Runner-Dateien

| Skript | Aufgabe |
|---|---|
| `runner/run_once.py` | Single-Run: Setup, Aider, SWE-bench-Eval, Artefakte, SQLite-Insert |
| `runner/calibrate.py` | Kalibration: Kandidaten laufen lassen, diskriminative Tasks auswählen |
| `runner/run_matrix.py` | Haupt-Experiment: Task x Run x Condition ausführen |
| `runner/judge.py` | Judge-Ergebnisse schreiben und `runs.judge_score` aktualisieren |
| `runner/summarize.py` | SQLite lesen und Markdown-Reports erzeugen |

---

## 15.3 Muss nicht gebaut werden

- UI
- Dashboard
- Live-Telemetrie
- Agent-Optimizer
- automatische Regelmutation
- Cross-Harness-Support
- Team-/Multi-User-System

---

## 16. Technische Anforderungen

### Reproduzierbarkeit
- jeder Run in frischem Arbeitsverzeichnis
- sauberer Git-Status vor Start
- identische SWE-bench-Instanz pro Task
- identischer `base_commit` pro Task

### Isolation
- keine Wiederverwendung desselben Worktree-States
- keine Run-übergreifende Persistenz

### Determinismus so weit wie möglich
- identisches Modell
- identische CLI-Flags
- identischer Prompt
- identische Instruktionsdatei pro Condition
- identische Testumgebung

### Logging
- vollständige Rohlogs aufheben
- keine Zusammenfassung ohne Rohdaten

---

## 17. Empfohlene Task-Spezifikation

Für jede finale Task:

```json
{
  "task_id": "django__django-12345",
  "source": "princeton-nlp/SWE-bench_Lite",
  "task_class": "python_bugfix",
  "repo": "django/django",
  "base_commit": "...",
  "problem_statement": "...",
  "success_criterion": "all FAIL_TO_PASS and PASS_TO_PASS tests pass",
  "repo_constraints": {
    "max_files_expected": 4,
    "network_access_required": false
  }
}
```

---

## 18. Empfohlene Judge-Spezifikation

Der Judge soll **nicht** fragen „ist das brilliant?“
Sondern nur:
- ist die Änderung minimal?
- ist sie scope-treu?
- ist der Diff verständlich?

Der Judge läuft in zwei Stufen:
1. Rubrik-Scores und `judge_score`
2. kurze Konklusion mit klarer Tendenz

### Judge-Output

```json
{
  "prompt_version": "two_stage_v1",
  "scope_adherence": 4,
  "minimality": 5,
  "diff_clarity": 4,
  "judge_score": 4.33,
  "rationale": "...",
  "verdict": "support",
  "conclusion": "..."
}
```

---

## 19. Erfolgskriterien des gesamten Experiments

Das Experiment gilt als **gelungen**, wenn nach der Baseline-Phase mindestens eine dieser Aussagen belastbar beantwortet werden kann:

1. Die natürliche Varianz ist klein genug, um Markdown-Änderungen überhaupt zu messen.
2. Eine konkrete Regeländerung verbessert harte Resultate auf der kleinen Task-Klasse.
3. Die Methode ist in dieser Form zu noisy und sollte verworfen oder umgebaut werden.

Wichtig:
Auch **„die Methode bricht“** ist ein valides Ergebnis.

---

## 20. Nicht-Ziele

Dieses Experiment soll **nicht** beweisen:
- welches Modell generell am besten ist
- welches Harness generell am besten ist
- dass LLM-as-a-judge „objektiv“ ist
- dass Markdown-Optimierung schon self-improving agents liefert
- dass die Methode auf große reale Codebasen skaliert

Es soll nur beweisen oder falsifizieren:

> Kann man in einem minimalen Setup den Effekt kleiner Instruktionsänderungen an einem Coding-Harness belastbar messen?

---

## 21. Konkrete Startreihenfolge

### Tag 1
- `docker run hello-world` auf dem Host ausführen
- Aider x MiniMax in einem Throwaway-Repo testen:
  `aider --model <minimax-spec> --message "echo test"`
- falls Aider MiniMax nicht nativ unterstützt: OpenAI-kompatiblen MiniMax-Endpoint
  über LiteLLM (`openai/<model>` plus `MINIMAX_BASE_URL`) testen
- falls auch das scheitert: erst `MiniMax-M2.7` als Standardvariante prüfen,
  bevor Runner-Code gebaut wird
- Aider lokal lauffähig machen
- SWE-bench-Lite-Dataset laden
- SWE-bench-Evaluation-Backend und Docker prüfen
- `run_once.py` bauen
- 6-10 Kandidaten-Tasks vorfiltern
- `calibrate.py` bauen und Kalibrationsläufe fahren
- 3 finale Tasks fixieren

### Tag 2
- `run_matrix.py` bauen
- 15 Baseline-Runs fahren
- `variance_report.md` erzeugen
- Baseline-Varianz auswerten

### Tag 3
- erste manuelle Mutation definieren
- 15 Candidate-Runs fahren
- `iteration_1.md` erzeugen
- Baseline vs Candidate laut §14 vergleichen

### Danach
Nur wenn das Signal brauchbar ist:
- zweite Mutation
- dritte Mutation
- erst dann über automatische Mutationserzeugung nachdenken

---

## 22. Eine klare Arbeitsregel für den Coder

Wenn während der Implementierung ein Feature dazukommt, das nicht direkt nötig ist, um

- Runs reproduzierbar auszuführen,
- Tests auszuwerten,
- Diffs zu speichern,
- und Baseline vs Candidate zu vergleichen,

wird es **nicht** gebaut.

Das Ziel ist nicht eine Plattform.
Das Ziel ist ein **Messritus**.
