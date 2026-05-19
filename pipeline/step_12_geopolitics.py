"""PHASE 12 — Geopolitical risk monitoring via GDELT.

GDELT (Global Database of Events, Language, and Tone) indexes global news
events with location, sentiment, and theme tags. Free public API.

We track countries critical to OCP's phosphate value chain:
- Morocco (production hub)
- Tunisia, Algeria (regional peers)
- Russia, China (top competitors)
- India, Brazil (top buyers)
- Major shipping lanes (Mediterranean, Indian Ocean, Suez)
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
import requests
from . import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("geopolitics")

# GDELT 2.0 GKG API — themes/locations focused
GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

# Countries critical to OCP / feed phosphate value chain
WATCH_COUNTRIES = {
    "Morocco":       {"iso": "MA", "role": "OCP origin",       "criticality": "high"},
    "Tunisia":       {"iso": "TS", "role": "phosphate peer",   "criticality": "high"},
    "Russia":        {"iso": "RS", "role": "competitor",       "criticality": "high"},
    "China":         {"iso": "CH", "role": "competitor & buyer","criticality": "high"},
    "India":         {"iso": "IN", "role": "top buyer",        "criticality": "high"},
    "Brazil":        {"iso": "BR", "role": "top buyer",        "criticality": "high"},
    "USA":           {"iso": "US", "role": "competitor",       "criticality": "medium"},
    "Saudi Arabia":  {"iso": "SA", "role": "competitor",       "criticality": "medium"},
    "Algeria":       {"iso": "AG", "role": "regional",         "criticality": "medium"},
    "Egypt":         {"iso": "EG", "role": "transit (Suez)",   "criticality": "high"},
}

# GDELT themes that signal supply chain / trade risk
RISK_THEMES = [
    "ECON_TRADE_DISPUTE", "TAX_FNCACT_TARIFF", "EPU_POLICY_LAW",
    "PROTEST", "MIL_FORCEPOSTURE", "WB_805_AGRICULTURE",
    "EPU_ECONOMY", "EPU_CATS_MIGRATION_FEAR_TENSIONS",
]


def fetch_country_events(country: str, info: dict) -> dict:
    """Query GDELT for recent articles mentioning the country + phosphate/feed/trade themes."""
    # Query: events related to phosphate, fertilizer, trade in this country
    query = f'({country.lower()} OR sourcecountry:{info["iso"]}) AND (phosphate OR fertilizer OR "animal feed" OR "trade dispute" OR sanctions OR export)'

    params = {
        "query": query,
        "mode": "TimelineTone",
        "timespan": "30d",
        "format": "JSON",
        "maxrecords": 10,
    }
    try:
        r = requests.get(GDELT_DOC_API, params=params, timeout=20,
                         headers={"User-Agent": config.USER_AGENT})
        if r.status_code != 200:
            return {"events_count": 0, "avg_tone": 0.0, "timeline": []}
        data = r.json()
        timeline = data.get("timeline", [])
        if not timeline or not timeline[0].get("data"):
            return {"events_count": 0, "avg_tone": 0.0, "timeline": []}

        points = timeline[0]["data"]
        tones = [p.get("value", 0) for p in points]
        # Mention volume
        vol_params = {**params, "mode": "TimelineVolRaw"}
        vr = requests.get(GDELT_DOC_API, params=vol_params, timeout=20,
                          headers={"User-Agent": config.USER_AGENT})
        events_count = 0
        if vr.status_code == 200:
            vdata = vr.json()
            vline = vdata.get("timeline", [])
            if vline and vline[0].get("data"):
                events_count = int(sum(p.get("value", 0) for p in vline[0]["data"]))

        avg_tone = sum(tones) / len(tones) if tones else 0
        return {
            "events_count": events_count,
            "avg_tone": round(avg_tone, 2),
            "timeline": [{"date": p.get("date", "")[:10], "tone": round(p.get("value", 0), 2)}
                         for p in points[-30:]],
        }
    except Exception as e:  # noqa: BLE001
        log.debug("GDELT fail %s: %s", country, e)
        return {"events_count": 0, "avg_tone": 0.0, "timeline": []}


def compute_risk_score(country_data: dict) -> float:
    """Combine event volume + negative tone into a 0-100 risk score."""
    events = country_data.get("events_count", 0)
    tone = country_data.get("avg_tone", 0)  # GDELT tone: -100 (very negative) to +100
    # Higher volume + more negative tone = higher risk
    volume_score = min(50, events / 20)  # cap at 50
    tone_score = max(0, -tone * 1.0)     # negative tone → up to 50
    return round(volume_score + tone_score, 1)


def collect() -> dict:
    countries = {}
    for country, info in WATCH_COUNTRIES.items():
        log.info("  Fetching GDELT for %s…", country)
        data = fetch_country_events(country, info)
        risk = compute_risk_score(data)
        countries[country] = {**info, **data, "risk_score": risk}

    ranked = sorted(countries.items(), key=lambda x: x[1]["risk_score"], reverse=True)
    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "countries": dict(ranked),
        "top_risks": [
            {"country": c, "iso": d["iso"], "role": d["role"],
             "risk_score": d["risk_score"], "events": d["events_count"],
             "tone": d["avg_tone"]}
            for c, d in ranked[:6]
        ],
    }


def main() -> None:
    log.info("Fetching geopolitical risk signals from GDELT…")
    data = collect()
    out_path = config.SITE_DATA_DIR / "geopolitics.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Wrote geopolitics → %s", out_path.name)


if __name__ == "__main__":
    main()
