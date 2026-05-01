# Effizienter Testplan — Erste signifikante Ergebnisse

## Ziel

Minimale Runs für maximale statistische Power.
Token- und Hardware-schonend.
Proof of Concept: Messmethode funktioniert, erste Treatment Effects sichtbar.

---

## Das Problem: Compute-Budget

| Setup | Realistisch | Optimistisch |
|-------|------------|-------------|
| Token-Budget | ??? €/Tag | begrenzt |
| GPU-Parallel | 5–10 Aider-Instanzen | 10 |
| Zeit bis Ergebnis | < 4 Stunden | 2 Stunden |
| Ziel: erste Signal | N = 30 Runs | N = 20 Runs |

**Faustregel:** Für eine erste Trend-Aussage ("Regel X hilft oder schadet") brauchst du minimum **3 Tasks × 3 Repeats × 3 Bedingungen = 27 Runs**.

Mehr ist besser, aber nicht wenn es bedeutet nie anzufangen.

---

## Strategie: Compute-optimiertes Mini-Screening

Samuel's Budget: ~25 Runs maximum.

```
5 Tasks
× 5 Runs (Baseline + 4 Regeln, je 1 Run pro Bedingung)
= 25 Runs total
```

**Keine Repeats.** Jede Bedingung wird genau 1× pro Task gemessen.
Das ist ein Proof-of-Concept, kein publishesbares Ergebnis.

---

## Task-Auswahl: Compute-optimiert

Kriterien:
- Lösbar in < 5 Minuten Agent-Zeit
- Unterschiedliche FAIL_TO_PASS Counts (1–5) für Varianz
- Unterschiedliche Repos für Generalisierbarkeit

### Aktuelle Tasks (aus selected_tasks.json)

```
django__django-10924   # 1 FAIL_TO_PASS, 1 PASS_TO_PASS → sehr leicht
django__django-12113   # 1 FAIL_TO_PASS, 0 PASS_TO_PASS → kein grainularity
sympy__sympy-23117    # 1 FAIL_TO_PASS, 3 PASS_TO_PASS → mittel
```

### Fehlende Tasks: 2 weitere

```bash
cd /home/smlflg/Projekte/FirstRealHarnessEvaluation_KarpathiesMD
uv run python -c "
import json
with open('data/selected_tasks.json') as f:
    tasks = json.load(f)['tasks']
for t in tasks:
    print(t['instance_id'], '| fail:', t['FAIL_TO_PASS'], '| pass:', t['PASS_TO_PASS'])
"
```

Zu prüfen: `astropy__astropy-14365`, `astropy__astropy-14182`, `astropy__astropy-12907` als Ergänzung.

---

## Bedingungs-Plan

### Bedingung 1: baseline_v0 (Referenz)
- `.md`: minimal baseline (6 Zeilen)
- Runs: 1 × 5 Tasks = **5 Runs**

### Bedingung 2: karpathy_rule_1 (isoliert)
- Regel 1 allein zur Baseline
- Runs: 1 × 5 Tasks = **5 Runs**

### Bedingung 3: karpathy_rule_2 (isoliert)
- Regel 2 allein zur Baseline
- Runs: 1 × 5 Tasks = **5 Runs**

### Bedingung 4: karpathy_rule_3 (isoliert)
- Regel 3 allein zur Baseline
- Runs: 1 × 5 Tasks = **5 Runs**

### Bedingung 5: karpathy_rule_4 (isoliert)
- Regel 4 allein zur Baseline
- Runs: 1 × 5 Tasks = **5 Runs**

---

## Gesamt: 25 Runs

| Bedingung | Runs | Tokens/Rough Estimate |
|-----------|------|----------------------|
| baseline_v0 | 5 | ~250K |
| + Regel 1 | 5 | ~250K |
| + Regel 2 | 5 | ~250K |
| + Regel 3 | 5 | ~250K |
| + Regel 4 | 5 | ~250K |
| **Total** | **25** | **~1.25M Tokens** |

**Tokens-Kosten (MiniMax-M2.7):** ~$1.25 für 1.25M Tokens.
**Laufzeit:** ~25 Runs × 5 min = 125 min sequentiell.
**Parallel bei 5 Instanzen:** ~25 min.

---

## Was du messen wirst

### Primär: Tests-Pass-Rate

```
Pro Bedingung pro Task:
  tests_passed / tests_total (ein Wert, kein Mean)

Aggregiert über alle 5 Tasks:
  mean_pass_rate_per_condition
  Trend: rule besser oder schlechter als baseline?
```

### Sekundär

- Agent-Dauer (Tokens = Kosten)
- Judge-Score (wenn evalCompleted=true)
- Files Changed
- failure_reason breakdown

### Statistik: Was mit n=1 geht und was nicht

**Mit n=1 pro Task × Bedingung:**
- Kein t-test, kein Bootstrap pro Task (n zu klein)
- Keine Konfidenzintervalle
- **Keine statistische Signifikanz möglich**

**Was trotzdem geht:**
- **Deskriptiv**: Pro Task — Baseline vs Rule A: 2/4 vs 3/4
- **Trend**: Über 5 Tasks — Rule A: 4× besser, 1× schlechter als Baseline
- **Ranking**: Welche Regel hat die höchste durchschnittliche Pass-Rate über alle Tasks

**Was das bedeutet:**
- Ergebnisse sind **deskriptiv**, nicht inferenziell
- Du bekommst **Hinweise** welche Regeln tendenziell helfen
- Für Signifikanz brauchst du Repeats (spätere Phase)

### Effekt-Größe (deskriptiv)

```
Δ_per_task = tests_pass_rate(rule) - tests_pass_rate(baseline)

Aggregiert:
  mean_Δ = average(Δ over 5 tasks)
  sign(Δ): positive/negative trend
  freq(Δ > 0): wie oft besser als Baseline (z.B. 4/5 = 80%)
```

**Faustregel für Trend:**
- Δ > 0 über alle Tasks → Regel tendenziell hilfreich
- Δ < 0 über alle Tasks → Regel tendenziell schädlich
- gemischtes Bild → kein konsistenter Effekt

---

## Vor dem Start: Was prüfen

### 1. Tasks auf Existenz und Tests prüfen
```
Für alle 5 Tasks: FAIL_TO_PASS und PASS_TO_PASS Counts prüfen
→ Zu wenige Tests (< 2 total) → Task ersetzen
→ 0 PASS_TO_PASS → kein Zwischenwert möglich, trotzdem verwendbar
```

### 2.abbruch-Kriterien definieren
```
Wenn baseline_v0 auf Task X: 0/1 Runs mit tests_pass > 0
→ Task könnte zu schwer sein, aber nicht stoppen — trotzdem messen

Wenn eine Regel auf Task X: eval nie gestartet (infra_failed)
→ Regel für diesen Task fehlerhaft, skippen und dokumentieren
```

---

## Zeitplan

```
T+0:00   Alle 5 Baseline-Runs parallel starten (parallel=5)
T+0:05   Check: erste Runs laufen?
         Wenn ja → weiter. Wenn nicht → debug.

T+0:20   Regel-1 Runs starten (parallel=5)
T+0:40   Regel-2 Runs starten (parallel=5)
T+1:00   Regel-3 Runs starten (parallel=5)
T+1:20   Regel-4 Runs starten (parallel=5)

T+1:40   Alle 25 Runs done
T+1:45   Analyse-Script laufen lassen
T+1:50   Erste Ergebnisse interpretieren
```

Realistisch mit Infra-Fails: **~2–3 Stunden**.

---

## Analyse-Script (Pseudocode)

```python
# analyze_screening.py
import sqlite3
import json

db = sqlite3.connect("results/experiment.db")

# Sammle alle Runs aus diesem Screening
query = """
SELECT run_id, task_id, condition_id,
       tests_passed, tests_total,
       agent_duration_seconds, tokens_used,
       judge_report_status, failure_kind
FROM runs
WHERE condition_id IN ('baseline_v0', 'karpathy_rule_1', 'karpathy_rule_2',
                       'karpathy_rule_3', 'karpathy_rule_4')
  AND run_id LIKE 'efficient_screening%'
"""

# Schreibe Ergebnis-Tabelle
print("Task | Baseline | Rule1 | Rule2 | Rule3 | Rule4")
print("-" * 70)

tasks = set()
results = {}
for row in db.execute(query):
    task_id, condition_id = row.task_id, row.condition_id
    pass_rate = row.tests_passed / row.tests_total if row.tests_total > 0 else None
    results[(task_id, condition_id)] = pass_rate
    tasks.add(task_id)

for task in sorted(tasks):
    baseline = results.get((task, 'baseline_v0'), '-')
    r1 = results.get((task, 'karpathy_rule_1'), '-')
    r2 = results.get((task, 'karpathy_rule_2'), '-')
    r3 = results.get((task, 'karpathy_rule_3'), '-')
    r4 = results.get((task, 'karpathy_rule_4'), '-')
    print(f"{task} | {baseline} | {r1} | {r2} | {r3} | {r4}")

# Delta pro Regel vs Baseline aggregiert
print("\nDelta vs Baseline (Rule - Baseline):")
for rule in ['karpathy_rule_1', 'karpathy_rule_2', 'karpathy_rule_3', 'karpathy_rule_4']:
    deltas = []
    wins = 0
    for task in tasks:
        b = results.get((task, 'baseline_v0'))
        r = results.get((task, rule))
        if b is not None and r is not None:
            deltas.append(r - b)
            if r > b:
                wins += 1
    if deltas:
        mean_delta = sum(deltas) / len(deltas)
        print(f"  {rule}: mean_Δ={mean_delta:+.3f}, win_rate={wins}/{len(deltas)}")

print("\nInterpretation:")
print("  mean_Δ > 0 → Regel tendenziell hilfreich")
print("  mean_Δ < 0 → Regel tendenziell schädlich")
print("  win_rate ≥ 4/5 → starker Trend")
```

---

## Exit-Kriterien für Phase 1

```
✓ Wenn eine Regel auf ≥ 4/5 Tasks besser als Baseline ist:
  → Starker Trend — Phase 2 lohnt sich

✓ Wenn eine Regel auf ≥ 4/5 Tasks schlechter als Baseline ist:
  → Starker negativer Trend — Regel aktiv meiden

~ Wenn gemischtes Bild (2–3/5 besser):
  → Kein klares Signal — mehr Repeats nötig oder Regel hat task-spezifischen Effekt

✗ Wenn alle Regeln gemischtes Bild zeigen:
  → Messmethode zu noisy, oder Regeln machen keinen konsistenten Unterschied
```

---

## Offene Fragen vor dem Start

- [ ] **Welche 5 Tasks?** Die selected_tasks.json hat django/sympy — passend für 3. Für 2 weitere Tasks müssen wir Astropy-Tasks hinzufügen oder eine andere Quelle finden.
- [ ] **Welche 4 Regeln testen wir?** Karpathy-Regeln einzeln? Oder eigene?
- [ ] **Rule-Codierung**: Wie genau kodieren wir `rule_1` an/aus in der DB und im harness?
- [ ] **Was wenn ein Task 0 PASS_TO_PASS hat?** Ergebnis ist immer 0/1 oder 1/1 — trotzdem messbar aber wenig granular.
- [ ] **Naming der runs**: Wie heißen die runs in der DB? `efficient_screening_{task}_{condition}`?
- [ ] **Infra-Fails**: Was wenn 1-2 Runs scheitern? Kriterium: ≥ 4/5 Tasks pro Bedingung müssen durchlaufen für belastbare Aussage.

---

## Nächste Schritte (nach diesem Plan)

1. **5 Tasks festlegen** — Welche Tasks nehmen? (django/sympy ausgewählt + 2 weitere)
2. **4 Regeln festlegen** — Welche Karpathy-Regeln isoliert testen
3. **Batch-Script schreiben** — `scripts/run_efficient_screening.sh`
   - Führt alle 25 Runs aus mit korrektem condition_id
   - Parallel=5, monitoring
4. **Analyse-Script** — `scripts/analyze_screening.py`
5. **Rule-Codierung in DB** — Spalten `rule_1/2/3/4` als 0/1
6. **Pilot-Run** — 1 Baseline-Run als Sanity-Check bevor alle 25
7. **Starten**

