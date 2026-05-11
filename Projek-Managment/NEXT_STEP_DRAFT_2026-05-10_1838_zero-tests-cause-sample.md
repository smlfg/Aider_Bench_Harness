Step type: VERIFICATION_STEP
Step ID: NEXT_STEP_2026-05-10_1838_zero-tests-cause-sample
Lifecycle mode: VERIFY_FIRST

Problem:
Die Blocker-Inventur zeigt `zero_tests` als dominanten Evidenzkiller: 80 von 102 Runs haben `tests_total <= 0`, während nur 19 Runs harte valide Testmetriken haben. Für den Kernvergleich `baseline_6line` vs `negative_control_karpathy40` sind 20 von 21 relevanten Runs zero-tests; dadurch gibt es keine gemeinsamen validen Task-Zellen. Bevor ein Gate oder neue Runs sinnvoll sind, muss klar sein, warum vorhandene Runs keine Testmetriken liefern.

Why now:
Das ist die kleinste konkrete Folge aus der akzeptierten Blocker-Inventur. Es bleibt read-only, nutzt vorhandene Artefakte und verhindert, dass wir abstrakte Methodik oder neue Runs planen, bevor die Messpipeline-Ursache bekannt ist.

Smallest next step:
Prüfe an 2-3 vorhandenen zero-test-Run-Artefakten read-only, ob `tests_total=0` durch fehlende Eval-Reports, SWE-bench-Testmapping, Docker/Eval-Ausführung, Agent-Patch-Ausbleiben oder Result-Parsing entsteht.

Scope:
Nur lokale Artefakte einzelner bestehender zero-test-Runs aus `results/`, bevorzugt aus `baseline_6line` und `negative_control_karpathy40`.

Allowed Changes:
- read-only Lesen von 2-3 vorhandenen Run-Artefaktordnern
- read-only Lesen der zugehörigen DB-Zeilen aus `results/experiment.db`
- Schreiben eines HAI-Berichts `Projek-Managment/VERIFICATION_REPORT_ZERO_TESTS_CAUSE.md`

Forbidden Changes:
- keine Source-Code-Änderungen
- keine Experimente, Docker-, Aider-, Netzwerk- oder Model-Runs
- kein Lesen oder Ändern von Secrets, `.env` oder Credential-Dateien
- keine Git-Aktionen, kein Commit, kein Push
- kein HAI-Execution-Loop

Recommended default:
A) Read-only zero-tests-Ursache an wenigen Beispielruns prüfen. Das ist besser als ein Gate, weil es den realen Messblocker direkt adressiert, aber noch billiger und sicherer ist als ein Fix oder neuer Run.

Decision options:
- A) Read-only zero-tests-Ursache an 2-3 Beispielruns prüfen (recommended)
- B) Stattdessen direkt einen Fix-Step planen
- C) Projekt parken

Definition of Done:
- 2-3 konkrete zero-test-Runs sind mit Pfad und Befund benannt.
- Der wahrscheinlichste Ursachenbereich ist eingegrenzt: fehlender Eval-Report, Testmapping, Docker/Eval, Agent-Patch oder Parser.
- Es gibt genau eine Folgeempfehlung: Fix, weiterer Read-only-Check, Gate oder Parken.

Verification:
Datei-/DB-Inspektion vorhandener lokaler Run-Artefakte; keine neuen Prozesse außer kurzen read-only Shell-/Python-Abfragen.

Not included:
- Codefix
- neuer Run
- Gate-Design
- Pre-Registration
- UI/Präsentation

Decision for Samuel:
Soll ich A machen: read-only die zero-tests-Ursache an 2-3 vorhandenen Beispielruns eingrenzen?
