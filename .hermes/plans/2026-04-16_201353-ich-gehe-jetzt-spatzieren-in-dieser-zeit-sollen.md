# Plan: Validation Loop — Karpathy Prompt Progression

## Ausgangslage

- **Token-Budget:** ~800 Prompts im MiniMax-Konto
- **Test-Tasks:** 3 Astropy-Tasks (je 1-2 FAIL_TO_PASS, 8-13 PASS_TO_PASS)
- **Vorheriger Run:** `litellm.BadRequestError` — Model-String ohne `openai/` Prefix
- **Fix:** `AIDER_MODEL=openai/MiniMax-M2.7-highspeed` (bestätigt funktioniert)

## Die Validation Loop

```
WHILE prompts_verfügbar:
    1. Prüfe ob MiniMax-API noch Budget hat
    2. Starte Run N mit CONVENTIONS.md Version N
    3. Wartes bis fertig (~5-15min)
    4. VALIDATION CHECK: Hat MiniMax wirklich gecoded?
       - tokens_in > 0?
       - patch enthält mehr als nur .aider*?
       - FAIL_TO_PASS tests > 0?
       - IF NOT → log, fix, next run
    5. Judge ausführen (blind, stub ist OK für Bewertung)
    6. Report-Zeile schreiben
    7. Nächste CONVENTIONS.md Version vorbereiten
```

---

## CONVENTIONS.md Versionen (progressive Karpathy-Addition)

### v0 — Baseline (aktuell, 6 Rules)
```markdown
## Goal
Solve the requested bug with the smallest correct change.

## Rules
1. State the bug hypothesis before editing.
2. Reproduce or inspect the failing behavior first.
3. Prefer the smallest fix that makes tests pass.
4. Do not refactor unrelated code.
5. Run the relevant tests before finalizing.
6. In the final message, state what changed and which tests passed.
```

### v1 — Baseline + Think-Before-Coding (Karpathy §1)
```markdown
## Goal
Solve the requested bug with the smallest correct change.

## Rules
1. State the bug hypothesis before editing.
2. Reproduce or inspect the failing behavior first.
3. Prefer the smallest fix that makes tests pass.
4. Do not refactor unrelated code.
5. Run the relevant tests before finalizing.
6. In the final message, state what changed and which tests passed.

## Think Before Coding
Before implementing: State your assumptions explicitly. If uncertain, ask.
If multiple interpretations exist, present them — don't pick silently.
If something is unclear, stop. Name what's confusing. Ask.
```

### v2 — + Simplicity First (Karpathy §2)
```markdown
## Goal
Solve the requested bug with the smallest correct change.

## Rules
1. State the bug hypothesis before editing.
2. Reproduce or inspect the failing behavior first.
3. Prefer the smallest fix that makes tests pass.
4. Do not refactor unrelated code.
5. Run the relevant tests before finalizing.
6. In the final message, state what changed and which tests passed.

## Think Before Coding
Before implementing: State your assumptions explicitly. If uncertain, ask.
If multiple interpretations exist, present them — don't pick silently.
If something is unclear, stop. Name what's confusing. Ask.

## Simplicity First
Minimum code that solves the problem. Nothing speculative.
If you write 200 lines and it could be 50, rewrite it.
```

### v3 — + Surgical Changes (Karpathy §3)
```markdown
## Goal
Solve the requested bug with the smallest correct change.

## Rules
1. State the bug hypothesis before editing.
2. Reproduce or inspect the failing behavior first.
3. Prefer the smallest fix that makes tests pass.
4. Do not refactor unrelated code.
5. Run the relevant tests before finalizing.
6. In the final message, state what changed and which tests passed.

## Think Before Coding
Before implementing: State your assumptions explicitly. If uncertain, ask.

## Simplicity First
Minimum code that solves the problem. Nothing speculative.

## Surgical Changes
Touch only what you must. Do not refactor things that aren't broken.
Match existing style. Every changed line should trace directly to the user's request.
```

### v4 — + Goal-Driven Execution (Karpathy §4)
```markdown
## Goal
Solve the requested bug with the smallest correct change.

## Rules
1. State the bug hypothesis before editing.
2. Reproduce or inspect the failing behavior first.
3. Prefer the smallest fix that makes tests pass.
4. Do not refactor unrelated code.
5. Run the relevant tests before finalizing.
6. In the final message, state what changed and which tests passed.

## Think Before Coding
Before implementing: State your assumptions explicitly. If uncertain, ask.

## Simplicity First
Minimum code that solves the problem. Nothing speculative.

## Surgical Changes
Touch only what you must. Do not refactor things that aren't broken.

## Goal-Driven Execution
Define success criteria. Loop until verified.
Write a test that reproduces the bug, then make it pass.
```

---

## Validation-Check nach jedem Run

**CRITICAL — muss nach JEDEM Run geprüft werden:**

```
CHECK 1: tokens_in > 0 AND tokens_out > 0
  → IF FAIL: MiniMax hat nicht gecoded. Log + Fix + next run

CHECK 2: git_diff.patch enthält NICHT NUR .aider*
  → IF FAIL: Nur Auto-Gitignore, kein echter Code. Log + Fix + next run

CHECK 3: Mindestens 1 FAIL_TO_PASS Test bestanden
  → IF FAIL: Modell hat den Bug nicht gefixt. Log aber weiter (interessant)
```

**Fix-Strategien wenn CHECK 1 oder 2 fehlschlägt:**
- Model-String prüfen: `openai/MiniMax-M2.7-highspeed`?
- MINIMAX_API_KEY in `.env` prüfen
- Timeout erhöhen
- Aider extra args prüfen

---

## Monitoring während Samuel unterwegs ist

**Ich prüfe alle 2-3 Minuten:**
1. Prozess-Status (`ps aux | grep harness`)
2. Neue Log-Files in `results/`
3. tokens_in / tokens_out in `run_meta.json`
4. Patch-Inhalt in `git_diff.patch`

**Ich schreibe nach jedem Run eine Zeile in das Report-Dokument:**

```
## Run <N> — CONVENTIONS v<K> — <task_id>
- timestamp: <zeit>
- tokens_in: <zahl>  tokens_out: <zahl>
- files_changed: <n>  lines_added: <n>
- FAIL_TO_PASS: <x>/<y> bestanden
- PASS_TO_PASS: <x>/<y> bestanden
- task_success: true/false
- VALIDATION: PASS/FAIL
- Judge score: <falls vorhanden>
- Hermes-Analyse: <kurze Einschätzung>
```

---

## Report-Dokument

**Pfad:** `/home/smlflg/Projekte/FirstRealHarnessEvaluation_KarpathiesMD/results/VALIDATION_LOOP.md`

Aktualisiert nach jedem Run mit:
- Run-Ergebnis
- VALIDATION Status (echt gecoded ja/nein)
- Judge-Bewertung
- Meine Analyse: Was hat funktioniert, was nicht, warum

---

## Offene Fragen die ich klären werde

1. Funktioniert `openai/MiniMax-M2.7-highspeed` wirklich mit echtem Key?
2. Wieviele Prompts verbraucht ein einzelner Run?
3. Reicht das Budget für alle 4+ Versionen?
4. Welche CONVENTIONS-Version produziert die besten Results?

---

## Success-Kriterien

- Jeder Run erzeugt tokens_in > 0, tokens_out > 0
- Nach jeder CONVENTIONS-Änderung: Judge-Bewertung dokumentiert
- Nach jedem Run: eigene Analyse geschrieben
- Budget-Tracking: nie mehr als 780 Prompts verbrauchen (Reserve)
