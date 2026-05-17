/* ============================================================================
   charts.js — Chart.js v4 rendering for positions / entities / narratives
   ============================================================================ */

const Charts = (() => {

  const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const palette = {
    bullish: '#16a34a',
    bearish: '#dc2626',
    neutral: '#ca8a04',
    accent: '#2563eb',
    grid: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)',
    text: isDark ? '#cbd5e1' : '#4b5563',
  };
  const narrativeColors = {
    supply: '#3b82f6',
    demand: '#8b5cf6',
    prices: '#ca8a04',
    regulatory: '#db2777',
    innovation: '#16a34a',
    sustainability: '#0891b2',
    trade: '#ea580c',
    disease: '#dc2626',
    'M&A': '#7c3aed',
    geopolitics: '#525252',
  };

  function commonOptions() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: palette.text, font: { size: 11 } } } },
    };
  }

  function renderPositions(timeseries) {
    const ctx = document.getElementById('chart-positions');
    if (!ctx) return;
    const labels = timeseries.dates.map(d => d.slice(5));  // MM-DD
    new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [
          { label: 'Bullish',  data: timeseries.positions.bullish,
            backgroundColor: palette.bullish + '40', borderColor: palette.bullish,
            fill: true, tension: 0.3, borderWidth: 1.5, pointRadius: 0 },
          { label: 'Bearish',  data: timeseries.positions.bearish,
            backgroundColor: palette.bearish + '40', borderColor: palette.bearish,
            fill: true, tension: 0.3, borderWidth: 1.5, pointRadius: 0 },
          { label: 'Neutral',  data: timeseries.positions.neutral,
            backgroundColor: palette.neutral + '40', borderColor: palette.neutral,
            fill: true, tension: 0.3, borderWidth: 1.5, pointRadius: 0 },
        ],
      },
      options: {
        ...commonOptions(),
        scales: {
          x: { stacked: true, grid: { color: palette.grid }, ticks: { color: palette.text, font: { size: 10 } } },
          y: { stacked: true, beginAtZero: true, grid: { color: palette.grid }, ticks: { color: palette.text, font: { size: 10 } } },
        },
        interaction: { mode: 'index', intersect: false },
      },
    });
  }

  function renderEntities(entities) {
    const ctx = document.getElementById('chart-entities');
    if (!ctx) return;
    const top = entities.slice(0, 10);
    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: top.map(e => e.company),
        datasets: [{
          label: 'Mentions (30d)',
          data: top.map(e => e.mentions_30d),
          backgroundColor: top.map(e =>
            e.sentiment_avg > 0.2 ? palette.bullish :
            e.sentiment_avg < -0.2 ? palette.bearish :
            palette.neutral),
          borderRadius: 3,
        }],
      },
      options: {
        ...commonOptions(),
        indexAxis: 'y',
        plugins: { legend: { display: false } },
        scales: {
          x: { beginAtZero: true, grid: { color: palette.grid }, ticks: { color: palette.text, font: { size: 10 } } },
          y: { grid: { display: false }, ticks: { color: palette.text, font: { size: 10 } } },
        },
      },
    });
  }

  function renderNarratives(timeseries) {
    const ctx = document.getElementById('chart-narratives');
    if (!ctx) return;
    const entries = Object.entries(timeseries.narratives_total || {});
    entries.sort((a, b) => b[1] - a[1]);
    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: entries.map(e => e[0]),
        datasets: [{
          label: 'Articles',
          data: entries.map(e => e[1]),
          backgroundColor: entries.map(e => narrativeColors[e[0]] || palette.accent),
          borderRadius: 3,
        }],
      },
      options: {
        ...commonOptions(),
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { color: palette.text, font: { size: 10 }, autoSkip: false, maxRotation: 45 } },
          y: { beginAtZero: true, grid: { color: palette.grid }, ticks: { color: palette.text, font: { size: 10 } } },
        },
      },
    });
  }

  return { renderPositions, renderEntities, renderNarratives };

})();
