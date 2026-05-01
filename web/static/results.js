/* Results Visualiser JS — loads /api/runs and builds the results tab */
(function() {
  const API = '/api/runs';
  const NS = 'results';

  // --- State ---
  let allRuns = [];
  let conditions = [];
  let tasks = [];

  // --- Init ---
  async function init() {
    try {
      const resp = await fetch(API);
      const data = await resp.json();
      allRuns = data.runs || data || [];
    } catch(e) {
      console.error('[results] fetch error:', e);
      return;
    }

    // Derive sets
    const condSet = new Set();
    const taskSet = new Set();
    allRuns.forEach(r => {
      if (r.condition_id) condSet.add(r.condition_id);
      if (r.task_id) taskSet.add(r.task_id);
    });
    conditions = [...condSet].sort();
    tasks = [...taskSet].sort();

    render();
  }

  // --- Helpers ---
  function passRate(r) {
    if (!r.tests_total || r.tests_total === 0) return null;
    return r.tests_passed / r.tests_total;
  }

  function fmt(pct) {
    if (pct === null || pct === undefined) return '—';
    return (pct * 100).toFixed(1) + '%';
  }

  function fmtDur(s) {
    if (!s) return '—';
    if (s < 60) return s.toFixed(0) + 's';
    if (s < 3600) return (s/60).toFixed(1) + 'm';
    return (s/3600).toFixed(1) + 'h';
  }

  function fmtTokens(n) {
    if (!n) return '—';
    if (n < 1000) return n + '';
    if (n < 1000000) return (n/1000).toFixed(1) + 'K';
    return (n/1000000).toFixed(2) + 'M';
  }

  function heatColor(rate) {
    if (rate === null || rate === undefined) return '#333';
    // 0 → red, 0.5 → orange, 1 → green
    const r = Math.round(255 * (1 - rate));
    const g = Math.round(200 * rate);
    return `rgb(${r},${g},50)`;
  }

  function failureColor(kind) {
    const map = {
      'task_failure': '#ff9800',
      'eval_report_missing': '#9c27b0',
      'agent_timeout': '#f44336',
      'agent_import_error': '#e91e63',
      'eval_patch_apply_failed': '#795548',
      'success': '#4caf50',
      'unknown': '#666',
    };
    return map[kind] || '#666';
  }

  // --- Render ---
  function render() {
    const el = document.getElementById('results-content');
    if (!el) return;

    const infraRuns = allRuns.filter(r => r.infrastructure_error);
    const validRuns = allRuns.filter(r => !r.infrastructure_error && r.tests_total > 0);
    const successes = validRuns.filter(r => r.task_success);
    const totalTokensIn = allRuns.reduce((s, r) => s + (r.tokens_in || 0), 0);
    const totalTokensOut = allRuns.reduce((s, r) => s + (r.tokens_out || 0), 0);
    const totalTokensUsed = totalTokensIn + totalTokensOut;
    const failedKinds = {};
    allRuns.forEach(r => {
      const k = r.failure_kind || 'unknown';
      failedKinds[k] = (failedKinds[k] || 0) + 1;
    });

    let html = '';

    // --- Summary Cards ---
    html += '<div class="results-summary">';
    html += statCard('Total Runs', allRuns.length, '');
    html += statCard('Valid Runs', validRuns.length, validRuns.length > 0 ? 'good' : '');
    html += statCard('Successes', successes.length, successes.length > 0 ? 'good' : 'bad');
    html += statCard('Success Rate', validRuns.length > 0 ? fmt(successes.length / validRuns.length) : '—',
                     successes.length / Math.max(validRuns.length,1) > 0.3 ? 'good' : 'bad');
    html += statCard('Infra Errors', infraRuns.length, infraRuns.length > 0 ? 'bad' : 'good');
    html += statCard('Total Tokens Used', fmtTokens(totalTokensUsed), 'neutral');
    html += statCard('Tokens In', fmtTokens(totalTokensIn), 'neutral');
    html += statCard('Tokens Out', fmtTokens(totalTokensOut), 'neutral');
    html += statCard('Conditions', conditions.length, 'neutral');
    html += statCard('Tasks', tasks.length, 'neutral');
    html += '</div>';

    // --- Failure Breakdown ---
    html += '<div class="card"><h3>Failure Breakdown</h3>';
    html += '<div class="failure-bar">';
    const total = allRuns.length || 1;
    const sortedFails = Object.entries(failedKinds).sort((a,b) => b[1] - a[1]);
    sortedFails.forEach(([kind, count]) => {
      const pct = (count / total * 100).toFixed(1);
      html += `<div class="failure-bar-segment" style="width:${pct}%;background:${failureColor(kind)}" title="${kind}: ${count} (${pct}%)"><span>${count > 3 ? kind.replace(/_/g,' ').substring(0,15) : ''}</span></div>`;
    });
    html += '</div>';
    html += '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:8px;">';
    sortedFails.forEach(([kind, count]) => {
      html += `<span style="font-size:11px;"><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${failureColor(kind)};margin-right:3px;vertical-align:middle;"></span>${kind.replace(/_/g,' ')}: ${count}</span>`;
    });
    html += '</div></div>';

    // --- Condition Cards ---
    html += '<h3 style="margin-top:16px;">Per Condition</h3>';
    html += '<div class="condition-grid">';
    conditions.forEach(cond => {
      const cRuns = allRuns.filter(r => r.condition_id === cond);
      const cValid = cRuns.filter(r => r.tests_total > 0);
      const cSuccess = cValid.filter(r => r.task_success);
      const avgPass = cValid.length > 0 ? cValid.reduce((s,r) => s + passRate(r), 0) / cValid.length : null;
      const avgDur = cRuns.length > 0 ? cRuns.reduce((s,r) => s + (r.duration_seconds||0), 0) / cRuns.length : 0;
      const totalTokens = cRuns.reduce((s,r) => s + (r.tokens_in||0), 0);
      const avgDiff = cValid.length > 0 ? cValid.reduce((s,r) => s + ((r.lines_added||0)+(r.lines_removed||0)), 0) / cValid.length : 0;

      html += `<div class="condition-card">`;
      html += `<h4>${cond}</h4>`;
      html += metricRow('Runs', `${cValid.length}/${cRuns.length} valid`);
      html += metricRow('Success Rate', cValid.length > 0 ? fmt(cSuccess.length/cValid.length) : '—');
      html += metricRow('Avg Pass Rate', fmt(avgPass));
      html += metricRow('Avg Duration', fmtDur(avgDur));
      html += metricRow('Total Tokens In', fmtTokens(totalTokens));
      html += metricRow('Avg Diff (LOC)', avgDiff.toFixed(1));
      html += `</div>`;
    });
    html += '</div>';

    // --- Heatmap: Task × Condition ---
    html += '<div class="card"><h3>Heatmap: Pass Rate by Task × Condition</h3>';
    html += '<div style="overflow-x:auto;">';
    html += '<table class="heatmap-table"><thead><tr><th>Task \\ Condition</th>';
    conditions.forEach(c => {
      html += `<th style="writing-mode:vertical-rl;text-orientation:mixed;max-width:40px;font-size:10px;">${c}</th>`;
    });
    html += '</tr></thead><tbody>';
    tasks.forEach(task => {
      html += `<tr><td style="text-align:left;font-size:11px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${task}</td>`;
      conditions.forEach(cond => {
        const run = allRuns.find(r => r.task_id === task && r.condition_id === cond);
        const rate = run ? passRate(run) : null;
        const bg = heatColor(rate);
        const text = rate !== null ? (rate*100).toFixed(0) + '%' : '—';
        const detail = run ? `${run.tests_passed}/${run.tests_total}` : '';
        html += `<td style="background:${bg};color:white;" title="${task} | ${cond}\n${detail}\n${run?.failure_kind || ''}">${text}</td>`;
      });
      html += '</tr>';
    });
    html += '</tbody></table></div></div>';

    // --- Charts ---
    html += '<div class="results-charts-row">';
    html += '<div class="results-chart-card"><h4>Success Rate by Condition</h4><canvas id="results-chart-success"></canvas></div>';
    html += '<div class="results-chart-card"><h4>Avg Pass Rate by Condition</h4><canvas id="results-chart-passrate"></canvas></div>';
    html += '</div>';
    html += '<div class="results-charts-row">';
    html += '<div class="results-chart-card"><h4>Duration by Condition</h4><canvas id="results-chart-duration"></canvas></div>';
    html += '<div class="results-chart-card"><h4>Diff Size by Condition</h4><canvas id="results-chart-diff"></canvas></div>';
    html += '</div>';

    // --- Timeline (last 30 runs) ---
    const recent = [...allRuns].sort((a,b) => (b.start_ts||'').localeCompare(a.start_ts||'')).slice(0, 30);
    const maxDur = Math.max(...recent.map(r => r.duration_seconds || 0), 1);

    html += '<div class="card"><h3>Recent Runs Timeline</h3>';
    recent.forEach(r => {
      const dur = r.duration_seconds || 0;
      const w = (dur / maxDur * 100).toFixed(1);
      const rate = passRate(r);
      const color = rate === null ? '#666' : (rate >= 0.8 ? '#4caf50' : rate >= 0.5 ? '#ff9800' : '#f44336');
      const ts = r.start_ts ? r.start_ts.substring(11, 19) : '—';
      html += `<div class="timeline-row">`;
      html += `<span class="tl-time">${ts}</span>`;
      html += `<span class="tl-id" title="${r.run_id}">${r.run_id}</span>`;
      html += `<div class="tl-bar"><div class="tl-bar-fill" style="width:${w}%;background:${color};"></div></div>`;
      html += `<span class="tl-result" style="color:${color}">${rate !== null ? (rate*100).toFixed(0)+'%' : '—'}</span>`;
      html += `</div>`;
    });
    html += '</div>';

    el.innerHTML = html;

    // --- Draw Charts ---
    drawCharts();
  }

  function statCard(label, value, cls) {
    return `<div class="results-stat-card"><span class="label">${label}</span><span class="value ${cls}">${value}</span></div>`;
  }

  function metricRow(label, value) {
    return `<div class="metric-row"><span class="metric-label">${label}</span><span class="metric-value">${value}</span></div>`;
  }

  function drawCharts() {
    if (typeof Chart === 'undefined') return;

    const chartColors = [
      '#4caf50','#2196f3','#ff9800','#f44336','#9c27b0',
      '#00bcd4','#ffeb3b','#795548','#607d8b','#e91e63'
    ];

    // Success Rate by Condition
    const successData = conditions.map(cond => {
      const cRuns = allRuns.filter(r => r.condition_id === cond && r.tests_total > 0);
      return cRuns.length > 0 ? cRuns.filter(r => r.task_success).length / cRuns.length : 0;
    });
    drawBarChart('results-chart-success', conditions, successData, chartColors, 'Success Rate');

    // Avg Pass Rate by Condition
    const passRateData = conditions.map(cond => {
      const cRuns = allRuns.filter(r => r.condition_id === cond && r.tests_total > 0);
      if (cRuns.length === 0) return 0;
      return cRuns.reduce((s,r) => s + passRate(r), 0) / cRuns.length;
    });
    drawBarChart('results-chart-passrate', conditions, passRateData, chartColors, 'Avg Pass Rate');

    // Duration by Condition
    const durData = conditions.map(cond => {
      const cRuns = allRuns.filter(r => r.condition_id === cond);
      if (cRuns.length === 0) return 0;
      return cRuns.reduce((s,r) => s + (r.duration_seconds||0), 0) / cRuns.length;
    });
    drawBarChart('results-chart-duration', conditions, durData.map(v => v.toFixed(1)), chartColors, 'Duration (s)');

    // Diff by Condition
    const diffData = conditions.map(cond => {
      const cRuns = allRuns.filter(r => r.condition_id === cond && r.tests_total > 0);
      if (cRuns.length === 0) return 0;
      return cRuns.reduce((s,r) => s + ((r.lines_added||0)+(r.lines_removed||0)), 0) / cRuns.length;
    });
    drawBarChart('results-chart-diff', conditions, diffData.map(v => v.toFixed(1)), chartColors, 'Avg Diff (LOC)');
  }

  function drawBarChart(canvasId, labels, data, colors, label) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    new Chart(canvas, {
      type: 'bar',
      data: {
        labels: labels.map(l => l.length > 20 ? l.substring(0,18)+'…' : l),
        datasets: [{
          label: label,
          data: data,
          backgroundColor: labels.map((_, i) => colors[i % colors.length] + '99'),
          borderColor: labels.map((_, i) => colors[i % colors.length]),
          borderWidth: 1,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        indexAxis: labels.length > 8 ? 'y' : 'x',
        plugins: {
          legend: { display: false },
        },
        scales: {
          y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: '#999' } },
          x: { grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: '#999', maxRotation: 45 } },
        }
      }
    });
  }

  // --- Tab activation hook ---
  document.addEventListener('DOMContentLoaded', () => {
    // Standalone page mode: load immediately if container exists
    if (document.getElementById('results-content')) {
      init();
    }

    // Dashboard tab mode: load on tab click
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        if (btn.dataset.tab === 'results') {
          init();
        }
      });
    });

    // If results tab is already active at load time
    if (document.querySelector('.tab-btn[data-tab="results"]')?.classList.contains('active')) {
      init();
    }
  });

  // Expose for manual refresh
  window.refreshResults = init;
})();
