# Statistisch Belastbarer Testplan — Treatment Effect Estimation

## Für wann?

Dieser Plan ist für wenn du **genug GPU/Token-Budget** hast:
- TH Mannheim Compute-Cluster Zugriff
- Oder größeres Token-Budget
- Oder publikationsreife Ergebnisse brauchst

Der Plan unten ist ** Publishable-ready**, nicht Proof-of-Concept.

---

## Das Ziel

**Treatment Effect Estimation**: Wie viel Impact hat jede Regel (A/B/C/D) auf `tests_pass_rate`, kontrolliert für Task-Effekte.

Mathematisch sauber:

```
y_{i,j} = β0 + βA × A_j + βB × B_j + βC × C_j + βD × D_j + γ_{task(i)} + ε_{i,j}

y      = tests_pass_rate (kontinuierlich 0-1)
A/B/C/D = Regel an/aus (binär 0/1)
γ      = fixed effect pro Task (absorbiert Task-schwierigkeit)
βA     = Treatment Effect von Regel A (das was wir wollen)
ε      = residuals
```

Was wir schätzen: **βA, βB, βC, βD** — der marginale Effekt jeder Regel, ceteris paribus.

---

## Statistische Power: Was brauchst du wirklich?

### Für mittleren Effekt (Δ = 0.15) bei α = 0.05

Faustregel für 2-Gruppen-Vergleich (lineares Modell):

```
n pro Gruppe ≈ 350  (für d = 0.3 bei 80% power)
n pro Gruppe ≈ 90   (für d = 0.5 bei 80% power)
```

Dein Design ist **faktoriell**, nicht 2-Gruppen.
Aber fürs Screening von 4 Regeln brauchst du mindestens:

| Design | Runs nötig |
|--------|-----------|
| 5 Tasks × 3 Repeats × 5 Bedingungen | **75 Runs** |
| 10 Tasks × 3 Repeats × 5 Bedingungen | **150 Runs** |
| 10 Tasks × 5 Repeats × 5 Bedingungen | **250 Runs** |

Für **signifikante β-Schätzer mit 95% CI** brauchst du minimum **n = 30 pro Zelle** (was 5 Tasks × 3 Repeats ≈ 15 ergibt — zu wenig).

**Empfohlen: 10 Tasks × 5 Repeats × 5 Bedingungen = 250 Runs**

---

## Design: 2^4 Fractional Factorial (Resolution IV)

Statt alle 2^4 = 16 Kombinationen zu testen, nutze **FFD mit Resolution IV**.

Resolution IV Design mit 4 Faktoren:

| Run | A | B | C | D |
|-----|---|---|---|---|
| 1   | 0 | 0 | 0 | 0 |  ← Baseline
| 2   | 1 | 0 | 0 | 1 |
| 3   | 0 | 1 | 0 | 1 |
| 4   | 1 | 1 | 0 | 0 |
| 5   | 0 | 0 | 1 | 1 |
| 6   | 1 | 0 | 1 | 0 |
| 7   | 0 | 1 | 1 | 0 |
| 8   | 1 | 1 | 1 | 1 |
| 9   | 1 | 0 | 0 | 0 |  ← A only
| 10  | 0 | 1 | 0 | 0 |  ← B only
| 11  | 0 | 0 | 1 | 0 |  ← C only
| 12  | 0 | 0 | 0 | 1 |  ← D only

Das sind **12 Runs** pro Task-Iteration.

Mit **5 Repeats × 10 Tasks**:

```
12 Runs × 5 Repeats × 10 Tasks = 600 Runs
```

Das ist viel. Aber dafür bekommst du:
- Main Effects βA, βB, βC, βD mit 95% CI
- 2-Wege-Interaktionen (AB, AC, AD, BC, BD, CD) approximativ
- Modellgüte (R², residual plots)

---

## Design: Alternativ — One-at-a-Time + Baseline

Einfacher, weniger Runs, aber keine Interaktionen messbar:

```
Baseline + 4 Regeln einzeln:
(1 Baseline + 4 Regeln) × 10 Tasks × 5 Repeats = 250 Runs
```

| Bedingung | Runs |
|-----------|------|
| baseline_v0 | 10 × 5 = 50 |
| Regel_A | 10 × 5 = 50 |
| Regel_B | 10 × 5 = 50 |
| Regel_C | 10 × 5 = 50 |
| Regel_D | 10 × 5 = 50 |
| **Total** | **250** |

**Pro Regel bekommst du:**
- βA mit 95% CI
- Win-rate vs Baseline
- Pro Task Breakdown
- Subgroup-Analyse (Regel wirkt nur auf manchen Tasks?)

**Was du NICHT bekommst:**
- Interaktionen (A×B, A×C, etc.)
- Ob Regeln sich **adder** oder **kompetieren**

---

## Empfohlenes Design: 10 Tasks × 5 Repeats × 5 Conditions = 250 Runs

### Warum 10 Tasks?

- Task-Diversity: Generalisierbarkeit über Repos hinweg
- Precision: Mehr Tasks = präzisere β-Schätzer
- Power: Du kannst Subgruppen bilden (leicht/mittel/schwer)

### Warum 5 Repeats?

- Schätzer-variance reduzieren
- outliers-handling
- Baseline-Noise abschätzen

### Warum 5 Bedingungen?

- Baseline
- 4 Regeln einzeln

### Warum nicht factorial (16 Kombinationen)?

- Zu teuer (160 Runs × 5 Repeats × 10 Tasks = 8000 Runs)
- Interaktionen sind sekundär — erst Main Effects verstehen
- Falls Interaktionen wichtig sind → Phase 2

---

## Task-Auswahl

Kriterien:
- 5 FAIL_TO_PASS bis 20 FAIL_TO_PASS (zu wenig = keine Varianz, zu viel = zu hart)
- 3+ PASS_TO_PASS (für Pass-Rate-Granularität)
- Verschiedene Repos (django, astropy, sympy, flask, etc.)
- Lösbar in < 10 Minuten Agent-Zeit

### Empfohlene 10 Tasks

```
django__django-10924     # 1 fail, 1 pass   — Kontrolle: sehr leicht
django__django-12113     # 1 fail, 0 pass   — Kontrolle: binäres Outcome
sympy__sympy-23117      # 1 fail, 3 pass   — Mittelschwer
astropy__astropy-14365  # 2 fail, 7 pass   — Gut für Varianz
astropy__astropy-14182  # 2 fail, 8 pass   — Gut für Varianz
flask__flask-XXXX       # 3 fail, 5 pass   — Web-Framework-Diversity
pandas__pandas-XXXX     # 4 fail, 10 pass  — Data-Science-Diversity
numpy__numpy-XXXX       # 3 fail, 8 pass   — Math-Diversity
requests__requests-XXXX  # 2 fail, 4 pass   — Library-Diversity
pytest__pytest-XXXX     # 3 fail, 6 pass   — Testing-Diversity
```

*Die konkreten Instanz-IDs müssen noch ausgewählt werden.*

---

## Regel-Auswahl

### Zu testen: 4 Karpathy-Regeln isoliert

```
Regel 1: "Write one function at a time"
Regel 2: "Always search for existing implementations first"  
Regel 3: "Think step by step before writing code"
Regel 4: "Write minimal changes, verify each step"
```

Jede Regel als eigene .md-Datei:
- `harness/CONVENTIONS.rule_1.md`
- `harness/CONVENTIONS.rule_2.md`
- etc.

Die Baseline: `harness/CONVENTIONS.baseline.md` (deine 6 Zeilen)

---

## Datenformat

### Pro Run speichern (DB)

```sql
runs (
  run_id TEXT PRIMARY KEY,
  task_id TEXT,
  condition_id TEXT,  -- 'baseline', 'rule_1', 'rule_2', 'rule_3', 'rule_4'
  rule_1 INTEGER,    -- 0 oder 1
  rule_2 INTEGER,
  rule_3 INTEGER,
  rule_4 INTEGER,
  tests_passed INTEGER,
  tests_total INTEGER,
  tests_pass_rate REAL,  -- calculated
  task_success INTEGER,  -- 1 wenn tests_passed == FAIL_TO_PASS
  agent_duration_seconds INTEGER,
  tokens_used INTEGER,
  judge_score REAL,
  failure_kind TEXT,
  PRIMARY KEY (run_id)
)
```

### Für Analyse in R/Python

```python
import pandas as pd
import statsmodels.formula.api as smf

df = pd.read_sql_query("SELECT * FROM runs", db)

# OLS mit fixed effects für Task
model = smf.ols(
    'tests_pass_rate ~ rule_1 + rule_2 + rule_3 + rule_4 + C(task_id)',
    data=df
).fit()

print(model.summary())

# 95% CIs für Treatment Effects
conf = model.conf_int()
print(conf.loc[['rule_1', 'rule_2', 'rule_3', 'rule_4']])
```

Interpretation:
- `rule_1 coef = +0.12, 95% CI [0.03, 0.21]` → Regel 1 erhöht Pass-Rate um 12%, signifikant
- `rule_2 coef = -0.05, 95% CI [-0.14, 0.04]` → Regel 2 hat keinen signifikanten Effekt

---

## Analyse: Vollständig

### Phase 1: Deskriptiv

```python
# Summary statistics pro condition
df.groupby('condition').agg({
    'tests_pass_rate': ['mean', 'std', 'count'],
    'task_success': 'mean',
    'agent_duration_seconds': 'mean',
    'tokens_used': 'mean'
}).round(3)
```

### Phase 2: Visualisierung

```python
import matplotlib.pyplot as plt

# Boxplot pro condition
df.boxplot(column='tests_pass_rate', by='condition')
plt.title('Pass-Rate by Condition')
plt.savefig('results/boxplot_condition.png')

# Scatter: Baseline vs Rule per Task
for task in df.task_id.unique():
    subset = df[df.task_id == task]
    # plot baseline vs rule_1 for this task
```

### Phase 3: Inferenz

```python
# Lineare Regression mit Task-Fixed-Effects
# (siehe oben)

# Für binären Outcome (task_success): Logistic Regression
model_logit = smf.logit(
    'task_success ~ rule_1 + rule_2 + rule_3 + rule_4 + C(task_id)',
    data=df
).fit(disp=0)

print(model_logit.summary())
# Odds ratios mit CIs
print(np.exp(model_logit.conf_int()))
```

### Phase 4: Interaktionen (nur wenn Power ausreicht)

```python
# Full factorial design (16 combos) muss extra gelaufen sein
# Sonst nur main effects interpretieren

# 2-Wege-Interaktion plotten
from statsmodels.interaction import plot_partregress

fig, axs = plt.subplots(2, 3)
for i, (r1, r2) in enumerate([('rule_1','rule_2'), ('rule_1','rule_3'), ...]):
    plot_partregress('tests_pass_rate', r1, r2, data=df, ax=axs.flat[i])
```

### Phase 5: Robustness Checks

```python
# Nur leichte Tasks (FAIL_TO_PASS <= 3)
df_easy = df[df.fail_to_pass <= 3]
model_easy = smf.ols('tests_pass_rate ~ rule_1 + rule_2 + rule_3 + rule_4 + C(task_id)', data=df_easy).fit()

# Nur schwere Tasks (FAIL_TO_PASS >= 5)
df_hard = df[df.fail_to_pass >= 5]
model_hard = smf.ols('tests_pass_rate ~ rule_1 + rule_2 + rule_3 + rule_4 + C(task_id)', data=df_hard).fit()

# Compare βs between subgroups
```

---

## Timeline

### Mit 10 parallelen Instanzen

```
Woche 1:
  - Tag 1-2: Pilot auf 1 Task × 5 Repeats (5 Runs) → Infrastructure Check
  - Tag 3-4: Alle 10 Tasks × 5 Repeats × Baseline (50 Runs)
  - Tag 5: Baseline-Analysis — welche Tasks sind zu schwer?

Woche 2:
  - Tag 1-3: Regel-1 Runs (50 Runs)
  - Tag 4-5: Regel-2 Runs (50 Runs)

Woche 3:
  - Tag 1-3: Regel-3 Runs (50 Runs)
  - Tag 4-5: Regel-4 Runs (50 Runs)

Woche 4:
  - Analyse + Rapport + Decision für Phase 2
```

**Total: ~4 Wochen**, je nach Infrastructure-Stabilität.

---

## Compute-Kosten Schätzung

### Token-Budget

```
250 Runs × ~100K tokens/run = 25M tokens input
25M tokens × $0.001/1K = $25
```

### GPU/Server-Stunden

```
250 Runs × 8 min/run = 2000 min = 33 Stunden
Bei 10 parallelen Instanzen = 3.3 Stunden pure compute time
+ 20% Infra-Overhead = 4 Stunden
```

### Realistisch mit Ausfällen

```
Einplanen: 1 Woche für alle 250 Runs inkl. Failures und Re-Runs
```

---

## Was du am Ende hast

### Publishbare Ergebnisse

1. **Table 1**: Deskriptive Statistik pro Bedingung
2. **Table 2**: Regression Results — β-Schätzer mit 95% CI
3. **Figure 1**: Boxplot/Violin-Plot der Pass-Raten
4. **Figure 2**: Interaktions-Plot (wenn factorial)

### Konkret pro Regel

```
Regel 1 ("Write one function..."):
  β = +0.12 [95% CI: +0.03, +0.21], p < 0.01
  → Statistisch signifikanter positiver Effekt
  
Regel 2 ("Search first..."):
  β = -0.02 [95% CI: -0.08, +0.04], p = 0.52
  → Kein messbarer Effekt

Regel 3 ("Think step by step..."):
  β = +0.07 [95% CI: -0.01, +0.15], p = 0.09
  → Tendenz positiv, aber nicht signifikant bei α=0.05

Regel 4 ("Minimal changes..."):
  β = -0.11 [95% CI: -0.19, -0.03], p = 0.01
  → Statistisch signifikanter negativer Effekt
```

---

## Offene Fragen

- [ ] Konkrete Instanz-IDs für 10 Tasks festlegen
- [ ] Regel-Texte final definieren
- [ ] Judge-Score als secondary outcome?
- [ ] Mixed Model statt fixed effects? (random effects für task)

---

## Nächste Schritte (wenn TH Mannheim GPU verfügbar)

1. Task-Liste finalisieren (10 Tasks mit richtigen Instanz-IDs)
2. Regel-Dateien erstellen
3. Design-Matrix für FFD oder OaT dokumentieren
4. Batch-Runner scripten (parallel=10)
5. Datenbank-Schema prüfen/erweitern
6. Pilot-Run (5 Runs auf 1 Task)
7. Volle Studie starten
8. Analyse nach Week 4
