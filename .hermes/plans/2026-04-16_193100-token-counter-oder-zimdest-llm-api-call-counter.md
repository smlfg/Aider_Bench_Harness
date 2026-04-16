# Plan: Token-Counter / API-Call-Counter für Harness Dashboard

## Goal
Token-Verbrauch und API-Calls pro Run im Dashboard anzeigen — live während der Run läuft, und in den Run-Ergebnissen.

## Current Context
- `runner/tokens.py` hat `extract_token_counts()` das nach Patterns in stdout/stderr sucht
- Aider's Format: `Tokens: 2.0k sent, 337 received.` oder `163k sent, 26k received.`
- Problem: Pattern `INT = r"([0-9][0-9,._]*)"` parsed keine `k`-Suffixe (2.0k = 2000)
- Daher: `tokens_in: null, tokens_out: null` obwohl Aider Token-Zahlen ausgibt
- Dashboard zeigt `tokens_in`, `tokens_out`, `cost_estimate` aus `run_meta.json`

## Proposed Approach

### Phase 1: Fix token extraction (2 Änderungen)

**`runner/tokens.py`**:
- Neues Pattern: `Tokens: N sent, M received.` — Aider's Format
- Parse-Funktion die `k` (×1000) und `M` (×1,000,000) suffixehandled
- Alternativ: `api_count` — zähle wie oft `Tokens:` in Logs vorkommt = API-Calls

**`runner/run_once.py`**:
- Nach Run-Ende: `extract_token_counts()` + `estimate_agent_cost()` schreibt in `run_meta.json`
- Bereits implementiert aber broken wegen pattern

### Phase 2: Live Token-Counter im Dashboard

**`web/static/app.js`** (wenn live-monitor wiederkommt):
- Token-Zahlen live aus SSE-Log-Stream extrahieren
- Anzeige: "In: 84k | Out: 26k | $0.00123 | Calls: 3"

**`server.py`**:
- `/api/runs/{run_id}` soll tokens aus `run_meta.json` zurückgeben

### Phase 3: API-Call Counter

Aider logged bei jedem API-Call: `Tokens: N sent, M received.`
→ Zählen wie oft dieser String vorkommt = Anzahl API-Calls.

## Step-by-Step Plan

### Step 1: Aider Token-Pattern in tokens.py fixen
```python
# Neues Pattern für Aider Format
(re.compile(r"Tokens:\s*([\d.]+[kKmM]?)\s+sent,\s*([\d.]+[kKmM]?)\s+received", re.I), "aider_tokens"),

def _parse_token_value(raw: str) -> int:
    """Parse token values like '2.0k', '163k', '26M' into int."""
    raw = raw.strip()
    if raw[-1].lower() == 'k':
        return int(float(raw[:-1]) * 1000)
    if raw[-1].lower() == 'm':
        return int(float(raw[:-1]) * 1_000_000)
    return int(raw.replace(",", ""))
```

### Step 2: API-Call Counter Funktion
```python
def count_api_calls(text: str) -> int:
    """Count how many API calls Aider made by counting 'Tokens:' lines."""
    return len(re.findall(r"Tokens:\s*[\d.]+[kKmM]?\s+sent", text, re.I))
```

### Step 3: Test auf Run #3 logs
```bash
python3 -c "
from runner.tokens import extract_token_counts
with open('results/baseline/sympy__sympy-20590/baseline_sympy__sympy-20590_run03/agent_stdout.log') as f:
    text = f.read()
tokens_in, tokens_out = extract_token_counts(text)
print(f'tokens_in={tokens_in}, tokens_out={tokens_out}')
# Aider format zählen
import re
matches = re.findall(r'Tokens:\s*([\d.]+[kKmM]?)\s+sent,\s*([\d.]+[kKmM]?)\s+received', text, re.I)
print(f'API calls: {len(matches)}')
# Summe
total_in = sum(int(float(m[0][:-1])*1000) if m[0][-1]=='k' else int(m[0]) for m in matches)
total_out = sum(int(float(m[1][:-1])*1000) if m[1][-1]=='k' else int(m[1]) for m in matches)
print(f'total_in={total_in}, total_out={total_out}')
"
```

### Step 4: Live Dashboard — Token-Anzeige im inline Monitor
- SSE log-stream parsen mit gleichem Pattern
- Zeige: "Calls: 3 | In: 84k | Out: 26k | $0.00123"
- Aktualisiere bei jedem `Tokens:` match

### Step 5: `/api/runs/{run_id}` um tokens erweitern
Falls `run_meta.json` tokens enthält, in API Response aufnehmen.

## Files likely to change
- `runner/tokens.py` — Pattern + parse Funktion
- `web/static/app.js` — Token-Anzeige (wenn live-monitor aktiv)
- `web/static/index.html` — Token-Spalte in Live-Tabelle

## Risks & Tradeoffs
- `k` suffix parsing muss robust sein (2.0k, 163k, keine Spaces)
- Dashboard braucht `run_meta.json` mit tokens_in/tokens_out — das wird erst nach Phase 1 funktionieren
- Token-Zahlen sind kumuliert pro Call, nicht summiert — muss über alle Calls aufsummieren

## Open Questions
1. Sollen die Token-Summen über alle API-Calls summiert werden, oder nur den letzten Call anzeigen?
2. Soll ein "Budget Tracker" rein — wie viel des MiniMax-Limits verbraucht?
3. Reichen API-Calls als Metrik, oder brauchen wir unbedingt absolute Token-Zahlen?
