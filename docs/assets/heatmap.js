/* ============================================================================
   heatmap.js — Commodity × region heatmap using D3 color scale
   ============================================================================ */

const Heatmap = (() => {

  function render(heatmapData) {
    const container = document.getElementById('heatmap');
    if (!container || !heatmapData) return;

    const { commodities, regions, matrix } = heatmapData;

    // Color scale: diverging (red → grey → green) based on sentiment
    const colorScale = d3.scaleDiverging()
      .domain([-1, 0, 1])
      .interpolator(d3.interpolateRdYlGn);

    // Build HTML table
    let html = '<table class="heatmap-table"><thead><tr><th></th>';
    regions.forEach(r => { html += `<th>${r}</th>`; });
    html += '</tr></thead><tbody>';

    matrix.forEach(row => {
      html += `<tr><td class="label">${row.commodity.replace(/_/g, ' ')}</td>`;
      regions.forEach(reg => {
        const cell = row.regions[reg] || { count: 0, sentiment: 0 };
        if (cell.count === 0) {
          html += '<td><div class="heatmap-cell empty" title="No mentions">—</div></td>';
        } else {
          const color = colorScale(cell.sentiment);
          const title = `${row.commodity} × ${reg}: ${cell.count} mentions, sentiment ${cell.sentiment.toFixed(2)}`;
          html += `<td><div class="heatmap-cell" style="background:${color}" title="${title}">${cell.count}</div></td>`;
        }
      });
      html += '</tr>';
    });
    html += '</tbody></table>';

    container.innerHTML = html;
  }

  return { render };
})();
