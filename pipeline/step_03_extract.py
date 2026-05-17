"""PHASE 3 — Content extraction.

Fetches HTML for each pending URL, extracts article content using:
1. Trafilatura (primary — best multilingual quality)
2. newspaper3k (fallback if trafilatura returns nothing or < 200 chars)

Handles 429 (exponential backoff), 403 (skip), timeouts.

Usage: python -m pipeline.step_03_extract
"""

from __future__ import annotations

import json
import logging
import time

import requests
import trafilatura
from newspaper import Article  # type: ignore

from . import config, get_connection, init_schema

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("extract")


def _fetch_html(url: str) -> tuple[str | None, str | None]:
    """Fetch URL with retries. Returns (html, error_msg)."""
    headers = {
        "User-Agent": config.USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,fr;q=0.8,es;q=0.7",
    }
    delay = 1.0
    for attempt in range(config.REQUEST_RETRIES + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=config.REQUEST_TIMEOUT, allow_redirects=True)
            if resp.status_code == 200:
                return resp.text, None
            if resp.status_code == 429:
                log.debug("429 on %s — backing off %.1fs", url, delay)
                time.sleep(delay)
                delay *= config.BACKOFF_BASE
                continue
            if resp.status_code in (403, 401):
                return None, f"http_{resp.status_code}"
            return None, f"http_{resp.status_code}"
        except requests.Timeout:
            return None, "timeout"
        except requests.RequestException as e:
            return None, f"req_error:{type(e).__name__}"
    return None, "max_retries"


def _extract_trafilatura(html: str, url: str) -> dict | None:
    """Returns dict {title, text, authors, date, language} or None."""
    try:
        result = trafilatura.extract(
            html,
            url=url,
            output_format="json",
            include_comments=False,
            include_tables=False,
            with_metadata=True,
            favor_recall=True,
        )
        if not result:
            return None
        data = json.loads(result)
        text = data.get("text") or data.get("raw_text") or ""
        if len(text) < 200:
            return None
        return {
            "title": (data.get("title") or "").strip()[:500],
            "body": text,
            "authors": ", ".join(data.get("author", "").split(";")) if data.get("author") else None,
            "published_date": data.get("date"),
            "language": data.get("language"),
        }
    except Exception as e:  # noqa: BLE001
        log.debug("Trafilatura fail for %s: %s", url, e)
        return None


def _extract_newspaper(html: str, url: str) -> dict | None:
    """Fallback extractor using newspaper3k."""
    try:
        art = Article(url)
        art.set_html(html)
        art.parse()
        text = art.text or ""
        if len(text) < 200:
            return None
        return {
            "title": (art.title or "").strip()[:500],
            "body": text,
            "authors": ", ".join(art.authors) if art.authors else None,
            "published_date": art.publish_date.isoformat() if art.publish_date else None,
            "language": None,
        }
    except Exception as e:  # noqa: BLE001
        log.debug("Newspaper fail for %s: %s", url, e)
        return None


def extract_one(url_id: int, canonical: str) -> str:
    """Extract one article. Returns status: 'extracted' | 'failed' | 'skipped'."""
    html, err = _fetch_html(canonical)
    if html is None:
        with get_connection() as conn:
            conn.execute("UPDATE urls SET status = 'failed', error_msg = ? WHERE id = ?",
                         (err, url_id))
            conn.commit()
        return "failed"

    article = _extract_trafilatura(html, canonical)
    extractor = "trafilatura"
    if article is None:
        article = _extract_newspaper(html, canonical)
        extractor = "newspaper3k"

    if article is None:
        with get_connection() as conn:
            conn.execute("UPDATE urls SET status = 'failed', error_msg = ? WHERE id = ?",
                         ("no_content", url_id))
            conn.commit()
        return "failed"

    word_count = len(article["body"].split())
    with get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO articles
               (url_id, title, body, authors, published_date, language, word_count, extractor)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (url_id, article["title"], article["body"], article["authors"],
             article["published_date"], article["language"], word_count, extractor),
        )
        conn.execute("UPDATE urls SET status = 'extracted' WHERE id = ?", (url_id,))
        conn.commit()
    return "extracted"


def main() -> None:
    init_schema()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, url_canonical FROM urls WHERE status = 'pending' LIMIT 500"
        ).fetchall()

    log.info("Extracting %d URLs", len(rows))
    counts = {"extracted": 0, "failed": 0}

    for i, row in enumerate(rows, 1):
        status = extract_one(row["id"], row["url_canonical"])
        counts[status] = counts.get(status, 0) + 1
        if i % 25 == 0:
            log.info("  progress: %d/%d (ok=%d, fail=%d)",
                     i, len(rows), counts["extracted"], counts["failed"])
        time.sleep(0.5)  # be polite to publishers

    log.info("=" * 70)
    log.info("Extraction summary: %s", counts)


if __name__ == "__main__":
    main()
