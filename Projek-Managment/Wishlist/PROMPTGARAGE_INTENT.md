# WISHLIST

## Source
- PromptGarage DB: /home/smlflg/Projekte/PromptGarage/prompts.db
- Access mode: read-only SQLite URI with `immutable=1`
- Search terms: FirstRealHarnessEvaluation, KarpathiesMD, KarparthysClaude, negative_control_karpathy40, baseline_6line

## Result
found

## Matching User Prompts

### high - PromptGarage #11560: okay jetzt gerne ein eval run, /plan ...
- Source: hermes-raw:2c666c734914
- Tags: hermes,cli
- Updated: 2026-04-21 13:23:47
- Note: Full prompt has 5415 chars. The project-specific requirements are preserved below as excerpt; no secret values were exposed in the read excerpt.

```text
okay jetzt gerne ein eval run, /plan 
Du sollst einen **reproduzierbaren Versuchsaufbau** für ein Harness-Evaluations-Experiment entwerfen und im Repo umsetzen.

## Ziel

Wir wollen messen, ob kleine Änderungen an einer minimalen `CONVENTIONS.md` / Harness-Policy einen **messbaren Einfluss** auf Coding-Performance haben.

Nicht Ziel:

* kein Produkt bauen
* keine Plattform bauen
* kein Queueing / Multi-User / große UI
* keine allgemeine Benchmark-Infrastruktur für alles

Ziel ist ein **kleines, sauberes Experimentier-Rig**.

## Experiment-Hypothese

Eine kleine, minimalistische Harness-Policy kann besser performen als ein großes, überladenes Regelwerk.

Wir wollen deshalb:

1. eine **stabile Baseline-Condition** definieren
2. eine **Negativkontrolle** definieren
3. danach **einzelne Regeln isoliert** zur Baseline hinzufügen
4. den Effekt über harte Metriken messen

## Feste methodische Regeln

* `baseline_6line` = minimale 6-Zeilen-Policy, aktueller Control
* `negative_control_karpathy40` = große 40-§-Policy als Negativkontrolle
* Nie mehrere neue Regeln gleichzeitig testen
* Immer nur **eine atomare Regeländerung** pro neuer Condition
* Baseline bleibt unverändert und ist der feste Vergleichspunkt

## Tasks

Baue das Experiment zunächst für **3 kleine Python-Bugfix-Tasks derselben Task-Klasse**.

## Primäre Metriken

Die wichtigste Metrik ist **nicht** Judge-Score, sondern harte Test-Metrik:

1. `FAIL_TO_PASS`
2. `PASS_TO_PASS`
3. `task_success`
4. `tests_passed / tests_total`

## Judge

Judge nur als **sekundäre qualitative Instanz** verwenden.

Wichtig:

* harte Metrik > Judge
* Judge nur Tiebreaker / qualitative Begründung
```

### medium - PromptGarage #11487: es geht los, was sagst du zu diesem PRojekt...
- Source: hermes-raw:e502b5341ec0
- Tags: hermes,cli
- Updated: 2026-04-21 13:23:46

```text
es geht los, was sagst du zu diesem PRojekt: /home/smlflg/Projekte/FirstRealHarnessEvaluation_KarpathiesMD (just read and talk)
```

## Supporting Context / Unsichere Treffer
- #11749 mentions adding an Opus 4.7 assessment; useful as later evaluation-context only, not as core project intent.
- Several Claude/Codex transcripts mention debugging runs and compacted context; they are execution/support traces, not direct product wishes.

## Use In HAI
- These prompts are user-intent source material.
- They are not automatically current scope.
- `hai-idea-spec` must separate these wishes from local project reality and Samuel's current instruction.
