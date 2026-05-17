/* ============================================================================
   dashboard.js — orchestrator
   Fetches the 4 JSON files, populates KPIs & table, dispatches to map / charts
   ============================================================================ */

(async function init() {

  const state = {
    articles: [],
    entities: [],
    timeseries: null,
    metadata: null,
  };

  // ---- Load data ----
  const dataPath = 'data/';
  const [articles, entities, timeseries, metadata] = await Promise.all([
    fetch(dataPath + 'articles.json').then(r => r.ok ? r.json() : []).catch(() => []),
    fetch(dataPath + 'entities.json').then(r => r.ok ? r.json() : []).catch(() => []),
    fetch(dataPath + 'timeseries.json').then(r => r.ok ? r.json() : null).catch(() => null),
    fetch(dataPath + 'metadata.json').then(r => r.ok ? r.json() : null).catch(() => null),
  ]);

  state.articles = articles;
  state.entities = entities;
  state.timeseries = timeseries;
  state.metadata = metadata;

  // ---- Empty state ----
  if (!articles.length) {
    document.getElementById('articles-body').innerHTML =
      '<tr><td colspan="8" style="text-align:center;padding:2rem;color:var(--text-muted);">' +
      'No articles yet. The pipeline will populate this on first run.</td></tr>';
  }

  // ---- Header & KPIs ----
  populateKPIs();

  // ---- Charts ----
  if (timeseries) {
    Charts.renderPositions(timeseries);
    Charts.renderNarratives(timeseries);
  }
  if (entities.length) Charts.renderEntities(entities);

  // ---- Map ----
  WorldMap.render(articles);

  // ---- Filters & table ----
  populateFilters();
  renderTable();

  // Wire up filters
  ['filter-region', 'filter-narrative', 'filter-position', 'filter-search']
    .forEach(id => document.getElementById(id).addEventListener('input', renderTable));

  // ============================================================================

  function populateKPIs() {
    const last = state.metadata && state.metadata.last_updated;
    document.getElementById('last-updated').textContent =
      last ? `Last updated: ${new Date(last).toLocaleString()}` : 'Last updated: —';

    // Articles in last 7 days
    const cutoff = Date.now() - 7 * 24 * 3600 * 1000;
    const recent = state.articles.filter(a => {
      const t = a.date ? new Date(a.date).getTime() : 0;
      return t >= cutoff;
    });
    document.getElementById('kpi-articles').textContent = recent.length || state.articles.length;
    document.getElementById('kpi-articles-sub').textContent =
      recent.length ? `qualified + classified` : `total (no recent dates)`;

    document.getElementById('kpi-entities').textContent = state.entities.length;

    if (state.metadata) {
      document.getElementById('kpi-sources').textContent = state.metadata.sources_active_7d ?? '—';
      document.getElementById('kpi-confidence').textContent =
        state.metadata.avg_confidence_7d ? state.metadata.avg_confidence_7d + '%' : '—';
    }
  }

  function populateFilters() {
    const regions = new Set();
    const narratives = new Set();
    state.articles.forEach(a => {
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
      opt.value = v;
      opt.textContent = v;
      sel.appendChild(opt);
    });
  }

  function renderTable() {
    const region = document.getElementById('filter-region').value;
    const narrative = document.getElementById('filter-narrative').value;
    const position = document.getElementById('filter-position').value;
    const search = document.getElementById('filter-search').value.toLowerCase();

    const filtered = state.articles.filter(a => {
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
      tbody.innerHTML =
        '<tr><td colspan="8" style="text-align:center;padding:1.5rem;color:var(--text-muted);">No articles match these filters.</td></tr>';
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
      `Showing ${filtered.length} of ${state.articles.length} articles`;
  }

  function escapeHtml(s) {
    return String(s || '').replace(/[&<>"']/g, c => ({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
    }[c]));
  }
  function escapeAttr(s) { return escapeHtml(s); }

})();
