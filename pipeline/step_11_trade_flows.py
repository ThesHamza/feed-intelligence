"""PHASE 11 — Trade flows from UN Comtrade.

Pulls phosphate-related HS codes export/import data from the free
UN Comtrade public API. Annual data with 1-2 year lag (typical).

HS codes of interest:
- 2510 : natural phosphates (rock)
- 2835 : phosphates (chemical compounds incl. feed phosphates)
- 280910 : phosphoric acid

Free API: 100 calls/hour, no auth needed (public endpoint).
"""
from __future__ import annotations
import json
import logging
import time
from datetime import datetime, timezone
import requests
from . import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("trade")

# Top phosphate exporting countries by reporter code (ISO numeric)
EXPORTERS = {
    "504": "Morocco",
    "643": "Russia",
    "356": "India",
    "788": "Tunisia",
    "682": "Saudi Arabia",
    "156": "China",
    "076": "Brazil",
    "840": "USA",
    "398": "Kazakhstan",
}

HS_CODES = {
    "2510":   "Phosphate rock",
    "2835":   "Phosphates (incl. feed phosphates)",
    "280910": "Phosphoric acid",
}

BASE_URL = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"


def fetch_flows(year: int, hs_code: str, reporter: str) -> list:
    """Fetch yearly export flows for a single (reporter, HS) pair."""
    params = {
        "reporterCode": reporter,
        "period": str(year),
        "cmdCode": hs_code,
        "flowCode": "X",  # X = exports
        "partnerCode": "0",  # 0 = World
        "motCode": "0",
        "customsCode": "C00",
        "maxRecords": 100,
        "format": "JSON",
    }
    try:
        r = requests.get(BASE_URL, params=params, timeout=20,
                         headers={"User-Agent": config.USER_AGENT})
        if r.status_code != 200:
            return []
        data = r.json()
        return data.get("data", [])
    except Exception as e:  # noqa: BLE001
        log.debug("Comtrade fail %s/%s/%s: %s", reporter, hs_code, year, e)
        return []


def collect() -> dict:
    # Comtrade typically has 2-year lag. Try current-2 and fall back.
    current_year = datetime.now(timezone.utc).year
    years_to_try = [current_year - 2, current_year - 3]

    flows_by_country = {}
    flows_by_hs = {hs: 0 for hs in HS_CODES}
    total_value = 0

    for reporter, country in EXPORTERS.items():
        country_total = {hs: 0 for hs in HS_CODES}
        year_used = None
        for year in years_to_try:
            hits_year = 0
            for hs in HS_CODES:
                results = fetch_flows(year, hs, reporter)
                time.sleep(0.4)  # rate limit polite
                for row in results:
                    val = row.get("primaryValue", 0) or 0
                    country_total[hs] += val
                    flows_by_hs[hs] += val
                    total_value += val
                    hits_year += 1
            if hits_year > 0:
                year_used = year
                break
        flows_by_country[country] = {
            "iso_num": reporter, "total_usd": country_total,
            "grand_total_usd": sum(country_total.values()),
            "year": year_used,
        }
        log.info("  %s: $%.0fM exported (HS-aggregated)", country, sum(country_total.values()) / 1e6)

    # Top exporters ranking
    ranked = sorted(flows_by_country.items(),
                    key=lambda x: x[1]["grand_total_usd"], reverse=True)

    out = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "hs_codes": HS_CODES,
        "by_country": dict(ranked),
        "by_hs_code": flows_by_hs,
        "total_value_usd": total_value,
        "top_exporters": [
            {"country": c, "value_usd": d["grand_total_usd"], "year": d["year"]}
            for c, d in ranked[:10]
        ],
    }
    return out


def main() -> None:
    log.info("Fetching UN Comtrade phosphate trade flows…")
    data = collect()
    out_path = config.SITE_DATA_DIR / "trade_flows.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Wrote trade flows ($%.0fM total) → %s",
             data["total_value_usd"] / 1e6, out_path.name)


if __name__ == "__main__":
    main()
