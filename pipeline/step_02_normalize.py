"""PHASE 2 — URL normalization & deduplication.

For each raw_url not yet normalized:
- Resolve Google News wrappers (extract real article URL)
- Strip tracking params (utm_*, fbclid, gclid, ref, etc.)
- Canonicalize (lowercase host, no trailing slash)
- SHA-256 hash for deduplication
- Insert into urls table with status='pending'

Usage: python -m pipeline.step_02_normalize
"""

from __future__ import annotations

import base64
import hashlib
import logging
import re
import time
from urllib.parse import parse_qs, urlparse, urlunparse

import requests

from . import config, get_connection, init_schema

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("normalize")

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "msclkid", "yclid", "dclid",
    "ref", "ref_src", "ref_url",
    "mc_cid", "mc_eid",
    "_ga", "_gl",
    "ocid", "cmpid",
}


def _resolve_google_news(url: str) -> str:
    """Resolve a Google News wrapper URL to the real article URL.

    Strategy:
    1. If URL matches news.google.com/articles/... pattern, try base64 decode
       (the article ID often contains the original URL).
    2. Fallback: HTTP HEAD request follows redirects.
    """
    parsed = urlparse(url)
    if "news.google.com" not in parsed.netloc:
        return url

    # Strategy 1: extract from article ID (base64 encoded)
    m = re.search(r"/articles/([A-Za-z0-9_-]+)", parsed.path)
    if m:
        try:
            article_id = m.group(1)
            # Google News article IDs are base64url-encoded protobuf
            padded = article_id + "=" * (-len(article_id) % 4)
            decoded = base64.urlsafe_b64decode(padded)
            # Look for http(s):// pattern in decoded bytes
            url_match = re.search(rb"https?://[^\s\x00-\x1f]+", decoded)
            if url_match:
                candidate = url_match.group(0).decode("utf-8", errors="ignore")
                # Trim at first non-URL char
                candidate = re.sub(r"[^\w/:.\-?&=%#~+,@!$'*();]+.*$", "", candidate)
                if candidate.startswith("http"):
                    return candidate
        except Exception:  # noqa: BLE001
            pass

    # Strategy 2: HTTP redirect resolution
    try:
        resp = requests.head(
            url,
            allow_redirects=True,
            timeout=config.REQUEST_TIMEOUT,
            headers={"User-Agent": config.USER_AGENT},
        )
        if resp.url and "news.google.com" not in urlparse(resp.url).netloc:
            return resp.url
    except Exception as e:  # noqa: BLE001
        log.debug("HEAD resolve failed for %s: %s", url, e)

    return url  # give up — keep wrapper


def _strip_tracking(url: str) -> str:
    """Remove tracking params from query string."""
    p = urlparse(url)
    if not p.query:
        return url
    keep = []
    for pair in p.query.split("&"):
        if "=" in pair:
            k = pair.split("=", 1)[0].lower()
            if k in TRACKING_PARAMS:
                continue
        keep.append(pair)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, "&".join(keep), ""))


def _canonicalize(url: str) -> tuple[str, str]:
    """Return (canonical_url, sha256_hash). Lowercases host, trims slashes/fragment."""
    p = urlparse(url)
    netloc = p.netloc.lower()
    path = p.path.rstrip("/")
    if not path:
        path = "/"
    canonical = urlunparse((p.scheme.lower(), netloc, path, p.params, p.query, ""))
    h = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return canonical, h


def normalize_one(raw_id: int, url: str, lang_hint: str | None, region_hint: str | None) -> str:
    """Normalize a single raw URL. Returns status: 'inserted' | 'duplicate' | 'failed'."""
    try:
        resolved = _resolve_google_news(url)
        cleaned = _strip_tracking(resolved)
        canonical, url_hash = _canonicalize(cleaned)
        domain = urlparse(canonical).netloc

        with get_connection() as conn:
            cur = conn.execute(
                """INSERT OR IGNORE INTO urls
                   (raw_url_id, url_canonical, url_hash, domain, lang_hint, region_hint, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
                (raw_id, canonical, url_hash, domain, lang_hint, region_hint),
            )
            inserted = cur.rowcount > 0
            conn.execute("UPDATE raw_urls SET processed = 1 WHERE id = ?", (raw_id,))
            conn.commit()
        return "inserted" if inserted else "duplicate"
    except Exception as e:  # noqa: BLE001
        log.warning("Normalize failed for raw_id=%d: %s", raw_id, e)
        with get_connection() as conn:
            conn.execute("UPDATE raw_urls SET processed = 1 WHERE id = ?", (raw_id,))
            conn.commit()
        return "failed"


def main() -> None:
    init_schema()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, url, lang_hint, region_hint FROM raw_urls WHERE processed = 0"
        ).fetchall()

    log.info("Normalizing %d raw URLs", len(rows))
    counts = {"inserted": 0, "duplicate": 0, "failed": 0}

    for i, row in enumerate(rows, 1):
        status = normalize_one(row["id"], row["url"], row["lang_hint"], row["region_hint"])
        counts[status] += 1
        if i % 50 == 0:
            log.info("  progress: %d/%d (inserted=%d, dup=%d, fail=%d)",
                     i, len(rows), counts["inserted"], counts["duplicate"], counts["failed"])
        time.sleep(0.15)  # rate limit head requests

    log.info("=" * 70)
    log.info("Normalization summary: %s", counts)


if __name__ == "__main__":
    main()
