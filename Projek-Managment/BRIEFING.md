# BRIEFING

## Kurzbriefing
Dieses Repo ist kein normales App-Projekt, sondern ein wissenschaftlich gemeintes Wegwerf-/Experimentier-Rig: Es soll zeigen, ob kleine Markdown-Policy-Änderungen in einem Aider/SWE-bench-Lite-Harness messbare Effekte haben. Die Infrastruktur ist sichtbar weit: Runner, Conditions, SQLite, A/B-Reports, Modellvergleich, Judge, UI und viele Result-Artefakte existieren. Der menschliche Nutzen ist aber nicht „noch mehr bauen“, sondern aus dem vorhandenen Chaos eine belastbare Entscheidung zu gewinnen: Kann Samuel dem Rig vertrauen, bevor wieder Geld/Zeit in Runs fließt? Die sichtbaren Reports sagen derzeit: nein, die Kernvergleiche sind noch nicht entscheidbar, weil harte valide gemeinsame Zellen fehlen. `PROJECT_SCOPE.md` hat bereits richtig gegated: Dashboard und Präsentation sind nur Hilfen, nicht Primärziel. Deshalb wäre ein weiterer UI-/Showcase-Schritt jetzt Drift. Der kleinste sinnvolle Fortschritt ist eine methodische Entscheidung, welche minimale Readiness-Voraussetzung erfüllt sein muss, bevor ein nächster teurer Run überhaupt erlaubt ist.

## Aktueller Kern
Das Projekt braucht keine neue Funktion als Default, sondern ein kleines methodisches Gate gegen weitere nicht-aussagekräftige Runs.

## Lifecycle-Check
ACTIVE_BUILD / VERIFY_FIRST: Kern-Infrastruktur existiert, aber das Erkenntnisziel ist noch nicht erreicht; vorhandene Reports sind `not_decisive`/`not_testable`, nicht Abschluss-Evidenz.

## Warum das relevant ist
Wenn jetzt einfach weitere Experimente laufen, können wieder Kosten entstehen, ohne dass eine klare Hypothese entscheidbar wird. Wenn stattdessen erst ein kleines Readiness-Gate festgelegt wird, wird die nächste teure Aktion entweder legitim oder bewusst gestoppt. Nichts zu tun ist akzeptabel, wenn Samuel das Projekt nur parken will; riskant ist es nur, wenn später unklar bleibt, welche Voraussetzungen vor einem Run gelten. UI, Diagramme und GitHub Pages dürfen warten, weil sie die zentrale Evidenzlücke nicht schließen.

## Top-Optionen
1. Recommended: Ein DECISION_STEP legt fest, dass vor jedem neuen teuren Run zuerst ein kleines Pre-Registration/Validity-Gate existieren muss.
2. Parken: Projekt als explorativen Prototyp stehen lassen und keine weiteren Runs planen.
3. Späterer Build: Erst nach Gate-Entscheidung einen winzigen Dokument-/Script-Step bauen, der genau dieses Gate festhält oder prüft.

## Scope-Parkplatz
- Neue Model-/Aider-/Docker-Läufe.
- Dashboard-, Monitor-, Debrief- oder GitHub-Pages-Ausbau.
- Große README-/Docs-Aufräumarbeiten.
- Breite statistische Re-Designs wie 250/600-Run-Pläne.
- Git-Aufräumen, Commits, Pushes oder Secret-/Env-Prüfung.

## Frage an Samuel
Soll der nächste kanonische Schritt ein reiner Decision-Step sein: „Vor weiteren teuren Runs gilt ein minimales Pre-Registration/Validity-Gate“?
