# Visualisierung.md — Auswertung & Web-UI für das Eval-Experiment

**Zielgruppe:** Codex 5.4 als Implementierungs-Guide für Schritt 2 (Web-UI + Statistik-Skripte). Nach Fertigstellung des Runners aus `Versuchsaufbau.md` + `stateful-swinging-kernighan.md`.

**Kontext:** Samuel hat das Experiment durchgeführt und steht vor der SQLite-DB mit N×{baseline, candidate}-Runs über mehrere Iterationen. Er will den Output visuell und statistisch belastbar auswerten — nicht nur Rohzahlen lesen.

---

## 1. Kernfrage, die die Auswertung beantworten muss

Nicht: „War Iteration N besser als N−1?"
Sondern: **„Hat sich `task_success` signifikant verändert, und zu welchem Preis (Diff-Größe, Zeit, Judge)?"**

Samuels eigenes Beispiel macht den Kern klar:

| Iteration | Regeln in .md | task_success | diff_size (LOC) | Interpretation |
|---|---|---|---|---|
| 0 | — | 0/15 | 10 | Kaputt, kein Fix |
| 1 | +Think Before Coding | 10/15 | 234 | Richtig, aber bloated |
| 2 | +Simplicity First | 3/15 | 60 | AI-Slop (weniger Bloat, aber kaputte Logik) |
| 3 | +Surgical Changes | 12/15 | 28 | Pareto-Verbesserung |

Eine einzelne Metrik (`task_success`) würde Iteration 1 und 3 gleichwertig erscheinen lassen. Das ist falsch. Auswertung muss **multidimensional** sein: Erfolg + Kosten + Qualität.

---

## 2. Statistische Auswertung — `runner/analyze.py`

Läuft nach `summarize.py`. Liest `runs`-Tabelle, schreibt zwei neue SQLite-Tabellen.

### 2.1 Pro-Condition-Aggregate → Tabelle `analysis`

Für jede `(iteration, condition, metric)`-Kombination:

```
iteration, condition, metric, n, point_estimate, ci_low, ci_high, method
```

Metriken und Verfahren:

| Metrik | Typ | CI-Verfahren |
|---|---|---|
| `task_success` | Binär | **Wilson-Score-Interval** (stabil bei kleinem n, auch bei 0/n oder n/n) |
| `tests_pass_rate` | Proportion [0,1] pro Run, Mittelwert über Runs | **Bootstrap-CI**, 10 000 Resamples |
| `diff_size` (LOC hinzu+weg) | Integer | **Bootstrap-CI** |
| `duration_seconds` | Float | **Bootstrap-CI** |
| `judge_score` | Ordinal 1–5 | **Bootstrap-CI** auf Median |

### 2.2 Baseline-vs-Candidate-Vergleich → Tabelle `comparisons`

Pro Iteration und Metrik ein Zeileneintrag:

```
iteration, metric, baseline_estimate, candidate_estimate, delta, test_name, p_value, effect_size
```

| Metrik | Test | Warum |
|---|---|---|
| `task_success` | **Fisher's Exact** | Binäre Daten, kleines n (15 vs 15) |
| `tests_pass_rate` | **Mann-Whitney U** | Nicht-normal, ordinal-robust |
| `judge_score` | **Mann-Whitney U** | Ordinal |
| `diff_size` | **Mann-Whitney U** | Skewed, Ausreißer |

Effect-Size: **Cliff's Delta** für ordinale Vergleiche (robuster als Cohen's d bei n=15).

**Wichtig:** Kein multiple-testing-correction über Iterationen — das ist explorativ, nicht konfirmatorisch. Samuel dokumentiert das als Limitation.

### 2.3 Warum n=15 pro Condition

Claude.ai's Input war korrekt: n=3 liefert Wilson-CIs, die praktisch die gesamte [0,1]-Skala abdecken. n=15 ist der Kompromiss:

| Beobachtung | Wilson 95%-CI |
|---|---|
| 3/3 | [44%, 100%] |
| 5/5 | [57%, 100%] |
| 10/15 | [42%, 85%] |
| 12/15 | [57%, 93%] |
| 15/15 | [80%, 100%] |

n=15 lässt Unterschiede von ~30 Prozentpunkten erkennen — das reicht für „große" Mutationseffekte, nicht für Feinabstimmung.

**Kalibrationsphase bleibt bei n=3** (nur grobe Vorauswahl). Haupt-Experiment: **3 finale Tasks × 5 Runs = 15 pro Condition**.

### 2.4 Trajektorie-Auswertung über Iterationen

Zusätzliche Tabelle `trajectory` (eine Zeile pro Iteration):

```
iteration, conventions_hash, mutation_note, parent_hash,
  cumulative_success_rate, cumulative_diff_size_mean,
  pareto_dominated  -- 1 wenn schlechter in success UND diff_size vs best prior
```

`pareto_dominated=1` markiert Iteration 2 aus Samuels Beispiel automatisch (AI-Slop).

---

## 3. Web-UI — Architektur

**Entscheidung:** Kein Backend-Server. Statisches HTML + SQLite-im-Browser. Grund: zero-ops, Samuel öffnet einfach `index.html` lokal.

### 3.1 Stack-Optionen

**Option A — Datasette (Empfehlung für Schritt 2a, sofort nutzbar):**
```bash
pip install datasette datasette-vega
datasette results/experiment.db --open
```
Fertig. Automatische SQL-Browser-UI, Plots via Vega, Filter, Search. Samuel kann ab Tag 3 Ergebnisse im Browser sichten, ohne dass Custom-Code geschrieben wurde.

**Option B — Custom-Dashboard (Schritt 2b, wenn Datasette nicht reicht):**
- **Build:** Vite + React + TypeScript
- **DB-Zugriff:** `sql.js` (SQLite via WASM), DB-File wird als `fetch()` geladen
- **Charts:** `Observable Plot` (dichter als Recharts, weniger verbose als D3)
- **Diff-Viewer:** `monaco-editor` oder `react-diff-viewer`
- **Deployment:** statische Files in `web/dist/`, öffnen via `python -m http.server 8000`

Codex soll **zuerst A** umsetzen (1 Befehl), dann bei Bedarf B bauen.

### 3.2 Views — Custom Dashboard (Option B)

**View 1: `/iteration/:n` — Iteration-Vergleich (Hauptscreen)**

Layout: zwei Spalten Baseline | Candidate, oben ein Verdict-Banner.

Elemente:
- **Verdict-Badge:** `CANDIDATE WINS ✓` / `NO DECISION` / `CANDIDATE LOSES ✗` (aus §14-Regeln)
- **Success-Bar-Chart:** pro Task (3 Task-IDs) zwei Balken nebeneinander, Fehlerbalken = Wilson-CI
- **Tests-Pass-Rate-Boxplot:** je Condition 15 Datenpunkte, Median + IQR + Outlier
- **Diff-Size-Boxplot:** dto, zeigt Bloat-Risiko
- **Judge-Radar-Chart:** 3 Achsen (scope_adherence, minimality, diff_clarity), 2 Polygone überlagert
- **Stats-Tabelle:** pro Metrik {baseline, candidate, Δ, p-value, Cliff's δ}

**View 2: `/trajectory` — Lernkurve über Iterationen**

Zwei verknüpfte Line-Charts untereinander, gleiche x-Achse (Iteration 0…N):
- oben: `mean task_success` pro Iteration, Condition als Farbe
- unten: `mean diff_size` pro Iteration

Hover auf Punkt: Tooltip mit `mutation_note` + `conventions_hash[:8]` + Δ zur Vorgänger-Iteration.

Zusätzlich: **Pareto-Frontier-Scatterplot** (x = mean diff_size, y = mean task_success). Jede Iteration ein Punkt. Dominierte Punkte grau, Frontier rot verbunden. Samuels Iteration 2 (AI-Slop) fällt hier sofort auf.

**View 3: `/runs` — Run-Explorer**

Filterbare Tabelle aller Einzelruns:
- Spalten: `run_id`, `iteration`, `condition`, `task_id`, `success`, `tests_pass_rate`, `diff_size`, `duration`, `judge_score`
- Filter: Condition, Iteration, Task, Success-only
- Klick auf Zeile → Detail-Pane:
  - Links: Monaco-Diff-Viewer mit `git_diff.patch`
  - Rechts oben: `agent_stdout.log` (collapsible)
  - Rechts unten: Judge-Rationale + Rubric-Scores
  - Footer: Link zur `CONVENTIONS.md`-Version, die in diesem Run verwendet wurde

---

## 4. Wer wertet aus — Mensch vs. Skript

| Schritt | Automatisch | Mensch |
|---|---|---|
| Statistik rechnen | `analyze.py` | — |
| Plots rendern | Web-UI | — |
| Verdict laut §14-Regel | `summarize.py` (deterministisch) | — |
| **Interpretation:** „Ist diese Regel erhaltenswert?" | — | **Samuel** |
| Nächste Mutation wählen | — | **Samuel** (manuell, §7.3) |
| Abbruch-Entscheidung §12 | — | **Samuel** nach Sichtung Variance-Report |

Die Web-UI ist ein **Werkzeug zur menschlichen Urteilsbildung**, keine Autopilot-Auswertung.

---

## 5. Anti-AI-Slop-Regel (aus Samuels Beispiel)

Einbauen als harte Warnung in View 1:

> „⚠️ PARETO-WARNUNG: Candidate hat `diff_size` +X% bei `task_success` Δ ≤ 0. Nicht übernehmen."

Schwelle: wenn `delta_diff_size > 50%` UND `delta_task_success ≤ 0`.

Zusätzlich Composite-Score in `comparisons`-Tabelle:
```
composite = task_success_rate * exp(-diff_size / baseline_diff_size)
```
Straft Bloat exponentiell. Nicht als primäre Entscheidung, nur als Sanity-Check-Spalte.

---

## 6. Konkrete Dateistruktur für Codex

```
runner/
  analyze.py           # Schritt 1: SQLite → analysis + comparisons + trajectory Tabellen
  summarize.py         # (bereits geplant) → iteration_<n>.md + Verdict

web/
  serve-datasette.sh   # Option A: datasette results/experiment.db --open
  dashboard/           # Option B (später):
    index.html
    src/
      App.tsx
      views/
        IterationView.tsx
        TrajectoryView.tsx
        RunExplorer.tsx
      lib/
        db.ts          # sql.js loader
        stats.ts       # Wilson-CI, Bootstrap, Cliff's Delta
        charts.ts      # Observable Plot helpers
    vite.config.ts
    package.json
```

---

## 7. Verifikation

1. **`analyze.py` Smoke-Test:** Nach Iteration 1 existieren Tabellen `analysis`, `comparisons`, `trajectory`. `SELECT * FROM comparisons WHERE iteration=1` zeigt 4 Zeilen (4 Metriken) mit p-values.
2. **Datasette-Check:** `datasette results/experiment.db` öffnet localhost:8001, zeigt alle Tabellen, CSV-Export funktioniert.
3. **Dashboard-Smoke:** Mit Dummy-Daten (3 Iterationen, je 15+15 Runs) rendern alle 3 Views ohne Fehler, Pareto-Warnung erscheint bei künstlich eingebauter AI-Slop-Iteration.
4. **Statistik-Sanity:** Bei identischer Baseline vs. Candidate (beide 10/15) muss Fisher-p-value ≥ 0.5 sein und Verdict = `NO DECISION`. Bei 15/15 vs 0/15 muss p < 0.001 sein.
5. **Samuel-Handtest:** Nach Iteration 1 Browser öffnen, View 1 aufrufen, kann innerhalb 30 Sekunden Verdict + Δ-Metriken ablesen, ohne SQL zu schreiben.

---

## 8. Was nicht gebaut wird (Scope-Lock)

- Kein Login, keine Multi-User-Unterstützung
- Keine Live-Updates während laufender Runs (nur Post-hoc-Analyse)
- Keine Auto-Mutation-Vorschläge (bleibt manuell laut §7.3)
- Keine Cloud-Hosting, kein CI-Deploy
- Keine Vergleiche über Modellwechsel (ist in §4.1 Konstanzregel verboten)
- Kein A/B-Test-Framework-Ersatz (z. B. kein Optimizely-Clone)

Ziel ist ein **Sichtfenster auf die SQLite**, nicht eine Analytics-Plattform.
