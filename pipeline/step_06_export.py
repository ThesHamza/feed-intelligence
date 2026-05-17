"""PHASE 6 — JSON export for the dashboard.

Generates four files in site/data/:
  - articles.json    latest N qualified+classified articles
  - entities.json    aggregated mentions per company (rolling window)
  - timeseries.json  daily counts: positions, narratives, commodity mentions
  - metadata.json    last_updated, totals, active sources

Usage: python -m pipeline.step_06_export
"""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from . import config, get_connection, init_schema

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("export")


def _parse_json(s: str | None) -> list:
    if not s:
        return []
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return []


def _rel(path) -> str:
    """Pretty-print path relative to ROOT_DIR if possible, else absolute."""
    try:
        return str(path.relative_to(config.ROOT_DIR))
    except ValueError:
        return str(path)


def export_articles() -> int:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT a.id, a.title, a.body, a.language, a.word_count, a.published_date,
                      u.url_canonical AS url, u.region_hint, u.domain,
                      r.source,
                      c.position, c.tone, c.narrative, c.commodities, c.regions,
                      c.key_companies, c.impact, c.confidence, c.signal, c.time_horizon
               FROM articles a
               JOIN urls u ON u.id = a.url_id
               JOIN raw_urls r ON r.id = u.raw_url_id
               JOIN quality q ON q.article_id = a.id AND q.qualified = 1
               JOIN classifications c ON c.article_id = a.id
               ORDER BY COALESCE(a.published_date, a.extracted_at) DESC
               LIMIT ?""",
            (config.EXPORT_ARTICLE_LIMIT,),
        ).fetchall()

    out = []
    for r in rows:
        body = r["body"] or ""
        out.append({
            "id": r["id"],
            "title": r["title"] or "(untitled)",
            "url": r["url"],
            "source": r["source"],
            "domain": r["domain"],
            "date": r["published_date"],
            "lang": r["language"] or "unknown",
            "region": r["region_hint"] or "Global",
            "body_preview": (body[:300] + "…") if len(body) > 300 else body,
            "classification": {
                "position": r["position"],
                "tone": r["tone"],
                "narrative": r["narrative"],
                "commodities": _parse_json(r["commodities"]),
                "regions": _parse_json(r["regions"]),
                "key_companies": _parse_json(r["key_companies"]),
                "impact": r["impact"],
                "confidence": r["confidence"],
                "signal": r["signal"],
                "time_horizon": r["time_horizon"],
            },
        })

    out_path = config.SITE_DATA_DIR / "articles.json"
    config.SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Wrote %d articles → %s", len(out), _rel(out_path))
    return len(out)


def export_entities() -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=config.EXPORT_ENTITY_WINDOW_DAYS)).isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT c.key_companies, c.position, c.classified_at
               FROM classifications c
               JOIN quality q ON q.article_id = c.article_id AND q.qualified = 1
               WHERE c.classified_at >= ?""",
            (cutoff,),
        ).fetchall()

    counter: Counter = Counter()
    sentiment: defaultdict = defaultdict(list)
    last_seen: dict = {}
    pos_map = {"bullish": 1, "bearish": -1, "neutral": 0}

    for r in rows:
        for company in _parse_json(r["key_companies"]):
            counter[company] += 1
            sentiment[company].append(pos_map.get(r["position"], 0))
            if company not in last_seen or r["classified_at"] > last_seen[company]:
                last_seen[company] = r["classified_at"]

    entities = []
    for company, count in counter.most_common():
        scores = sentiment[company]
        avg = sum(scores) / len(scores) if scores else 0.0
        entities.append({
            "company": company,
            "mentions_30d": count,
            "sentiment_avg": round(avg, 2),
            "last_mention": last_seen[company],
        })

    out_path = config.SITE_DATA_DIR / "entities.json"
    out_path.write_text(json.dumps(entities, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Wrote %d entities → %s", len(entities), _rel(out_path))
    return len(entities)


def export_timeseries() -> int:
    today = datetime.now(timezone.utc).date()
    days = [today - timedelta(days=i) for i in range(config.EXPORT_TIMESERIES_DAYS - 1, -1, -1)]
    day_strs = [d.isoformat() for d in days]
    cutoff = days[0].isoformat()

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT c.position, c.narrative, c.commodities,
                      DATE(COALESCE(a.published_date, a.extracted_at)) AS day
               FROM classifications c
               JOIN articles a ON a.id = c.article_id
               JOIN quality q ON q.article_id = a.id AND q.qualified = 1
               WHERE DATE(COALESCE(a.published_date, a.extracted_at)) >= ?""",
            (cutoff,),
        ).fetchall()

    positions = {p: {d: 0 for d in day_strs} for p in ("bullish", "bearish", "neutral")}
    narratives_total: Counter = Counter()
    commodities: dict = defaultdict(lambda: {d: 0 for d in day_strs})

    for r in rows:
        day = r["day"]
        if day not in positions["bullish"]:
            continue
        if r["position"] in positions:
            positions[r["position"]][day] += 1
        if r["narrative"]:
            narratives_total[r["narrative"]] += 1
        for c in _parse_json(r["commodities"]):
            commodities[c][day] += 1

    out = {
        "dates": day_strs,
        "positions": {k: [v[d] for d in day_strs] for k, v in positions.items()},
        "narratives_total": dict(narratives_total.most_common()),
        "commodities": {k: [v[d] for d in day_strs] for k, v in commodities.items()},
    }

    out_path = config.SITE_DATA_DIR / "timeseries.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Wrote %d days timeseries → %s", len(day_strs), _rel(out_path))
    return len(day_strs)


def export_metadata(articles_count: int, entities_count: int) -> None:
    with get_connection() as conn:
        total_articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        total_qualified = conn.execute(
            "SELECT COUNT(*) FROM quality WHERE qualified = 1"
        ).fetchone()[0]
        total_classified = conn.execute("SELECT COUNT(*) FROM classifications").fetchone()[0]
        sources_active = conn.execute(
            "SELECT COUNT(DISTINCT source) FROM raw_urls WHERE fetched_at >= datetime('now', '-7 days')"
        ).fetchone()[0]
        avg_conf_row = conn.execute(
            "SELECT AVG(confidence) FROM classifications WHERE classified_at >= datetime('now', '-7 days')"
        ).fetchone()
        avg_conf = float(avg_conf_row[0]) if avg_conf_row[0] is not None else 0.0

    meta = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "articles_shown": articles_count,
        "entities_tracked": entities_count,
        "totals": {
            "articles_extracted": total_articles,
            "articles_qualified": total_qualified,
            "articles_classified": total_classified,
        },
        "sources_active_7d": sources_active,
        "avg_confidence_7d": round(avg_conf, 1),
    }

    out_path = config.SITE_DATA_DIR / "metadata.json"
    out_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Wrote metadata → %s", _rel(out_path))


def main() -> None:
    init_schema()
    articles_count = export_articles()
    entities_count = export_entities()
    export_timeseries()
    export_metadata(articles_count, entities_count)
    log.info("=" * 70)
    log.info("Export complete: %d articles, %d entities", articles_count, entities_count)


if __name__ == "__main__":
    main()
