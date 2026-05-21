/* ============================================================================
   info-export.js — Interactive legends + data export/consultation
   Auto-injects an info (ⓘ) tooltip and an export menu into each dashboard
   section. No HTML changes required beyond loading this script.
   ============================================================================ */

(function () {
  'use strict';

  // --------------------------------------------------------------------------
  // Explanations per section id. Each: what it shows, source, how to read it.
  // --------------------------------------------------------------------------
  const LEGENDS = {
    'tension': {
      title: 'Market Tension Index',
      what: 'Indice composite 0-100 résumant le niveau de tension global du marché des feed phosphates.',
      source: 'Calculé à partir de 4 sous-indicateurs : volatilité des prix (Yahoo Finance), polarisation du sentiment média (articles classifiés), sévérité réglementaire (alertes EFSA/FDA), densité de signaux faibles (détection d\'anomalies).',
      read: 'LOW (&lt;40) = marché calme · MEDIUM (40-69) = vigilance · HIGH (≥70) = forte tension, réactivité commerciale requise. Chaque sous-barre montre la contribution de sa dimension.',
      dataKey: 'tension',
    },
    'signals-weak': {
      title: 'Weak signals · détection d\'anomalies',
      what: 'Alertes statistiques sur les entités, commodités, narratifs ou régions dont les mentions médias s\'écartent anormalement de leur niveau habituel.',
      source: 'Calcul d\'un z-score sur fenêtre glissante de 14 jours à partir des articles classifiés. Un z-score ≥ 2σ déclenche une alerte.',
      read: 'Vert (↑ spike) = pic d\'attention soudain · Rouge (↓ drop) = chute inhabituelle. Plus le σ est élevé, plus l\'anomalie est marquée. À surveiller comme signaux précurseurs.',
      dataKey: 'weak_signals',
    },
    'prices': {
      title: 'Prix des commodités',
      what: 'Évolution des prix à terme (futures) des principales matières premières d\'alimentation animale, indexés à 100 au début de la période.',
      source: 'Yahoo Finance — contrats CBOT : maïs (ZC=F), soja (ZS=F), blé (ZW=F), tourteau de soja (ZM=F). Données réelles, mises à jour quotidiennement.',
      read: 'Indexation à 100 = on compare les variations relatives, pas les prix absolus. Une courbe à 110 = +10% depuis le début. Les pastilles donnent le prix réel + variation 30j.',
      dataKey: 'prices',
    },
    'forecasts': {
      title: 'Prévisions de prix 30 jours',
      what: 'Projection des prix des commodités sur 30 jours avec intervalle de confiance.',
      source: 'Modèle de lissage exponentiel double (Holt) appliqué aux séries de prix Yahoo Finance des 90 derniers jours.',
      read: 'La ligne centrale est la prévision la plus probable ; la bande colorée est l\'intervalle de confiance à 95% (plus elle s\'élargit, plus l\'incertitude augmente avec l\'horizon). Le % indique la variation attendue à 30j.',
      dataKey: 'forecasts',
    },
    'competitors': {
      title: 'Performance boursière des concurrents',
      what: 'Cours de bourse des concurrents directs d\'OCP sur 90 jours, indexés à 100, comparés à un indice sectoriel équipondéré.',
      source: 'Yahoo Finance — Mosaic (MOS), Nutrien (NTR), ICL (ICL), CF Industries (CF), Yara (YAR.OL), Bunge (BG), ADM, Tyson (TSN), JBS (JBSAY). Données réelles.',
      read: 'La ligne noire pointillée = indice sectoriel moyen. Une entreprise au-dessus surperforme le secteur. Les pastilles donnent cours réel + variation 30j. Proxy de la confiance des marchés envers chaque acteur.',
      dataKey: 'competitors',
    },
    'regulatory': {
      title: 'Radar réglementaire',
      what: 'Veille des publications réglementaires impactant les feed phosphates et la nutrition animale.',
      source: 'Flux RSS officiels : EFSA (UE), EUR-Lex, FDA (US), USDA, China MOA. Filtré par mots-clés (phosphate, contaminant, additif, métaux lourds, etc.).',
      read: 'Barre de couleur = sévérité estimée (rouge = haute, jaune = moyenne, vert = basse). Chaque alerte indique l\'organisme, la région et le sujet. Cliquer "source" pour le texte officiel.',
      dataKey: 'regulatory',
    },
    'trade': {
      title: 'Flux commerciaux',
      what: 'Exportations et importations mondiales de phosphates et préparations pour l\'alimentation animale.',
      source: 'UN Comtrade — codes douaniers HS 2510 (phosphates naturels), 2835 (phosphates chimiques), 2309 (préparations alimentaires animales). Données officielles avec ~2 ans de décalage.',
      read: 'Les barres montrent la valeur des échanges par pays (en M$). Les corridors indiquent les flux bilatéraux majeurs et leur évolution annuelle (YoY). Le Maroc y figure comme premier exportateur mondial.',
      dataKey: 'trade_flows',
    },
    'geopolitics': {
      title: 'Événements géopolitiques',
      what: 'Risques et événements politico-économiques affectant les routes commerciales des phosphates.',
      source: 'GDELT (Global Database of Events, Language, and Tone) — index mondial d\'événements médiatiques avec analyse de tonalité et géolocalisation.',
      read: 'Le carré coloré = tonalité moyenne (-10 très négatif → +10 très positif). Le score de risque par pays combine volume d\'événements et tonalité. Surveiller les pays exportateurs (Russie, Tunisie) pour anticiper les disruptions.',
      dataKey: 'geopolitics',
    },
    'patents': {
      title: 'Veille brevets',
      what: 'Dépôts de brevets récents sur les feed phosphates, additifs, substituts et procédés de fabrication.',
      source: 'Google Patents — recherche par thèmes (purification, bioavailabilité, substituts microbiens, procédés). Indicateur d\'innovation 3-5 ans en avance sur le marché.',
      read: 'Chaque carte = un brevet avec déposant et thème. Une concentration de dépôts sur un thème (ex. substituts microbiens) signale une rupture technologique potentielle à anticiper.',
      dataKey: 'patents',
    },
    'stakeholders': {
      title: 'Réseau d\'acteurs',
      what: 'Graphe des co-occurrences entre entreprises, régulateurs et acteurs clés dans le flux média.',
      source: 'Construit à partir des articles classifiés : deux acteurs sont reliés s\'ils apparaissent ensemble. Taille du nœud = volume de mentions.',
      read: 'Couleur = catégorie (bleu = phosphatiers, vert = additifs, orange = intégrateurs, violet = régulateurs). Les liens épais = co-occurrences fréquentes. Glisser les nœuds pour explorer. Révèle les alliances et axes d\'influence.',
      dataKey: 'stakeholders',
    },
    'signals': {
      title: 'Signaux de marché (IA)',
      what: 'Insights actionnables extraits automatiquement des articles par le modèle de langage.',
      source: 'Classification LLM (Gemini) de chaque article : une phrase d\'insight synthétique + position (bullish/bearish), impact, narratif, acteurs.',
      read: 'Bordure verte = bullish, rouge = bearish. Le badge impact (high/medium) priorise. Filtrer par impact en haut à droite. C\'est la couche "so what" au-dessus du flux brut d\'articles.',
      dataKey: 'signals',
    },
    'articles': {
      title: 'Flux d\'articles',
      what: 'Le corpus brut d\'articles collectés, extraits, qualifiés et classifiés — la source de toutes les autres sections.',
      source: 'Collecte RSS multilingue (58 sources : FeedNavigator, AllAboutFeed, Reuters, etc.) → extraction de texte → filtre qualité → classification IA.',
      read: 'Filtrer par région, narratif, position ou recherche libre. Chaque ligne lie à l\'article original. La confiance (%) indique la certitude de la classification IA.',
      dataKey: 'articles',
    },
  };

  // Cache of fetched data for export
  const dataCache = {};

  async function fetchData(key) {
    if (dataCache[key]) return dataCache[key];
    try {
      const r = await fetch('data/' + key + '.json');
      if (!r.ok) return null;
      const d = await r.json();
      dataCache[key] = d;
      return d;
    } catch { return null; }
  }

  // --------------------------------------------------------------------------
  // CSV conversion (flattens arrays of objects; best-effort for nested)
  // --------------------------------------------------------------------------
  function toCSV(data) {
    let rows = [];
    if (Array.isArray(data)) rows = data;
    else if (data && typeof data === 'object') {
      // find the first array property
      const arrKey = Object.keys(data).find(k => Array.isArray(data[k]) && data[k].length && typeof data[k][0] === 'object');
      if (arrKey) rows = data[arrKey];
      else {
        // flatten simple key/value
        const keys = Object.keys(data).filter(k => typeof data[k] !== 'object');
        return keys.join(',') + '\n' + keys.map(k => csvCell(data[k])).join(',');
      }
    }
    if (!rows.length) return '';
    const cols = [...new Set(rows.flatMap(r => Object.keys(r)))].filter(c => {
      // skip very long array columns (like full price history)
      const sample = rows.find(r => r[c] != null);
      return !(sample && Array.isArray(sample[c]) && sample[c].length > 12);
    });
    const header = cols.join(',');
    const body = rows.map(r => cols.map(c => csvCell(r[c])).join(',')).join('\n');
    return header + '\n' + body;
  }

  function csvCell(v) {
    if (v == null) return '';
    if (Array.isArray(v)) v = v.join('; ');
    else if (typeof v === 'object') v = JSON.stringify(v);
    v = String(v);
    if (/[",\n]/.test(v)) v = '"' + v.replace(/"/g, '""') + '"';
    return v;
  }

  function download(filename, content, mime) {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // --------------------------------------------------------------------------
  // Modal for raw data consultation
  // --------------------------------------------------------------------------
  function openModal(title, data) {
    let overlay = document.getElementById('ie-modal-overlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'ie-modal-overlay';
      overlay.className = 'ie-modal-overlay';
      overlay.innerHTML = `
        <div class="ie-modal">
          <div class="ie-modal-header">
            <h3 id="ie-modal-title"></h3>
            <button class="ie-modal-close" aria-label="Close">&times;</button>
          </div>
          <div class="ie-modal-body"><pre id="ie-modal-pre"></pre></div>
        </div>`;
      document.body.appendChild(overlay);
      overlay.addEventListener('click', e => { if (e.target === overlay) overlay.style.display = 'none'; });
      overlay.querySelector('.ie-modal-close').addEventListener('click', () => overlay.style.display = 'none');
    }
    document.getElementById('ie-modal-title').textContent = title;
    document.getElementById('ie-modal-pre').textContent = JSON.stringify(data, null, 2);
    overlay.style.display = 'flex';
  }

  // --------------------------------------------------------------------------
  // Build toolbar (ⓘ + export menu) for a section
  // --------------------------------------------------------------------------
  function buildToolbar(section, id, legend) {
    const toolbar = document.createElement('div');
    toolbar.className = 'ie-toolbar';

    // Info button + popover
    const infoWrap = document.createElement('div');
    infoWrap.className = 'ie-info-wrap';
    infoWrap.innerHTML = `
      <button class="ie-btn ie-info-btn" aria-label="Explain this section">&#9432;</button>
      <div class="ie-popover">
        <h4>${legend.title}</h4>
        <p><span class="ie-pop-label">Quoi&nbsp;:</span> ${legend.what}</p>
        <p><span class="ie-pop-label">Source&nbsp;:</span> ${legend.source}</p>
        <p><span class="ie-pop-label">Lecture&nbsp;:</span> ${legend.read}</p>
      </div>`;

    const infoBtn = infoWrap.querySelector('.ie-info-btn');
    const popover = infoWrap.querySelector('.ie-popover');
    infoBtn.addEventListener('click', e => {
      e.stopPropagation();
      document.querySelectorAll('.ie-popover.open').forEach(p => { if (p !== popover) p.classList.remove('open'); });
      popover.classList.toggle('open');
    });

    // Export menu
    const exportWrap = document.createElement('div');
    exportWrap.className = 'ie-export-wrap';
    exportWrap.innerHTML = `
      <button class="ie-btn ie-export-btn">Data &#9662;</button>
      <div class="ie-export-menu">
        <button data-act="view">View raw data</button>
        <button data-act="csv">Download CSV</button>
        <button data-act="json">Download JSON</button>
      </div>`;
    const exportBtn = exportWrap.querySelector('.ie-export-btn');
    const exportMenu = exportWrap.querySelector('.ie-export-menu');
    exportBtn.addEventListener('click', e => {
      e.stopPropagation();
      document.querySelectorAll('.ie-export-menu.open').forEach(m => { if (m !== exportMenu) m.classList.remove('open'); });
      exportMenu.classList.toggle('open');
    });

    exportMenu.querySelectorAll('button').forEach(btn => {
      btn.addEventListener('click', async e => {
        e.stopPropagation();
        exportMenu.classList.remove('open');
        const data = await fetchData(legend.dataKey);
        if (!data) { alert('Données non disponibles pour cette section.'); return; }
        const act = btn.getAttribute('data-act');
        if (act === 'view') openModal(legend.title, data);
        else if (act === 'json') download(legend.dataKey + '.json', JSON.stringify(data, null, 2), 'application/json');
        else if (act === 'csv') {
          const csv = toCSV(data);
          if (!csv) { alert('Format non exportable en CSV — utilise JSON.'); return; }
          download(legend.dataKey + '.csv', csv, 'text/csv');
        }
      });
    });

    toolbar.appendChild(infoWrap);
    toolbar.appendChild(exportWrap);
    return toolbar;
  }

  // Close popovers/menus on outside click
  document.addEventListener('click', () => {
    document.querySelectorAll('.ie-popover.open, .ie-export-menu.open').forEach(el => el.classList.remove('open'));
  });

  // --------------------------------------------------------------------------
  // Init: attach toolbar to each section with a known id
  // --------------------------------------------------------------------------
  function init() {
    Object.keys(LEGENDS).forEach(id => {
      const section = document.getElementById(id);
      if (!section) return;
      const h2 = section.querySelector('h2');
      if (!h2) return;
      // Wrap h2 in a flex row with the toolbar
      const toolbar = buildToolbar(section, id, LEGENDS[id]);
      h2.style.display = 'inline-block';
      const row = document.createElement('div');
      row.className = 'ie-title-row';
      h2.parentNode.insertBefore(row, h2);
      row.appendChild(h2);
      row.appendChild(toolbar);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
