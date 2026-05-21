/* ============================================================================
   brief.js — Executive decision brief ("so what") + feed phosphate proxies
   ============================================================================ */

const Brief = (() => {

  const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const palette = {
    grid: isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.05)',
    text: isDark ? '#cbd5e1' : '#475569',
  };

  function escapeHtml(s) {
    return String(s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  // ---- Executive brief ----
  function renderBrief(brief) {
    const container = document.getElementById('exec-brief');
    if (!container || !brief) return;

    const date = brief.generated_at ? new Date(brief.generated_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' }) : '';
    const items = (brief.items || []).slice(0, 5);

    const itemsHtml = items.map((it, i) => `
      <div class="brief-item priority-${it.priority || 'low'}">
        <div class="brief-item-num">${i + 1}</div>
        <div class="brief-item-body">
          <div class="brief-insight">${escapeHtml(it.insight)}</div>
          <div class="brief-implication"><span class="brief-arrow">→</span> ${escapeHtml(it.implication)}</div>
          ${it.action ? `<div class="brief-action"><span class="brief-action-label">Action</span> ${escapeHtml(it.action)}</div>` : ''}
        </div>
        <div class="brief-priority-badge ${it.priority || 'low'}">${it.priority || 'low'}</div>
      </div>`).join('');

    container.innerHTML = `
      <div class="brief-header">
        <div>
          <div class="brief-eyebrow">Executive Brief · ${date}</div>
          <div class="brief-headline">${escapeHtml(brief.headline || '')}</div>
        </div>
        <div class="brief-source" title="Mode de génération">${escapeHtml(brief.generated_by || '')}</div>
      </div>
      <div class="brief-items">${itemsHtml}</div>`;
  }

  // ---- Feed phosphate proxies ----
  function renderProxies(data) {
    if (!data || !data.proxies) return;

    // Caveat banner
    const caveatEl = document.getElementById('proxies-caveat');
    if (caveatEl && data.caveat) caveatEl.textContent = '⚠️ ' + data.caveat;

    // Summary pills
    const summaryEl = document.getElementById('proxies-summary');
    if (summaryEl) {
      summaryEl.innerHTML = data.proxies.map(p => {
        const ch = p.change_3m_pct;
        const cls = ch == null ? 'flat' : ch > 0.5 ? 'up' : ch < -0.5 ? 'down' : 'flat';
        const arrow = ch == null ? '—' : ch > 0 ? '▲' : ch < 0 ? '▼' : '●';
        return `
          <div class="price-pill">
            <span class="pname">${escapeHtml(p.label)}</span>
            <span class="pval">${p.latest ?? '—'} <span style="font-size:0.65rem;font-weight:400;color:var(--text-muted)">${escapeHtml(p.unit || '')}</span></span>
            <span class="pchange ${cls}">${arrow} ${ch == null ? '—' : (ch > 0 ? '+' : '') + ch + '% / 3m'}</span>
          </div>`;
      }).join('');
    }

    // Chart (indexed to 100)
    const ctx = document.getElementById('chart-proxies');
    if (!ctx) return;
    let allDates = [];
    data.proxies.forEach(p => { if (p.dates.length > allDates.length) allDates = p.dates; });

    const datasets = data.proxies.map(p => {
      const base = p.values[0];
      if (!base) return null;
      return {
        label: p.label,
        data: p.dates.map((d, i) => ({ x: d, y: +(p.values[i] / base * 100).toFixed(1) })),
        borderColor: p.color, backgroundColor: p.color + '15',
        tension: 0.25, borderWidth: 2, pointRadius: 0, pointHoverRadius: 4, fill: false,
      };
    }).filter(Boolean);

    new Chart(ctx, {
      type: 'line',
      data: { datasets },
      options: {
        responsive: true, maintainAspectRatio: false, parsing: false,
        scales: {
          x: { type: 'category', labels: allDates, grid: { color: palette.grid },
               ticks: { color: palette.text, font: { size: 10 }, maxTicksLimit: 9 } },
          y: { grid: { color: palette.grid }, ticks: { color: palette.text, font: { size: 10 } },
               title: { display: true, text: 'Index (début = 100)', color: palette.text, font: { size: 10 } } },
        },
        interaction: { mode: 'index', intersect: false },
        plugins: { legend: { labels: { color: palette.text, font: { size: 10 }, boxWidth: 18 }, position: 'bottom' },
          tooltip: { callbacks: { label: c => `${c.dataset.label}: ${c.parsed.y.toFixed(1)}` } } },
      },
    });
  }

  return { renderBrief, renderProxies };
})();
