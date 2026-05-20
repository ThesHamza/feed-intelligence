/* ============================================================================
   charts.js — Chart.js v4 renderers (prices, positioning, positions,
   entities, narratives). EI-specific charts live in ei-modules.js.
   ============================================================================ */

const Charts = (() => {

  const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const palette = {
    bullish: '#16a34a', bearish: '#dc2626', neutral: '#ca8a04', accent: '#2563eb',
    grid: isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.05)',
    text: isDark ? '#cbd5e1' : '#475569',
  };
  const narrativeColors = {
    supply: '#3b82f6', demand: '#8b5cf6', prices: '#ca8a04',
    regulatory: '#db2777', innovation: '#16a34a', sustainability: '#0891b2',
    trade: '#ea580c', disease: '#dc2626', 'M&A': '#7c3aed', geopolitics: '#525252',
  };
  const categoryColors = {
    phosphate_suppliers: '#3b82f6', additive_suppliers: '#16a34a',
    integrators: '#ea580c', other: '#94a3b8',
  };

  function commonOptions() {
    return {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { labels: { color: palette.text, font: { size: 11 } } } },
    };
  }

  // -------------------- Commodity prices (indexed to 100) --------------------
  function renderPrices(pricesData) {
    const ctx = document.getElementById('chart-prices');
    if (!ctx || !pricesData || !pricesData.series) return;
    const series = pricesData.series;
    const symbols = Object.keys(series);
    if (!symbols.length) return;

    let allDates = [];
    symbols.forEach(s => { if (series[s].dates.length > allDates.length) allDates = series[s].dates; });

    const datasets = symbols.map(sym => {
      const s = series[sym];
      const base = s.closes[0];
      if (!base) return null;
      const indexed = s.closes.map(v => +(v / base * 100).toFixed(2));
      return {
        label: s.name,
        data: s.dates.map((d, i) => ({ x: d, y: indexed[i] })),
        borderColor: s.color, backgroundColor: s.color + '20',
        tension: 0.25, borderWidth: 2, pointRadius: 0, pointHoverRadius: 4, fill: false,
      };
    }).filter(Boolean);

    new Chart(ctx, {
      type: 'line',
      data: { datasets },
      options: {
        ...commonOptions(),
        parsing: false,
        scales: {
          x: { type: 'category', labels: allDates, grid: { color: palette.grid },
               ticks: { color: palette.text, font: { size: 10 }, maxTicksLimit: 8 } },
          y: { grid: { color: palette.grid }, ticks: { color: palette.text, font: { size: 10 } },
               title: { display: true, text: 'Index (start = 100)', color: palette.text, font: { size: 10 } } },
        },
        interaction: { mode: 'index', intersect: false },
        plugins: { ...commonOptions().plugins,
          tooltip: { callbacks: { label: c => `${c.dataset.label}: ${c.parsed.y.toFixed(1)}` } } },
      },
    });
  }

  // -------------------- Player positioning (bubble) --------------------
  function renderPositioning(points) {
    const ctx = document.getElementById('chart-positioning');
    if (!ctx || !points || !points.length) return;

    const grouped = {};
    points.forEach(p => {
      const cat = p.category || 'other';
      (grouped[cat] = grouped[cat] || []).push({
        x: p.mentions, y: p.sentiment,
        r: Math.max(5, Math.min(28, Math.sqrt(p.weighted_impact || p.mentions) * 3)),
        company: p.company, mentions: p.mentions, sentiment: p.sentiment,
      });
    });

    const datasets = Object.entries(grouped).map(([cat, data]) => ({
      label: cat.replace(/_/g, ' '), data,
      backgroundColor: (categoryColors[cat] || palette.accent) + '99',
      borderColor: categoryColors[cat] || palette.accent, borderWidth: 1.5,
    }));

    new Chart(ctx, {
      type: 'bubble',
      data: { datasets },
      options: {
        ...commonOptions(),
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: c => `${c.raw.company}: ${c.raw.mentions} mentions, sentiment ${c.raw.sentiment.toFixed(2)}` } },
        },
        scales: {
          x: { grid: { color: palette.grid }, ticks: { color: palette.text, font: { size: 10 } },
               title: { display: true, text: 'Share of voice (mentions)', color: palette.text, font: { size: 11 } }, beginAtZero: true },
          y: { grid: { color: palette.grid }, ticks: { color: palette.text, font: { size: 10 } },
               title: { display: true, text: 'Sentiment (−1 → +1)', color: palette.text, font: { size: 11 } }, min: -1.1, max: 1.1 },
        },
      },
    });
  }

  // -------------------- Positions stacked area --------------------
  function renderPositions(timeseries) {
    const ctx = document.getElementById('chart-positions');
    if (!ctx || !timeseries) return;
    const labels = timeseries.dates.map(d => d.slice(5));
    new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [
          { label: 'Bullish', data: timeseries.positions.bullish, backgroundColor: palette.bullish + '40', borderColor: palette.bullish, fill: true, tension: 0.3, borderWidth: 1.5, pointRadius: 0 },
          { label: 'Bearish', data: timeseries.positions.bearish, backgroundColor: palette.bearish + '40', borderColor: palette.bearish, fill: true, tension: 0.3, borderWidth: 1.5, pointRadius: 0 },
          { label: 'Neutral', data: timeseries.positions.neutral, backgroundColor: palette.neutral + '40', borderColor: palette.neutral, fill: true, tension: 0.3, borderWidth: 1.5, pointRadius: 0 },
        ],
      },
      options: {
        ...commonOptions(),
        scales: {
          x: { stacked: true, grid: { color: palette.grid }, ticks: { color: palette.text, font: { size: 10 }, maxTicksLimit: 10 } },
          y: { stacked: true, beginAtZero: true, grid: { color: palette.grid }, ticks: { color: palette.text, font: { size: 10 } } },
        },
        interaction: { mode: 'index', intersect: false },
      },
    });
  }

  // -------------------- Top entities horizontal bar --------------------
  function renderEntities(entities) {
    const ctx = document.getElementById('chart-entities');
    if (!ctx || !entities) return;
    const top = entities.slice(0, 15);
    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: top.map(e => e.company),
        datasets: [{
          label: 'Mentions (30d)', data: top.map(e => e.mentions_30d),
          backgroundColor: top.map(e => e.sentiment_avg > 0.2 ? palette.bullish : e.sentiment_avg < -0.2 ? palette.bearish : palette.neutral),
          borderRadius: 4,
        }],
      },
      options: {
        ...commonOptions(), indexAxis: 'y',
        plugins: { legend: { display: false } },
        scales: {
          x: { beginAtZero: true, grid: { color: palette.grid }, ticks: { color: palette.text, font: { size: 10 } } },
          y: { grid: { display: false }, ticks: { color: palette.text, font: { size: 10 } } },
        },
      },
    });
  }

  // -------------------- Narratives bar --------------------
  function renderNarratives(timeseries) {
    const ctx = document.getElementById('chart-narratives');
    if (!ctx || !timeseries) return;
    const entries = Object.entries(timeseries.narratives_total || {});
    entries.sort((a, b) => b[1] - a[1]);
    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: entries.map(e => e[0]),
        datasets: [{ label: 'Articles', data: entries.map(e => e[1]),
          backgroundColor: entries.map(e => narrativeColors[e[0]] || palette.accent), borderRadius: 4 }],
      },
      options: {
        ...commonOptions(),
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { color: palette.text, font: { size: 10 }, maxRotation: 45, autoSkip: false } },
          y: { beginAtZero: true, grid: { color: palette.grid }, ticks: { color: palette.text, font: { size: 10 } } },
        },
      },
    });
  }

  return { renderPrices, renderPositioning, renderPositions, renderEntities, renderNarratives };
})();
