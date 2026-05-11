Step type: DECISION_STEP
Step ID: NEXT_STEP_2026-05-10_1829_run-readiness-gate
Lifecycle mode: VERIFY_FIRST

Problem:
Das Projekt hat bereits viel Infrastruktur und viele Result-Artefakte, aber die sichtbaren Kernvergleiche beantworten die Hypothese noch nicht belastbar. Der Report `baseline_6line vs negative_control_karpathy40` hat `valid_baseline=1`, `valid_candidate=0` und `common valid tasks=0`; ein Modellvergleich gegen GPT-5.5 ist ebenfalls nicht testbar. Ohne ein kleines Gate kann Samuel weitere Runs bezahlen oder beobachten, ohne am Ende eine bessere Entscheidung zu bekommen.

Why now:
Samuel hat diesen Lauf ausdrücklich als schweren HAI-Generalization-Test ohne teure Experimente, Netzwerk-/Model-Runs, Git-Aktionen oder Secret-Zugriff gestartet. Genau deshalb ist jetzt der richtige Moment, die nächste teure Aktion nicht auszulösen, sondern zuerst die minimale Entscheidungsregel davor zu klären.

Smallest next step:
Entscheide, dass vor jedem neuen teuren Run zuerst ein minimales Pre-Registration/Validity-Gate erfüllt sein muss.

Scope:
Nur die Projektmodus-Entscheidung für das nächste Run-Gate; keine technischen Änderungen.

Allowed Changes:
none

Forbidden Changes:
- keine Source-Code-Änderungen
- keine Docs-/README-Umbauten
- keine Experimente, Docker-, Aider-, Netzwerk- oder Model-Runs
- kein Lesen oder Ändern von Secrets, `.env` oder Credential-Dateien
- keine Git-Aktionen, kein Commit, kein Push
- kein HAI-Execution-Loop

Recommended default:
A) Gate vor teuren Runs festlegen. Das ist besser als sofortiges Weiterbauen oder Parken, weil es die zentrale Kosten-/Erkenntnisfalle schließt: Der nächste Run wird entweder methodisch zulässig oder bewusst nicht gestartet.

Decision options:
- A) Gate vor teuren Runs festlegen (recommended)
- B) Projekt vorerst parken; keine weiteren Runs und keine Gate-Arbeit
- C) Gate überspringen und später direkt einen neuen Run planen

Definition of Done:
- Samuel wählt genau A, B oder C.
- Es ist klar, ob neue teure Runs vorerst blockiert, geparkt oder ohne Gate weitergeplant werden dürfen.
- Es ist klar, dass diese Entscheidung selbst noch keine Datei-/Codeänderung und keinen Run ausführt.

Verification:
Chat-Verifikation: Samuel antwortet mit A, B oder C.

Not included:
- Pre-Registration-Datei schreiben
- Validity-Checker implementieren
- bestehende Resultate neu auswerten
- Run-Matrix starten
- UI/Präsentation/GitHub Pages ausbauen

Parked alternatives:
- Ein späterer EXECUTION_STEP könnte genau eine Pre-Registration-Datei für den nächsten Run anlegen.
- Ein späterer VERIFICATION_STEP könnte read-only prüfen, welche bestehenden Runs überhaupt valide gemeinsame Zellen haben.

Decision for Samuel:
Willst du A, B oder C als nächsten Projektmodus wählen?
