"""PHASE 5 — AI classification.

For each qualified article:
1. spaCy NER (language-specific model) extracts ORG, GPE entities
2. rapidfuzz matches detected ORGs against the domain entity list
3. Gemini classifies the article into a strict JSON schema

Rate-limited to stay under Gemini free tier limits.

Usage: python -m pipeline.step_05_classify
"""

from __future__ import annotations

import json
import logging
import os
import time

from dotenv import load_dotenv
from langdetect import detect, DetectorFactory, LangDetectException
from rapidfuzz import fuzz

from . import config, get_connection, init_schema

DetectorFactory.seed = 0  # deterministic langdetect

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("classify")


# Lazy-load spaCy models (heavy import)
_SPACY_CACHE: dict = {}


def _get_spacy(lang: str):
    if lang not in _SPACY_CACHE:
        import spacy
        model = config.SPACY_MODELS.get(lang)
        if not model:
            return None
        try:
            _SPACY_CACHE[lang] = spacy.load(model, disable=["parser", "tagger", "lemmatizer"])
        except OSError:
            log.warning("spaCy model not installed: %s", model)
            _SPACY_CACHE[lang] = None
    return _SPACY_CACHE[lang]


def _detect_language(text: str, hint: str | None) -> str:
    """Returns ISO 639-1 code. Falls back to hint or 'en'."""
    if hint and hint in config.SUPPORTED_LANGUAGES:
        return hint
    try:
        lang = detect(text[:1000])
        if lang in config.SUPPORTED_LANGUAGES:
            return lang
    except LangDetectException:
        pass
    return hint or "en"


def _extract_entities_nlp(text: str, lang: str) -> list[str]:
    """Run spaCy NER and fuzzy-match against domain entities. Returns canonical names."""
    nlp = _get_spacy(lang)
    if nlp is None:
        return _entities_keyword_fallback(text)

    doc = nlp(text[:5000])  # limit for speed
    candidate_orgs = {ent.text.strip() for ent in doc.ents if ent.label_ in ("ORG", "PERSON")}

    matched = set()
    for org in candidate_orgs:
        for canonical in config.ENTITIES_FLAT:
            if fuzz.partial_ratio(org.lower(), canonical.lower()) >= 85:
                matched.add(canonical)
                break
    return sorted(matched)


def _entities_keyword_fallback(text: str) -> list[str]:
    """When spaCy model missing: simple substring search."""
    lower = text.lower()
    return sorted({e for e in config.ENTITIES_FLAT if e.lower() in lower})


# =============================================================================
# Gemini classification
# =============================================================================
CLASSIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "position": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
        "tone": {"type": "string", "enum": ["positive", "negative", "neutral", "mixed"]},
        "narrative": {"type": "string", "enum": [
            "supply", "demand", "prices", "regulatory", "innovation",
            "sustainability", "trade", "disease", "M&A", "geopolitics",
        ]},
        "commodities": {
            "type": "array",
            "items": {"type": "string", "enum": [
                "MCP", "MDCP", "DCP", "TCP", "phosphoric_acid",
                "soybean", "corn", "wheat",
                "lysine", "methionine", "threonine",
                "vitamins", "enzymes", "other",
            ]},
        },
        "regions": {
            "type": "array",
            "items": {"type": "string", "enum": [
                "Americas", "Europe", "Asia-Pacific", "MENA", "Africa", "Global",
            ]},
        },
        "key_companies": {"type": "array", "items": {"type": "string"}},
        "impact": {"type": "string", "enum": ["high", "medium", "low"]},
        "confidence": {"type": "integer"},
        "signal": {"type": "string"},
        "time_horizon": {"type": "string", "enum": ["immediate", "short", "medium", "long"]},
    },
    "required": ["position", "tone", "narrative", "commodities", "regions",
                 "key_companies", "impact", "confidence", "signal", "time_horizon"],
}

PROMPT_TEMPLATE = """You are a senior market analyst specialized in global animal feed and nutrition markets (phosphates: MCP/MDCP/DCP; amino acids; additives; major players: OCP, Mosaic, DSM-Firmenich, Cargill, Tyson, JBS, etc.).

Classify this article for a market intelligence dashboard. Respond with ONLY a JSON object matching the schema.

Title: {title}
Pre-detected entities: {entities}
Region hint: {region_hint}

Body (first {max_chars} chars):
{body}

Classification rules:
- "position": bullish if signals point to higher prices/demand/growth; bearish if lower; neutral if unclear/balanced.
- "narrative": pick the SINGLE dominant theme.
- "key_companies": ONLY include companies actually mentioned in this article from the tier-1 list.
- "confidence": 0-100, your certainty in this classification.
- "signal": ONE sentence (max 30 words) summarizing the market signal for feed industry stakeholders.
- "time_horizon": immediate (days), short (weeks), medium (months), long (1y+).
"""


def _make_client():
    """Lazy-import the Gemini SDK so the module can be imported in test
    environments where google-genai isn't installed."""
    from google import genai  # noqa: PLC0415
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit("GEMINI_API_KEY missing. Set it in .env or environment.")
    return genai.Client(api_key=key)


def classify_with_gemini(client, article: dict, entities: list[str]) -> dict | None:
    """Call Gemini with structured output. Returns parsed dict or None."""
    from google.genai import types  # noqa: PLC0415
    body = (article["body"] or "")[: config.LLM_INPUT_BODY_CHARS]
    prompt = PROMPT_TEMPLATE.format(
        title=article["title"] or "(no title)",
        entities=", ".join(entities) if entities else "(none detected)",
        region_hint=article.get("region_hint") or "unknown",
        body=body,
        max_chars=config.LLM_INPUT_BODY_CHARS,
    )

    try:
        response = client.models.generate_content(
            model=config.LLM_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=config.LLM_TEMPERATURE,
                response_mime_type="application/json",
                response_schema=CLASSIFICATION_SCHEMA,
            ),
        )
        text = response.text or ""
        return json.loads(text)
    except Exception as e:  # noqa: BLE001
        log.warning("Gemini classify error for article %d: %s", article["id"], e)
        return None


def main() -> None:
    init_schema()
    client = _make_client()

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT a.id, a.title, a.body, a.language, a.word_count, u.region_hint
               FROM articles a
               JOIN quality q ON q.article_id = a.id AND q.qualified = 1
               JOIN urls u ON u.id = a.url_id
               LEFT JOIN classifications c ON c.article_id = a.id
               WHERE c.article_id IS NULL
               LIMIT 200"""
        ).fetchall()

    log.info("Classifying %d articles with %s", len(rows), config.LLM_MODEL)
    interval = 60.0 / config.LLM_REQUESTS_PER_MINUTE
    ok = fail = 0

    for i, row in enumerate(rows, 1):
        article = dict(row)
        lang = _detect_language(article["body"] or "", article["language"])
        entities = _extract_entities_nlp((article["title"] or "") + " " + (article["body"] or ""), lang)

        result = classify_with_gemini(client, article, entities)
        if result is None:
            fail += 1
        else:
            with get_connection() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO classifications
                       (article_id, position, tone, narrative, commodities, regions,
                        key_companies, impact, confidence, signal, time_horizon)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        article["id"],
                        result.get("position"),
                        result.get("tone"),
                        result.get("narrative"),
                        json.dumps(result.get("commodities", [])),
                        json.dumps(result.get("regions", [])),
                        json.dumps(result.get("key_companies", [])),
                        result.get("impact"),
                        int(result.get("confidence", 0)),
                        (result.get("signal") or "")[:500],
                        result.get("time_horizon"),
                    ),
                )
                conn.commit()
            ok += 1

        if i % 10 == 0:
            log.info("  progress: %d/%d (ok=%d, fail=%d)", i, len(rows), ok, fail)
        time.sleep(interval)

    log.info("=" * 70)
    log.info("Classification summary: ok=%d, fail=%d", ok, fail)


if __name__ == "__main__":
    main()
