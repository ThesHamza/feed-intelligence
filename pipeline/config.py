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
LLM_MODEL = "gemini-2.5-flash-lite"
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
COLLECTION_WINDOW_HOURS = 720

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
