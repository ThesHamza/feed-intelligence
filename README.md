# Feed Market Intelligence

Automated daily monitoring of the global animal feed market — focused on feed phosphates (MCP, MDCP, DCP, TCP), nutritional additives, and key industry players (OCP Group, Mosaic, DSM-Firmenich, Cargill, Tyson, JBS, and others).

The pipeline collects news from 56 RSS feeds (multilingual — EN, FR, ES, PT), extracts content, filters for quality and relevance, classifies each article with AI, and publishes a static dashboard updated daily at 06:00 UTC.

## Live dashboard

After deployment: `https://<your-github-username>.github.io/feed-intelligence/`

## Architecture

```
feed-intelligence/
├── .github/workflows/daily-pipeline.yml   ← daily cron
├── pipeline/                              ← Python data pipeline
│   ├── config.py                          ← entities, thresholds, paths
│   ├── sources.yaml                       ← 56 RSS sources
│   ├── step_01_collect.py                 ← Google/Bing News + direct feeds
│   ├── step_02_normalize.py               ← URL canonicalization + dedup
│   ├── step_03_extract.py                 ← trafilatura → newspaper3k fallback
│   ├── step_04_quality.py                 ← paywall + relevance filters
│   ├── step_05_classify.py                ← spaCy NER + Gemini classification
│   └── step_06_export.py                  ← JSON exports for frontend
├── data/feed_intelligence.db              ← SQLite, committed
├── site/                                  ← static dashboard
│   ├── index.html
│   ├── assets/{style.css, dashboard.js, charts.js, map.js}
│   └── data/{articles, entities, timeseries, metadata}.json
├── tests/                                 ← pytest smoke tests
├── requirements.txt
└── .env.example
```

## Stack

| Layer | Tool |
|---|---|
| RSS collection | `feedparser` |
| Content extraction | `trafilatura` (primary), `newspaper3k` (fallback) |
| NLP | `spaCy` (en, fr, es), `rapidfuzz`, `langdetect` |
| LLM classification | **Google Gemini 2.5 Flash** (free tier) |
| Storage | SQLite |
| Frontend | Vanilla JS + D3.js v7 + Chart.js v4 + TopoJSON (all via CDN) |
| Hosting | GitHub Pages |
| Scheduling | GitHub Actions (cron) |

## Setup

### 1. Local development

```bash
git clone https://github.com/<your-username>/feed-intelligence.git
cd feed-intelligence

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Download spaCy models (~50 MB each)
python -m spacy download en_core_web_sm
python -m spacy download fr_core_news_sm
python -m spacy download es_core_news_sm

# Configure your Gemini API key
cp .env.example .env
# Edit .env and paste your key from https://aistudio.google.com/apikey
```

### 2. Run the pipeline manually

```bash
python -m pipeline.step_01_collect   # ~2-5 min
python -m pipeline.step_02_normalize # ~1-3 min
python -m pipeline.step_03_extract   # ~5-15 min (network-bound)
python -m pipeline.step_04_quality   # ~10 sec
python -m pipeline.step_05_classify  # ~5-10 min (rate-limited LLM)
python -m pipeline.step_06_export    # ~1 sec
```

Then open `site/index.html` in a browser — or serve locally:

```bash
python -m http.server 8000 --directory site
# Visit http://localhost:8000
```

### 3. Deploy to GitHub Pages

1. **Push to GitHub** (public repo)
2. **Add secret**: Settings → Secrets and variables → Actions → New repository secret
   - Name: `GEMINI_API_KEY`
   - Value: your key from https://aistudio.google.com/apikey
3. **Enable Pages**: Settings → Pages → Source: **Deploy from a branch** → Branch: `main`, Folder: `/site`
4. **Trigger first run**: Actions tab → "Daily pipeline" → "Run workflow"

## How it works

| Step | What it does |
|---|---|
| 1. Collect | Queries Google News & Bing News RSS for 50+ feed-industry topics + direct publication feeds |
| 2. Normalize | Resolves Google News wrappers, strips UTM/fbclid, computes SHA-256 hash for dedup |
| 3. Extract | Fetches HTML and runs trafilatura; falls back to newspaper3k if extraction fails |
| 4. Quality | Drops articles that are too short, behind a paywall, or off-topic (relevance score < 2/1000 words) |
| 5. Classify | spaCy NER extracts companies; Gemini 2.5 Flash classifies position, narrative, impact, confidence, signal |
| 6. Export | Writes 4 JSON files consumed by the dashboard |

## Adding sources

Edit `pipeline/sources.yaml` and append entries:

```yaml
- name: "GN: <topic short name>"
  type: google_news        # or bing_news, or rss
  query: 'your search query'   # for google_news / bing_news
  # url: 'https://example.com/feed.xml'   # for rss
  language: en             # en | fr | es | pt
  region_hint: Global      # Americas | Europe | Asia-Pacific | MENA | Africa | Global
```

Then rerun the pipeline. URLs are deduplicated, so adding sources is safe.

To extend entity coverage, edit `pipeline/config.py` → `ENTITIES_TIER_1`.

## Costs

| Item | Cost |
|---|---|
| GitHub repo (public) | Free |
| GitHub Pages | Free |
| GitHub Actions (public repo) | Free (unlimited minutes) |
| Google Gemini 2.5 Flash | Free tier: **1500 req/day**, 15 req/min |
| **Total** | **$0 / month** |

At ~100 articles classified per day, the pipeline uses ~7% of the daily Gemini quota.

## Update frequency

- **Automatic**: GitHub Actions runs daily at **06:00 UTC**
- **Manual trigger**: Actions tab → "Daily pipeline" → "Run workflow"
- **Window**: each run collects articles published in the last 48h

## Testing

```bash
pytest tests/ -v
```

## Troubleshooting

**"Module not found" errors locally** — Ensure your virtualenv is active and run `pip install -r requirements.txt`.

**spaCy model errors** — Run the three `python -m spacy download …` commands above.

**Gemini "API key not found"** — Verify your `.env` has `GEMINI_API_KEY=...` (no quotes, no spaces around `=`).

**No articles in dashboard** — Check that the pipeline ran without errors (`Actions` tab on GitHub). Some sources may return empty feeds temporarily; the pipeline tolerates individual source failures.

**Extraction failure rate high** — Many sites block automated requests. Aim for 60-75% success — the rest fail gracefully (status='failed' in DB). Paywalled or JS-rendered sites are expected losses.

**Dashboard shows "no data"** — Open browser DevTools → Network tab. The dashboard fetches 4 JSON files from `data/` — check they exist in `site/data/` and contain non-empty arrays.

## License

MIT
