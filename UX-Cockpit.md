# UX-Cockpit.md — Live-Steuerung & Observability

**Zielgruppe:** OpenCode (4. Agent, baut gerade an der Website aus `Visualisierung.md`). Diese Datei **ergänzt** `Visualisierung.md`, ersetzt sie nicht.

**Warum separat:** `Visualisierung.md` beschreibt Post-hoc-Analyse (abgeschlossene Runs auswerten). Dieses Dokument beschreibt die **Live-Schicht**: Runs starten, zuschauen, verstehen, was passiert — während es passiert.

---

## 1. Samuels Problem in einem Satz

> „Wenn Aider 10 Minuten läuft, sehe ich nichts. Wenn etwas schiefgeht (wie der LiteLLM-Provider-Bug heute), merke ich es erst, wenn ich Post-hoc die Logs lese. Ich will ein Cockpit — ein Input-Feld und ein Schau-Feld."

Die drei Fragen, die das Cockpit jederzeit beantworten muss:
1. **Was ist der Task?** (problem_statement, FAIL_TO_PASS-Tests, Repo)
2. **Was macht der Agent gerade?** (Aider-Steps live, Patch im Entstehen, Token-Verbrauch)
3. **Was ist am Ende rausgekommen?** (Verdict, Diff, Test-Resultat, Dauer, Kosten)

---

## 2. Architektur-Shift gegenüber `Visualisierung.md`

`Visualisierung.md` geht von **statischem HTML + `sql.js`** aus. Für Live-Cockpit reicht das nicht, weil:
- Runs müssen **gestartet** werden (POST)
- `agent_stdout.log` muss **gestreamt** werden, während Aider schreibt
- `git_diff.patch` muss **live** aktualisiert werden

Deshalb: **schlanker FastAPI-Backend-Server** ergänzt das Static-Frontend. Kein Production-Stack, kein Docker, keine Auth — lokal only, ein User (Samuel), ein Prozess.

Stack:
- **Backend:** FastAPI + Uvicorn, Port 8000
- **Frontend:** gleicher Vite/React-Stack wie in Visualisierung.md; spricht Backend via `fetch` + Server-Sent-Events
- **Run-Orchestrierung:** Backend spawnt `uv run harness-run-once ...` als `subprocess.Popen`, streamt dessen stdout

---

## 3. Backend-Endpoints

Alle Endpoints lokal, keine Auth.

| Methode | Pfad | Zweck |
|---|---|---|
| `GET` | `/tasks` | Liste aus `data/swebench_lite_candidates.json` — für Task-Picker |
| `GET` | `/tasks/{task_id}` | Einzel-Task inkl. `problem_statement`, `FAIL_TO_PASS`, `PASS_TO_PASS`, `base_commit` |
| `GET` | `/conventions` | Liste aller `harness/CONVENTIONS*.md` + Hashes + `mutation_note` |
| `GET` | `/runs` | SQLite-Query: alle bisherigen Runs, filterbar nach condition/iteration/task |
| `GET` | `/runs/{run_id}` | Einzelrun-Details (run_meta.json + tests.json + Pfade zu Artefakten) |
| `POST` | `/runs` | **Startet neuen Run.** Body: `{task_id, condition, iteration, run_index, conventions_path}`. Returniert `{run_id, status: "starting"}`. |
| `GET` | `/runs/{run_id}/stream` | **Server-Sent-Events** für Live-Updates (siehe §4) |
| `GET` | `/runs/{run_id}/patch` | Aktueller Inhalt von `git_diff.patch` (auch während Aider noch läuft) |
| `POST` | `/runs/{run_id}/abort` | Schickt SIGTERM an den Subprocess. Nicht-graceful erlaubt. |

**Harte Regel:** Nur **ein Run gleichzeitig**. `POST /runs` während ein Run läuft → 409 Conflict. Grund: Docker-Eval und Aider-Workdirs würden kollidieren. Sichtbar im UI als „Run blockiert — läuft bereits `<run_id>`".

---

## 4. Server-Sent-Events auf `/runs/{run_id}/stream`

Events, die das Frontend abonniert:

```
event: phase
data: {"phase": "setup_repo" | "aider_running" | "docker_eval" | "done"}

event: log
data: {"source": "aider" | "eval", "line": "Aider v0.86.2 ..."}

event: patch_changed
data: {"files_changed": 1, "lines_added": 4, "lines_removed": 2}

event: tokens
data: {"tokens_in": 1230, "tokens_out": 450, "cost_estimate": 0.008}

event: done
data: {"exit_code": 0, "task_success": false, "tests_passed": 21, "tests_total": 22, "infrastructure_error": false}
```

Implementierung: Backend hält File-Tail auf `agent_stdout.log` + `eval_stdout.log`, pollt `git_diff.patch`-Mtime alle 2 s, parst Token-Angaben aus Aider-Output (regex auf Aider-Zeilen wie `Tokens: 1.2k sent, 450 received`).

---

## 5. Frontend-Views

Drei neue Views ergänzen die drei Views aus `Visualisierung.md`:

### View 4: `/launch` — Run-Launcher (Samuels „Input-Feld")

Einspaltiges Formular:

| Feld | Typ | Quelle |
|---|---|---|
| Task | Dropdown + Search | `GET /tasks` |
| Task-Preview | Markdown-Anzeige | `GET /tasks/{id}` → `problem_statement` |
| Condition | Dropdown | `baseline`, `candidate_v1`, ... |
| Conventions-File | Dropdown | `GET /conventions` |
| Iteration | Number | Default = letzte + 0 oder +1 |
| Run-Index | Number | Default = letzter Run für diese (task, condition, iteration) + 1 |
| **Button: Start Run** | | → `POST /runs` → redirect auf `/monitor/{run_id}` |

Unter dem Button: Preview-Sektion „Dieser Run wird sein: `baseline_sympy__sympy-20590_run02` mit `CONVENTIONS.baseline.md` (hash `a3f1...`)".

Guardrails:
- Wenn bereits ein Run läuft → Button disabled, roter Banner „Läuft gerade: `<run_id>`" + Link zum Monitor
- Kosten-Hochrechnung angezeigt: „Bisheriger Durchschnitt: 0.08 € pro Run" (aus SQLite)

### View 5: `/monitor/{run_id}` — Run-Monitor (Samuels „Schau-Feld")

Split-Screen, 4 Quadranten:

```
┌─────────────────────────┬──────────────────────────────┐
│ TASK (Q1)               │ AIDER LIVE OUTPUT (Q3)       │
│ - instance_id           │ ─ streaming stdout           │
│ - problem_statement     │ ─ auto-scroll, pause button  │
│ - FAIL_TO_PASS tests    │ ─ token counter oben rechts  │
├─────────────────────────┼──────────────────────────────┤
│ CONVENTIONS (Q2)        │ PATCH VIEW (Q4)              │
│ - Inhalt der aktiven .md│ ─ diff, live-refreshing      │
│ - Hash + mutation_note  │ ─ „Keine Änderungen bisher"  │
└─────────────────────────┴──────────────────────────────┘
```

Oben drüber: **Status-Bar** mit:
- Aktuelle Phase (`setup_repo` → `aider_running` → `docker_eval` → `done`)
- Progress-Indikator (Dauer, erwartete Rest-Dauer aus Median vergangener Runs)
- Abort-Button

Unten drunter: **Event-Feed** (chronologische Liste der SSE-Events als Zeitleiste)

### View 6: `/debrief/{run_id}` — Run-Debriefing (Samuels „Was ist rausgekommen")

Automatischer Redirect von Monitor, sobald `event: done` empfangen.

Struktur:
1. **Verdict-Banner** (ganz oben, groß):
   - ✅ `TASK SUCCESS` — grün — FAIL_TO_PASS erreicht
   - ⚠️ `TASK FAIL (Agent-Fehler)` — gelb — Aider hat echten Patch versucht, aber Tests rot
   - 🚫 `INFRASTRUCTURE ERROR` — rot — Aider hat nie richtig gearbeitet (wie heute: LiteLLM-Provider-Bug). Dieser Run zählt **nicht** für Statistik.
2. **Was hat der Agent gemacht?** — Step-Zusammenfassung aus Aider-Log:
   - Anzahl Turns, Anzahl Datei-Edits, welche Files
   - Finaler Diff mit Syntax-Highlighting (Monaco)
3. **Test-Resultate:** FAIL_TO_PASS Tabelle (rot/grün pro Test) + PASS_TO_PASS Zähler
4. **Metriken:** Dauer, tokens_in/out, Kosten, files_changed, lines ±
5. **Judge** (falls gelaufen): Rubrics + Rationale
6. **Actions:**
   - „Run wiederholen" (identische Config, +1 run_index)
   - „Als Candidate markieren" (promote Conventions zur neuen Baseline)
   - „Run verwerfen" (Eintrag aus SQLite löschen, Artefakte behalten)

---

## 6. Erkennung von „Infrastructure Error" (heute gelernt)

Der LiteLLM-Fail von heute hat aussehen wie ein normaler Baseline-Fail. Das darf sich nicht wiederholen. Das Cockpit muss ihn erkennen und **klar ausweisen**.

Backend-seitig: Beim `done`-Event läuft ein Klassifikator über `agent_stdout.log` mit diesen Heuristiken:

```python
INFRA_ERROR_PATTERNS = [
    "litellm.BadRequestError",
    "litellm.APIConnectionError",
    "LLM Provider NOT provided",
    "AuthenticationError",
    "authorized_error",
    "login fail",
    "ConnectionError",
    "Timeout connecting to",
    "Docker daemon not running",
    "Could not pull image",
]
```

Wenn eines der Patterns in stdout/stderr → `infrastructure_error=true` in SQLite-Zeile UND Debriefing zeigt rotes Banner. Solche Runs dürfen **nicht** in `analyze.py`-Aggregate einfließen (in `Visualisierung.md` ergänzen: `WHERE infrastructure_error = 0` in allen Stats-Queries).

---

## 7. Nicht-Ziele (Scope-Lock)

- **Kein Multi-User-Login.** Lokal, ein User.
- **Keine parallelen Runs.** Ein Run gleichzeitig. Samuel will verstehen, nicht durchsatzoptimieren.
- **Kein Server-Deployment.** `uv run harness-ui` startet Backend + öffnet Browser.
- **Keine Mutation der `CONVENTIONS.md` im UI.** Bearbeitung bleibt im Editor. UI zeigt nur, wählt aus.
- **Kein Replay von alten Runs im Monitor.** Monitor ist live only. Debriefing ist statisch.

---

## 8. Ein-Befehl-Start

OpenCode soll ein neues Projekt-Script ergänzen:

```
[project.scripts]
harness-ui = "web.api.main:run"
```

`uv run harness-ui` macht:
1. FastAPI-Backend auf :8000 starten
2. Vite-Dev-Server auf :5173 (dev) oder statischen Build serven (prod)
3. Browser auf `http://localhost:5173` öffnen

Samuel tippt einen Befehl, sieht das Cockpit, wählt Task, klickt Start — und sieht Aider live arbeiten.

---

## 9. Verifikation

1. **Launcher:** `uv run harness-ui` öffnet Browser auf `/launch`. Task-Dropdown zeigt 30 SWE-bench-Lite-Kandidaten.
2. **Start:** Task wählen, `baseline`, `CONVENTIONS.baseline.md`, Klick „Start Run" → Redirect auf `/monitor/{run_id}` binnen 1 s.
3. **Live-Stream:** Innerhalb 2 s erscheinen erste Aider-Log-Zeilen in Q3. Token-Counter beginnt zu zählen, sobald erster LLM-Call erfolgt.
4. **Patch-Live:** Sobald Aider eine Datei editiert, zeigt Q4 Diff. Vorher: „Keine Änderungen bisher."
5. **Infra-Error-Erkennung:** Test mit absichtlich kaputtem `.env` (falscher Model-String) → Debriefing zeigt rotes Banner + „Run zählt nicht für Statistik".
6. **Abbruch:** Abort-Button → SIGTERM → Aider-Subprocess endet → `done`-Event mit `aborted: true`.
7. **Konflikt-Schutz:** Zweiter `POST /runs` während Run läuft → HTTP 409 + UI-Banner.

---

## 10. Hinweis für OpenCode

- Dieses Dokument ergänzt `Visualisierung.md`. **Dort nichts löschen.** Post-hoc-Analyse-Views (Iteration-Vergleich, Trajektorie, Run-Explorer) bleiben wie dort beschrieben und zeigen historische Runs aus SQLite.
- **Frontend-Architektur:** Gleicher React-Tree, zusätzliche Routen `/launch`, `/monitor/:id`, `/debrief/:id`.
- **Erste Implementierungs-Reihenfolge:** Backend-Endpoints zuerst (ohne UI via `curl` testbar), dann Launcher (einfachste UI), dann Monitor (am aufwändigsten wegen SSE), dann Debriefing.
- **Das Wichtigste:** Infrastructure-Error-Erkennung aus §6 ist **nicht optional**. Ohne sie wiederholt sich der heutige Bug, und Samuel kann der Statistik nicht trauen.
