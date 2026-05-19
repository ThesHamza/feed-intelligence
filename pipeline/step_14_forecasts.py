"""PHASE 14 — Commodity price forecasts.

Produces 30-day forward forecasts for the 4 tracked commodities using
Holt-Winters double exponential smoothing (trend, no seasonality given
short history). Pure Python implementation — no statsmodels/prophet
to keep dependencies minimal.
"""
from __future__ import annotations
import json
import logging
import math
from datetime import datetime, timedelta, timezone
from . import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("forecasts")

FORECAST_DAYS = 30
ALPHA = 0.3  # level smoothing
BETA = 0.1   # trend smoothing


def holt_winters_forecast(values: list, n_forecast: int):
    """Holt's linear trend method — returns (forecasts, lower_ci, upper_ci)."""
    if len(values) < 5:
        return [None] * n_forecast, [None] * n_forecast, [None] * n_forecast

    # Initialize level and trend
    level = values[0]
    trend = values[1] - values[0]
    levels = [level]
    trends = [trend]

    for v in values[1:]:
        new_level = ALPHA * v + (1 - ALPHA) * (level + trend)
        new_trend = BETA * (new_level - level) + (1 - BETA) * trend
        level, trend = new_level, new_trend
        levels.append(level); trends.append(trend)

    # Residuals for confidence interval
    residuals = [values[i] - (levels[i-1] + trends[i-1]) for i in range(1, len(values))]
    if residuals:
        mean_r = sum(residuals) / len(residuals)
        var = sum((r - mean_r) ** 2 for r in residuals) / len(residuals)
        sigma = math.sqrt(var)
    else:
        sigma = 0

    forecasts, lowers, uppers = [], [], []
    for h in range(1, n_forecast + 1):
        f = level + h * trend
        # Confidence widens with horizon
        margin = 1.96 * sigma * math.sqrt(h)
        forecasts.append(round(f, 2))
        lowers.append(round(f - margin, 2))
        uppers.append(round(f + margin, 2))

    return forecasts, lowers, uppers


def main() -> None:
    try:
        prices = json.loads((config.SITE_DATA_DIR / "prices.json").read_text())
    except FileNotFoundError:
        log.error("prices.json not found — run step_07_prices first.")
        return

    output = {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "horizon_days": FORECAST_DAYS,
        "method": "Holt double exponential smoothing",
        "forecasts": {},
    }

    for symbol, s in prices.get("series", {}).items():
        closes = s.get("closes", [])
        if len(closes) < 10:
            continue
        forecasts, lowers, uppers = holt_winters_forecast(closes, FORECAST_DAYS)
        last_date = datetime.fromisoformat(s["dates"][-1])
        forecast_dates = [(last_date + timedelta(days=i)).date().isoformat()
                          for i in range(1, FORECAST_DAYS + 1)]

        latest = closes[-1]
        forecast_30d = forecasts[-1] if forecasts and forecasts[-1] is not None else None
        change_pct = None
        if forecast_30d is not None and latest:
            change_pct = round((forecast_30d - latest) / latest * 100, 1)

        output["forecasts"][symbol] = {
            "name": s["name"],
            "color": s["color"],
            "unit": s.get("unit", ""),
            "historical_dates": s["dates"],
            "historical_closes": closes,
            "forecast_dates": forecast_dates,
            "forecast_values": forecasts,
            "forecast_lower": lowers,
            "forecast_upper": uppers,
            "current": latest,
            "forecast_30d": forecast_30d,
            "change_pct": change_pct,
        }
        log.info("  %s: current %.2f → 30d forecast %.2f (%+.1f%%)",
                 s["name"], latest, forecast_30d or 0, change_pct or 0)

    out_path = config.SITE_DATA_DIR / "forecasts.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Wrote forecasts → %s", out_path.name)


if __name__ == "__main__":
    main()
