# Scope Assessment

Projekt: FirstRealHarnessEvaluation_KarpathiesMD
Datum: 2026-05-10 17:00

## Ursprünglicher Scope
Dieses Repo war ursprünglich ein kleines, reproduzierbares Experiment-Rig für eine enge Hypothese:

Kann eine minimale Harness-/Policy-Instruktion besser funktionieren als eine überladene?

Im Repo sichtbar durch:
- `experiment_README.md`: kleines, reproduzierbares Experimentier-Rig
- Vergleich von genau zwei Bedingungen:
  - `baseline_6line`
  - `negative_control_karpathy40`
- wenige ausgewählte Tasks
- mehrere Wiederholungen
- klare Metriken:
  - task success
  - FAIL_TO_PASS / PASS_TO_PASS
  - Tokens
  - Laufzeit
  - unrelated edits

Kurzform:
Mini-Eval-Rig für eine einzelne Hypothese.
Nicht Plattform, nicht Produkt, nicht allgemeines Forschungsprogramm.

## Drift-Einschätzung
Kein harter Scope Creep, aber leichte Scope-Drift-Tendenz.

Drift-Signale im Repo:
- Web-UI / Dashboard
- GitHub Pages
- Diagramm-/Visualisierungsarbeit
- Scientific A/B layer
- Protocol-Dokumentation

Einordnung:
- Scientific A/B layer: eher scope-gerecht, solange er nur die Aussagekraft der Kernmessung verbessert
- Protocol-Dokumentation: eher scope-gerecht, solange sie der Kernhypothese dient
- Dashboard / Pages / Diagramm-Arbeit: größte Drift-Gefahr, weil Darstellung und Tooling leicht wichtiger werden können als die eigentliche Hypothesenantwort

## Empfehlung
Projektidentität aktiv schärfen:

Entscheidungsfrage:
Ist dieses Repo primär
A) ein einmalig fokussiertes Hypothesentest-Rig
oder
B) der Anfang einer allgemeinen Harness-Evaluationsplattform?

Empfehlung: A

Begründung:
Das entspricht dem ursprünglichen Scope und reduziert die Gefahr, dass Infrastruktur, Präsentation und Verallgemeinerung schneller wachsen als die evidenzbasierte Beantwortung der Kernfrage.

## Empfohlene Scope-Definition
Dieses Repo dient primär dazu, die Hypothese zu testen, ob eine minimale Harness-Policy gegenüber einer überladenen Policy messbar besser performt. Web-UI, Diagramme und Zusatzprotokolle sind unterstützende Mittel und nicht der Hauptscope.
