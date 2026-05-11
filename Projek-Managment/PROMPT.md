# PROMPT

## Ziel
Dieses Projekt soll kein allgemeines Agenten-Produkt und keine breite Benchmark-Plattform werden. Sein Kernziel ist ein kleines, reproduzierbares Experimentier-Rig zur Frage, ob kleine Änderungen an einer minimalen `CONVENTIONS.md` / Harness-Policy in einem kontrollierten Coding-Harness messbares Agentenverhalten verändern. Der wissenschaftliche Wert liegt in enger Scope-Sprache: gleicher Harness, gleiches Modell, gleiche Task-Auswahl, harte Metriken zuerst, Judge nur sekundär. Lokale Artefakte zeigen, dass Runner, Conditions, Result-Schema, A/B-Auswertung, Modellvergleich und eine unterstützende UI bereits weit ausgebaut sind. Gleichzeitig zeigen die vorhandenen Summary-Reports, dass die sichtbaren Kernvergleiche noch nicht belastbar entscheidbar sind, weil viele Runs `zero_tests`/Infra-Probleme oder keine gemeinsamen validen Task-Zellen haben. Samuels aktuelle Anweisung für diesen Lauf ist nicht Umsetzung, sondern Projektstand verstehen, menschlichen Nutzen klären und den kleinsten sinnvollen NEXT_STEP formulieren. Daraus folgt: Der nächste sinnvolle Schritt sollte keine teuren Runs starten, sondern klären, welche eine Evidenzlücke den größten Nutzen für die Kernhypothese hat.

## Nicht-Ziel
- Keine teuren Experimente, keine Netzwerk-/Model-Runs, keine Docker-/Aider-Läufe in diesem HAI-Ladevorgang.
- Keine Git-Aktionen und kein Umgang mit Secrets.
- Kein Ausbau von Dashboard, Präsentation, GitHub Pages oder allgemeiner Plattformfunktion als Default.

## Akzeptanzkriterien
- Der Projektkern ist als fokussiertes Hypothesentest-Rig erkennbar dokumentiert.
- Der aktuelle Evidenzstand unterscheidet klar zwischen vorhandener Infrastruktur und noch nicht belastbarer wissenschaftlicher Aussage.
- Der nächste Schritt ist atomar, billig, scope-treu und ohne externe Nebenwirkungen entscheidbar.
- Präsentations-/UI-/Plattformdrift bleibt geparkt, solange sie die Kernhypothese nicht direkt beantwortet.

## Todo
- Bestehende Result- und Summary-Artefakte weiter nur read-only als Evidenzlage nutzen.
- Eine einzige nächste Entscheidung formulieren: welche minimale, nicht-teure Klärung macht die nächste teure Messung später überhaupt sinnvoll?
- Erst nach Samuels Entscheidung ggf. einen separaten Execution- oder Verification-Step erzeugen.

## Offene Frage
Soll der nächste aktive Projektmodus auf methodische Readiness der nächsten Messung gehen, oder soll das Projekt vorerst als explorativer/prototypischer Stand geparkt werden?

## Completion/Lifecycle
ACTIVE_BUILD / VERIFY_FIRST: Die Harness-Infrastruktur ist sichtbar weit gebaut, aber das ursprüngliche Erkenntnisziel ist nach den vorhandenen Validity Gates noch nicht erreicht; sinnvoll ist zuerst eine kleine Readiness-/Design-Entscheidung, nicht mehr UI oder sofort neue teure Runs.

## Quellen
- Aktuelle Samuel-Anweisung: schwerer HAI-Generalization-Test, keine teuren Experimente, keine Git-/Netz-/Secret-Aktionen, Projektstand und NEXT_STEP klären.
- `README.md`, `pyproject.toml`, `experiment_README.md`, `Versuchsaufbau.md`, `docs/scientific_evaluation_protocol.md`, `docs/statistically_rigorous_plan.md`.
- `Projek-Managment/PROJECT_SCOPE.md`, `Projek-Managment/NEXT_STEP.md`, `Projek-Managment/Wishlist/USER_WISHLIST_2026-05-10_1745.md`.
- `Projek-Managment/Wishlist/PROMPTGARAGE_INTENT.md`.
- `results/summary/scientific_ab_iteration_1_baseline_6line_vs_negative_control_karpathy40.md`, `results/summary/model_ab_iteration_1_openai_MiniMax-M2.7_vs_openai_gpt-5.5.md`, `results/summary/variance_report.md`.
