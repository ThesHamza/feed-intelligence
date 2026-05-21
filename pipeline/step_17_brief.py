"""PHASE 17 — Executive decision brief (the "so what" layer).

Aggregates signals from ALL dashboard data files, then asks an LLM to produce a
concise decision-oriented brief for an OCP audience: the 3-5 things that matter
today and the business implication of each. If the LLM is unavailable, falls
back to deterministic rules so the dashboard always has a brief.

Output: docs/data/brief.json
Run AFTER all other modules + export, so it can read their JSON outputs.

Usage: python -m pipeline.step_17_brief
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from . import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("brief")


def _load(name: str, default=None):
    path = config.SITE_DATA_DIR / name
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def gather_context() -> dict:
    """Collect a compact snapshot of all signals for the LLM / rules."""
    tension = _load("tension.json", {})
    weak = _load("weak_signals.json", [])
    regulatory = _load("regulatory.json", {})
    competitors = _load("competitors.json", {})
    prices = _load("prices.json", {})
    trade = _load("trade_flows.json", {})
    geo = _load("geopolitics.json", {})
    patents = _load("patents.json", {})
    signals = _load("signals.json", [])
    proxies = _load("feed_proxies.json", {})

    # Compact extraction
    ctx = {
        "tension": {
            "composite": tension.get("composite"),
            "level": tension.get("level"),
            "components": tension.get("components", {}),
        },
        "weak_signals": [
            {"item": w.get("item"), "type": w.get("type"), "direction": w.get("direction"),
             "z": w.get("z_score")}
            for w in (weak or [])[:8]
        ],
        "regulatory_high": [
            {"title": a.get("title"), "region": a.get("region"), "body": a.get("body")}
            for a in (regulatory.get("alerts", []) if regulatory else [])
            if a.get("severity") == "high"
        ][:5],
        "competitors_moves": [
            {"name": c.get("name"), "change_30d_pct": c.get("change_30d_pct")}
            for c in (competitors.get("competitors", []) if competitors else [])
            if c.get("change_30d_pct") is not None
        ][:9],
        "prices_30d": [
            {"name": s.get("name"), "change_30d_pct": s.get("change_30d_pct")}
            for s in (prices.get("summaries", []) if prices else [])
        ],
        "proxies": [
            {"label": p.get("label"), "change_3m_pct": p.get("change_3m_pct"),
             "change_12m_pct": p.get("change_12m_pct")}
            for p in (proxies.get("proxies", []) if proxies else [])
        ],
        "top_exporters": [
            {"country": e.get("country"), "value_usd": e.get("value_usd")}
            for e in (trade.get("top_exporters", []) if trade else [])
        ][:5],
        "geo_risks": [
            {"country": r.get("country"), "risk_score": r.get("risk_score"), "tone": r.get("tone")}
            for r in (geo.get("top_risks", []) if geo else [])
        ][:5],
        "patents_recent": (patents.get("count") if patents else 0),
        "top_signals": [
            {"signal": s.get("signal"), "impact": s.get("impact"), "position": s.get("position")}
            for s in (signals or [])[:6]
        ],
    }
    return ctx


# ===========================================================================
# LLM brief
# ===========================================================================
def generate_llm_brief(ctx: dict) -> dict | None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        log.info("No GEMINI_API_KEY; skipping LLM brief.")
        return None

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        log.info("google-genai not installed; skipping LLM brief.")
        return None

    prompt = f"""Tu es analyste senior en intelligence économique pour OCP Group (leader mondial des phosphates, Maroc), spécialisé sur le marché des feed phosphates (MCP, MDCP, DCP, MAP).

Voici un instantané des signaux de marché du jour (données réelles agrégées) :

{json.dumps(ctx, ensure_ascii=False, indent=2)}

Produis un "brief décisionnel" pour le management OCP au format JSON.

Structure attendue :
- "headline": une phrase de synthèse du jour (max 20 mots)
- "items": liste de 3 à 5 objets, chacun avec :
  - "insight": le fait marquant (1 phrase factuelle, cite le chiffre réel)
  - "implication": ce que ça veut dire pour OCP (1 phrase business spécifique : position marocaine, corridors export, grades, concurrents nommés)
  - "action": action concrète suggérée (1 phrase, verbe à l'infinitif)
  - "priority": "high", "medium" ou "low"

Règles : classe par priorité décroissante, appuie chaque item sur un signal RÉEL du snapshot, ton factuel et tranché, en français."""

    BRIEF_SCHEMA = {
        "type": "object",
        "properties": {
            "headline": {"type": "string"},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "insight": {"type": "string"},
                        "implication": {"type": "string"},
                        "action": {"type": "string"},
                        "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                    },
                    "required": ["insight", "implication", "action", "priority"],
                },
            },
        },
        "required": ["headline", "items"],
    }

    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:  # noqa: BLE001
        log.warning("Could not init Gemini client: %s", e)
        return None

    for model_name in (getattr(config, "LLM_MODEL", "gemini-2.5-flash"), "gemini-2.5-flash-lite"):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.4,
                    response_mime_type="application/json",
                    response_schema=BRIEF_SCHEMA,
                ),
            )
            data = json.loads(response.text or "")
            if data.get("items"):
                log.info("LLM brief generated via %s (%d items)", model_name, len(data["items"]))
                data["generated_by"] = f"AI ({model_name})"
                return data
        except Exception as e:  # noqa: BLE001
            log.warning("LLM brief failed on %s: %s", model_name, e)
            continue
    return None


# ===========================================================================
# Deterministic fallback
# ===========================================================================
def generate_rule_brief(ctx: dict) -> dict:
    """Rule-based brief when the LLM is unavailable. Always produces output."""
    items = []

    # Rule 1: market tension
    t = ctx.get("tension", {})
    if t.get("composite") is not None:
        lvl = t.get("level", "")
        comp = t.get("composite")
        if lvl == "HIGH":
            items.append({
                "insight": f"Indice de tension marché à {comp}/100 (élevé).",
                "implication": "Conditions instables sur le complexe phosphate — risque accru sur les marges et la planification commerciale OCP.",
                "action": "Activer une revue commerciale hebdomadaire et sécuriser les contrats prioritaires.",
                "priority": "high",
            })
        elif lvl == "MEDIUM":
            items.append({
                "insight": f"Indice de tension marché à {comp}/100 (modéré).",
                "implication": "Vigilance requise : plusieurs signaux convergents pourraient faire basculer le marché.",
                "action": "Surveiller l'évolution des sous-indicateurs sur 2 semaines.",
                "priority": "medium",
            })

    # Rule 2: high-severity regulation
    for reg in ctx.get("regulatory_high", [])[:1]:
        items.append({
            "insight": f"Alerte réglementaire ({reg.get('body')}, {reg.get('region')}) : {reg.get('title')}.",
            "implication": "Impact potentiel sur les spécifications produit ou l'accès marché — la roche marocaine peut être un avantage si déjà conforme.",
            "action": "Valider la conformité des grades export concernés avec les futures exigences.",
            "priority": "high",
        })

    # Rule 3: weak signal spike
    spikes = [w for w in ctx.get("weak_signals", []) if w.get("direction") == "spike"]
    if spikes:
        top = spikes[0]
        items.append({
            "insight": f"Pic d'attention anormal sur {top.get('item')} ({top.get('type')}, z={top.get('z')}σ).",
            "implication": "Possible déplacement de demande ou événement émergent à anticiper avant les concurrents.",
            "action": f"Investiguer la cause du pic sur {top.get('item')} et évaluer l'exposition OCP.",
            "priority": "medium",
        })

    # Rule 4: trade flow opportunity (declining competitor exporters)
    exporters = ctx.get("top_exporters", [])
    if exporters:
        names = [e.get("country") for e in exporters]
        if "Russia" in names or "Tunisia" in names:
            items.append({
                "insight": "Exportateurs concurrents (Russie/Tunisie) sous pression sur les volumes.",
                "implication": "Parts de marché potentiellement disponibles sur les corridors Atlantique et Asie pour OCP.",
                "action": "Prioriser l'effort commercial sur les marchés desservis par ces concurrents fragilisés.",
                "priority": "medium",
            })

    # Rule 5: proxy price direction
    for p in ctx.get("proxies", []):
        if p.get("label", "").startswith("Phosphate rock") and p.get("change_3m_pct") is not None:
            ch = p["change_3m_pct"]
            direction = "hausse" if ch > 2 else "baisse" if ch < -2 else "stabilité"
            items.append({
                "insight": f"Phosphate rock (proxy upstream) en {direction} de {ch:+.1f}% sur 3 mois.",
                "implication": "Indicateur directionnel du coût amont — influence la structure de marge des feed phosphates OCP.",
                "action": "Intégrer cette tendance dans les projections de pricing trimestrielles.",
                "priority": "low",
            })
            break

    # Headline
    high_count = sum(1 for i in items if i["priority"] == "high")
    if high_count >= 2:
        headline = "Plusieurs signaux haute priorité requièrent une attention immédiate du management."
    elif high_count == 1:
        headline = "Un signal majeur à traiter, dans un contexte de marché à surveiller."
    else:
        headline = "Marché sous surveillance, pas d'alerte critique à ce jour."

    return {
        "headline": headline,
        "items": items[:5],
        "generated_by": "Rules (LLM unavailable)",
    }


def main() -> None:
    ctx = gather_context()
    brief = generate_llm_brief(ctx)
    if brief is None:
        log.info("Falling back to rule-based brief.")
        brief = generate_rule_brief(ctx)

    brief["generated_at"] = datetime.now(timezone.utc).isoformat()
    out_path = config.SITE_DATA_DIR / "brief.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Wrote brief (%d items, %s) → %s",
             len(brief.get("items", [])), brief.get("generated_by"), out_path.name)


if __name__ == "__main__":
    main()
