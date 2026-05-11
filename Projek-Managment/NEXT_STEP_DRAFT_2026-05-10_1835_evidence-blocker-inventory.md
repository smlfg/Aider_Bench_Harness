Step type: VERIFICATION_STEP
Step ID: NEXT_STEP_2026-05-10_1835_evidence-blocker-inventory
Lifecycle mode: VERIFY_FIRST

Problem:
Das vorgeschlagene `Gate` ist wahrscheinlich noch eine Ebene zu abstrakt. Bevor Samuel entscheiden kann, welches Gate sinnvoll ist, muss klarer sein, welcher konkrete Blocker die vorhandenen Messungen unbrauchbar macht: zero-tests, Infra-Errors, fehlende Task-Paarung, Modell-/Policy-Mismatch oder etwas anderes. Sonst bauen wir ein Gate aus Prinzip, nicht aus Evidenz.

Why now:
Samuel hat zu Recht gefragt, ob ein Gate wirklich der kleinste wichtigste Schritt ist. Die billigere und kleinere Vorstufe ist eine read-only Blocker-Inventur aus den vorhandenen Reports/SQLite-Daten, ohne neue Runs, ohne Git und ohne Secrets.

Smallest next step:
Prüfe read-only, welcher eine Blocker-Typ die vorhandene Evidenz am stärksten daran hindert, die Kernhypothese zu beantworten.

Scope:
Nur bestehende lokale Reports und `results/experiment.db` read-only zur Evidenz-Blocker-Klassifikation.

Allowed Changes:
- read-only Lesen von `results/summary/*.md` und `results/experiment.db`
- optional Schreiben eines HAI-Berichts `Projek-Managment/VERIFICATION_REPORT_NEXT_STEP.md`

Forbidden Changes:
- keine Source-Code-Änderungen
- keine Docs-/README-Umbauten außerhalb des HAI-Reports
- keine Experimente, Docker-, Aider-, Netzwerk- oder Model-Runs
- kein Lesen oder Ändern von Secrets, `.env` oder Credential-Dateien
- keine Git-Aktionen, kein Commit, kein Push
- kein HAI-Execution-Loop

Recommended default:
A) Diese read-only Blocker-Inventur machen. Sie ist kleiner als ein Gate, weil sie noch keine Methode festlegt, sondern nur klärt, welches konkrete Problem zuerst entscheidet; danach kann ein Gate, ein Parken oder ein Reparaturstep viel präziser werden.

Decision options:
- A) Read-only Blocker-Inventur machen (recommended)
- B) Direkt Gate-Entscheidung treffen, ohne weitere Inventur
- C) Projekt parken, keine weitere Analyse

Definition of Done:
- Der dominante Evidenz-Blocker ist benannt, z.B. `zero_tests`, `infrastructure_error`, fehlende gemeinsame Zellen, Modell-Mismatch oder unklare Run-Identität.
- Es gibt eine kurze Begründung mit vorhandener lokaler Evidenz.
- Es gibt genau eine daraus folgende Empfehlung: Gate, Reparatur, Parken oder späterer Run.

Verification:
Read-only Bericht gegen `results/summary/*` und SQLite-Counts aus `results/experiment.db`; keine neuen Runs.

Not included:
- Gate entwerfen
- Gate implementieren
- Pre-Registration schreiben
- Run-Matrix starten
- UI/Präsentation/GitHub Pages ausbauen

Decision for Samuel:
Soll ich A machen: eine read-only Blocker-Inventur als noch kleineren Schritt vor dem Gate?
