/* ============================================================================
   dashboard.js — v3 orchestrator
   Fetches all data files and dispatches to v2 + v3 renderers
   ============================================================================ */

(async function init() {

  const dataPath = 'data/';
  const fetchJSON = (name, fallback) =>
    fetch(dataPath + name).then(r => r.ok ? r.json() : fallback).catch(() => fallback);

  // Parallel fetch of all 16 data files (v2 + v3)
  const [
    articles, entities, timeseries, metadata,
    prices, positioning, heatmap, signals,
    // v3 additions
    competitors, regulatory, weakSignals, tension,
    tradeFlows, geopolitics, patents, forecasts, stakeholders,
  ] = await Promise.all([
    fetchJSON('articles.json', []),
    fetchJSON('entities.json', []),
    fetchJSON('timeseries.json', null),
    fetchJSON('metadata.json', null),
    fetchJSON('prices.json', null),
    fetchJSON('positioning.json', []),
    fetchJSON('heatmap.json', null),
    fetchJSON('signals.json', []),
    fetchJSON('competitors.json', null),
    fetchJSON('regulatory.json', null),
    fetchJSON('weak_signals.json', []),
    fetchJSON('tension.json', null),
    fetchJSON('trade_flows.json', null),
    fetchJSON('geopolitics.json', null),
    fetchJSON('patents.json', null),
    fetchJSON('forecasts.json', null),
    fetchJSON('stakeholders.json', null),
  ]);

  // ============ KPIs ============
  populateKPIs(metadata, articles, signals, weakSignals, regulatory, patents);

  // ============ v3 NEW: render in display order ============
  EI.renderTension(tension);
  EI.renderWeakSignals(weakSignals);

  if (prices) {
    Charts.renderPrices(prices);
    renderPricesSummary(prices);
  }

  EI.renderForecasts(forecasts);

  EI.renderCompetitors(competitors);

  if (positioning.length) Charts.renderPositioning(positioning);
  if (heatmap) Heatmap.render(heatmap);

  EI.renderRegulatory(regulatory);
  EI.renderTradeFlows(tradeFlows);
  EI.renderGeopolitics(geopolitics);
  EI.renderPatents(patents);

  Stakeholders.render(stakeholders);

  if (timeseries) {
    Charts.renderPositions(timeseries);
    Charts.renderNarratives(timeseries);
  }
  if (entities.length) Charts.renderEntities(entities);

  if (signals.length) renderSignals(signals);

  setupArticleTable(articles);
  setupSignalsFilter(signals);

  // ==========================================================================

  function populateKPIs(metadata, articles, signals, weakSignals, regulatory, patents) {
    if (metadata && metadata.last_updated) {
      document.getElementById('last-updated').textContent =
        'Last updated: ' + new Date(metadata.last_updated).toLocaleString();
    }

    const cutoff = Date.now() - 7 * 24 * 3600 * 1000;
    const recent = articles.filter(a => a.date && new Date(a.date).getTime() >= cutoff);
    document.getElementById('kpi-articles').textContent = recent.length || articles.length;
    document.getElementById('kpi-signals').textContent = signals.length;
    document.getElementById('kpi-weak').textContent = weakSignals.length;
    document.getElementById('kpi-regulatory').textContent = (regulatory && regulatory.count) || 0;
    document.getElementById('kpi-patents').textContent = (patents && patents.count) || 0;

    if (metadata) {
      document.getElementById('kpi-confidence').textContent =
        metadata.avg_confidence_7d ? metadata.avg_confidence_7d + '%' : '—';
    }
  }

  function renderPricesSummary(prices) {
    const container = document.getElementById('prices-summary');
    if (!container || !prices.summaries) return;
    container.innerHTML = prices.summaries.map(s => {
      const ch = s.change_30d_pct;
      const cls = ch == null ? 'flat' : ch > 0.1 ? 'up' : ch < -0.1 ? 'down' : 'flat';
      const arrow = ch == null ? '—' : ch > 0 ? '▲' : ch < 0 ? '▼' : '●';
      return `
        <div class="price-pill">
          <span class="pname">${s.name}</span>
          <span class="pval">${s.latest ?? '—'} <span style="font-weight:400;font-size:0.65rem;color:var(--text-muted)">${s.unit}</span></span>
          <span class="pchange ${cls}">${arrow} ${ch == null ? '—' : (ch > 0 ? '+' : '') + ch + '% / 30d'}</span>
        </div>`;
    }).join('');
  }

  function renderSignals(signals) {
    window._signalsAll = signals;
    paintSignals(signals);
  }

  function paintSignals(list) {
    const container = document.getElementById('signals-stream');
    if (!list.length) {
      container.innerHTML = '<p style="color:var(--text-muted);padding:1rem;">No signals match this filter.</p>';
      return;
    }
    container.innerHTML = list.slice(0, 12).map(s => {
      const cls = s.position || 'neutral';
      const date = s.date ? new Date(s.date).toISOString().slice(0, 10) : '';
      const companies = (s.companies || []).slice(0, 2).map(escapeHtml).join(', ');
      return `
        <div class="signal-card ${cls}">
          <div class="signal-text">${escapeHtml(s.signal)}</div>
          <div class="signal-meta">
            <span class="badge ${s.impact === 'high' ? 'impact-high' : s.impact === 'medium' ? 'impact-medium' : 'impact-low'}">${s.impact}</span>
            <span class="badge ${cls}">${cls}</span>
            <span class="badge">${escapeHtml(s.narrative || '')}</span>
            ${companies ? `<span>${companies}</span>` : ''}
            <span>${escapeHtml(s.region || '')}</span>
            <span>${date}</span>
            ${s.url ? `<a href="${escapeAttr(s.url)}" target="_blank" rel="noopener noreferrer">source ↗</a>` : ''}
          </div>
        </div>`;
    }).join('');
  }

  function setupSignalsFilter(signals) {
    const filter = document.getElementById('signal-filter-impact');
    if (!filter) return;
    filter.addEventListener('input', () => {
      const val = filter.value;
      paintSignals(val ? signals.filter(s => s.impact === val) : signals);
    });
  }

  function setupArticleTable(articles) {
    window._articlesAll = articles;
    populateFilters(articles);
    renderTable();
    ['filter-region', 'filter-narrative', 'filter-position', 'filter-search']
      .forEach(id => document.getElementById(id).addEventListener('input', renderTable));
  }

  function populateFilters(articles) {
    const regions = new Set(), narratives = new Set();
    articles.forEach(a => {
      if (a.region) regions.add(a.region);
      const n = a.classification && a.classification.narrative;
      if (n) narratives.add(n);
    });
    fillSelect('filter-region', [...regions].sort());
    fillSelect('filter-narrative', [...narratives].sort());
    fillSelect('filter-position', ['bullish', 'bearish', 'neutral']);
  }

  function fillSelect(id, values) {
    const sel = document.getElementById(id);
    if (!sel) return;
    values.forEach(v => {
      const opt = document.createElement('option');
      opt.value = v; opt.textContent = v;
      sel.appendChild(opt);
    });
  }

  function renderTable() {
    const region = document.getElementById('filter-region').value;
    const narrative = document.getElementById('filter-narrative').value;
    const position = document.getElementById('filter-position').value;
    const search = document.getElementById('filter-search').value.toLowerCase();

    const filtered = (window._articlesAll || []).filter(a => {
      const cls = a.classification || {};
      if (region && a.region !== region) return false;
      if (narrative && cls.narrative !== narrative) return false;
      if (position && cls.position !== position) return false;
      if (search) {
        const hay = (a.title + ' ' + (cls.key_companies || []).join(' ')).toLowerCase();
        if (!hay.includes(search)) return false;
      }
      return true;
    });

    const tbody = document.getElementById('articles-body');
    if (!filtered.length) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:1.5rem;color:var(--text-muted);">No articles match these filters.</td></tr>';
    } else {
      tbody.innerHTML = filtered.map(a => {
        const cls = a.classification || {};
        const date = a.date ? new Date(a.date).toISOString().slice(0, 10) : '—';
        const companies = (cls.key_companies || []).slice(0, 3)
          .map(c => `<span class="badge">${escapeHtml(c)}</span>`).join(' ');
        return `
          <tr>
            <td class="date">${date}</td>
            <td class="title"><a href="${escapeAttr(a.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(a.title)}</a></td>
            <td>${escapeHtml(a.source || '')}</td>
            <td>${escapeHtml(a.region || '')}</td>
            <td>${cls.position ? `<span class="badge ${cls.position}">${cls.position}</span>` : '—'}</td>
            <td>${cls.narrative ? `<span class="badge">${escapeHtml(cls.narrative)}</span>` : '—'}</td>
            <td class="companies-cell">${companies}</td>
            <td>${cls.confidence != null ? cls.confidence + '%' : '—'}</td>
          </tr>`;
      }).join('');
    }
    document.getElementById('articles-count').textContent =
      `Showing ${filtered.length} of ${(window._articlesAll || []).length} articles`;
  }

  function escapeHtml(s) {
    return String(s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }
  function escapeAttr(s) { return escapeHtml(s); }
})();
