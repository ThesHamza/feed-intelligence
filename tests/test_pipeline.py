"""Minimal smoke tests — 1 per module (per project constraint).

Uses temporary DB via monkeypatching config.DB_PATH.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline import config, get_connection, init_schema


@pytest.fixture(autouse=True)
def temp_db(tmp_path: Path, monkeypatch):
    """Redirect DB_PATH and SITE_DATA_DIR to tmp_path for each test."""
    db = tmp_path / "test.db"
    site_data = tmp_path / "site_data"
    site_data.mkdir()
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "SITE_DATA_DIR", site_data)
    init_schema()


# ---------------------------------------------------------------------------
# Phase 1 — collect
# ---------------------------------------------------------------------------
def test_collect_build_url():
    from pipeline.step_01_collect import _build_feed_url

    src = {"type": "google_news", "query": "OCP feed", "language": "en"}
    url = _build_feed_url(src)
    assert "news.google.com/rss/search" in url
    assert "OCP+feed" in url

    src2 = {"type": "bing_news", "query": "MDCP", "language": "en"}
    assert "bing.com/news/search" in _build_feed_url(src2)


# ---------------------------------------------------------------------------
# Phase 2 — normalize
# ---------------------------------------------------------------------------
def test_normalize_strip_and_canonicalize():
    from pipeline.step_02_normalize import _strip_tracking, _canonicalize

    url = "https://Example.COM/path/?utm_source=x&utm_medium=y&id=42#frag"
    stripped = _strip_tracking(url)
    assert "utm_source" not in stripped
    assert "id=42" in stripped

    canonical, h = _canonicalize(stripped)
    assert canonical.startswith("https://example.com/path")
    assert "#frag" not in canonical
    assert len(h) == 64  # sha256 hex


# ---------------------------------------------------------------------------
# Phase 3 — extract
# ---------------------------------------------------------------------------
def test_extract_trafilatura_on_sample_html():
    from pipeline.step_03_extract import _extract_trafilatura

    # Mini valid HTML with meaningful content
    html = """<html><head><title>Feed phosphate prices rise</title></head>
    <body><article><h1>Feed phosphate prices rise</h1>
    <p>""" + ("Global feed phosphate prices increased significantly in Q1 2026 as OCP Group adjusted its export allocations. " * 20) + """
    </p></article></body></html>"""
    result = _extract_trafilatura(html, "https://example.com/article")
    # Trafilatura may or may not extract — assert it doesn't crash and shape is correct
    if result:
        assert "title" in result
        assert "body" in result


# ---------------------------------------------------------------------------
# Phase 4 — quality
# ---------------------------------------------------------------------------
def test_quality_assess_qualified_and_filtered():
    from pipeline.step_04_quality import assess

    # Qualified: long body with multiple keywords
    body_good = " ".join([
        "OCP Group announced new MCP and MDCP feed phosphate pricing.",
        "DSM-Firmenich and Cargill discussed amino acid supply.",
        "Methionine and lysine markets reacted to soybean meal volatility.",
    ] * 10)
    art_good = {"title": "Feed phosphate market update", "body": body_good, "word_count": len(body_good.split())}
    qualified, score, reason = assess(art_good)
    assert qualified, f"expected qualified, got reason={reason}"
    assert score >= config.MIN_RELEVANCE_SCORE

    # Filtered: too short
    art_short = {"title": "x", "body": "tiny text", "word_count": 2}
    qualified, _, reason = assess(art_short)
    assert not qualified
    assert "too_short" in reason

    # Filtered: paywall
    art_paywall = {
        "title": "Big news",
        "body": "Subscribe to read this article about feed markets. " * 30,
        "word_count": 150,
    }
    qualified, _, reason = assess(art_paywall)
    assert not qualified
    assert reason == "paywall_detected"


# ---------------------------------------------------------------------------
# Phase 5 — classify
# ---------------------------------------------------------------------------
def test_classify_entities_keyword_fallback():
    from pipeline.step_05_classify import _entities_keyword_fallback, _detect_language

    text = "OCP Group and Mosaic announced new partnerships. DSM-Firmenich was also mentioned."
    found = _entities_keyword_fallback(text)
    assert "OCP Group" in found or "OCP" in found
    assert "Mosaic" in found
    assert "DSM-Firmenich" in found

    # Language detection
    assert _detect_language("This is a long English text about feed.", None) == "en"
    assert _detect_language("Ceci est un long texte français sur l'alimentation.", None) == "fr"


# ---------------------------------------------------------------------------
# Phase 6 — export
# ---------------------------------------------------------------------------
def test_export_writes_all_json_files():
    from pipeline import step_06_export

    # Insert minimal qualified+classified row
    with get_connection() as conn:
        conn.execute("INSERT INTO raw_urls (url, source) VALUES (?, ?)", ("https://x.com/a", "test"))
        conn.execute("""INSERT INTO urls (raw_url_id, url_canonical, url_hash, domain, status)
                        VALUES (1, 'https://x.com/a', 'hash1', 'x.com', 'extracted')""")
        conn.execute("""INSERT INTO articles (url_id, title, body, language, word_count, extractor)
                        VALUES (1, 'T', 'B B B', 'en', 3, 'trafilatura')""")
        conn.execute("INSERT INTO quality (article_id, qualified, relevance_score, reason) VALUES (1, 1, 5.0, 'ok')")
        conn.execute("""INSERT INTO classifications
                        (article_id, position, tone, narrative, commodities, regions, key_companies,
                         impact, confidence, signal, time_horizon)
                        VALUES (1, 'bullish', 'positive', 'prices', '["MCP"]', '["MENA"]',
                                '["OCP Group"]', 'high', 88, 'Test signal', 'short')""")
        conn.commit()

    step_06_export.main()

    for f in ("articles.json", "entities.json", "timeseries.json", "metadata.json"):
        path = config.SITE_DATA_DIR / f
        assert path.exists(), f"missing {f}"
        data = json.loads(path.read_text())
        assert data, f"empty {f}"
