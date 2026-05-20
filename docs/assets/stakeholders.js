/* ============================================================================
   stakeholders.js — D3 force-directed graph of stakeholder co-occurrence
   ============================================================================ */

const Stakeholders = (() => {

  function render(data) {
    const container = document.getElementById('stakeholder-graph');
    if (!container || !data || !data.nodes) return;

    const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const colors = {
      phosphate_suppliers: '#3b82f6',
      additive_suppliers: '#16a34a',
      integrators: '#ea580c',
      regulator: '#8b5cf6',
      other: '#94a3b8',
    };
    const textColor = isDark ? '#cbd5e1' : '#0f172a';

    const width = container.clientWidth || 800;
    const height = 500;

    container.innerHTML = '';
    const svg = d3.select(container).append('svg')
      .attr('viewBox', `0 0 ${width} ${height}`);

    // Defensive copy of data (D3 mutates)
    const nodes = data.nodes.map(d => Object.assign({}, d));
    const links = (data.edges || []).map(d => Object.assign({}, d));

    // Module emits 'mentions'; sample data emits 'size' — normalize
    nodes.forEach(n => {
      if (n.size == null) n.size = n.mentions || 1;
      if (n.label == null) n.label = n.id;
    });

    const sizeScale = d3.scaleLinear()
      .domain([0, Math.max(...nodes.map(n => n.size))])
      .range([8, 22]);

    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id(d => d.id).distance(90).strength(0.5))
      .force('charge', d3.forceManyBody().strength(-220))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(d => sizeScale(d.size) + 4));

    const link = svg.append('g')
      .attr('stroke', isDark ? '#475569' : '#cbd5e1')
      .attr('stroke-opacity', 0.55)
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke-width', d => Math.sqrt(d.weight || 1));

    const node = svg.append('g')
      .selectAll('g')
      .data(nodes)
      .join('g')
      .call(d3.drag()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x; d.fy = d.y;
        })
        .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null; d.fy = null;
        }));

    node.append('circle')
      .attr('r', d => sizeScale(d.size))
      .attr('fill', d => colors[d.category] || colors.other)
      .attr('stroke', isDark ? '#0f172a' : '#fff')
      .attr('stroke-width', 1.5);

    node.append('title').text(d => `${d.label}\n${d.category}\n${d.size} mentions`);

    node.append('text')
      .attr('class', 'node-label')
      .attr('dx', d => sizeScale(d.size) + 4)
      .attr('dy', 4)
      .attr('fill', textColor)
      .text(d => d.label);

    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);
      node.attr('transform', d => `translate(${d.x},${d.y})`);
    });
  }

  return { render };
})();
