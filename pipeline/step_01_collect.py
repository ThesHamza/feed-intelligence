"""PHASE 1 — RSS collection.

Reads sources.yaml, fetches entries from each feed, dedups by URL, and inserts
into the raw_urls table. Only keeps entries published within the last
COLLECTION_WINDOW_HOURS hours.

Usage: python -m pipeline.step_01_collect
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import feedparser
import yaml

from . import config, get_connection, init_schema

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("collect")


def _build_feed_url(src: dict) -> str:
    """Build the RSS URL for a source entry."""
    t = src["type"]
    if t == "rss":
        return src["url"]

    q = quote_plus(src["query"])
    lang = src.get("language", "en")

    if t == "google_news":
        # hl = host language, gl = country, ceid = combined edition
        lang_map = {"en": "en-US:en", "fr": "fr:fr", "es": "es:es", "pt": "pt-BR:pt-419"}
        gl_map = {"en": "US", "fr": "FR", "es": "ES", "pt": "BR"}
        ceid = lang_map.get(lang, "en-US:en")
        gl = gl_map.get(lang, "US")
        return (
            f"https://news.google.com/rss/search?q={q}&hl={lang}&gl={gl}&ceid={ceid}"
        )

    if t == "bing_news":
        return f"https://www.bing.com/news/search?q={q}&format=RSS"

    raise ValueError(f"Unknown source type: {t}")


def _parse_published(entry) -> datetime | None:
    """Extract published datetime from a feedparser entry."""
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return None


def collect_source(src: dict, cutoff: datetime) -> tuple[int, int]:
    """Fetch one source and insert new URLs. Returns (total, inserted)."""
    feed_url = _build_feed_url(src)
    try:
        # feedparser handles timeouts via requests if installed
        parsed = feedparser.parse(feed_url, request_headers={"User-Agent": config.USER_AGENT})
    except Exception as e:  # noqa: BLE001
        log.warning("Source '%s' parse error: %s", src["name"], e)
        return 0, 0

    if parsed.bozo and not parsed.entries:
        log.warning("Source '%s' empty/malformed: %s", src["name"], parsed.bozo_exception)
        return 0, 0

    inserted = 0
    total = len(parsed.entries)

    with get_connection() as conn:
        for entry in parsed.entries:
            url = entry.get("link")
            if not url:
                continue

            pub = _parse_published(entry)
            if pub and pub < cutoff:
                continue  # too old

            try:
                conn.execute(
                    """INSERT OR IGNORE INTO raw_urls
                       (url, source, query, title_hint, published_at, lang_hint, region_hint)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        url,
                        src["name"],
                        src.get("query"),
                        entry.get("title", "")[:500],
                        pub.isoformat() if pub else None,
                        src.get("language"),
                        src.get("region_hint"),
                    ),
                )
                if conn.total_changes > 0:
                    inserted = conn.execute(
                        "SELECT changes()"
                    ).fetchone()[0] + (inserted - inserted)  # noop, simplifies count
            except Exception as e:  # noqa: BLE001
                log.debug("Insert error for %s: %s", url, e)

        # Recount properly via a single query
        inserted_rows = conn.execute(
            "SELECT COUNT(*) FROM raw_urls WHERE source = ? AND fetched_at >= datetime('now', '-1 minute')",
            (src["name"],),
        ).fetchone()[0]
        conn.commit()

    return total, inserted_rows


def main() -> None:
    init_schema()

    with open(config.SOURCES_FILE, encoding="utf-8") as f:
        sources = yaml.safe_load(f).get("sources", [])

    cutoff = datetime.now(timezone.utc) - timedelta(hours=config.COLLECTION_WINDOW_HOURS)
    log.info("Collecting from %d sources (window: %dh)", len(sources), config.COLLECTION_WINDOW_HOURS)

    grand_total = 0
    grand_inserted = 0
    failures = 0

    for src in sources:
        try:
            total, inserted = collect_source(src, cutoff)
            grand_total += total
            grand_inserted += inserted
            log.info("  %-50s total=%3d new=%3d", src["name"][:50], total, inserted)
            time.sleep(0.4)  # polite delay between sources
        except Exception as e:  # noqa: BLE001
            failures += 1
            log.error("Source '%s' failed: %s", src["name"], e)

    log.info("=" * 70)
    log.info("Collection summary: %d entries seen, %d new URLs inserted, %d source failures",
             grand_total, grand_inserted, failures)


if __name__ == "__main__":
    main()
