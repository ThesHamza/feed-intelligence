"""Global configuration for the Feed Market Intelligence pipeline.

Single source of truth for paths, entity lists, language settings, and quality
thresholds. Modify entity lists here to extend coverage — no other file should
hardcode entity names.
"""

from pathlib import Path

# =============================================================================
# Paths
# =============================================================================
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "feed_intelligence.db"
SITE_DIR = ROOT_DIR / "docs"
SITE_DATA_DIR = SITE_DIR / "data"
SOURCES_FILE = Path(__file__).resolve().parent / "sources.yaml"

# =============================================================================
# Languages
# =============================================================================
SUPPORTED_LANGUAGES = ["en", "fr", "es", "pt"]

SPACY_MODELS = {
    "en": "en_core_web_sm",
    "fr": "fr_core_news_sm",
    "es": "es_core_news_sm",
    # Portuguese: spaCy has pt_core_news_sm; enable in Phase 5 if needed.
}

# =============================================================================
# LLM (Gemini free tier)
# =============================================================================
LLM_MODEL = "gemini-2.5-flash"
LLM_TEMPERATURE = 0.2
LLM_MAX_PARALLEL = 10               # batch size for concurrent classifications
LLM_INPUT_BODY_CHARS = 1500         # truncate body to first N chars for prompt
LLM_REQUESTS_PER_MINUTE = 12        # free tier safety margin (limit is 15)

# =============================================================================
# Entities to track (tier-1 = high priority companies)
# =============================================================================
# Aliases allow fuzzy matching to catch variants (e.g. "DSM" → "DSM-Firmenich").
ENTITIES_TIER_1 = {
    "phosphate_suppliers": [
        "OCP Group", "OCP",
        "Mosaic", "The Mosaic Company",
        "Nutrien",
        "ICL Group", "ICL",
        "PhosAgro",
        "EuroChem",
        "Yara",
        "Ma'aden", "Maaden",
    ],
    "additive_suppliers": [
        "DSM-Firmenich", "dsm-firmenich", "DSM",
        "Adisseo",
        "Alltech",
        "Novus International", "Novus",
        "Kemin", "Kemin Industries",
        "Cargill",
        "ADM", "Archer Daniels Midland",
        "Bunge",
        "Nutreco",
        "Evonik",
        "Ajinomoto",
        "CJ Bio", "CJ CheilJedang",
        "Phibro", "Phibro Animal Health",
        "Innovad",
    ],
    "integrators": [
        "Tyson Foods", "Tyson",
        "JBS",
        "Smithfield", "Smithfield Foods",
        "CP Group", "Charoen Pokphand",
        "New Hope Liuhe", "New Hope",
        "Wens Foodstuff", "Wens",
        "Muyuan Foodstuff", "Muyuan",
    ],
}

# Flat list for fuzzy matching loops
ENTITIES_FLAT = [
    alias
    for group in ENTITIES_TIER_1.values()
    for alias in group
]

# =============================================================================
# Commodities & themes (used for keyword matching + LLM context)
# =============================================================================
COMMODITIES = [
    # Phosphates (core focus)
    "MCP", "Monocalcium Phosphate",
    "MDCP", "Monodicalcium Phosphate",
    "DCP", "Dicalcium Phosphate",
    "TCP", "Tricalcium Phosphate",
    "phosphoric acid",
    "rock phosphate",
    # Cereals & oilseeds
    "soybean meal", "soya meal", "soybean",
    "corn", "maize",
    "wheat",
    "barley",
    # Amino acids
    "lysine",
    "methionine",
    "threonine",
    "tryptophan",
    "valine",
    # Other
    "fishmeal",
    "vitamin",
    "enzyme",
]

THEMES = [
    # Sustainability / regulation
    "methane reduction", "enteric methane", "3-NOP", "Bovaer",
    "antibiotic-free", "antimicrobial resistance", "AMR",
    "sustainability", "GHG", "greenhouse gas",
    "feed regulation", "feed safety", "Fit for 55", "Farm to Fork",
    # Animal health
    "gut health", "probiotics", "prebiotics", "phytogenic",
    "mycotoxin", "mycotoxins",
    "African swine fever", "ASF",
    "avian influenza", "bird flu", "HPAI",
    # Markets / trade
    "feed prices", "feed costs",
    "tariff", "export tax", "import ban",
]

# =============================================================================
# Quality filter thresholds (Phase 4)
# =============================================================================
MIN_WORD_COUNT = 80                    # below: too short to classify
MIN_RELEVANCE_SCORE = 2.0              # matches per 1000 words

# Multilingual paywall markers — lowercase comparison
PAYWALL_MARKERS = [
    # English
    "subscribe to read", "subscribe to continue",
    "sign in to continue", "sign in to read",
    "premium content", "premium article",
    "this article is for subscribers", "subscribers only",
    "create a free account",
    # French
    "abonnez-vous", "réservé aux abonnés", "article réservé",
    "créer un compte", "déjà abonné", "se connecter pour lire",
    # Spanish
    "suscríbete para leer", "contenido exclusivo", "solo suscriptores",
    # Portuguese
    "assine para ler", "conteúdo exclusivo", "apenas assinantes",
]

# =============================================================================
# HTTP fetching (Phase 3)
# =============================================================================
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 15        # seconds
REQUEST_RETRIES = 2
BACKOFF_BASE = 2.0          # exponential backoff for 429

# =============================================================================
# Collection window (Phase 1)
# =============================================================================
COLLECTION_WINDOW_HOURS = 48

# =============================================================================
# Regions (for dashboard choropleth)
# =============================================================================
REGIONS = ["Americas", "Europe", "Asia-Pacific", "MENA", "Africa"]

# =============================================================================
# Export (Phase 6)
# =============================================================================
EXPORT_ARTICLE_LIMIT = 200          # latest qualified+classified articles
EXPORT_TIMESERIES_DAYS = 30         # rolling window for daily aggregates
EXPORT_ENTITY_WINDOW_DAYS = 30      # mentions counted within this window

# =============================================================================
# v3 — Economic Intelligence configuration
# =============================================================================

# Competitor stock tickers (Yahoo Finance symbols)
COMPETITOR_STOCKS = {
    "MOS":    {"name": "Mosaic",       "category": "phosphate_suppliers", "color": "#3b82f6"},
    "NTR":    {"name": "Nutrien",      "category": "phosphate_suppliers", "color": "#2563eb"},
    "ICL":    {"name": "ICL Group",    "category": "phosphate_suppliers", "color": "#1e40af"},
    "CF":     {"name": "CF Industries","category": "phosphate_suppliers", "color": "#60a5fa"},
    "YAR.OL": {"name": "Yara",         "category": "phosphate_suppliers", "color": "#1e3a8a"},
    "BG":     {"name": "Bunge",        "category": "additive_suppliers",  "color": "#16a34a"},
    "ADM":    {"name": "ADM",          "category": "additive_suppliers",  "color": "#22c55e"},
    "TSN":    {"name": "Tyson Foods",  "category": "integrators",         "color": "#ea580c"},
    "JBSAY":  {"name": "JBS",          "category": "integrators",         "color": "#f97316"},
}

# Regulatory RSS sources for the radar
REGULATORY_FEEDS = [
    {"name": "EFSA Animal Feed",    "url": "https://www.efsa.europa.eu/en/rss/efsa-animal-feed.xml", "region": "Europe"},
    {"name": "EUR-Lex animal feed", "url": "https://eur-lex.europa.eu/EN/display-feed.rss?myRssId=NEWS_NEW_FEED_CLASSIFIED&topic=Animal+feed", "region": "Europe"},
    {"name": "USDA News",           "url": "https://www.usda.gov/rss/latest-news.xml", "region": "Americas"},
    {"name": "FDA Animal & Vet",    "url": "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/animal-veterinary/rss.xml", "region": "Americas"},
    {"name": "EFSA all",            "url": "https://www.efsa.europa.eu/en/rss/efsa-news.xml", "region": "Europe"},
]
REGULATORY_KEYWORDS = [
    "feed", "phosphate", "monocalcium", "dicalcium", "MCP", "DCP",
    "additive", "contaminant", "cadmium", "lead", "heavy metal",
    "antibiotic", "amino acid", "premix", "compound feed", "labeling",
]

# Weak signal detection
WEAK_SIGNAL_WINDOW_DAYS = 14       # rolling baseline for z-score
WEAK_SIGNAL_ZSCORE_THRESHOLD = 2.0 # alert if z >= 2

# Trade flows (UN Comtrade)
# HS codes relevant to feed phosphates: 2510 (phosphates), 2835 (phosphates chemical),
# 2309 (animal feed preparations)
COMTRADE_HS_CODES = ["2510", "2835", "2309"]
COMTRADE_REPORTERS = ["504", "842", "643", "156", "276", "356"]  # Morocco, USA, Russia, China, Germany, India

# GDELT geopolitical (events with phosphate/feed/morocco relevance)
GDELT_THEMES_OF_INTEREST = [
    "ECON_PRICE", "ECON_TRADE", "ECON_TAX", "ECON_TAXATION",
    "TRADE_AGREEMENT", "EXPORT", "IMPORT",
    "AGRICULTURE", "FOOD_SECURITY",
    "GOV_REGULATION", "WB_2429_ENVIRONMENTAL_REGULATION",
]
GDELT_COUNTRIES_OF_INTEREST = ["MO", "US", "CN", "RU", "FR", "DE", "IN", "BR", "TN", "EG", "SA"]

# Forecasting
FORECAST_HORIZON_DAYS = 30          # how far ahead to forecast
FORECAST_LOOKBACK_DAYS = 90         # history used for the model
