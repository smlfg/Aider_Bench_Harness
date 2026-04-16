# Analyse: Erster E2E Run — Was ist passiert?

## 1. Was ist wirklich passiert

### Der entscheidende Fehler

```
agent_stdout.log, Zeile 19:
litellm.BadRequestError: LLM Provider NOT provided.
Pass in the LLM provider you are trying to call.
You passed model=MiniMax-M2.7-highspeed
```

**Aider hat den LLM-Call nie gemacht.** Litellm hat `MiniMax-M2.7-highspeed` nicht als Provider erkannt und einen Fehler geworfen BEVOR überhaupt ein API-Request stattfand.

Konsequenz:
- `tokens_in: null`, `tokens_out: null` — kein einziger Token ausgetauscht
- Der `.aider*` Gitignore-Eintrag wurde beim Repo-Scan erzeugt (Aiders auto-gitignore Feature), NICHT vom Model
- Das Problem-Statement wurde dem Model **nie** übergeben

### Warum der Preflight erfolgreich war

Der Preflight in `preflight.py` nutzt **exakt denselben Model-String** (`MiniMax-M2.7-highspeed`) — Aider im interaktiven Modus. Der Echo-Test war erfolgreich, weil:
1. Interaktives Terminal → Aider nutzt stdin direkt
2. `--yes-always` flag → akzeptiert automatisch alle Prompts
3. Die "Antwort" im Preflight war vermutlich nur "echo test" als Text, kein echter API-Call nötig ODER litellm verhält sich im interaktiven Modus anders

**Aber:** Der Preflight testet nur ob Aider **startet**, nicht ob der komplette API-Throughput funktioniert.

---

## 2. Die Blackbox-Frage: Arbeitet Aider im Container?

**Nein.** Aider läuft auf dem Host, nicht im SWE-bench Docker-Container. Die Architektur ist:

```
Host (Aider + MiniMax API)
  └── /tmp/swebench-aider-XXXX/repo/     ← lokales Git-Repo mit base_commit
        └── git diff.patch                ← Aiders Output

Docker Container (SWE-bench Eval)
  └── wird separat gestartet
  └── zieht predictions.jsonl
  └── wertet Patch aus
  └── läuft 6 Sekunden
```

Aider hat also **alle Permissions** auf dem Host-Dateisystem. Die Frage nach Permissions ist hier nicht das Problem.

---

## 3. Warum hat Aider/MiniMax versagt?

### Drei mögliche Ursachen

**A) Model-String-Format (wahrscheinlichste Ursache)**

Litellm (das Aider intern nutzt) kennt `MiniMax-M2.7-highspeed` nicht nativ. Es braucht das OpenAI-kompatible Format:

```
FALSCH:  MiniMax-M2.7-highspeed
RICHTIG: openai/MiniMax-M2.7-highspeed   ← mit Provider-Präfix
```

`preflight.py` testet den Echo-Test mit `--model MiniMax-M2.7-highspeed` und meint "funktioniert", aber der Echo-Test misst nur ob Aider startet, nicht ob API-Calls durchgehen.

**B) Environment Variables nicht in Subprocess**

`subprocess_env()` setzt `OPENAI_API_KEY` und `OPENAI_API_BASE`, aber Aider/litellm sucht möglicherweise nach `MINIMAX_API_KEY` direkt. In nicht-interaktiven Modus (stdin kein TTY) ist das Verhalten anders.

**C) Litellm-Version-Inkompatibilität**

Aider 0.86.2 hat ein `LiteLLMExceptions`-Modul das nach `litellm.BadGatewayError` sucht — das Attribut fehlte im ersten Smoke-Test. Möglicherweise ist auch die Provider-Routing-Logik in dieser Version anders.

---

## 4. Was die Logs zeigen

| Log-Datei | Inhalt | Befund |
|---|---|---|
| `agent_stdout.log` | `litellm.BadRequestError: LLM Provider NOT provided` | **Kritisch: API-Call fand nie statt** |
| `agent_stderr.log` | Repo-Scan 0-100%, "Input is not a terminal" | Scan OK, aber kein API-Call |
| `tokens_in` | `null` | Kein Token-Exchange |
| `tokens_out` | `null` | Kein Token-Exchange |
| `git_diff.patch` | Nur `.aider*` in `.gitignore` | Aiders Auto-Feature, nicht vom Model |
| `tests.json` | 21/22 PASS, 0/1 FAIL | `test_immutable` failed (erwartet ohne Bugfix) |
| `eval_stdout.log` | Docker Eval: resolved=0, 6s | SWE-bench Eval-Pipeline funktioniert einwandfrei |

---

## 5. Offene Fragen

1. **Warum war der Preflight-Echo-Test erfolgreich?** Wurde dort wirklich ein API-Call gemacht?
2. **Welches Model-String-Format nutzt Litellm für MiniMax?** `openai/MiniMax-M2.7-highspeed` oder `minimax/MiniMax-M2.7-highspeed`?
3. **Wurden die Environment Variables korrekt an Aiders Subprocess durchgereicht?**
4. **Was ist mit `tokens_in: null` passiert?** `extract_token_counts()` parsed Aiders Output — fand nichts weil nie ein API-Call stattfand.
5. **Wie bewerte ich das Ergebnis?** 21/22 Tests = 95.5% PASS — aber nur weil das Model NICHTS gemacht hat (PASS_TO_PASS sind die Tests die vorher schon passen). Das ist **nicht** ein gutes Zeichen.

---

## 6. Geplanter Fix-Iteration

### Step 1: Model-String korrigieren

```python
# config.py — subprocess_env()
# Bereits korrekt:
# env["OPENAI_API_KEY"] = config.minimax_api_key
# env["OPENAI_BASE_URL"] = config.minimax_base_url   # https://api.minimax.io/v1
# ABER: model muss als openai/MiniMax-... angegeben werden
```

In `.env`:
```
AIDER_MODEL=openai/MiniMax-M2.7-highspeed
```

### Step 2: Preflight verbessern

Preflight's `aider_echo_test()` sollte prüfen ob ein echter API-Call stattfand:
- Tokens > 0 in agent_stdout
- Kein litellm BadRequestError

### Step 3: Nochmal E2E mit `openai/MiniMax-M2.7-highspeed`

### Step 4: Prüfen ob Litellm MiniMax als Custom-Provider kennt

```bash
# Testen ob MiniMax als Custom-Provider funktioniert
python3 -c "
import litellm
response = litellm.completion(
    model='openai/MiniMax-M2.7-highspeed',
    messages=[{'role': 'user', 'content': 'Say exactly one word: hi'}],
    api_key='...',
    api_base='https://api.minimax.io/v1'
)
print(response)
"
```

---

## 7. Erkenntnisse für die Methode

1. **Preflight ist nicht genug** — ein erfolgreicher Preflight bedeutet nicht dass der komplette Throughput funktioniert
2. **Model-String-Format ist kritisch** — Litellm-spezifisch, nicht intuitiv
3. **Die SWE-bench Eval Pipeline** (Docker) funktioniert einwandfrei — 6s für eval, alles grün
4. **95.5% PASS ist irreführend** — das sind nur PASS_TO_PASS Tests die schon vorher passen; der FAIL_TO_PASS (`test_immutable`) ist 0/1
5. **Ohne echten API-Call ist das Experiment wertlos** — tokens_in=null bedeutet das Model hat das Problem nie gesehen

---

## 8. Geplante Schritte bis nächster Run

| # | Aktion | Aufwand |
|---|---|---|
| 1 | `.env`: `AIDER_MODEL=openai/MiniMax-M2.7-highspeed` setzen | 1 min |
| 2 | Prüfen ob `litellm.completion(openai/MiniMax-M2.7-highspeed)` in uv venv funktioniert | 5 min |
| 3 | Preflight mit echtem API-Call-Test erweitern | 15 min |
| 4 | Neuen E2E Run starten mit korrigiertem Model-String | 15 min |
| 5 | Prüfen ob tokens_in > 0 und ob ein realer Patch entsteht | 5 min |

**Ergebnis-Check:** Nächster Run ist nur dann brauchbar wenn `tokens_in > 0` UND `tokens_out > 0` UND der Patch mehr als nur `.aider*` ist.
