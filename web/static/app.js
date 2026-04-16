const C = window.HarnessCharts;
let liveInterval = null;
let monitorEventSource = null;
let currentMonitorRunId = null;
let allRuns = [];

// Inline live monitor state
let liveMonitorES = null;
let liveMonitorRunId = null;
let liveMonitorTimer = null;
let liveMonitorStartTime = null;

// ── Tab switching ──────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    if (btn.dataset.tab === 'iteration') { iterLoaded = false; loadIteration(); }
    if (btn.dataset.tab === 'trajectory') { trajectoryLoaded = false; loadTrajectory(); }
    if (btn.dataset.tab === 'runs') { runsLoaded = false; loadRuns(); }
    if (btn.dataset.tab === 'launch') initLaunch();
  });
});

// ── Helpers ────────────────────────────────────────
async function api(url, opts) {
  const resp = await fetch(url, opts);
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`${resp.status}: ${text}`);
  }
  const ct = resp.headers.get('content-type') || '';
  if (ct.includes('application/json')) return resp.json();
  return resp;
}

function fmtDuration(s) {
  if (s == null) return '-';
  if (s < 60) return `${s.toFixed(1)}s`;
  if (s < 3600) return `${(s/60).toFixed(1)}m`;
  return `${(s/3600).toFixed(1)}h`;
}

function successBadge(val) {
  if (val == null) return '<span class="badge badge-dim">?</span>';
  return val ? '<span class="badge badge-green">PASS</span>' : '<span class="badge badge-red">FAIL</span>';
}

function statusBadge(r) {
  if (r.infrastructure_error) return '<span class="badge badge-red">INFRA ERR</span>';
  if (r.task_success) return '<span class="badge badge-green">PASS</span>';
  if (r.failure_kind === 'task_failure') return '<span class="badge badge-yellow">FAIL</span>';
  if (r.end_ts == null) return '<span class="badge badge-dim">RUNNING</span>';
  return '<span class="badge badge-red">FAIL</span>';
}

function judgeBadge(score) {
  if (score == null) return '<span class="badge badge-dim">-</span>';
  const cls = score >= 4 ? 'badge-green' : score >= 2.5 ? 'badge-yellow' : 'badge-red';
  return `<span class="badge ${cls}">${score.toFixed(1)}</span>`;
}

function fmtDelta(val, higherIsGood) {
  if (val == null) return '-';
  const sign = val > 0 ? '+' : '';
  const cls = higherIsGood ? (val > 0 ? 'positive' : val < 0 ? 'negative' : '') : (val < 0 ? 'positive' : val > 0 ? 'negative' : '');
  return `<span class="delta ${cls}">${sign}${val.toFixed(3)}</span>`;
}

function escHtml(s) { return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function formatPatch(text) {
  return text.split('\n').map(line => {
    if (line.startsWith('+++') || line.startsWith('---') || line.startsWith('@@')) return `<span class="line-hunk">${escHtml(line)}</span>`;
    if (line.startsWith('+')) return `<span class="line-add">${escHtml(line)}</span>`;
    if (line.startsWith('-')) return `<span class="line-remove">${escHtml(line)}</span>`;
    return escHtml(line);
  }).join('\n');
}

function renderActiveRunLinks(activeRuns) {
  if (!activeRuns || activeRuns.length === 0) return '';
  return activeRuns.map(r => {
    const phase = r.phase ? ` <span class="badge badge-dim">${escHtml(r.phase)}</span>` : '';
    return `<a href="#" onclick="openMonitor(${JSON.stringify(r.run_id)});return false;">${escHtml(r.run_id)}</a>${phase}`;
  }).join(' · ');
}

// ── TAB: Live Monitor ──────────────────────────────
async function loadLive() {
  try {
    const data = await api('/api/status');
    const running = await api('/api/runs/active');
    const activeRuns = running.active_runs || [];
    const activeCount = running.active_run_count ?? running.active_count ?? activeRuns.length;
    const activeLimit = running.max_active_runs ?? running.limit ?? 10;
    const tbody = document.getElementById('live-tbody');
    tbody.innerHTML = data.map(r => {
      const diff = (r.lines_added || 0) + (r.lines_removed || 0);
      const tests = (r.tests_passed == null || r.tests_total == null) ? '-' : `${r.tests_passed}/${r.tests_total}`;
      return `<tr class="clickable-row" data-run-id="${r.run_id}">
        <td><span class="status-dot ${r.end_ts ? (r.infrastructure_error ? 'error' : 'completed') : 'running'}"></span></td>
        <td>${r.run_id}</td>
        <td>${r.task_id}</td>
        <td>${r.condition_id}</td>
        <td>${r.iteration}</td>
        <td>${statusBadge(r)}</td>
        <td>${tests}</td>
        <td>${fmtDuration(r.duration_seconds)}</td>
        <td>${diff}</td>
        <td>${r.infrastructure_error ? `<span class="badge badge-red infra-badge" title="${escHtml(r.error_detail || '').substring(0, 300)}">YES</span>` : '-'}</td>
      </tr>`;
    }).join('');
    tbody.querySelectorAll('tr').forEach(tr => {
      tr.addEventListener('click', () => openDebrief(tr.dataset.runId));
    });
    const banner = document.getElementById('live-running-banner');
    if (activeCount > 0) {
      banner.style.display = 'block';
      banner.innerHTML = `Active runs (${activeCount}/${activeLimit}): ${renderActiveRunLinks(activeRuns)}`;
    } else {
      banner.style.display = 'none';
    }

    const launchBanner = document.getElementById('launch-blocking-banner');
    const launchBtn = document.getElementById('launch-btn');
    if (launchBanner) {
      if (activeCount >= activeLimit) {
        launchBanner.style.display = 'block';
        launchBanner.innerHTML = `Run cap reached (${activeCount}/${activeLimit}). Wait for a slot or open one of the active runs above.`;
      } else if (activeCount > 0) {
        launchBanner.style.display = 'block';
        launchBanner.innerHTML = `Active runs (${activeCount}/${activeLimit}): ${renderActiveRunLinks(activeRuns)}`;
      } else {
        launchBanner.style.display = 'none';
        launchBanner.innerHTML = '';
      }
    }
    if (launchBtn) {
      launchBtn.disabled = activeCount >= activeLimit;
    }

    // ── Inline Live Monitor (SSE) ──
    const panel = document.getElementById('live-monitor');
    if (activeCount > 0) {
      const current = activeRuns.find(r => r.run_id === liveMonitorRunId);
      const target = current || activeRuns[0];
      panel.style.display = 'block';
      document.getElementById('lm-run-id').textContent = target.run_id;
      document.getElementById('lm-open-btn').onclick = () => openMonitor(target.run_id);
      if (liveMonitorRunId !== target.run_id) {
        liveMonitorClose();
        liveMonitorRunId = target.run_id;
        liveMonitorStartTime = Date.now();
        liveMonitorOpen(target.run_id);
      }
    } else {
      panel.style.display = 'none';
      liveMonitorClose();
    }
  } catch(e) { console.error('Live load failed:', e); }
}

// ── TAB: Launch ────────────────────────────────────
let tasksLoaded = false;
async function initLaunch() {
  if (!tasksLoaded) {
    try {
      const tasks = await api('/api/tasks');
      const sel = document.getElementById('launch-task');
      sel.innerHTML = '<option value="">Select task...</option>' + tasks.map(t =>
        `<option value="${t.instance_id}">${t.instance_id} — ${t.repo || '?'}</option>`
      ).join('');
      sel.addEventListener('change', loadTaskPreview);
      tasksLoaded = true;
    } catch(e) { console.error('Tasks load failed:', e); }
    try {
      const convs = await api('/api/conventions');
      const sel2 = document.getElementById('launch-conventions');
      sel2.innerHTML = '<option value="">Default (CONVENTIONS.baseline.md)</option>' + convs.map(c =>
        `<option value="${c.path}">${c.name} (${c.hash.slice(0,8)})</option>`
      ).join('');
    } catch(e) { console.error('Conventions load failed:', e); }
  }
  updateLaunchPreview();
  try {
    const runs = await api('/api/runs');
    const avg = runs.filter(r => r.cost_estimate).reduce((s, r) => s + (r.cost_estimate || 0), 0) / (runs.filter(r => r.cost_estimate).length || 1);
    if (avg > 0) {
      document.getElementById('launch-cost-estimate').style.display = 'block';
      document.getElementById('launch-avg-cost').textContent = `$${avg.toFixed(4)}`;
    }
  } catch(e) {}
  document.getElementById('launch-btn').addEventListener('click', launchRun);
}

async function loadTaskPreview() {
  const taskId = document.getElementById('launch-task').value;
  const preview = document.getElementById('task-preview');
  const content = document.getElementById('task-preview-content');
  if (!taskId) { preview.style.display = 'none'; return; }
  try {
    const task = await api(`/api/tasks/${taskId}`);
    preview.style.display = 'block';
    content.textContent = `Repo: ${task.repo}\nBase: ${task.base_commit}\n\n${task.problem_statement}`;
  } catch(e) { content.textContent = 'Task not found'; }
  updateLaunchPreview();
}

function updateLaunchPreview() {
  const taskId = document.getElementById('launch-task').value;
  const condition = document.getElementById('launch-condition').value || 'baseline';
  const iter = document.getElementById('launch-iteration').value || '1';
  const ri = document.getElementById('launch-run-index').value || '1';
  const preview = document.getElementById('launch-preview');
  if (!taskId) { preview.style.display = 'none'; return; }
  const cleanTask = taskId.replace('/', '__');
  const runId = `${condition}_${cleanTask}_run${String(ri).padStart(2, '0')}`;
  preview.style.display = 'block';
  document.getElementById('launch-preview-text').textContent = `Run ID: ${runId} | Iteration: ${iter}`;
}

async function launchRun() {
  const taskId = document.getElementById('launch-task').value;
  if (!taskId) return;
  const btn = document.getElementById('launch-btn');
  btn.disabled = true;
  btn.textContent = 'Starting...';
  try {
    const body = {
      task_id: taskId,
      condition: document.getElementById('launch-condition').value || 'baseline',
      iteration: parseInt(document.getElementById('launch-iteration').value) || 1,
      run_index: parseInt(document.getElementById('launch-run-index').value) || 1,
    };
    const convPath = document.getElementById('launch-conventions').value;
    if (convPath) body.conventions_path = convPath;
    const result = await api('/api/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    openMonitor(result.run_id);
  } catch(e) {
    alert('Failed to start run: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Start Run';
  }
}

// ── Monitor ───────────────────────────────────────
function openMonitor(runId) {
  currentMonitorRunId = runId;
  document.getElementById('monitor-overlay').style.display = 'block';
  document.getElementById('monitor-title').textContent = `Monitor: ${runId}`;
  document.getElementById('monitor-events-content').innerHTML = '';
  document.getElementById('mq-output-content').textContent = '';
  document.getElementById('mq-patch-content').textContent = '(waiting for patch...)';
  document.getElementById('mq-task-content').textContent = 'Loading...';
  document.getElementById('mq-conventions-content').textContent = 'Loading...';

  if (monitorEventSource) { monitorEventSource.close(); }
  monitorEventSource = new EventSource(`/api/runs/${runId}/stream`);
  let startTime = Date.now();

  monitorEventSource.addEventListener('phase', (e) => {
    const d = JSON.parse(e.data);
    const statusEl = document.getElementById('monitor-status');
    statusEl.textContent = d.phase;
    statusEl.className = 'badge ' + (d.phase === 'done' ? 'badge-green' : d.phase === 'error' ? 'badge-red' : 'badge-yellow');
    addEvent(`Phase: ${d.phase}`, 'evt-phase');
    if (d.phase === 'done') {
      addEvent('Run complete. Redirecting to debrief...', 'evt-done');
      setTimeout(() => { closeMonitor(); openDebrief(runId); }, 1500);
    }
    if (d.phase === 'aider_running') startTime = Date.now();
  });

  monitorEventSource.addEventListener('log', (e) => {
    const d = JSON.parse(e.data);
    const out = document.getElementById('mq-output-content');
    out.textContent += d.content;
    out.scrollTop = out.scrollHeight;
  });

  monitorEventSource.addEventListener('patch_changed', (e) => {
    const d = JSON.parse(e.data);
    const patchEl = document.getElementById('mq-patch-content');
    if (d.patch) {
      patchEl.innerHTML = formatPatch(d.patch);
    } else {
      patchEl.textContent = `Files: ${d.files_changed}, +${d.lines_added}/-${d.lines_removed}`;
    }
    addEvent(`Patch updated: ${d.files_changed} files, +${d.lines_added}/-${d.lines_removed}`, 'evt-patch');
  });

  monitorEventSource.addEventListener('done', (e) => {
    addEvent('Stream ended.', 'evt-done');
    monitorEventSource.close();
  });

  monitorEventSource.onerror = () => {
    monitorEventSource.close();
  };

  // Timer
  const timerEl = document.getElementById('monitor-timer');
  const timerInterval = setInterval(() => {
    timerEl.textContent = fmtDuration((Date.now() - startTime) / 1000);
    if (document.getElementById('monitor-overlay').style.display === 'none') clearInterval(timerInterval);
  }, 1000);

  // Abort button
  document.getElementById('monitor-abort-btn').style.display = 'inline-block';
  document.getElementById('monitor-abort-btn').onclick = async () => {
    try { await api(`/api/runs/${runId}/abort`, { method: 'POST' }); } catch(e) { alert(e.message); }
  };

  // Load task info
  api(`/api/runs/${runId}`).then(r => {
    api(`/api/tasks/${r.task_id}`).then(t => {
      document.getElementById('mq-task-content').textContent = `${t.instance_id}\n\n${t.problem_statement}`;
    }).catch(() => {
      document.getElementById('mq-task-content').textContent = `Task: ${r.task_id}`;
    });
    if (r.conventions_path) {
      api(`/api/conventions`).then(convs => {
        const c = convs.find(c => c.path === r.conventions_path);
        document.getElementById('mq-conventions-content').textContent = c ? c.content : r.conventions_path;
      }).catch(() => {
        document.getElementById('mq-conventions-content').textContent = r.conventions_path;
      });
    }
  }).catch(() => {});

  // Close button
  document.getElementById('monitor-close-btn').onclick = closeMonitor;
}

function closeMonitor() {
  document.getElementById('monitor-overlay').style.display = 'none';
  if (monitorEventSource) { monitorEventSource.close(); monitorEventSource = null; }
}

function addEvent(text, cls) {
  const el = document.getElementById('monitor-events-content');
  const line = document.createElement('div');
  line.className = 'evt ' + (cls || '');
  line.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
  el.appendChild(line);
  el.scrollTop = el.scrollHeight;
}

// ── Debrief ────────────────────────────────────────
async function openDebrief(runId) {
  currentMonitorRunId = runId;
  document.getElementById('debrief-overlay').style.display = 'block';

  try {
    const r = await api(`/api/runs/${runId}`);
    const diff = (r.lines_added || 0) + (r.lines_removed || 0);

    // Verdict
    const vEl = document.getElementById('debrief-verdict');
    let cls, text;
    if (r.infrastructure_error) {
      cls = 'verdict-banner infra-error'; text = '\u{1F6AB} INFRASTRUCTURE ERROR \u2014 this run does NOT count for statistics';
    } else if (r.task_success) {
      cls = 'verdict-banner task-success'; text = '\u2705 TASK SUCCESS';
    } else {
      cls = 'verdict-banner task-failure'; text = '\u26A0\uFE0F TASK FAIL (agent error)';
    }
    vEl.className = cls;
    vEl.textContent = text;

    // Error detail block (visible only on infra errors)
    const errDetailEl = document.getElementById('debrief-error-detail');
    if (r.infrastructure_error && r.error_detail) {
      errDetailEl.style.display = 'block';
      errDetailEl.textContent = r.error_detail;
    } else {
      errDetailEl.style.display = 'none';
    }

    // Stats
    document.getElementById('debrief-stats').innerHTML = `
      <div class="stat-card"><div class="label">Task</div><div class="value" style="font-size:13px">${r.task_id}</div></div>
      <div class="stat-card"><div class="label">Condition</div><div class="value">${r.condition_id}</div></div>
      <div class="stat-card"><div class="label">Success</div><div class="value">${successBadge(r.task_success)}</div></div>
      <div class="stat-card"><div class="label">Tests</div><div class="value">${r.tests_passed}/${r.tests_total}</div></div>
      <div class="stat-card"><div class="label">Duration</div><div class="value">${fmtDuration(r.duration_seconds)}</div></div>
      <div class="stat-card"><div class="label">Diff</div><div class="value">${diff} LOC</div></div>
      <div class="stat-card"><div class="label">Infra Error</div><div class="value">${r.infrastructure_error ? '<span class="badge badge-red">YES</span>' : 'No'}</div></div>
      <div class="stat-card"><div class="label">Judge</div><div class="value">${judgeBadge(r.judge_score)}</div></div>
    `;

    // Task / Problem Statement
    const taskMetaEl = document.getElementById('debrief-task-meta');
    const taskContentEl = document.getElementById('debrief-task-content');
    try {
      const task = await api(`/api/tasks/${r.task_id}`);
      taskMetaEl.innerHTML = `<span class="badge badge-dim">${escHtml(task.repo || '')}</span> <span class="badge badge-dim">${escHtml((task.base_commit || '').slice(0, 8))}</span>`;
      taskContentEl.textContent = task.problem_statement || '(no problem statement)';
    } catch(_) {
      taskMetaEl.innerHTML = `<span class="badge badge-dim">${escHtml(r.task_id)}</span>`;
      taskContentEl.textContent = '(task details not available)';
    }

    // Conventions / Input Prompt
    const convMeta = document.getElementById('debrief-conventions-meta');
    const convContent = document.getElementById('debrief-conventions-content');
    const convPath = r.conventions_path || '';
    const convName = convPath ? convPath.split('/').pop() : 'unknown';
    const convHash = (r.conventions_hash || '').slice(0, 8);
    const convNote = r.conventions_mutation_note || '';
    convMeta.innerHTML = `<strong>${escHtml(convName)}</strong> <span class="badge badge-dim" title="${escHtml(r.conventions_hash || '')}">${convHash}</span>`
      + (convNote ? ` <span class="badge badge-yellow">${escHtml(convNote)}</span>` : '');
    if (r.conventions_content) {
      convContent.textContent = r.conventions_content;
    } else {
      convContent.textContent = '(conventions content not available)';
    }

    // Judge
    const judgeMetaEl = document.getElementById('debrief-judge-meta');
    const judgeContentEl = document.getElementById('debrief-judge-content');
    const jr = r.judge_result;
    if (jr) {
      const verdict = (jr.verdict || 'mixed').toLowerCase();
      const verdictCls = verdict === 'support' ? 'badge-green' : verdict === 'reject' ? 'badge-red' : 'badge-yellow';
      const score = typeof jr.judge_score === 'number' ? jr.judge_score.toFixed(2) : (jr.judge_score ?? '-');
      judgeMetaEl.innerHTML = `
        <span class="badge ${verdictCls}">${escHtml(verdict.toUpperCase())}</span>
        <span class="badge badge-dim">${escHtml(jr.prompt_version || 'unknown')}</span>
        <span class="badge badge-dim">${escHtml(jr.judge_model || '')}</span>
      `;
      judgeContentEl.innerHTML = `
        <div><strong>Score</strong>: ${escHtml(String(score))}</div>
        <div><strong>Scope</strong>: ${escHtml(String(jr.scope_adherence ?? '-'))}</div>
        <div><strong>Minimality</strong>: ${escHtml(String(jr.minimality ?? '-'))}</div>
        <div><strong>Diff clarity</strong>: ${escHtml(String(jr.diff_clarity ?? '-'))}</div>
        <div style="margin-top:8px;"><strong>Rationale</strong></div>
        <div>${escHtml(jr.rationale || '(missing)')}</div>
        <div style="margin-top:8px;"><strong>Conclusion</strong></div>
        <div>${escHtml(jr.conclusion || '(missing)')}</div>
      `;
    } else {
      judgeMetaEl.innerHTML = '<span class="badge badge-dim">not run yet</span>';
      judgeContentEl.textContent = '(judge_result.json not available)';
    }

    // Artifacts
    if (r.has_git_diff_patch) loadArtifact(runId, 'git_diff.patch', 'debrief-patch', true);
    if (r.has_tests_json) loadArtifact(runId, 'tests.json', 'debrief-tests', false);
    if (r.has_agent_stdout_log) loadArtifact(runId, 'agent_stdout.log', 'debrief-log', false);

    // Debrief actions
    document.getElementById('debrief-dismiss').onclick = () => {
      document.getElementById('debrief-overlay').style.display = 'none';
    };
    document.getElementById('debrief-repeat').onclick = () => {
      document.getElementById('debrief-overlay').style.display = 'none';
      const cleanTask = r.task_id.replace('/', '__');
      const ri = parseInt((r.run_id.match(/run(\d+)$/) || [])[1] || '1') + 1;
      document.getElementById('launch-task').value = r.task_id;
      document.getElementById('launch-condition').value = r.condition_id;
      document.getElementById('launch-iteration').value = r.iteration;
      document.getElementById('launch-run-index').value = ri;
      document.querySelector('[data-tab="launch"]').click();
    };

  } catch(e) {
    document.getElementById('debrief-verdict').textContent = 'Error loading run: ' + e.message;
    document.getElementById('debrief-verdict').className = 'verdict-banner';
  }
}

async function loadArtifact(runId, filename, elementId, isPatch) {
  try {
    const text = await (await fetch(`/api/artifacts/${runId}/${filename}`)).text();
    const el = document.getElementById(elementId);
    if (!el) return;
    if (isPatch) { el.innerHTML = formatPatch(text); }
    else if (filename.endsWith('.json')) { el.textContent = JSON.stringify(JSON.parse(text), null, 2); }
    else { el.textContent = text; }
  } catch(e) {
    const el = document.getElementById(elementId);
    if (el) el.textContent = '(not available)';
  }
}

// ── TAB: Iteration Comparison ─────────────────────
let charts = {};

async function loadIteration() {
  const sel = document.getElementById('iter-select');
  const iters = await api('/api/completed-iterations');
  if (iters.length === 0) { sel.innerHTML = '<option>No iterations yet</option>'; return; }
  const prevVal = sel.value;
  sel.innerHTML = iters.map(i => `<option value="${i}">${i}</option>`).join('');
  if (prevVal && iters.includes(parseInt(prevVal))) sel.value = prevVal;
  sel.onchange = loadIterationData;
  await loadIterationData();
}

async function loadIterationData() {
  const iter = document.getElementById('iter-select').value;
  if (!iter || isNaN(iter)) return;
  const iteration = parseInt(iter);
  const [runs, analysis, comparisons] = await Promise.all([
    api(`/api/runs?iteration=${iteration}`),
    api(`/api/analysis?iteration=${iteration}`),
    api(`/api/comparisons?iteration=${iteration}`),
  ]);
  const conditions = [...new Set(runs.map(r => r.condition_id))];
  const tasks = [...new Set(runs.map(r => r.task_id))];

  const byMetric = {};
  for (const a of analysis) {
    if (!byMetric[a.metric]) byMetric[a.metric] = {};
    byMetric[a.metric][a.condition] = a;
  }

  const verdictEl = document.getElementById('iter-verdict');
  if (comparisons.length === 0) {
    verdictEl.style.display = 'block';
    verdictEl.className = 'verdict-banner no-decision';
    verdictEl.textContent = 'NO DECISION (no candidate data)';
  } else {
    const tsComp = comparisons.find(c => c.metric === 'task_success');
    if (tsComp) {
      const delta = tsComp.delta;
      let cls, text;
      if (delta > 0.01) { cls = 'candidate-wins'; text = `CANDIDATE WINS (\u0394 task_success = +${delta.toFixed(3)})`; }
      else if (delta < -0.01) { cls = 'candidate-loses'; text = `CANDIDATE LOSES (\u0394 task_success = ${delta.toFixed(3)})`; }
      else { cls = 'no-decision'; text = `NO DECISION (\u0394 task_success = ${delta.toFixed(3)})`; }
      verdictEl.style.display = 'block';
      verdictEl.className = `verdict-banner ${cls}`;
      verdictEl.textContent = text;
    } else { verdictEl.style.display = 'none'; }
  }

  // Pareto warning
  const paretoEl = document.getElementById('iter-pareto-warning');
  const dsComp = comparisons.find(c => c.metric === 'diff_size_loc');
  if (tsComp && dsComp) {
    const baselineDS = dsComp.baseline_estimate || 0;
    const deltaDS = (dsComp.candidate_estimate || 0) - baselineDS;
    const pctDS = baselineDS > 0 ? (deltaDS / baselineDS * 100) : 0;
    if (pctDS > 50 && tsComp.delta <= 0) {
      paretoEl.style.display = 'block';
      paretoEl.textContent = `\u26A0\uFE0F PARETO WARNING: Candidate diff_size +${pctDS.toFixed(0)}% at task_success \u0394 \u2264 0.`;
    } else { paretoEl.style.display = 'none'; }
  } else { paretoEl.style.display = 'none'; }

  // Charts
  charts.success = C.destroyChart(charts.success);
  charts.success = C.makeBarChart('chart-success', buildTaskChart(runs, tasks, conditions, 'task_success').labels, buildTaskChart(runs, tasks, conditions, 'task_success').datasets, 'Success Rate');
  charts.passRate = C.destroyChart(charts.passRate);
  charts.passRate = C.makeBarChart('chart-pass-rate', buildTaskChart(runs, tasks, conditions, 'pass_rate').labels, buildTaskChart(runs, tasks, conditions, 'pass_rate').datasets, 'Pass Rate');
  charts.diffSize = C.destroyChart(charts.diffSize);
  charts.diffSize = C.makeBarChart('chart-diff-size', buildTaskChart(runs, tasks, conditions, 'diff_size').labels, buildTaskChart(runs, tasks, conditions, 'diff_size').datasets, 'LOC');
  charts.duration = C.destroyChart(charts.duration);
  charts.duration = C.makeBarChart('chart-duration', buildTaskChart(runs, tasks, conditions, 'duration').labels, buildTaskChart(runs, tasks, conditions, 'duration').datasets, 'Seconds');

  // Stats table
  const tbody = document.getElementById('stats-tbody');
  tbody.innerHTML = comparisons.map(c => `<tr>
    <td>${c.metric}</td>
    <td>${(c.baseline_estimate ?? 0).toFixed?.(3) ?? c.baseline_estimate ?? '-'}</td>
    <td>${(c.candidate_estimate ?? 0).toFixed?.(3) ?? c.candidate_estimate ?? '-'}</td>
    <td>${fmtDelta(c.delta, c.metric !== 'diff_size_loc')}</td>
    <td>${c.test_name}</td>
    <td>${c.p_value != null ? c.p_value.toFixed(4) : '-'}</td>
    <td>${c.effect_size != null ? c.effect_size.toFixed(3) : '-'}</td>
  </tr>`).join('');
}

function buildTaskChart(runs, tasks, conditions, metric) {
  const labels = tasks;
  const datasets = conditions.map((cond) => {
    const color = cond === 'baseline' ? C.COLORS.baseline : C.COLORS.candidate;
    const bgColor = cond === 'baseline' ? C.COLORS.baseline_bg : C.COLORS.candidate_bg;
    const data = tasks.map(task => {
      const taskRuns = runs.filter(r => r.task_id === task && r.condition_id === cond);
      if (taskRuns.length === 0) return 0;
      if (metric === 'task_success') return taskRuns.reduce((s, r) => s + (r.task_success || 0), 0) / taskRuns.length;
      if (metric === 'pass_rate') return taskRuns.reduce((s, r) => s + (r.tests_passed / Math.max(r.tests_total, 1)), 0) / taskRuns.length;
      if (metric === 'diff_size') return taskRuns.reduce((s, r) => s + ((r.lines_added || 0) + (r.lines_removed || 0)), 0) / taskRuns.length;
      if (metric === 'duration') return taskRuns.reduce((s, r) => s + (r.duration_seconds || 0), 0) / taskRuns.length;
      return 0;
    });
    return { label: cond, data, backgroundColor: bgColor, borderColor: color, borderWidth: 1 };
  });
  return { labels, datasets };
}

// ── TAB: Trajectory ───────────────────────────────
let trajectoryLoaded = false;
async function loadTrajectory() {
  if (trajectoryLoaded) return;
  trajectoryLoaded = true;
  const [trajectory] = await Promise.all([api('/api/trajectory')]);
  if (trajectory.length === 0) {
    document.getElementById('traj-tbody').innerHTML = '<tr><td colspan="6" class="loading">No trajectory data. Run harness-analyze first.</td></tr>';
    return;
  }
  const labels = trajectory.map(t => `Iter ${t.iteration}`);
  charts.trajSuccess = C.destroyChart(charts.trajSuccess);
  charts.trajSuccess = C.makeLineChart('chart-traj-success', labels, [{
    label: 'Task Success Rate', data: trajectory.map(t => t.cumulative_success_rate),
    borderColor: C.COLORS.baseline, backgroundColor: C.COLORS.baseline_bg, fill: false, tension: 0.1,
  }], 'Success Rate');
  charts.trajDiff = C.destroyChart(charts.trajDiff);
  charts.trajDiff = C.makeLineChart('chart-traj-diff', labels, [{
    label: 'Mean Diff Size (LOC)', data: trajectory.map(t => t.cumulative_diff_size_loc_mean),
    borderColor: C.COLORS.candidate, backgroundColor: C.COLORS.candidate_bg, fill: false, tension: 0.1,
  }], 'LOC');

  const frontier = trajectory.filter(t => t.pareto_dominated === 0 || t.pareto_dominated === false);
  const dominated = trajectory.filter(t => t.pareto_dominated === 1 || t.pareto_dominated === true);
  charts.pareto = C.destroyChart(charts.pareto);
  charts.pareto = C.makeScatterChart('chart-pareto', [
    { label: 'Frontier', data: frontier.map(t => ({ x: t.cumulative_diff_size_loc_mean, y: t.cumulative_success_rate, iter: t.iteration })), backgroundColor: C.COLORS.frontier, pointRadius: 8 },
    { label: 'Dominated', data: dominated.map(t => ({ x: t.cumulative_diff_size_loc_mean, y: t.cumulative_success_rate, iter: t.iteration })), backgroundColor: C.COLORS.dominated, pointRadius: 6 },
  ], 'Success Rate', 'Diff Size (LOC)');

  const tbody = document.getElementById('traj-tbody');
  tbody.innerHTML = trajectory.map(t => `<tr>
    <td>${t.iteration}</td><td title="${t.conventions_hash}">${(t.conventions_hash || '').slice(0, 8)}</td>
    <td>${t.mutation_note || '-'}</td><td>${t.cumulative_success_rate.toFixed(3)}</td>
    <td>${t.cumulative_diff_size_loc_mean.toFixed(1)}</td>
    <td>${(t.pareto_dominated === 1 || t.pareto_dominated === true) ? '<span class="badge badge-red">DOMINATED</span>' : '<span class="badge badge-green">FRONTIER</span>'}</td>
  </tr>`).join('');
}

// ── TAB: Runs Explorer ─────────────────────────────
let runsLoaded = false;
async function loadRuns() {
  if (runsLoaded) return;
  runsLoaded = true;
  allRuns = await api('/api/runs');
  populateFilters();
  filterRuns();
}

function populateFilters() {
  const conditions = [...new Set(allRuns.map(r => r.condition_id))].sort();
  const iterations = [...new Set(allRuns.map(r => r.iteration))].sort();
  const condSel = document.getElementById('filter-condition');
  condSel.innerHTML = '<option value="">All</option>' + conditions.map(c => `<option value="${c}">${c}</option>`).join('');
  const iterSel = document.getElementById('filter-iteration');
  iterSel.innerHTML = '<option value="">All</option>' + iterations.map(i => `<option value="${i}">${i}</option>`).join('');
  condSel.addEventListener('change', filterRuns);
  iterSel.addEventListener('change', filterRuns);
  document.getElementById('filter-success').addEventListener('change', filterRuns);
}

function filterRuns() {
  const cond = document.getElementById('filter-condition').value;
  const iter = document.getElementById('filter-iteration').value;
  const successOnly = document.getElementById('filter-success').checked;
  let filtered = allRuns;
  if (cond) filtered = filtered.filter(r => r.condition_id === cond);
  if (iter) filtered = filtered.filter(r => r.iteration === parseInt(iter));
  if (successOnly) filtered = filtered.filter(r => r.task_success);
  const tbody = document.getElementById('runs-tbody');
  tbody.innerHTML = filtered.map(r => {
    const diff = (r.lines_added || 0) + (r.lines_removed || 0);
    const convName = (r.conventions_path || '').split('/').pop() || '-';
    const convHash = (r.conventions_hash || '').slice(0, 8);
    return `<tr class="clickable-row" data-run-id="${r.run_id}">
      <td>${r.run_id}</td><td>${r.task_id}</td><td>${r.condition_id}</td>
      <td title="${escHtml(r.conventions_path || '')} ${escHtml(r.conventions_hash || '')}">${escHtml(convName)} <span class="badge badge-dim">${convHash}</span>${r.conventions_mutation_note ? ' <span class="badge badge-yellow">' + escHtml(r.conventions_mutation_note) + '</span>' : ''}</td>
      <td>${r.iteration}</td>
      <td>${statusBadge(r)}</td><td>${r.tests_passed}/${r.tests_total}</td>
      <td>${fmtDuration(r.duration_seconds)}</td><td>${diff}</td><td>${judgeBadge(r.judge_score)}</td>
    </tr>`;
  }).join('');
  tbody.querySelectorAll('tr').forEach(tr => {
    tr.addEventListener('click', () => openDebrief(tr.dataset.runId));
  });
}

// ── Preflight Checks ──────────────────────────────────
async function loadPreflight() {
  try {
    const data = await api('/api/preflight');
    const keys = ['docker', 'swebench', 'datasets', 'aider', 'apikey', 'litellm'];
    const elIds = ['pf-docker', 'pf-swebench', 'pf-datasets', 'pf-aider', 'pf-apikey', 'pf-litellm'];
    keys.forEach((key, i) => {
      const el = document.getElementById(elIds[i]);
      if (!el) return;
      const check = data[key];
      if (!check) { el.innerHTML = '<span class="badge badge-dim">?</span>'; return; }
      const cls = check.ok ? 'badge-green' : 'badge-red';
      const sym = check.ok ? '\u2713' : '\u2717';
      el.innerHTML = `<span class="badge ${cls}">${sym} ${sym === '\u2717' ? 'FAIL' : 'OK'}</span> <span style="color:var(--text-dim);font-size:11px;">${escHtml(check.detail || '')}</span>`;
    });
  } catch(e) { console.error('Preflight failed:', e); }
}

// ── Init ──────────────────────────────────────────
loadLive();
loadPreflight();
liveInterval = setInterval(loadLive, 5000);
