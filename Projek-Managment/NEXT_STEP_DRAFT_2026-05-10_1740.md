Step type: DECISION_STEP
Step ID: NEXT_STEP_2026-05-10_1740_scope-freeze

Problem:
Die Scope-Diskussion ist in mehrere Folgeentscheidungen gekippt. Das vergrößert den Entscheidungsraum wieder, obwohl der Kern schon weitgehend geklärt ist: Hypothesentest-Rig als Primärscope, Dashboard nur nice-to-have, kein Plattformziel. Bevor weitere Downscope-Details diskutiert werden, sollte diese Klärung einmal knapp eingefroren werden.

Why now:
Ohne Freeze erzeugt jeder nächste Scope-Unterpunkt neue Mini-Debatten. Das ist selbst schon Scope-Drift auf Meta-Ebene.

Smallest next step:
Bestätige, dass die aktuelle Scope-Definition in `PROJECT_SCOPE.md` vorerst eingefroren wird und keine weitere Downscope-Feinzerlegung folgt, bis ein konkreter Arbeitskonflikt auftaucht.

Scope:
Nur Freeze oder Nicht-Freeze der bereits getroffenen Scope-Definition; keine neue Flächen-Priorisierung.

Allowed Changes:
none

Forbidden Changes:
- keine Änderungen an Source-Code
- keine weiteren Bereichs-Priorisierungen
- keine UI-, Diagramm- oder Runner-Entscheidungen im Detail
- kein Commit, kein Push, kein Execution-Loop

Recommended default:
A) Scope jetzt einfrieren.
Das ist der kleinste sinnvolle Schritt, weil er die bereits gewonnene Klarheit konserviert, ohne neue Scope-Kaskaden zu öffnen.

Decision options:
- A) aktuelle Scope-Definition jetzt einfrieren (recommended)
- B) noch genau eine weitere Scope-Präzisierung machen
- C) Scope-Definition wieder öffnen und neu schneiden

Definition of Done:
- Samuel wählt A, B oder C.
- Bei A ist klar, dass `PROJECT_SCOPE.md` vorerst als ausreichend gilt.
- Es ist klar, dass noch keine technische Umsetzung erfolgt ist.

Verification:
Chat-Verifikation: Samuel antwortet mit A, B oder C.

Not included:
- technische Bereinigung
- konkrete Dateiänderungen
- Git-Aufräumen
- Priorisierung einzelner Features

Decision for Samuel:
Willst du den Scope jetzt mit A einfrieren?