"""PHASE 8 — Competitor financial tracking.

Fetches daily stock data for direct OCP competitors via Yahoo Finance.
Computes performance vs benchmark and an equal-weighted sector index.
Writes docs/data/competitors.json.

Usage: python -m pipeline.step_08_competitors
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

import yfinance as yf

from . import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("competitors")

LOOKBACK_DAYS = 90


def _pct(latest, base):
    if latest is None or base is None or base == 0:
        return None
    return round((latest - base) / base * 100, 1)


def fetch_competitor(ticker: str, meta: dict):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=LOOKBACK_DAYS + 14)
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(start=start.date().isoformat(), end=end.date().isoformat(), interval="1d")
        if hist.empty:
            log.warning("  Empty data for %s", ticker)
            return None

        hist = hist.tail(LOOKBACK_DAYS)
        closes = hist["Close"].round(2).tolist()
        dates = [d.strftime("%Y-%m-%d") for d in hist.index]
        latest = closes[-1] if closes else None

        info = {}
        try:
            info = tk.info or {}
        except Exception:  # noqa: BLE001
            pass

        return {
            "ticker": ticker,
            "name": meta["name"],
            "category": meta["category"],
            "color": meta["color"],
            "latest_price": latest,
            "currency": info.get("currency") or "USD",
            "market_cap_usd": info.get("marketCap"),
            "change_7d_pct": _pct(latest, closes[-6]) if len(closes) >= 6 else None,
            "change_30d_pct": _pct(latest, closes[-23]) if len(closes) >= 23 else None,
            "change_90d_pct": _pct(latest, closes[0]) if closes else None,
            "dates": dates,
            "closes": closes,
        }
    except Exception as e:  # noqa: BLE001
        log.warning("  Failed for %s: %s", ticker, e)
        return None


def main() -> None:
    competitors = []
    for ticker, meta in config.COMPETITOR_STOCKS.items():
        log.info("Fetching %s (%s)…", ticker, meta["name"])
        result = fetch_competitor(ticker, meta)
        if result:
            competitors.append(result)

    # Equal-weighted sector index, base 100
    sector_index = {"dates": [], "values": []}
    if competitors:
        all_dates = max((c["dates"] for c in competitors), key=len)
        values = []
        for d_idx in range(len(all_dates)):
            indexed = []
            for c in competitors:
                if d_idx >= len(c["closes"]) or not c["closes"]:
                    continue
                base = c["closes"][0]
                if base:
                    indexed.append(c["closes"][d_idx] / base * 100)
            if indexed:
                values.append(round(sum(indexed) / len(indexed), 2))
        sector_index = {"dates": all_dates[: len(values)], "values": values}

    out = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "competitors": competitors,
        "sector_index": sector_index,
    }
    out_path = config.SITE_DATA_DIR / "competitors.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Wrote %d competitors → %s", len(competitors), out_path.name)


if __name__ == "__main__":
    main()
