# Plan: Stufe 2 — Echter E2E Single-Task

## Ziel

Ein einziger realer SWE-bench Task wird komplett durchgespielt:
Clone → Aider → Patch → Docker-Eval → Ergebnis.

Danach ist das Framework als "grundsätzlich funktionsfähig" validiert (oder als "broken" erkannt).

---

## Aktueller Stand

- Framework-Skeleton: ✅ gebaut
- Preflight (Docker, Aider-echo): ✅ green
- Synthetic smoke (--skip-agent --skip-eval): ✅ green
- Judge stub: ✅ green
- **Echter Aider + SWE-bench Docker-Eval: ❌ noch nie gelaufen**

---

## Schritt 1: .env mit echten Werten füllen

**Datei:** `/home/smlflg/Projekte/FirstRealHarnessEvaluation_KarpathiesMD/.env`

```bash
cp /home/smlflg/Projekte/FirstRealHarnessEvaluation_KarpathiesMD/.env.example \
   /home/smlflg/Projekte/FirstRealHarnessEvaluation_KarpathiesMD/.env
```

Dann eintragen:

| Variable | Wert | Quelle |
|---|---|---|
| `AIDER_MODEL` | `openai/MiniMax-M2.7-highspeed` oder `MiniMax-M2.7-highspeed` | Aus preflight ermitteln welches Format funktioniert hat |
| `MINIMAX_API_KEY` | `***` | Aus `~/.hermes/.env` → `MINIMAX_API_KEY` |
| `MINIMAX_BASE_URL` | `https://api.minimax.io/v1` | Standard MiniMax OpenAI-compatible Endpoint |
| `AIDER_EXTRA_ARGS` | `--yes-always --no-auto-commits` | passt |
| `JUDGE_MODEL` | `claude-sonnet-4.5` (oder leer für stub) | separat konfigurieren wenn Judge läuft |
| `AGENT_INPUT_USD_PER_1M` | `0` | bis Token-Pricing bekannt |
| `AGENT_OUTPUT_USD_PER_1M` | `0` | dito |

**Achtung:** `MINIMAX_BASE_URL` in `subprocess_env()` wird als `OPENAI_API_BASE` durchgereicht → Aider muss das als `--openai-api-base` verstehen. Das muss im Aider-echo-Preflight bestätigt worden sein.

---

## Schritt 2: swebench Installationsquelle prüfen

**Offenes Issue:** PyPI `swebench>=3.0.14` vs. `pip install -e .` vom SWE-bench GitHub Repo.

Die SWE-bench README sagt explizit `pip install -e .` — PyPI und Repo-Harness können divergent sein.

**Prüfen:**
```bash
cd /home/smlflg/Projekte/FirstRealHarnessEvaluation_KarpathiesMD
python3 -c "import swebench.harness.run_evaluation; print('harness import OK')"
```
Wenn das fehlschlägt → Repo-Version installieren:
```bash
pip install git+https://github.com/SWE-bench/SWE-bench.git
```

---

## Schritt 3: Einen einzelnen SWE-bench Task laufen

**Task:** ein möglichst kleiner, schneller Python-Bugfix aus SWE-bench Lite.
Idealerweise `sympy__sympy-20590` (steht in der SWE-bench README als Demo).

**Vorgehen:**
```bash
cd /home/smlflg/Projekte/FirstRealHarnessEvaluation_KarpathiesMD

# Task-ID aus SWE-bench Lite holen falls nicht已知
uv run harness-fetch-candidates --limit 1

# Den einen Task ohne skip flags
uv run harness-run-once \
  --task-id sympy__sympy-20590 \
  --condition baseline \
  --iteration 1 \
  --run-index 1 \
  --agent-timeout 600 \
  --eval-timeout 600
```

**Erwartete Ausgaben nach `results/baseline/sympy__sympy-20590/<run_id>/`:**
- `agent_stdout.log` — Aider-Output
- `agent_stderr.log` — Fehler falls vorhanden
- `git_diff.patch` — der erzeugte Patch
- `tests.json` — SWE-bench Testergebnis
- `run_meta.json` — Metadaten
- `eval_stdout.log` — Docker-Build + Eval-Output

---

## Schritt 4: Ergebnis prüfen

**Was muss passieren:**
- Docker Image wird gebaut oder gezogen
- Aider läuft durch und erzeugt einen Patch (oder gibt vernünftig auf)
- SWE-bench Eval evaluiert den Patch
- `tests.json` enthält PASS_TO_PASS / FAIL_TO_PASS

**Was kaputt sein kann (Risiken):**

| Risiko | Symptom | Fix |
|---|---|---|
| Aider-model string funktioniert nicht | Aider exit != 0, stderr contain "model not found" | Model-String ändern (openai/MiniMax-...) |
| MINIMAX_API_KEY nicht in subprocess_env | 401 auth error | subprocess_env() prüfen |
| swebench PyPI vs. Repo Divergenz | `run_evaluation` import fehlt oder API geändert | `pip install git+...` |
| Docker can't pull swebench images | timeout / disk space | Docker daemon + 120GB prüfen |
| Aider hanging on MiniMax | timeout | agent_timeout runter setzen |
| Patch empty | diff ist leer → eval skip oder 0/0 | Aider stdout prüfen |

---

## Schritt 5: Iteration 1 Summary

```bash
uv run harness-summarize --iteration 1
```

Ziel: `results/summary/iteration_1.md` zeigt eine sinnvolle Zeile (nicht alle Nullen).

---

## Offene Fragen die während des E2E geklärt werden

1. **Welches AIDER_MODEL Format** hat im preflight funktioniert?
   - `MiniMax-M2.7-highspeed` (natives Format) oder `openai/MiniMax-M2.7-highspeed`?
   - Steht im preflight output

2. **Läuft SWE-bench Docker-Eval** mit PyPI-swebench oder braucht es git+https?
   - `import swebench.harness.run_evaluation` in der uv-Umgebung testen

3. **Wie viele FAIL_TO_PASS Tests** hat sympy__sympy-20590?
   - Wenn >5 und/oder >2min Eval → anderen kleineren Task nehmen

4. **Token-Parsing** — können wir tokens_in/tokens_out aus Aider-Output extrahieren?
   - Prüfen ob `extract_token_counts()` in agent_stdout etwas findet

---

## Dateien die voraussichtlich angefasst werden

- `.env` — triviale Konfiguration
- `pyproject.toml` — möglicherweise swebench-Installation anpassen
- `runner/config.py` — möglicherweise model-string handling anpassen

---

## Erfolgsdefinition

**Stufe 2 ist bestanden wenn:**
- `uv run harness-run-once` ohne `--skip-agent --skip-eval` durchläuft
- `results/baseline/<task>/<run_id>/tests.json` existiert und gültig ist
- `run_meta.json` tokens_in > 0 und tokens_out > 0 hat (oder beide 0 aber kein Fehler)

**Dann:** Framework ist E2E-validiert, Calibration-Runs können starten.
