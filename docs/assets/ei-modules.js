/* ============================================================================
   ei-modules.js — v3 Economic Intelligence renderers
   Tension index, weak signals, regulatory, trade flows, geopolitics, patents,
   competitors stock chart, forecasts.
   ============================================================================ */

const EI = (() => {

  const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const palette = {
    grid: isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.05)',
    text: isDark ? '#cbd5e1' : '#475569',
    positive: isDark ? '#4ade80' : '#16a34a',
    negative: isDark ? '#f87171' : '#dc2626',
    neutral: isDark ? '#fbbf24' : '#ca8a04',
    accent: isDark ? '#60a5fa' : '#2563eb',
  };

  function escapeHtml(s) {
    return String(s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  // ============================================================================
  // 1. TENSION INDEX
  // ============================================================================
  function renderTension(tension) {
    if (!tension) return;
    const value = tension.composite;
    const level = (tension.level || '').toLowerCase();

    document.getElementById('tension-value').textContent = value;
    document.getElementById('tension-level').textContent = tension.level;
    document.getElementById('tension-interpretation').textContent = tension.interpretation || '';

    const circle = document.getElementById('tension-circle');
    circle.classList.add(level);

    const components = tension.components || {};
    const compHtml = Object.entries(components).map(([k, v]) => {
      const color = v >= 65 ? 'var(--high)' : v >= 40 ? 'var(--medium)' : 'var(--low)';
      const label = k.replace(/_/g, ' ');
      return `
        <div class="tension-component">
          <div class="tc-label">${label}</div>
          <div class="tc-value">${v}</div>
          <div class="tc-bar"><div class="tc-bar-fill" style="width:${Math.min(100,v)}%;background:${color}"></div></div>
        </div>`;
    }).join('');
    document.getElementById('tension-components').innerHTML = compHtml;
  }

  // ============================================================================
  // 2. WEAK SIGNALS
  // ============================================================================
  function renderWeakSignals(signals) {
    const container = document.getElementById('weak-signals-list');
    if (!container) return;
    if (!signals || !signals.length) {
      container.innerHTML = '<p style="color:var(--text-muted);padding:1rem">No weak signals detected.</p>';
      return;
    }
    container.innerHTML = signals.map(s => {
      const direction = s.direction || 'spike';
      const zSign = s.z_score >= 0 ? '+' : '';
      return `
        <div class="weak-signal ${direction}">
          <div class="weak-signal-header">
            <span class="weak-signal-type">${escapeHtml(s.type)}</span>
            <span class="weak-signal-z ${direction}">${zSign}${s.z_score}σ ${direction === 'spike' ? '↑' : '↓'}</span>
          </div>
          <div class="weak-signal-item">${escapeHtml(s.item)}</div>
          <div class="weak-signal-desc">${escapeHtml(s.description || '')}</div>
        </div>`;
    }).join('');
  }

  // ============================================================================
  // 3. REGULATORY
  // ============================================================================
  function renderRegulatory(reg) {
    if (!reg) return;

    // Stats
    const statsEl = document.getElementById('regulatory-stats');
    const sev = reg.by_severity || {};
    statsEl.innerHTML = `
      <div class="reg-stat"><strong>${reg.count}</strong> total alerts</div>
      <div class="reg-stat high"><strong>${sev.high || 0}</strong> high severity</div>
      <div class="reg-stat medium"><strong>${sev.medium || 0}</strong> medium</div>
      <div class="reg-stat low"><strong>${sev.low || 0}</strong> low</div>
    `;

    // List
    const listEl = document.getElementById('regulatory-list');
    const alerts = (reg.alerts || []).slice(0, 20);
    listEl.innerHTML = alerts.map(a => {
      const date = a.published_at ? new Date(a.published_at).toISOString().slice(0, 10) : '';
      return `
        <div class="reg-item">
          <div class="reg-severity ${a.severity}" title="${a.severity}"></div>
          <div>
            <div class="reg-title">${escapeHtml(a.title)}</div>
            <div class="reg-meta">
              <strong>${escapeHtml(a.body)}</strong> · ${escapeHtml(a.region)} · ${escapeHtml(a.topic)} · ${date}
            </div>
          </div>
          ${a.url ? `<a href="${escapeHtml(a.url)}" target="_blank" rel="noopener noreferrer">source ↗</a>` : ''}
        </div>`;
    }).join('');
  }

  // ============================================================================
  // 4. TRADE FLOWS — handles both rich sample format and minimal module format
  // ============================================================================
  function renderTradeFlows(trade) {
    if (!trade) return;

    // Summary
    const summary = document.getElementById('trade-summary');
    const totalValue = ((trade.total_value_usd || 0) / 1e9).toFixed(2);
    const period = trade.period || (trade.top_exporters?.[0]?.year ? `Year ${trade.top_exporters[0].year}` : 'Latest');
    const hsCount = (trade.hs_codes || []).length;
    summary.innerHTML = `
      <div class="trade-stat"><strong>$${totalValue}B</strong>Total trade value</div>
      <div class="trade-stat"><strong>${period}</strong>Period</div>
      <div class="trade-stat"><strong>${hsCount}</strong>HS codes tracked</div>
      <div class="trade-stat"><strong>${(trade.top_exporters || []).length}</strong>Top exporters</div>
    `;

    // Exporters chart
    if (trade.top_exporters?.length) {
      renderTradeChart('chart-exporters', trade.top_exporters, palette.positive);
    }
    // Importers chart (only if present in data)
    if (trade.top_importers?.length) {
      renderTradeChart('chart-importers', trade.top_importers, palette.accent);
    } else {
      const importersEl = document.getElementById('chart-importers');
      if (importersEl) {
        const parent = importersEl.closest('.chart-wrap');
        if (parent) parent.innerHTML = '<p style="color:var(--text-muted);padding:1rem;font-size:0.8125rem">Importers data not available from this source. UN Comtrade reports flows from exporter side.</p>';
      }
    }

    // Corridors (only if present)
    const corridors = trade.key_corridors || [];
    const corridorsEl = document.getElementById('trade-corridors');
    if (corridors.length) {
      corridorsEl.innerHTML = corridors.map(c => {
        const yoyCls = (c.yoy_pct ?? 0) >= 0 ? 'up' : 'down';
        const yoySign = (c.yoy_pct ?? 0) >= 0 ? '+' : '';
        const value = (c.value_usd / 1e6).toFixed(0);
        return `
          <div class="corridor">
            <div>
              <div class="corridor-route">${escapeHtml(c.from)} <span class="corridor-arrow">→</span> ${escapeHtml(c.to)}</div>
              <div class="corridor-value">$${value}M</div>
            </div>
            ${c.yoy_pct != null ? `<div class="corridor-yoy ${yoyCls}">${yoySign}${c.yoy_pct}%</div>` : ''}
          </div>`;
      }).join('');
    } else {
      corridorsEl.innerHTML = '<p style="color:var(--text-muted);font-size:0.8125rem">Bilateral corridor data not available in current dataset.</p>';
    }
  }

  function renderTradeChart(canvasId, data, color) {
    const ctx = document.getElementById(canvasId);
    if (!ctx || !data) return;
    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: data.map(d => d.country),
        datasets: [{
          data: data.map(d => (d.value_usd || 0) / 1e6),
          backgroundColor: color,
          borderRadius: 4,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: 'y',
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: c => `$${c.parsed.x.toFixed(0)}M` } },
        },
        scales: {
          x: {
            beginAtZero: true,
            grid: { color: palette.grid },
            ticks: { color: palette.text, font: { size: 10 }, callback: v => '$' + v + 'M' },
          },
          y: { grid: { display: false }, ticks: { color: palette.text, font: { size: 10 } } },
        },
      },
    });
  }

  // ============================================================================
  // 5. GEOPOLITICS — handles both real module (top_risks) and sample (events) formats
  // ============================================================================
  function renderGeopolitics(geo) {
    if (!geo) return;
    const listEl = document.getElementById('geo-events-list');

    // Real module format: top_risks (country-level)
    if (geo.top_risks?.length) {
      listEl.innerHTML = geo.top_risks.map(r => {
        const tone = r.tone || 0;
        const toneBg = tone > 1 ? palette.positive : tone < -1 ? palette.negative : palette.neutral;
        const toneText = tone > 0 ? '+' + tone.toFixed(1) : tone.toFixed(1);
        const riskBadge = r.risk_score >= 70 ? 'high' : r.risk_score >= 40 ? 'medium' : 'low';
        return `
          <div class="geo-event">
            <div class="geo-tone" style="background:${toneBg}">${toneText}</div>
            <div>
              <div><strong>${escapeHtml(r.country)}</strong> <span style="color:var(--text-muted)">(${escapeHtml(r.iso || '')})</span></div>
              <div class="geo-event-meta">
                <span class="badge ${riskBadge}">Risk ${r.risk_score}</span>
                · ${r.events} events
                · ${escapeHtml(r.role || '')}
              </div>
            </div>
          </div>`;
      }).join('');
      return;
    }

    // Sample/legacy format: individual events
    const events = geo.events || [];
    listEl.innerHTML = events.map(e => {
      const tone = e.tone || 0;
      const toneBg = tone > 1 ? palette.positive : tone < -1 ? palette.negative : palette.neutral;
      const toneText = tone > 0 ? '+' + tone.toFixed(1) : tone.toFixed(1);
      const date = e.date ? new Date(e.date).toISOString().slice(0, 10) : '';
      const countries = [e.primary_country, e.secondary_country].filter(Boolean).join(' / ');
      return `
        <div class="geo-event">
          <div class="geo-tone" style="background:${toneBg}">${toneText}</div>
          <div>
            <div>${escapeHtml(e.title)}</div>
            <div class="geo-event-meta">${countries} · ${escapeHtml(e.theme || '')} · ${date}</div>
          </div>
          ${e.url ? `<a href="${escapeHtml(e.url)}" target="_blank" rel="noopener noreferrer" style="color:var(--accent);font-size:0.7rem">source ↗</a>` : ''}
        </div>`;
    }).join('');
  }

  // ============================================================================
  // 6. PATENTS
  // ============================================================================
  function renderPatents(p) {
    if (!p) return;
    document.getElementById('patents-stats').innerHTML = `
      <div class="reg-stat"><strong>${p.count}</strong> patents (last 12mo)</div>
      <div class="reg-stat"><strong>${Object.keys(p.by_applicant || {}).length}</strong> applicants</div>
      <div class="reg-stat"><strong>${Object.keys(p.by_country || {}).length}</strong> countries</div>
    `;
    const listEl = document.getElementById('patents-list');
    listEl.innerHTML = (p.patents || []).map(pt => {
      const date = pt.published_at ? new Date(pt.published_at).toISOString().slice(0, 10) : '';
      // Module emits 'theme' + 'applicant_hint'; sample emits 'tags' + 'applicant' + country + year
      const applicant = pt.applicant || pt.applicant_hint || 'Unknown applicant';
      const tagSource = pt.tags || (pt.theme ? [pt.theme] : []);
      const tags = tagSource.map(t => `<span class="badge">${escapeHtml(t)}</span>`).join(' ');
      const metaParts = [
        `<span class="patent-applicant">${escapeHtml(applicant)}</span>`,
        pt.applicant_country ? `<span>${escapeHtml(pt.applicant_country)}</span>` : '',
        pt.publication_year ? `<span>${pt.publication_year}</span>` : '',
        `<span>${date}</span>`,
        pt.url ? `<a href="${escapeHtml(pt.url)}" target="_blank" rel="noopener noreferrer">↗</a>` : '',
      ].filter(Boolean).join(' ');
      return `
        <div class="patent">
          <div class="patent-title">${escapeHtml(pt.title)}</div>
          <div class="patent-meta">${metaParts}</div>
          ${tags ? `<div style="margin-top:0.375rem">${tags}</div>` : ''}
        </div>`;
    }).join('');
  }

  // ============================================================================
  // 7. COMPETITORS STOCKS
  // ============================================================================
  function renderCompetitors(comp) {
    if (!comp || !comp.competitors) return;
    // Summary pills
    const summary = document.getElementById('competitors-summary');
    summary.innerHTML = comp.competitors.slice(0, 5).map(c => {
      const ch = c.change_30d_pct;
      const cls = ch == null ? 'flat' : ch > 0 ? 'up' : ch < 0 ? 'down' : 'flat';
      const arrow = ch == null ? '—' : ch > 0 ? '▲' : ch < 0 ? '▼' : '●';
      return `
        <div class="price-pill">
          <span class="pname">${escapeHtml(c.name)} (${escapeHtml(c.ticker)})</span>
          <span class="pval">${c.latest_price} <span style="font-size:0.65rem;font-weight:400;color:var(--text-muted)">${c.currency}</span></span>
          <span class="pchange ${cls}">${arrow} ${ch == null ? '—' : (ch > 0 ? '+' : '') + ch + '% / 30d'}</span>
        </div>`;
    }).join('');

    // Multi-line chart (indexed to 100)
    const ctx = document.getElementById('chart-competitors');
    if (!ctx) return;
    const datasets = comp.competitors.map(c => {
      const base = c.closes[0];
      if (!base) return null;
      return {
        label: c.name,
        data: c.dates.map((d, i) => ({ x: d, y: +(c.closes[i] / base * 100).toFixed(2) })),
        borderColor: c.color,
        backgroundColor: c.color + '15',
        tension: 0.25,
        borderWidth: 1.5,
        pointRadius: 0,
        pointHoverRadius: 3,
        fill: false,
      };
    }).filter(Boolean);
    // Add sector index as dashed black line
    if (comp.sector_index && comp.sector_index.values.length) {
      datasets.push({
        label: 'Sector index',
        data: comp.sector_index.dates.map((d, i) => ({ x: d, y: comp.sector_index.values[i] })),
        borderColor: isDark ? '#fafafa' : '#0f172a',
        borderDash: [6, 4],
        borderWidth: 2,
        pointRadius: 0,
        fill: false,
        tension: 0.25,
      });
    }
    const allDates = comp.competitors[0]?.dates || [];
    new Chart(ctx, {
      type: 'line',
      data: { datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        parsing: false,
        scales: {
          x: { type: 'category', labels: allDates, grid: { color: palette.grid }, ticks: { color: palette.text, font: { size: 10 }, maxTicksLimit: 8 } },
          y: { grid: { color: palette.grid }, ticks: { color: palette.text, font: { size: 10 } }, title: { display: true, text: 'Index (start=100)', color: palette.text, font: { size: 10 } } },
        },
        interaction: { mode: 'index', intersect: false },
        plugins: { legend: { labels: { color: palette.text, font: { size: 10 }, boxWidth: 18 }, position: 'bottom' } },
      },
    });
  }

  // ============================================================================
  // 8. FORECASTS — handles module output format (dict keyed by ticker)
  // ============================================================================
  function renderForecasts(fc) {
    if (!fc || !fc.forecasts) return;

    // Module output is a DICT keyed by ticker (ZC=F, ZS=F, …). Convert to list.
    let forecasts;
    if (Array.isArray(fc.forecasts)) {
      forecasts = fc.forecasts;  // backwards compat
    } else {
      forecasts = Object.entries(fc.forecasts).map(([ticker, f]) => ({
        ticker,
        name: f.name,
        color: f.color,
        unit: f.unit,
        dates: f.forecast_dates,
        point: f.forecast_values,
        lower_bound: f.forecast_lower,
        upper_bound: f.forecast_upper,
        current: f.current,
        forecast_30d: f.forecast_30d,
        change_pct: f.change_pct,
      }));
    }

    const grid = document.getElementById('forecasts-grid');
    grid.innerHTML = forecasts.map((f, idx) => {
      const ch = f.change_pct;
      const cls = ch == null ? 'flat' : ch > 0.1 ? 'up' : ch < -0.1 ? 'down' : 'flat';
      const arrow = ch == null ? '—' : ch > 0 ? '▲' : ch < 0 ? '▼' : '●';
      return `
        <div class="forecast-card">
          <h4>${escapeHtml(f.name || f.ticker)}</h4>
          <div class="forecast-chart-wrap"><canvas id="forecast-${idx}"></canvas></div>
          <div class="forecast-meta">
            <span>30d: <strong style="color:${ch >= 0 ? 'var(--positive)' : 'var(--negative)'}">${arrow} ${ch == null ? '—' : (ch > 0 ? '+' : '') + ch + '%'}</strong></span>
            <span>Current: ${f.current ?? '—'}</span>
          </div>
        </div>`;
    }).join('');

    // Render each forecast mini chart
    forecasts.forEach((f, idx) => {
      const ctx = document.getElementById('forecast-' + idx);
      if (!ctx || !f.point) return;
      new Chart(ctx, {
        type: 'line',
        data: {
          labels: f.dates || [],
          datasets: [
            { label: 'Upper', data: f.upper_bound, borderColor: 'transparent',
              backgroundColor: 'rgba(37,99,235,0.10)', fill: '+1', pointRadius: 0 },
            { label: 'Forecast', data: f.point, borderColor: f.color || palette.accent,
              backgroundColor: 'transparent', borderWidth: 2, pointRadius: 0, tension: 0.3 },
            { label: 'Lower', data: f.lower_bound, borderColor: 'transparent',
              backgroundColor: 'rgba(37,99,235,0.10)', fill: false, pointRadius: 0 },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `${c.dataset.label}: ${c.parsed.y?.toFixed(1) ?? '-'}` } } },
          scales: {
            x: { display: false },
            y: { grid: { color: palette.grid }, ticks: { color: palette.text, font: { size: 9 } } },
          },
        },
      });
    });
  }

  return { renderTension, renderWeakSignals, renderRegulatory, renderTradeFlows, renderGeopolitics, renderPatents, renderCompetitors, renderForecasts };
})();
