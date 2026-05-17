"""Feed Market Intelligence — data pipeline package.

Shared DB helpers used by every step_*.py module.
init_schema() is idempotent — safe to call at every step.
"""

import sqlite3
from . import config


def get_connection() -> sqlite3.Connection:
    """SQLite connection with FK + Row factory."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema() -> None:
    """Create all tables if absent. Idempotent."""
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS raw_urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                source TEXT NOT NULL,
                query TEXT,
                title_hint TEXT,
                published_at TEXT,
                fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                lang_hint TEXT,
                region_hint TEXT,
                processed INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_raw_urls_processed ON raw_urls(processed);
            CREATE INDEX IF NOT EXISTS idx_raw_urls_fetched ON raw_urls(fetched_at);

            CREATE TABLE IF NOT EXISTS urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_url_id INTEGER NOT NULL REFERENCES raw_urls(id),
                url_canonical TEXT NOT NULL,
                url_hash TEXT NOT NULL UNIQUE,
                domain TEXT,
                lang_hint TEXT,
                region_hint TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                error_msg TEXT,
                normalized_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_urls_status ON urls(status);
            CREATE INDEX IF NOT EXISTS idx_urls_domain ON urls(domain);

            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url_id INTEGER NOT NULL UNIQUE REFERENCES urls(id),
                title TEXT,
                body TEXT,
                authors TEXT,
                published_date TEXT,
                language TEXT,
                word_count INTEGER,
                extractor TEXT,
                extracted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_date);
            CREATE INDEX IF NOT EXISTS idx_articles_language ON articles(language);

            CREATE TABLE IF NOT EXISTS quality (
                article_id INTEGER PRIMARY KEY REFERENCES articles(id),
                qualified INTEGER NOT NULL,
                relevance_score REAL,
                reason TEXT,
                checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS classifications (
                article_id INTEGER PRIMARY KEY REFERENCES articles(id),
                position TEXT,
                tone TEXT,
                narrative TEXT,
                commodities TEXT,
                regions TEXT,
                key_companies TEXT,
                impact TEXT,
                confidence INTEGER,
                signal TEXT,
                time_horizon TEXT,
                classified_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_class_position ON classifications(position);
            CREATE INDEX IF NOT EXISTS idx_class_narrative ON classifications(narrative);
            """
        )
        conn.commit()
