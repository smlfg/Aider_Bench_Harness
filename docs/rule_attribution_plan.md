# Rule Attribution Plan — Welche Regel welchen Impact hat

## Ziel

Backpropagation: `.md`-Regeln (Konventionen) → Agent-Verhalten → `tests_pass`
→ Quantifizieren: Wie viel Impact hat jede Regel auf das Testergebnis?

**Richtige Bezeichnung:** Nicht "Backpropagation", sondern:
- **Treatment Effect Estimation**
- **Factor Screening**
- **Design of Experiments for Harness Policies**
- Kurz: **Policy Ablation**

---

## Die richtige Mathematik

Die gute Einsicht:

[
\text{Outcome} = f(\text{Regeln}, \text{Task}, \text{Run-Noise})
]

Regeln binär kodieren → als Faktoren behandeln:

[
y = \beta_0 + \beta_A A + \beta_B B + \beta_C C + \epsilon
]

mit:
- (y) = Erfolg, Tests, Score, Kosten
- (A,B,C) = Regeln an/aus
- (\beta_A) = geschätzter durchschnittlicher Effekt von Regel A
- (\epsilon) = Restrauschen

**Das ist nicht nur gute Intuition, sondern klassisches Experimentdesign.**

### Der wichtigste begriffliche Shift

**Behandle Regeln nicht als Philosophie, sondern als experimentelle Faktoren mit messbarem Treatment Effect.**

---

## Erweitertes Modell mit Task-Effekten

Das einfache Modell überschätzt Regelsignale, weil zusätzlich:
- Task-Effekte
- Run-to-run-Noise
- Modell-/Judge-Noise
- unterschiedliche Difficulty pro Task

Besseres Modell:

[
y_{i,j} = \beta_0 + \sum_k \beta_k x_{i,k} + \gamma_{task(j)} + \epsilon_{i,j}
]

Oder als Mixed Model:

[
y = \beta_0 + \beta_A A + \beta_B B + \dots + u_{\text{task}} + u_{\text{run}} + \epsilon
]

- **fixed effects** für Regeln
- **random effects** oder Kontrollvariablen für Tasks

---

## Das mathematsche Problem: Kombinatorische Explosion

Wenn du **10 Regeln** hast, die man an/aus schalten kann:

| Ansatz | Runs nötig |
|--------|-----------|
| Alle 2^10 Kombinationen | **1.024** |
| Jede Regel einzeln isoliert + Baseline | **11** (nur main effects, keine Interaktionen) |
| Fractional Factorial Design (FFD) | **17-32** |
| Full factorial × 5 Repeats × 20 Tasks | **5.000+** |

Für 20 Regeln: 2^20 = **1.048.576** Runs — nicht machbar.

### Warum Factorial Design nicht sofort

FFD hilft nur wenn:
- deine Messung halbwegs stabil ist
- die Regeln wirklich klar binär codiert sind
- du schon weißt, dass du mehr als 2–3 Faktoren ernsthaft untersuchen willst

**Richtige Reihenfolge:**
1. Screening — Welche Regeln haben überhaupt Signal?
2. Narrowing — Welche 2–4 sind relevant genug für Interaktionen?
3. Interaction phase — Erst dann Kombinationen testen

---

## Lösungsstrategien

### 1. Sequentiells Vorgehen (empfohlen)

```
Phase 1: Screening     — 20 Runs, rausfinden welche 3-4 Regeln überhaupt Impact haben
Phase 2: Fokussiert    — nur die wichtigen Regeln variieren
Phase 3: Interaktionen  — die wichtigsten 2-3 Regeln in Kombination testen
```

### 2. Fractional Factorial Design (DoE)

- Statistisches Sampling der Regel-Kombinationen
- Erst **nach** dem Screening — wenn überhaupt

### 3. Bayesian Optimization

- Nach jeder Run den nächsten Experiment designen
- Effizienter als fixes Design
- Tool: `scikit-optimize`, `ax-platform`

---

## Primärsignal vs Sekundärsignal

Dein Primärsignal sollte **nicht** ein einzelner Judge-Score sein, sondern:

- `FAIL_TO_PASS`
- `PASS_TO_PASS`
- `task_success`
- `tests_pass_fraction`

Das sind die robustesten Outcomes.

**Judge** kannst du nutzen:
- als **Sekundärsignal** bei gleicher Testlage
- als **Qualitätsmerkmal** für Minimalität / Slop / Scope-Treue
- **nicht** als Hauptzielgröße

---

## Datenformat das du brauchst

| run_id | task_id | condition | Regel_A | Regel_B | Regel_C | tests_passed | tests_total |
|--------|---------|-----------|---------|---------|---------|-------------|-------------|
| run_001 | sympy-23117 | baseline | 0 | 0 | 0 | 3 | 4 |
| run_002 | sympy-23117 | rule_A_only | 1 | 0 | 0 | 4 | 4 |
| ... | | | | | | | |

→ Das gibt dir deinen **Treatment Effect** pro Regel mit Confidence Intervals.

---

## Analyse: Was zuerst auswerten

**Nicht** sofort lineare Regression auf alles.

Sondern zuerst ganz einfach:

### pro Regel

[
\Delta = \text{mean(outcome | rule on)} - \text{mean(outcome | baseline)}
]

plus:
- Streuung
- Konfidenzintervall
- Win-rate gegen Baseline

Das ist viel robuster und verständlicher.

### Wenn dann ernster

Modell fitten:

[
\text{task_success} \sim \text{rule_A} + \text{rule_B} + \text{rule_C} + \text{task}
]

Für binäre Outcomes: **logistische Regression**:

[
\Pr(\text{success}=1) = \sigma(\beta_0 + \beta_A A + \beta_B B + \dots + \gamma_{task})
]

Für kontinuierliche Dinge (Dauer, Tokens): lineares Modell.

**Achtung:** `tests_pass` ist bei dir binär oder near-binär (0/22 oder 22/22, selten dazwischen). Lineare Regression auf binäre Outcomes ist schlecht. Logistische Regression braucht mehr Datenpunkte pro Zelle.

---

## Die beste erste Statistik für dich

Für jetzt: bleib bei Proportionen (3/3, 2/3, 1/3, 0/3) und Augapfel-Vergleich.

Statistische Signifikanz kommt mit **N**, nicht mit Methodik.

---

## Konkretes Beispiel

Annahmen:
- 10 Regeln in separaten `.md`-Dateien
- 20 Tasks
- 5 Wiederholungen

### Szenario A: Jede Regel einzeln gegen Baseline
```
11 Bedingungen × 20 Tasks × 3 Wiederholungen = 660 Runs
```
→ Für jede Regel: "+X% tests_pass im Schnitt (p < Y)"

### Szenario B: Fractional Factorial
```
32 Kombinationen × 20 Tasks × 3 Wiederholungen = 1.920 Runs
```
→ Alle Regeln gleichzeitig, inkl. Interaktionen

---

## Phasen-Plan

### Phase 0: Baseline Stability (Proof of Concept)
```
3 Tasks
3 Runs pro Task
nur Baseline

Ziel:
- Run-Noise sehen
- Task-Noise sehen
- Prüfen ob harte Metrik stabil genug ist
```

### Phase 1: One-Rule Additions
```
Baseline
Baseline + 1 Regel
3–5 Regeln insgesamt
gleiche 3–5 Tasks
3 Runs pro Bedingung

Ziel:
- Grobe Main Effects abschätzen
- Schlechte Regeln aussortieren
```

### Phase 2: Top-2 oder Top-3 Regeln

Erst jetzt lohnt sich ein kleines faktorielles Design.

Beispiel für 3 Regeln — 8 Kombinationen stemmbar:

- baseline
- A
- B
- C
- AB
- AC
- BC
- ABC

Das ist klein genug und schon sehr informativ.

---

## Realistisches Budget für jetzt

### Nicht

- 10 Regeln gleichzeitig
- großes FFD
- Bayesian Optimization
- komplizierte Modelle

### Sondern

- 1 feste Baseline
- 3–5 atomare Regeln
- 3–5 Tasks
- 3 Runs pro Bedingung
- Outcome zuerst simpel auswerten:
  - Erfolgsrate
  - mittlere Tests
  - Dauer
  - Tokens
  - Judge nur ergänzend

---

## Konkreter erster Schritt

Dein Smoke-Test hat gerade gezeigt: volle Karpathy-.md verschlechtert MiniMax dramatisch. Die Frage ist jetzt: **schadet jede einzelne Karpathy-Regel, oder nur die Masse?**

In deinem aktuellen Budget:

- **Baseline** (deine 6 Zeilen): 3 Runs auf 3 Tasks = 9 Runs
- **Baseline + Regel 1 allein**: 3 × 3 = 9 Runs
- **Baseline + Regel 2 allein**: 3 × 3 = 9 Runs
- **Baseline + Regel 3 allein**: 3 × 3 = 9 Runs
- **Baseline + Regel 4 allein**: 3 × 3 = 9 Runs

**Das sind 45 Runs.** Mit 10 parallelen Instanzen in ~1 Stunde machbar.

Du bekommst: **hilft / schadet / neutral** pro Regel, isoliert.

Kein Factorial nötig, keine Interaktionseffekte — die kommen in Phase 2 wenn Phase 1 überhaupt Signal zeigt.

### Warum nicht mehr?

20 Tasks × 5 Wiederholungen ist Science-Fiction für dein aktuelles Setup.
Du hast gerade 10 erfolgreiche Runs geschafft, nach 3 Tagen Debugging.
1.100 Runs bei ~10 Min pro Run = ~180 Stunden Compute.
Selbst mit 10 parallelen Aider-Instanzen: 18 Stunden reine Laufzeit, plus bekannte Infra-Fails.

---

## Offene Fragen

- [ ] Wie viele Tasks brauchen wir für statistische Power? (Pilot gibt Direction)
- [ ] Wie viele Repeats pro Run? (3 minimum, 5 für Significance)
- [ ] Welche Regeln zuerst testen? (Subjektives Prioritizing oder Random)
- [ ] Wie "stark" sollten Regel-Variationen sein? (Textlänge, Framing, Constraints)
- [ ] Welche der 4 Karpathy-Regeln sind isoliert schädlich vs. die Masse?

---

## Kleines statistisches Auswertungsschema

### CSV-Spalten pro Run

```
run_id,task_id,condition,rule_1,rule_2,rule_3,rule_4,tests_passed,tests_total,task_success,judge_score,duration_seconds,tokens_used
```

### Modellformeln

**Phase 1 (Main Effects):**
```
Δ_rule1 = mean(tests_passed/tests_total | rule_1=1) - mean(tests_passed/tests_total | rule_1=0)
Δ_rule2 = ...
Win_rate_rule1 = count(tests_passed > baseline) / N
```

**Phase 2 (Faktoriell):**
```
tests_passed ~ rule_1 + rule_2 + rule_3 + (task as fixed effect)
```

**Für binäre Outcomes (später):**
```
glm(task_success ~ rule_1 + rule_2, family=binomial)
```

### Reihenfolge der Analysen

1. **Deskriptiv**: Proportionen, Mittelwerte, StdDev pro condition
2. **Visualisierung**: Boxplots / Stripcharts rule vs baseline
3. **Statistik**: t-test oder Wilcoxon pro Regel gegen Baseline
4. **Modell**: Erst wenn N > 30 pro Zelle

### Wann von pairwise zu faktoriell wechseln

- Wenn Phase 1 zeigt: mindestens 2 Regeln haben Signal (|Δ| > 0.1)
- Und: Residuen sind halbwegs normalverteilt
- Und: Varianz ist halbwegs homogen

---

## Nächste Schritte

1. **Regeln definieren** — welche `.md`-Konventionen willst du testen?
2. **Pilot bauen** — 1 Regel gegen Baseline auf 5 Tasks × 3 Repeats
3. **Daten sammeln** — Pipeline muss `condition` + `rule_flags` in DB und events loggen
4. **Analyse-Script** — Regression/ANOVA nach Pilot
5. **Karpathy-Regeln isolieren** — jede einzeln gegen Baseline testen

