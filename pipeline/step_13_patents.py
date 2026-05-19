"""PHASE 13 — Patent watch.

Tracks recent patent filings relevant to feed phosphates, additives, and
amino acid manufacturing. Uses Google Patents search RSS-like (via Google
News scoped to patents.google.com) as a free fallback.

A production deployment would migrate to:
- Lens.org Scholar API (free up to 1000 req/mo, structured patent data)
- EPO Open Patent Services (free, requires registration)
For now we use free public search results.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus
import feedparser
from . import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("patents")

# Patent query themes
PATENT_QUERIES = [
    {"theme": "Feed phosphate manufacturing", "query": "patent (monocalcium phosphate OR MDCP OR DCP) feed manufacturing"},
    {"theme": "Methionine synthesis",         "query": "patent methionine feed production manufacturing"},
    {"theme": "Lysine biotechnology",         "query": "patent lysine fermentation feed"},
    {"theme": "Phytase enzymes",              "query": "patent phytase feed enzyme"},
    {"theme": "Probiotic feed additives",     "query": "patent probiotic poultry feed additive"},
    {"theme": "Methane reduction additives",  "query": "patent (methane reduction OR 3-NOP OR Bovaer) cattle feed"},
    {"theme": "Mycotoxin binders",            "query": "patent mycotoxin binder feed"},
    {"theme": "Heavy metals removal",         "query": "patent (cadmium removal OR heavy metals) phosphate purification"},
]

KEY_APPLICANTS = [
    "DSM", "Adisseo", "Evonik", "Ajinomoto", "CJ", "Cargill", "Novus",
    "Alltech", "Kemin", "Mosaic", "Nutrien", "OCP", "ICL", "Yara",
]


def fetch_patents() -> list:
    cutoff = datetime.now(timezone.utc) - timedelta(days=180)
    items = []

    for q in PATENT_QUERIES:
        # Google News restricted to patent-related sources
        query = q["query"] + " (site:patents.google.com OR site:patents.justia.com OR USPTO OR EPO)"
        url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en&gl=US&ceid=en-US:en"
        try:
            parsed = feedparser.parse(url, request_headers={"User-Agent": config.USER_AGENT})
        except Exception as e:  # noqa: BLE001
            log.warning("  %s failed: %s", q["theme"], e)
            continue

        for entry in parsed.entries[:8]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            if not title or not link:
                continue
            pub = None
            for k in ("published_parsed", "updated_parsed"):
                t = entry.get(k)
                if t:
                    pub = datetime(*t[:6], tzinfo=timezone.utc)
                    break
            if pub and pub < cutoff:
                continue
            # Detect known applicant in title
            applicant = next((a for a in KEY_APPLICANTS if a.lower() in title.lower()), None)

            items.append({
                "theme": q["theme"],
                "title": title[:300],
                "url": link,
                "published_at": pub.isoformat() if pub else None,
                "applicant_hint": applicant,
            })

    # Dedup by title prefix
    seen, dedup = set(), []
    for p in items:
        key = p["title"][:100].lower()
        if key in seen:
            continue
        seen.add(key)
        dedup.append(p)

    dedup.sort(key=lambda x: x.get("published_at") or "", reverse=True)
    return dedup[:40]


def main() -> None:
    log.info("Fetching patent signals from %d themes…", len(PATENT_QUERIES))
    patents = fetch_patents()

    # Aggregate by theme and applicant
    by_theme = {}
    by_applicant = {}
    for p in patents:
        by_theme[p["theme"]] = by_theme.get(p["theme"], 0) + 1
        if p["applicant_hint"]:
            by_applicant[p["applicant_hint"]] = by_applicant.get(p["applicant_hint"], 0) + 1

    out = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(patents),
        "patents": patents,
        "by_theme": by_theme,
        "by_applicant": dict(sorted(by_applicant.items(), key=lambda x: x[1], reverse=True)),
    }
    out_path = config.SITE_DATA_DIR / "patents.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Wrote %d patent signals → %s", len(patents), out_path.name)


if __name__ == "__main__":
    main()
