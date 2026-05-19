"""PHASE 10 — Weak signals detector + Market tension index.

Pure-Python anomaly detection on existing DB data — no external APIs.
1. Weak signals: z-score on entity/commodity/narrative mention frequencies
   over rolling 30d. Flags items where current 7d is >2σ from 30d baseline.
2. Tension index: composite 0-100 score combining price volatility,
   article sentiment dispersion, regulatory severity, and weak signal count.
"""
from __future__ import annotations
import json
import logging
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from . import config, get_connection, init_schema

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("weaksignals")


def _parse_json_field(s):
    if not s:
        return []
    try:
        return json.loads(s)
    except Exception:
        return []


def detect_weak_signals() -> list:
    """Compare recent (7d) frequency vs prior baseline (8-30d). Z-score > 2 flags."""
    end = datetime.now(timezone.utc)
    recent_cutoff = (end - timedelta(days=7)).isoformat()
    baseline_start = (end - timedelta(days=30)).isoformat()
    baseline_end = recent_cutoff

    with get_connection() as conn:
        recent_rows = conn.execute(
            """SELECT c.key_companies, c.commodities, c.narrative, c.position
               FROM classifications c
               JOIN quality q ON q.article_id = c.article_id AND q.qualified = 1
               WHERE c.classified_at >= ?""", (recent_cutoff,)).fetchall()
        baseline_rows = conn.execute(
            """SELECT c.key_companies, c.commodities, c.narrative, c.position
               FROM classifications c
               JOIN quality q ON q.article_id = c.article_id AND q.qualified = 1
               WHERE c.classified_at >= ? AND c.classified_at < ?""",
            (baseline_start, baseline_end)).fetchall()

    def aggregate(rows, field, is_list=True):
        c = Counter()
        for r in rows:
            if is_list:
                for v in _parse_json_field(r[field]):
                    c[v] += 1
            else:
                v = r[field]
                if v:
                    c[v] += 1
        return c

    signals = []
    for label, field, is_list in [("entity", "key_companies", True),
                                   ("commodity", "commodities", True),
                                   ("narrative", "narrative", False)]:
        recent = aggregate(recent_rows, field, is_list)
        baseline = aggregate(baseline_rows, field, is_list)
        baseline_days = 23  # 30 - 7

        # Normalize baseline to per-7d rate
        for item, recent_count in recent.items():
            baseline_count = baseline.get(item, 0)
            expected_7d = (baseline_count / baseline_days) * 7
            # Poisson approximation: σ = √expected
            sigma = math.sqrt(max(1, expected_7d))
            z = (recent_count - expected_7d) / sigma if sigma > 0 else 0
            if z >= 2.0 and recent_count >= 3:  # min absolute volume threshold
                signals.append({
                    "type": label,
                    "item": item,
                    "recent_7d": recent_count,
                    "baseline_7d_avg": round(expected_7d, 1),
                    "z_score": round(z, 2),
                    "direction": "spike",
                    "description": f"{label.capitalize()} '{item}' mentions spiked: {recent_count} vs baseline {expected_7d:.1f} (z={z:.1f}σ)",
                })
        # Also detect drops for items with significant baseline
        for item, baseline_count in baseline.items():
            if baseline_count < 5:
                continue
            recent_count = recent.get(item, 0)
            expected_7d = (baseline_count / baseline_days) * 7
            sigma = math.sqrt(max(1, expected_7d))
            z = (expected_7d - recent_count) / sigma if sigma > 0 else 0
            if z >= 2.0 and recent_count <= expected_7d / 2:
                signals.append({
                    "type": label,
                    "item": item,
                    "recent_7d": recent_count,
                    "baseline_7d_avg": round(expected_7d, 1),
                    "z_score": -round(z, 2),
                    "direction": "drop",
                    "description": f"{label.capitalize()} '{item}' mentions dropped: {recent_count} vs baseline {expected_7d:.1f} (z=-{z:.1f}σ)",
                })

    signals.sort(key=lambda s: abs(s["z_score"]), reverse=True)
    return signals[:30]


def compute_tension_index(weak_signals: list) -> dict:
    """Composite 0-100 market tension index across 4 dimensions."""
    components = {}

    # 1. Price volatility — average 7d move across our tracked commodities
    try:
        prices = json.loads((config.SITE_DATA_DIR / "prices.json").read_text())
        moves = [abs(s.get("change_7d_pct") or 0) for s in prices.get("summaries", [])]
        avg_move = sum(moves) / len(moves) if moves else 0
        # Calibrate: 0% = score 0, 5%+ = score 100
        components["price_volatility"] = min(100, round(avg_move * 20, 1))
    except Exception:
        components["price_volatility"] = 0

    # 2. Sentiment dispersion — std deviation of bullish/bearish ratios over 7d
    end = datetime.now(timezone.utc)
    cutoff = (end - timedelta(days=7)).isoformat()
    with get_connection() as conn:
        positions = conn.execute(
            """SELECT c.position FROM classifications c
               JOIN quality q ON q.article_id = c.article_id AND q.qualified = 1
               WHERE c.classified_at >= ?""", (cutoff,)).fetchall()
    bull = sum(1 for p in positions if p["position"] == "bullish")
    bear = sum(1 for p in positions if p["position"] == "bearish")
    total = max(1, bull + bear)
    polarization = abs(bull - bear) / total
    components["sentiment_polarization"] = round(polarization * 100, 1)

    # 3. Regulatory severity — share of high-severity alerts in recent regulatory
    try:
        reg = json.loads((config.SITE_DATA_DIR / "regulatory.json").read_text())
        sev = reg.get("by_severity", {})
        total_reg = sum(sev.values()) or 1
        high_share = sev.get("high", 0) / total_reg
        components["regulatory_pressure"] = round(high_share * 100, 1)
    except Exception:
        components["regulatory_pressure"] = 0

    # 4. Weak signal density — count of spikes & drops in 7d
    spike_count = len([s for s in weak_signals if abs(s["z_score"]) >= 2.5])
    components["weak_signal_density"] = min(100, spike_count * 10)

    # Composite: weighted average
    weights = {"price_volatility": 0.30, "sentiment_polarization": 0.25,
               "regulatory_pressure": 0.20, "weak_signal_density": 0.25}
    composite = sum(components[k] * w for k, w in weights.items())
    composite = round(composite, 1)

    # Interpretation
    if composite >= 70:
        level = "high"
        interpretation = "Marché sous forte tension : volatilité, polarisation et signaux multiples convergent. Décisions tactiques recommandées."
    elif composite >= 40:
        level = "medium"
        interpretation = "Tension modérée. Surveillance accrue des signaux émergents recommandée."
    else:
        level = "low"
        interpretation = "Marché stable. Pas de signaux critiques sur l'horizon court."

    return {
        "composite": composite,
        "level": level,
        "interpretation": interpretation,
        "components": components,
        "weights": weights,
        "computed_at": end.isoformat(),
    }


def main() -> None:
    init_schema()
    log.info("Detecting weak signals…")
    signals = detect_weak_signals()
    log.info("  Found %d signals", len(signals))

    log.info("Computing tension index…")
    tension = compute_tension_index(signals)
    log.info("  Tension index: %.1f (%s)", tension["composite"], tension["level"])

    out_signals = config.SITE_DATA_DIR / "weak_signals.json"
    out_signals.write_text(json.dumps(signals, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Wrote %d weak signals → %s", len(signals), out_signals.name)

    out_tension = config.SITE_DATA_DIR / "tension.json"
    out_tension.write_text(json.dumps(tension, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Wrote tension index → %s", out_tension.name)


if __name__ == "__main__":
    main()
