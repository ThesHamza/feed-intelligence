"""PHASE 7 — Real commodity prices from Yahoo Finance.

Fetches daily closes for the main feed-relevant commodity futures over
the last 90 days. Output saved to docs/data/prices.json for the dashboard.

Tickers:
- ZC=F : Corn futures (CBOT)
- ZS=F : Soybean futures (CBOT)
- ZW=F : Wheat futures (CBOT)
- ZM=F : Soybean meal futures (CBOT) — the actual feed input

Phosphates (MCP, MDCP, DCP) and amino acids (lysine, methionine) have no
public futures market, so these remain article-derived only.

Usage: python -m pipeline.step_07_prices
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

import yfinance as yf

from . import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("prices")

TICKERS = {
    "ZC=F": {"name": "Corn",         "color": "#ca8a04", "unit": "cents/bu"},
    "ZS=F": {"name": "Soybean",      "color": "#16a34a", "unit": "cents/bu"},
    "ZW=F": {"name": "Wheat",        "color": "#8b5cf6", "unit": "cents/bu"},
    "ZM=F": {"name": "Soybean meal", "color": "#dc2626", "unit": "USD/ton"},
}

LOOKBACK_DAYS = 90


def fetch_prices() -> dict:
    """Pull daily closes for all tickers over the lookback window."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=LOOKBACK_DAYS + 14)  # extra buffer for weekends

    series = {}
    summaries = []

    for symbol, meta in TICKERS.items():
        log.info("Fetching %s (%s)…", symbol, meta["name"])
        try:
            tk = yf.Ticker(symbol)
            hist = tk.history(start=start.date().isoformat(), end=end.date().isoformat(), interval="1d")
            if hist.empty:
                log.warning("  No data returned for %s", symbol)
                continue

            # Keep only the last LOOKBACK_DAYS trading days
            hist = hist.tail(LOOKBACK_DAYS)
            closes = hist["Close"].round(2).tolist()
            dates = [d.strftime("%Y-%m-%d") for d in hist.index]

            # Compute deltas
            latest = closes[-1] if closes else None
            week_ago = closes[-6] if len(closes) >= 6 else closes[0] if closes else None
            month_ago = closes[-23] if len(closes) >= 23 else closes[0] if closes else None
            start_val = closes[0] if closes else None

            def pct(a, b):
                if a is None or b is None or b == 0:
                    return None
                return round((a - b) / b * 100, 1)

            series[symbol] = {
                "name": meta["name"],
                "color": meta["color"],
                "unit": meta["unit"],
                "dates": dates,
                "closes": closes,
            }
            summaries.append({
                "symbol": symbol,
                "name": meta["name"],
                "latest": latest,
                "unit": meta["unit"],
                "change_7d_pct": pct(latest, week_ago),
                "change_30d_pct": pct(latest, month_ago),
                "change_90d_pct": pct(latest, start_val),
                "color": meta["color"],
            })
            log.info("  %s: %d points, latest=%s, 30d=%+.1f%%",
                     symbol, len(closes), latest, pct(latest, month_ago) or 0)
        except Exception as e:  # noqa: BLE001
            log.warning("  Failed to fetch %s: %s", symbol, e)

    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": LOOKBACK_DAYS,
        "series": series,
        "summaries": summaries,
    }


def main() -> None:
    data = fetch_prices()
    out_path = config.SITE_DATA_DIR / "prices.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("=" * 60)
    log.info("Wrote %d commodity series → %s",
             len(data["series"]), out_path.name)


if __name__ == "__main__":
    main()
