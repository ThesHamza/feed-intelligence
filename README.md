# Feed Market Intelligence

Automated daily monitoring of the global animal feed market — focused on feed phosphates (MCP, MDCP, DCP, TCP), nutritional additives, and key industry players (OCP, Mosaic, DSM-Firmenich, Cargill, Tyson, JBS, etc.).

🚧 **Status: scaffolding (Phase 0/9 complete)**

## Architecture

```
feed-intelligence/
├── pipeline/           Python data pipeline (Phases 1-6)
│   ├── config.py       Entities, thresholds, paths
│   ├── sources.yaml    News sources (Phase 1)
│   └── step_*.py       Sequential pipeline stages
├── data/               SQLite database (committed for cross-run state)
├── site/               Static dashboard (Phases 7)
│   ├── index.html
│   └── assets/         D3 + Chart.js + TopoJSON (CDN)
└── .github/workflows/  Daily cron via GitHub Actions (Phase 8)
```

## Stack

- **Backend**: Python 3.11+, feedparser, trafilatura, newspaper3k, spaCy, rapidfuzz
- **LLM**: Google Gemini 2.5 Flash (free tier — 1500 req/day)
- **Storage**: SQLite + JSON exports
- **Frontend**: Vanilla JS + D3.js v7 + Chart.js v4 + TopoJSON
- **Hosting**: GitHub Pages + GitHub Actions cron

## Setup (TBD — finalized in Phase 9)

```bash
# Placeholder — full instructions added at project completion
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # add your GEMINI_API_KEY
```

## Pipeline

| Step | File | Function |
|---|---|---|
| 1 | step_01_collect.py | RSS collection from Google/Bing News + direct feeds |
| 2 | step_02_normalize.py | URL canonicalization + dedup |
| 3 | step_03_extract.py | Content extraction (trafilatura → newspaper3k) |
| 4 | step_04_quality.py | Paywall + relevance + spam filters |
| 5 | step_05_classify.py | spaCy NER + Gemini LLM classification |
| 6 | step_06_export.py | JSON exports for dashboard |

## License

TBD
