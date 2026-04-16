const ChartJS = window.Chart;

const COLORS = {
  baseline: '#6c8cff',
  candidate: '#4ade80',
  baseline_bg: 'rgba(108,140,255,0.25)',
  candidate_bg: 'rgba(74,222,128,0.25)',
  dominated: '#4b5563',
  frontier: '#f87171',
  grid: '#2d3343',
  text: '#8b8fa3',
};

function destroyChart(chart) {
  if (chart) chart.destroy();
  return null;
}

function makeBarChart(canvasId, labels, datasets, yLabel) {
  const ctx = document.getElementById(canvasId).getContext('2d');
  return new ChartJS(ctx, {
    type: 'bar',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: COLORS.text } },
      },
      scales: {
        x: { ticks: { color: COLORS.text }, grid: { color: COLORS.grid } },
        y: {
          ticks: { color: COLORS.text },
          grid: { color: COLORS.grid },
          title: { display: true, text: yLabel, color: COLORS.text },
        },
      },
    },
  });
}

function makeLineChart(canvasId, labels, datasets, yLabel) {
  const ctx = document.getElementById(canvasId).getContext('2d');
  return new ChartJS(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: COLORS.text } },
      },
      scales: {
        x: { ticks: { color: COLORS.text }, grid: { color: COLORS.grid },
             title: { display: true, text: 'Iteration', color: COLORS.text } },
        y: {
          ticks: { color: COLORS.text },
          grid: { color: COLORS.grid },
          title: { display: true, text: yLabel, color: COLORS.text },
        },
      },
    },
  });
}

function makeScatterChart(canvasId, data, yLabel, xLabel) {
  const ctx = document.getElementById(canvasId).getContext('2d');
  return new ChartJS(ctx, {
    type: 'scatter',
    data: { datasets: data },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: COLORS.text } },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const pt = ctx.raw;
              return `Iter ${pt.iter}: success=${pt.y.toFixed(2)}, diff=${pt.x.toFixed(1)}`;
            },
          },
        },
      },
      scales: {
        x: { ticks: { color: COLORS.text }, grid: { color: COLORS.grid },
             title: { display: true, text: xLabel, color: COLORS.text } },
        y: { ticks: { color: COLORS.text }, grid: { color: COLORS.grid },
             title: { display: true, text: yLabel, color: COLORS.text } },
      },
    },
  });
}

window.HarnessCharts = {
  COLORS,
  destroyChart,
  makeBarChart,
  makeLineChart,
  makeScatterChart,
};