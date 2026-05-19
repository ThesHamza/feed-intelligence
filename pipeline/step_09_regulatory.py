"""PHASE 9 — Regulatory radar.

Pulls regulatory news from agency RSS feeds and filters for feed/phosphate
relevance. Outputs structured alerts (region, body, topic, severity).
"""
from __future__ import annotations
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus
import feedparser
from . import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("regulatory")

# Mix: direct agency feeds + Google News scoped queries for harder-to-reach sources
REGULATORY_SOURCES = [
    # EU
    {"body": "EFSA",   "region": "Europe", "type": "google_news",
     "query": 'site:efsa.europa.eu (feed OR phosphate OR cadmium OR additive)'},
    {"body": "EUR-Lex", "region": "Europe", "type": "google_news",
     "query": 'site:eur-lex.europa.eu (animal feed OR phosphate OR EFSA)'},
    {"body": "EU Commission", "region": "Europe", "type": "google_news",
     "query": 'site:ec.europa.eu (feed regulation OR phosphate OR heavy metals)'},
    # US
    {"body": "FDA", "region": "Americas", "type": "google_news",
     "query": 'site:fda.gov (animal feed OR phosphate OR CVM)'},
    {"body": "USDA", "region": "Americas", "type": "google_news",
     "query": 'site:usda.gov (feed OR phosphate OR fertilizer)'},
    {"body": "AAFCO", "region": "Americas", "type": "google_news",
     "query": 'site:aafco.org feed ingredient'},
    # International
    {"body": "FAO", "region": "Global", "type": "google_news",
     "query": 'site:fao.org (feed OR phosphate OR animal nutrition)'},
    {"body": "Codex Alimentarius", "region": "Global", "type": "google_news",
     "query": 'site:fao.org codex feed'},
    # Asia & MENA
    {"body": "China MARA", "region": "Asia-Pacific", "type": "google_news",
     "query": 'China (feed regulation OR phosphate import) 2025 OR 2026'},
    {"body": "Morocco ONSSA", "region": "MENA", "type": "google_news",
     "query": 'Maroc ONSSA aliment animal réglementation'},
]

TOPICS_KEYWORDS = {
    "heavy_metals":  ["cadmium", "lead", "mercury", "arsenic", "heavy metal"],
    "additives":     ["additive", "feed additive", "premix"],
    "sustainability":["ghg", "methane", "carbon", "emission", "sustainability"],
    "trade":         ["tariff", "import", "export", "quota", "duty"],
    "safety":        ["mycotoxin", "contamination", "recall", "salmonella"],
    "labeling":      ["label", "marking", "traceability", "origin"],
}

SEVERITY_KEYWORDS = {
    "high":   ["ban", "prohibition", "withdraw", "suspend", "recall", "mandatory", "obligation", "interdiction", "obligatoire"],
    "medium": ["amendment", "consultation", "proposal", "guideline", "modification"],
    "low":    ["opinion", "report", "study", "review", "assessment"],
}


def _build_url(src: dict) -> str:
    q = quote_plus(src["query"])
    return f"https://news.google.com/rss/search?q={q}&hl=en&gl=US&ceid=en-US:en"


def _detect_topic(text: str) -> str:
    text_l = text.lower()
    scores = {t: sum(1 for k in kws if k in text_l) for t, kws in TOPICS_KEYWORDS.items()}
    best = max(scores.items(), key=lambda x: x[1])
    return best[0] if best[1] > 0 else "general"


def _detect_severity(text: str) -> str:
    text_l = text.lower()
    for level in ("high", "medium", "low"):
        if any(k in text_l for k in SEVERITY_KEYWORDS[level]):
            return level
    return "low"


def collect() -> list:
    cutoff = datetime.now(timezone.utc) - timedelta(days=60)
    alerts = []

    for src in REGULATORY_SOURCES:
        url = _build_url(src)
        try:
            parsed = feedparser.parse(url, request_headers={"User-Agent": config.USER_AGENT})
        except Exception as e:  # noqa: BLE001
            log.warning("  %s failed: %s", src["body"], e)
            continue

        if not parsed.entries:
            log.info("  %s: 0 entries", src["body"])
            continue

        for entry in parsed.entries[:15]:
            link = entry.get("link", "")
            title = entry.get("title", "").strip()
            if not title or not link:
                continue
            # Try to parse date
            pub = None
            for k in ("published_parsed", "updated_parsed"):
                t = entry.get(k)
                if t:
                    pub = datetime(*t[:6], tzinfo=timezone.utc)
                    break
            if pub and pub < cutoff:
                continue

            alerts.append({
                "body": src["body"],
                "region": src["region"],
                "title": title[:300],
                "url": link,
                "published_at": pub.isoformat() if pub else None,
                "topic": _detect_topic(title),
                "severity": _detect_severity(title),
            })
        log.info("  %s: %d alerts", src["body"], len([a for a in alerts if a["body"] == src["body"]]))

    # Dedup by title hash (Google News may return same item via multiple sources)
    seen, dedup = set(), []
    for a in alerts:
        key = re.sub(r'\W+', '', a["title"].lower())[:100]
        if key in seen:
            continue
        seen.add(key)
        dedup.append(a)

    # Sort by severity (high first) then recency
    sev_order = {"high": 0, "medium": 1, "low": 2}
    dedup.sort(key=lambda x: (sev_order.get(x["severity"], 3), x["published_at"] or ""), reverse=False)
    return dedup[:60]


def main() -> None:
    log.info("Fetching regulatory alerts from %d sources…", len(REGULATORY_SOURCES))
    alerts = collect()
    out = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(alerts),
        "alerts": alerts,
        "by_region": _count_by(alerts, "region"),
        "by_severity": _count_by(alerts, "severity"),
        "by_topic": _count_by(alerts, "topic"),
    }
    out_path = config.SITE_DATA_DIR / "regulatory.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Wrote %d regulatory alerts → %s", len(alerts), out_path.name)


def _count_by(items, key):
    out = {}
    for it in items:
        v = it.get(key) or "unknown"
        out[v] = out.get(v, 0) + 1
    return out


if __name__ == "__main__":
    main()
