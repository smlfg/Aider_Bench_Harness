# Plan: Aider öffnet bei jedem Start https://aider.chat/docs/llms/warnings.html

## Goal
Verhindern dass Aider bei jedem Start einen Browser-Tab mit `https://aider.chat/docs/llms/warnings.html` öffnet.

## Current Context
- Aider startet via `uv run aider` im Projekt-venv
- Bei jedem Start öffnet sich automatisch ein Browser-Tab mit der Aider-Warnings-Dokumentation
- Das passiert sowohl interaktiv als auch im Headless-Modus (non-interactive)
- Samuel findet das störend

## Annahmen
- Dies ist ein bekanntes Aider-Verhalten, das mit LLM-Warnungen zusammenhängt (z.B. Model-Warnungen, API-Warnungen)
- Aider nutzt möglicherweise `webbrowser.open()` oder ähnliches um die URL zu öffnen
- Die URL deutet darauf hin dass Aider den LLM-Provider warnt (die MiniMax-Warnungen über den Model-Namen)

## Proposed Approach
1. **Diagnose**: Finden was genau den Browser-Aufruf auslöst — Suchen im Aider-Code nach `webbrowser.open` oder `aider.chat/docs/llms/warnings`
2. **Environment-Variable checken**: Aider hat möglicherweise eine `--no-browser` oder `AIDER_NO_BROWSER` Option
3. **Config-Option**: Prüfen ob Aider eine Config-Option hat um Browser-Öffnen zu deaktivieren
4. **Alternative**: Falls es eine Aider-Option ist, in `.env` oder Aider-Config setzen

## Step-by-Step Plan

### Step 1: Im Aider-Venv den Source durchsuchen
```bash
cd /home/smlflg/Projekte/FirstRealHarnessEvaluation_KarpathiesMD
uv run python -c "import aider; print(aider.__file__)"
grep -r "warnings.html" ~/.local/lib/python3.12/site-packages/aider/ 2>/dev/null || \
grep -r "webbrowser.open" ~/.local/lib/python3.12/site-packages/aider/ 2>/dev/null
```

### Step 2: Aider CLI Options für Browser prüfen
```bash
uv run aider --help | grep -i browser
uv run aider --help | grep -i web
```

### Step 3: Environment-Variable checken
```bash
# Aider könnte via ENV steuerbar sein
env | grep -i AIDER
# Prüfe ob --no-browser oder ähnliches existiert
```

### Step 4: Wenn Ursache gefunden, beheben
- Falls es ein Flag ist: `--no-browser` oder `AIDER_NO_BROWSER=1`
- Falls es vom LLM-Provider kommt: Model-Namen in Aider-Config oder `.env` anpassen
- Falls es ein Bug ist: Issue checken oder downgrade/upgrade

## Files likely to change
- `.env` (falls neue ENV-Variable nötig)
- Evtl. `~/.aider.conf.yml` oder Projekt-Aider-Config

## Risks & Tradeoffs
- `--no-browser` Flag könnte im headless Mode bereits aktiv sein — das Problem tritt trotzdem auf
- Es könnte ein Aider-Bug sein der behoben werden muss (neue Version)
- Es könnte mit dem MiniMax-Provider zusammenhängen (falsche Model-Warnung löst Browser-Öffnen aus)

## Open Questions
1. Tritt das auch mit anderen Models auf (z.B. `minimax/MiniMax-M2.1`) oder nur mit `MiniMax-M2.7`?
2. Passiert es auch beim direkten interaktiven Aider-Aufruf oder nur im Harness-Kontext?
3. Ist es ein Headless-Problem oder auch im normalen Terminal?
