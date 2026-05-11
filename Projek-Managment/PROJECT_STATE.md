# PROJECT_STATE

## Projekt
FirstRealHarnessEvaluation_KarpathiesMD ist ein lokales Python/FastAPI/React Experimentier-Rig, das messen soll, ob kleine Markdown-Harness-Policy-Änderungen in einem Aider/SWE-bench-Lite-Setup messbare Coding-Agent-Effekte erzeugen.

## Git-Stand
Nicht abgefragt: Samuel hat für diesen HAI-Generalization-Test ausdrücklich `keine Git-Aktionen` erlaubt. Branch, Status und Commit-Historie bleiben daher absichtlich unberührt/unbekannt.

## Letzte Bewegung
- README beschreibt Setup, Smoke-Test, Real Flow, wissenschaftliche A/B-Reports und Modell-A/B-Reports.
- Lokale Reports zeigen vorhandene Resultate in `results/summary/`, aber zentrale Vergleiche sind laut Validity Gates nicht entscheidend: z.B. baseline_6line vs negative_control_karpathy40 hat `valid_baseline=1`, `valid_candidate=0`, `common valid tasks=0`.
- `Projek-Managment/PROJECT_SCOPE.md` legt fest: Primärscope ist ein fokussiertes Hypothesentest-Rig; Dashboard/Web-UI und Präsentation sind nur unterstützend.

## Lifecycle-Signal
ACTIVE_BUILD / VERIFY_FIRST: Das Repo existiert und enthält Runner, Reports und UI, aber die eigentliche wissenschaftliche Kernaussage ist noch nicht belastbar; sichtbare Reports markieren harte Evidenz als `not_decisive`/`not_testable` statt abgeschlossen.

## Offene Signale
- Kein Standard-`IDEA` gefunden; intent-ähnliche Quellen sind `Versuchsaufbau.md`, `experiment_README.md`, `docs/scientific_evaluation_protocol.md`, `docs/statistically_rigorous_plan.md`, `UX-Cockpit.md`, `Visualisierung.md`, `PROJECT_SCOPE.md` und `Wishlist/USER_WISHLIST_2026-05-10_1745.md`.
- Ergebnisse und Datenbank sind lokal vorhanden; diese HAI-Runde hat nur read-only DB-Zusammenfassungen gelesen und keine Experimente/Modelle/Netzwerk/Git gestartet.
- Secrets wurden nicht geöffnet; `.env` oder credential-nahe Dateien wurden nicht gelesen.
