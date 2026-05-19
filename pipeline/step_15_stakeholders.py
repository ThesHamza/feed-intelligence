"""PHASE 15 — Stakeholder network graph.

Builds a co-occurrence network of all entities (companies, agencies, regions)
extracted from classified articles. Edges = co-mentions in same article.
Edge weight = number of co-mentions. Used as a force-directed graph in
the dashboard to map the OCP ecosystem.
"""
from __future__ import annotations
import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from itertools import combinations
from . import config, get_connection, init_schema

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("stakeholders")


def _entity_category(name: str) -> str:
    for cat, aliases in config.ENTITIES_TIER_1.items():
        if any(name.lower() == a.lower() for a in aliases):
            return cat
    return "other"


def main() -> None:
    init_schema()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT c.key_companies, c.regions
               FROM classifications c
               JOIN quality q ON q.article_id = c.article_id AND q.qualified = 1
               WHERE c.classified_at >= ?""", (cutoff,)).fetchall()

    nodes = Counter()
    edges = defaultdict(int)

    for r in rows:
        try:
            companies = json.loads(r["key_companies"] or "[]")
        except Exception:
            companies = []
        # Count nodes
        for c in companies:
            nodes[c] += 1
        # Build co-occurrence edges (companies mentioned together)
        for a, b in combinations(sorted(set(companies)), 2):
            key = (a, b)
            edges[key] += 1

    # Filter: keep only entities with enough mentions
    min_mentions = 2
    kept_nodes = {name: cnt for name, cnt in nodes.items() if cnt >= min_mentions}

    # Filter edges: both endpoints must be kept and weight >= 1
    kept_edges = [
        {"source": a, "target": b, "weight": w}
        for (a, b), w in edges.items()
        if a in kept_nodes and b in kept_nodes
    ]
    # Cap edges for visual readability
    kept_edges.sort(key=lambda e: e["weight"], reverse=True)
    kept_edges = kept_edges[:120]

    # Re-filter nodes: only keep those that appear in kept_edges or have high mention count
    used_in_edges = set()
    for e in kept_edges:
        used_in_edges.add(e["source"]); used_in_edges.add(e["target"])

    node_list = []
    for name, cnt in kept_nodes.items():
        if name not in used_in_edges and cnt < 5:
            continue
        node_list.append({
            "id": name,
            "category": _entity_category(name),
            "mentions": cnt,
        })

    log.info("  Built network: %d nodes, %d edges", len(node_list), len(kept_edges))

    out = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "nodes": node_list,
        "edges": kept_edges,
        "stats": {
            "total_entities": len(nodes),
            "kept_nodes": len(node_list),
            "kept_edges": len(kept_edges),
        },
    }
    out_path = config.SITE_DATA_DIR / "stakeholders.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Wrote stakeholders → %s", out_path.name)


if __name__ == "__main__":
    main()
