/* ============================================================================
   map.js — D3 v7 choropleth using world-atlas TopoJSON
   Intensity = article mentions per region (mapped to country list)
   ============================================================================ */

const WorldMap = (() => {

  // Map our internal regions to ISO 3166-1 numeric codes (TopoJSON uses these)
  // Subset only — what matters for the feed industry
  const REGION_COUNTRIES = {
    'Americas':     ['840', '076', '032', '170', '484', '124', '604', '152', '218', '858'],
    'Europe':       ['250', '276', '724', '380', '528', '826', '616', '208', '578', '752', '792'],
    'Asia-Pacific': ['156', '356', '392', '410', '360', '764', '704', '608', '036', '554'],
    'MENA':         ['504', '818', '682', '784', '414', '048', '634', '512', '320', '376', '364'],
    'Africa':       ['566', '710', '404', '231', '818', '288', '894', '894', '180', '012'],
  };

  function render(articles) {
    const container = document.getElementById('world-map');
    if (!container) return;

    // Count mentions per region from articles[] (each article has classification.regions)
    const regionCounts = {};
    articles.forEach(a => {
      const regs = (a.classification && a.classification.regions) || [];
      regs.forEach(r => { regionCounts[r] = (regionCounts[r] || 0) + 1; });
    });

    // Build country -> count map
    const countryCounts = {};
    Object.entries(regionCounts).forEach(([region, count]) => {
      const codes = REGION_COUNTRIES[region] || [];
      codes.forEach(c => { countryCounts[c] = (countryCounts[c] || 0) + count; });
    });

    const maxCount = Math.max(1, ...Object.values(countryCounts));

    // Color scale
    const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const color = d3.scaleSequential(d3.interpolateBlues).domain([0, maxCount]);
    if (isDark) color.interpolator(d3.interpolateRgb('#1c1c20', '#60a5fa'));

    const width = container.clientWidth || 600;
    const height = container.clientHeight || 280;

    // Clear previous
    container.innerHTML = '';
    const tooltip = d3.select(container).append('div').attr('class', 'map-tooltip');

    const svg = d3.select(container)
      .append('svg')
      .attr('viewBox', `0 0 ${width} ${height}`)
      .attr('preserveAspectRatio', 'xMidYMid meet');

    const projection = d3.geoNaturalEarth1().scale(width / 6.2).translate([width / 2, height / 2]);
    const path = d3.geoPath().projection(projection);

    // Fetch world TopoJSON (110m countries, ~100kb gzipped)
    fetch('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json')
      .then(r => r.json())
      .then(world => {
        const countries = topojson.feature(world, world.objects.countries).features;
        svg.append('g')
          .selectAll('path')
          .data(countries)
          .join('path')
          .attr('class', d => {
            const code = String(d.id).padStart(3, '0');
            return 'country' + (countryCounts[code] ? ' has-data' : '');
          })
          .attr('d', path)
          .attr('fill', d => {
            const code = String(d.id).padStart(3, '0');
            const c = countryCounts[code];
            return c ? color(c) : null;
          })
          .on('mousemove', (event, d) => {
            const code = String(d.id).padStart(3, '0');
            const c = countryCounts[code];
            tooltip.style('opacity', 1)
              .html(`<strong>${d.properties.name}</strong>${c ? `<br>${c} mentions` : ''}`)
              .style('left', (event.offsetX + 12) + 'px')
              .style('top',  (event.offsetY + 12) + 'px');
          })
          .on('mouseleave', () => tooltip.style('opacity', 0));
      })
      .catch(err => {
        container.innerHTML = '<p style="color:var(--text-muted);font-size:0.8125rem;">World map unavailable.</p>';
        console.error('World atlas load failed:', err);
      });
  }

  return { render };

})();
