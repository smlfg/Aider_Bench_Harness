# Plan: Live-Monitor inline im Dashboard

## Goal
Samuel sieht im Dashboard http://127.0.0.1:8420/ in Echtzeit was Aider macht — ohne CLI, ohne auf meine Reports angewiesen zu sein.

## Current Context
- Dashboard auf Port 8420, Vanilla-JS + FastAPI
- Live-Tab: Tabelle mit Runs, 5s Polling auf `/api/status`
- Monitor-Overlay: SSE-Stream `/api/runs/{runId}/stream` existiert bereits (app.js openMonitor())
- Problem: Monitor ist SEPARAT vom Live-Tab — muss manuell öffnen. Ausserdem: CLI-Runs (harness-run-once vom Terminal) erzeugen KEINE `_active_run` → Dashboard weiss nicht dass was läuft.

## Root Cause: CLI vs Dashboard Runs
Das Dashboard tracked nur Runs die über seine `/api/runs` POST-Endpoint gestartet werden.
CLI-Runs (`uv run harness-run-once ...`) → `_active_run` bleibt `None` → `/api/running` = `{"running": false}` → kein Live-Monitor.

**Lösung:** Dashboard polled aktiv das results/ Verzeichnis statt nur `_active_run` zu checken.

## Proposed Approach

### Phase 1: Dashboard pollt results/ Verzeichnis (nicht _active_run)
Server `/api/running` → sucht nach dem neuesten `.phase` file in results/ das nicht "done" ist.
Alternativ: App pollt ein "running from filesystem" pattern.

### Phase 2: Inline Live-Monitor in Live-Tab
Wenn ein Run aktiv ist:
- Panel unter der Tabelle: Live-Aider-Log (SSE gestreamt)
- Token-Counter (aus Logs)
- Phase-Badge
- "Open Full Monitor" Button

### Phase 3: Patch-Vorschau
Patch aus `git_diff.patch` live anzeigen während Aider läuft.

## Step-by-Step Plan

### Step 1: Server — `/api/running` erweitern
Check auch results/ Verzeichnis wenn `_active_run` None ist:
```python
# server.py /api/running
def _find_running_from_filesystem():
    """Check if any run is active by looking at .phase files."""
    results = Path("results")
    if not results.exists():
        return None
    now = time.time()
    for phase_file in results.rglob(".phase"):
        phase = phase_file.read_text().strip()
        if phase in ("done", "error", "setup_repo", "aider_running", "docker_eval"):
            mtime = phase_file.stat().st_mtime
            age = now - mtime
            # Active if touched in last 5 minutes
            if age < 300 and phase not in ("done", "error"):
                run_id = phase_file.parent.name
                task_id = run_id.split("_", 1)[1].rsplit("_run", 1)[0]
                return {"run_id": run_id, "task_id": task_id, "phase": phase}
    return None
```

### Step 2: HTML — Inline-Panel in Live-Tab
Bekanntes HTML-Fragment (aus vorherigem Versuch):
```html
<div id="live-monitor" style="display:none;">
  <div class="live-monitor-header">
    <span id="lm-run-id"></span>
    <span class="badge" id="lm-phase">init</span>
    <span id="lm-timer">0s</span>
    <span id="lm-tokens"></span>
  </div>
  <pre id="lm-output" class="log-viewer"></pre>
</div>
```

### Step 3: app.js — SSE-Streaming in loadLive()
Globals:
```javascript
let liveMonitorES = null;
let liveMonitorRunId = null;
let liveMonitorTimer = null;
```

loadLive() Erweiterung:
```javascript
// Nach bestehendem Banner-Code:
// ── Inline Live Monitor ──
if (running.running) {
  const panel = document.getElementById('live-monitor');
  panel.style.display = 'block';
  document.getElementById('lm-run-id').textContent = running.run_id;
  if (liveMonitorRunId !== running.run_id) {
    liveMonitorClose();
    liveMonitorRunId = running.run_id;
    liveMonitorStartTime = Date.now();
    liveMonitorOpen(running.run_id);
  }
}
```

liveMonitorOpen() + liveMonitorClose() —bekannte Implementierung aus vorherigem Versuch.

### Step 4: CSS
Bekanntes CSS aus vorherigem Versuch (inline-monitor-panel styling).

### Step 5: Token-Counter live
Regex auf SSE-Log-Stream:
```javascript
const tokenRe = /Tokens:\s*([\d.]+[kKmM]?)\s+sent,\s*([\d.]+[kKmM]?)\s+received/gi;
```
Zeige: "In: 84k | Out: 26k | Calls: 3"

### Step 6: Test mit Run #5
Run #5 (nächster) sollte automatisch im Dashboard live auftauchen.

## Files likely to change
- `web/server.py` — `_find_running_from_filesystem()` + `/api/running`
- `web/static/index.html` — `#live-monitor` div
- `web/static/app.js` — globals + loadLive() + liveMonitorOpen/Close
- `web/static/style.css` — panel styling

## Risks & Tradeoffs
- Filesystem-Polling kann falsch-positive liefern wenn Docker-Container hängt
- SSE muss robust sein gegen temporäre Netzwerkfehler
- Panel sollte nicht flackern wenn mehrere Runs gleichzeitig

## Open Questions
1. Reicht der filesystem-check alle 5s (wie bestehendes live-Polling)?
2. Soll das Panel auto-scroll zum neuesten Log machen?
3. Patch-Preview: wie gross darf die Datei sein bevor es langsam wird?
