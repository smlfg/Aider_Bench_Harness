# CODE_STATE

## Sprachen/Stack
Python 3.12, uv/Hatch, Aider, SWE-bench, SQLite, FastAPI/Uvicorn/SSE, Pydantic, scipy; zusätzlich React/Vite/TypeScript im `web/frontend` für ein lokales Dashboard.

## Hauptartefakte
- `runner/`: Kernlogik für Preflight, Task-Fetching, Single-Run, Matrix-Run, Calibration, Judge, Metrics, DB, Summary, Scientific A/B und Model A/B.
- `harness/`: viele `CONVENTIONS*.md`-Condition-Dateien, u.a. Baseline, negative control und Regelkombinationen.
- `data/`: Task- und Experiment-Konfigurationen.
- `results/`: SQLite DB, Run-Artefakte und Summary-Reports; read-only inspiziert.
- `docs/`, `Versuchsaufbau.md`, `Visualisierung.md`, `UX-Cockpit.md`: methodische und UI/Live-Cockpit-Spezifikationen.
- `web/server.py` und `web/frontend`: lokale FastAPI/React-Oberfläche.

## Einstiegspunkte
`pyproject.toml` definiert u.a. `harness-preflight`, `harness-fetch-candidates`, `harness-run-once`, `harness-calibrate`, `harness-run-matrix`, `harness-judge`, `harness-summarize`, `harness-analyze`, `harness-fail-fast`, `harness-science-ab`, `harness-model-ab`, `harness-serve` und `harness-ui`.

## Modularitaet
Die Codebase ist als Experimentier-Rig mit klaren Schichten aufgebaut: Task-/Config-Laden, Run-Ausführung, Artefakt-/DB-Erfassung, Metriken/Judge, wissenschaftliche Auswertung und UI. `runner/run_once.py` ist groß und prozessnah; es orchestriert Repo-Setup, Agent-/Eval-Ausführung, Logs, DB und Status. `runner/scientific_ab.py` und `runner/model_ab.py` kapseln spätere Auswertungslogik und trennen Policy- von Modellvergleichen. `web/server.py` ist ebenfalls groß und verbindet DB-Abfragen, Run-Launch, SSE/Monitoring und statische Auslieferung. Das Dashboard ist sichtbar umgesetzt (`web/frontend/src/...`, `dist/`), obwohl `PROJECT_SCOPE.md` UI nur als unterstützend und nicht als Primärscope einordnet. `node_modules` und gebaute Frontend-Artefakte liegen im Projektbaum und können Code-State-Suchen stark verrauschen. Die Architektur wirkt praktisch nutzbar, aber nicht klein: das Risiko liegt weniger bei fehlenden Dateien als bei Scope-/Evidence-Drift zwischen wissenschaftlicher Kernfrage, Live-Cockpit und Präsentationsflächen.

## Build/Test-Signale
- Keine Tests, Builds, Docker-, Aider-, Netzwerk- oder Model-Runs wurden in diesem HAI-Lauf gestartet.
- README dokumentiert `uv run harness-run-once ... --skip-agent --skip-eval ...` als Smoke-Test und `uv run harness-science-ab` / `harness-model-ab` für Auswertung.
- Read-only SQLite-Query auf `results/experiment.db` fand Tabellen `analysis`, `calibration_runs`, `comparisons`, `conventions`, `run_registry`, `runs`, `trajectory`.
- Sichtbare Reports: baseline_6line vs negative_control_karpathy40 ist `not_decisive` mit `valid_baseline=1`, `valid_candidate=0`, `common valid tasks=0`; MiniMax-vs-GPT-5.5 ist ebenfalls `not_testable` wegen fehlender valider gemeinsamer Zellen.

## Code-Risiken
- Viele gespeicherte Runs sind für harte Evidenz ausgeschlossen (`zero_tests`, `infrastructure_error` oder keine gemeinsamen Zellen); die Infrastruktur kann also Daten produzieren, ohne die Kernhypothese zu beantworten.
- UI/Live-Cockpit/Präsentationsartefakte sind deutlich gewachsen und können vom Primärscope ablenken, wenn kein klares Gate davorsteht.
- `web/server.py` und `runner/run_once.py` sind groß; künftige Änderungen sollten eng begrenzt werden, damit keine neue Orchestrierungs-/DB-/UI-Kopplung entsteht.
- `web/frontend/node_modules` und `dist` liegen lokal im Repo-Baum; für Such-/Analysewerkzeuge muss weiter bewusst gepruned werden.
- Ohne Git-Status ist unklar, welche dieser Dateien versioniert, unversioniert oder generiert sind; das wurde wegen Samuels No-Git-Vorgabe nicht geprüft.
