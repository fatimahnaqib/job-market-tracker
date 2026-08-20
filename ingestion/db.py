"""Database helpers for ingestion and run tracking."""

from __future__ import annotations

import os
import uuid
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from ingestion.logging_config import get_logger

logger = get_logger(__name__)

START_RUN = text("""
INSERT INTO ingestion_runs (run_id, keyword, status, started_at)
VALUES (:run_id, :keyword, 'running', :started_at)
""")

LIST_WATCHED_KEYWORDS = text("""
SELECT keyword
FROM watched_keywords
ORDER BY keyword
""")

ADD_WATCHED_KEYWORD = text("""
INSERT INTO watched_keywords (keyword)
VALUES (:keyword)
ON CONFLICT (keyword) DO NOTHING
RETURNING keyword
""")

DELETE_WATCHED_KEYWORD = text("""
DELETE FROM watched_keywords
WHERE keyword = :keyword
RETURNING keyword
""")

COMPLETE_RUN = text("""
UPDATE ingestion_runs
SET fetched_count = :fetched_count,
    inserted_count = :inserted_count,
    skipped_count = :skipped_count,
    failed_count = :failed_count,
    status = :status,
    completed_at = :completed_at
WHERE run_id = :run_id
""")


def get_engine() -> Engine:
    """Build a SQLAlchemy engine from environment variables."""
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    name = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    if not all([host, port, name, user, password]):
        raise RuntimeError(
            "DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD must be set in .env"
        )
    return create_engine(f"postgresql://{user}:{password}@{host}:{port}/{name}")


def start_ingestion_run(keyword: str, engine: Engine | None = None) -> uuid.UUID:
    """Insert a running ingestion_runs row and return its run_id."""
    run_id = uuid.uuid4()
    engine = engine or get_engine()
    with engine.begin() as conn:
        conn.execute(
            START_RUN,
            {"run_id": run_id, "keyword": keyword, "started_at": datetime.utcnow()},
        )
    logger.info("Started ingestion run %s for keyword '%s'", run_id, keyword)
    return run_id


def complete_ingestion_run(
    run_id: uuid.UUID,
    *,
    fetched_count: int,
    inserted_count: int,
    skipped_count: int,
    failed_count: int,
    status: str,
    engine: Engine | None = None,
) -> None:
    """Finalize an ingestion_runs row with counts and terminal status."""
    engine = engine or get_engine()
    with engine.begin() as conn:
        conn.execute(
            COMPLETE_RUN,
            {
                "run_id": run_id,
                "fetched_count": fetched_count,
                "inserted_count": inserted_count,
                "skipped_count": skipped_count,
                "failed_count": failed_count,
                "status": status,
                "completed_at": datetime.utcnow(),
            },
        )
    logger.info(
        "Completed run %s — status=%s fetched=%d inserted=%d skipped=%d failed=%d",
        run_id,
        status,
        fetched_count,
        inserted_count,
        skipped_count,
        failed_count,
    )


def normalize_keyword(keyword: str) -> str:
    """Trim whitespace and lowercase a search term."""
    return " ".join((keyword or "").split()).lower()


def get_watched_keywords(engine: Engine | None = None) -> list[str]:
    """Return tracked Adzuna search terms, sorted alphabetically."""
    engine = engine or get_engine()
    with engine.connect() as conn:
        rows = conn.execute(LIST_WATCHED_KEYWORDS).fetchall()
    return [row.keyword for row in rows]


def add_watched_keyword(keyword: str, engine: Engine | None = None) -> str | None:
    """Insert a search term if it is new. Returns the stored keyword, or None if it already exists."""
    normalized = normalize_keyword(keyword)
    if not normalized:
        raise ValueError("keyword must not be empty")
    engine = engine or get_engine()
    with engine.begin() as conn:
        row = conn.execute(ADD_WATCHED_KEYWORD, {"keyword": normalized}).fetchone()
    if row:
        logger.info("Added watched keyword '%s'", normalized)
        return row.keyword
    logger.info("Watched keyword '%s' already exists", normalized)
    return None


def remove_watched_keyword(keyword: str, engine: Engine | None = None) -> bool:
    """Delete a tracked search term. Returns True if a row was removed."""
    normalized = normalize_keyword(keyword)
    if not normalized:
        raise ValueError("keyword must not be empty")
    engine = engine or get_engine()
    with engine.begin() as conn:
        row = conn.execute(DELETE_WATCHED_KEYWORD, {"keyword": normalized}).fetchone()
    if row:
        logger.info("Removed watched keyword '%s'", normalized)
        return True
    logger.info("Watched keyword '%s' was not found", normalized)
    return False
