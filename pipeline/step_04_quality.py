"""PHASE 4 — Quality filtering.

For each extracted article, computes verdict (qualified or filtered) based on:
1. Word count >= MIN_WORD_COUNT
2. No paywall markers
3. Relevance score >= MIN_RELEVANCE_SCORE (domain keywords + entities per 1000 words)
4. Not press-wire spam (short PR-style with no tier-1 entity)

Usage: python -m pipeline.step_04_quality
"""

from __future__ import annotations

import logging
import re

from . import config, get_connection, init_schema

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("quality")

_KEYWORDS_LOWER = [k.lower() for k in (config.COMMODITIES + config.THEMES + config.ENTITIES_FLAT)]
_TIER1_LOWER = [e.lower() for e in config.ENTITIES_FLAT]
_PAYWALL_LOWER = [p.lower() for p in config.PAYWALL_MARKERS]
_PR_WIRE = re.compile(r"\b(prnewswire|business wire|globe newswire|press release wire)\b", re.IGNORECASE)


def _has_paywall(text: str) -> bool:
    lower = text.lower()
    return any(m in lower for m in _PAYWALL_LOWER)


def _relevance_score(text: str, word_count: int) -> float:
    """Matches per 1000 words. Counts each occurrence of any keyword."""
    if word_count <= 0:
        return 0.0
    lower = text.lower()
    matches = sum(lower.count(k) for k in _KEYWORDS_LOWER)
    return (matches / word_count) * 1000.0


def _has_tier1_entity(text: str) -> bool:
    lower = text.lower()
    return any(e in lower for e in _TIER1_LOWER)


def assess(article: dict) -> tuple[bool, float, str]:
    """Return (qualified, relevance_score, reason)."""
    body = article["body"] or ""
    title = article["title"] or ""
    full = title + " " + body
    word_count = article["word_count"] or 0

    if word_count < config.MIN_WORD_COUNT:
        return False, 0.0, f"too_short:{word_count}_words"

    if _has_paywall(body):
        return False, 0.0, "paywall_detected"

    score = _relevance_score(full, word_count)
    if score < config.MIN_RELEVANCE_SCORE:
        return False, score, f"low_relevance:{score:.2f}"

    if _PR_WIRE.search(body) and word_count < 200 and not _has_tier1_entity(full):
        return False, score, "pr_wire_no_entity"

    return True, score, "qualified"


def main() -> None:
    init_schema()
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT a.id, a.title, a.body, a.word_count
               FROM articles a
               LEFT JOIN quality q ON q.article_id = a.id
               WHERE q.article_id IS NULL"""
        ).fetchall()

    log.info("Assessing quality on %d articles", len(rows))
    counts = {"qualified": 0, "filtered": 0}
    reasons: dict[str, int] = {}

    for row in rows:
        qualified, score, reason = assess(dict(row))
        with get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO quality (article_id, qualified, relevance_score, reason)
                   VALUES (?, ?, ?, ?)""",
                (row["id"], 1 if qualified else 0, score, reason),
            )
            conn.commit()

        if qualified:
            counts["qualified"] += 1
        else:
            counts["filtered"] += 1
            short_reason = reason.split(":")[0]
            reasons[short_reason] = reasons.get(short_reason, 0) + 1

    log.info("=" * 70)
    log.info("Quality summary: qualified=%d, filtered=%d", counts["qualified"], counts["filtered"])
    log.info("Filter reasons: %s", reasons)


if __name__ == "__main__":
    main()
