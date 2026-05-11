# VERIFICATION_REPORT_NEXT_STEP

Step ID: NEXT_STEP_2026-05-10_1835_evidence-blocker-inventory
Step type: VERIFICATION_STEP
Zeit: 2026-05-10 18:37 CEST

## Scope
Read-only Blocker-Inventur aus bestehenden lokalen Reports und `results/experiment.db`.

## Nicht getan
- keine Experimente
- keine Docker-/Aider-/Model-Runs
- keine Netzwerkaktionen
- keine Git-Aktionen
- kein Secret-/`.env`-Zugriff
- keine Source-Code- oder normalen Docs-Änderungen

## Gelesene Evidenz
- `results/experiment.db` read-only via SQLite URI `mode=ro`
- `results/summary/scientific_ab_iteration_1_baseline_6line_vs_negative_control_karpathy40.md`
- `results/summary/model_ab_iteration_1_openai_MiniMax-M2.7_vs_openai_gpt-5.5.md`
- `results/summary/variance_report.md`

## Ergebnis in einem Satz
Der dominante Evidenz-Blocker ist `zero_tests` / keine harten Testmetriken; die fehlenden gemeinsamen validen Zellen sind hauptsächlich eine direkte Folge davon, nicht der erste separate Blocker.

## Lokale DB-Counts
Gesamt in `runs`:

- total runs: 102
- infrastructure_error: 5
- zero_tests (`tests_total <= 0`): 80
- valid_hard (`infrastructure_error=0 AND tests_total>0`): 19
- tasks: 8
- conditions: 31
- models: 6

Invalid-Run-Gründe nach einfacher Klassifikation:

- `zero_tests`: 78
- `infrastructure_error`: 3
- `infra_and_zero_tests`: 2

Failure-Kinds:

- `task_failure`: 82, davon 70 zero-tests
- `eval_report_missing`: 6, davon 6 zero-tests
- `agent_exit_nonzero`: 3, davon 3 infra
- `agent_timeout`: 2, davon 2 zero-tests
- weitere kleine Klassen: `unknown`, `success`, `infrastructure_error`, `docker_container_conflict`, `agent_import_error`

## Zentrale Vergleichszelle: baseline_6line vs negative_control_karpathy40
Für iteration 1, model `openai/MiniMax-M2.7`:

- `baseline_6line`: 12 total, 11 zero-tests, 1 valid_hard
- `negative_control_karpathy40`: 9 total, 9 zero-tests, 0 valid_hard
- gemeinsame valide Tasks: 0

Task-Detail:

- `baseline_6line` / `astropy__astropy-14182`: 1 total, 1 valid_hard
- `baseline_6line` / `django__django-10924`: 5 total, 5 zero-tests
- `baseline_6line` / `django__django-12113`: 3 total, 3 zero-tests
- `baseline_6line` / `sympy__sympy-23117`: 3 total, 3 zero-tests
- `negative_control_karpathy40` / `django__django-10924`: 3 total, 3 zero-tests
- `negative_control_karpathy40` / `django__django-12113`: 3 total, 3 zero-tests
- `negative_control_karpathy40` / `sympy__sympy-23117`: 3 total, 3 zero-tests

Der vorhandene Scientific-A/B-Report bestätigt das:

- Trust in comparison: `not_decisive`
- hard_metric_rows: `FAIL`, `valid_baseline=1`, `valid_candidate=0`
- task_overlap: `FAIL`, `common_tasks=0`
- excluded rows: baseline `{'zero_tests': 11}`, candidate `{'zero_tests': 9}`

## Interpretation
Der wichtigste Blocker ist nicht zuerst „wir brauchen ein Gate“ und auch nicht zuerst „mehr Runs“. Der wichtigste Blocker ist: Viele Runs liefern keine harte Testbasis (`tests_total=0`). Dadurch entsteht automatisch kein valider A/B-Vergleich, selbst wenn Conditions, Reports und UI vorhanden sind.

Infra-Errors existieren, sind aber nach lokaler DB-Zählung kleiner als zero-tests: 5 Infra-Markierungen vs. 80 zero-test-Runs. Fehlende gemeinsame Zellen sind für den Kernvergleich real, aber sie entstehen hier vor allem deshalb, weil fast alle relevanten Candidate/Baseline-Zellen durch zero-tests invalid werden.

## Empfehlung
Der nächste sinnvolle HAI-Schritt sollte kein allgemeines Pre-Registration-Gate sein. Besser ist ein kleiner, konkreter `VERIFICATION_STEP` oder `EXECUTION_STEP` zur zero-test-Ursache:

Recommended next decision: Soll als nächstes read-only geklärt werden, warum `tests_total=0` in den relevanten Runs entsteht?

Warum read-only zuerst: Es kann wahrscheinlich anhand vorhandener Run-Artefakte (`eval_stdout.log`, `eval_stderr.log`, `run_meta.json`, `tests.json`/fehlende Reports) eingegrenzt werden, ohne neue Model-/Docker-/Aider-Runs zu starten.

## Kleinster daraus folgender NEXT_STEP-Kandidat
Step type: VERIFICATION_STEP

Smallest next step: Prüfe an 2-3 vorhandenen zero-test-Run-Artefakten read-only, ob `tests_total=0` durch fehlende Eval-Reports, SWE-bench-Testmapping, Docker/Eval-Ausführung, Agent-Patch-Ausbleiben oder Result-Parsing entsteht.

Nicht enthalten: Fix implementieren, neuen Run starten, Gate schreiben, UI ausbauen.
