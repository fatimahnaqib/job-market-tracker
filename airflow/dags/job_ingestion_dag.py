"""Daily job market ingestion DAG."""

import sys
from datetime import datetime
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator
from dotenv import load_dotenv
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from ingestion.db import get_engine
from ingestion.fetch_jobs import ingest_keyword
from ingestion.logging_config import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

KEYWORDS = [
    "data engineer",
    "data analyst",
    "machine learning engineer",
    "backend engineer",
]


def fetch_and_store(**context):
    """Fetch jobs from Adzuna and store them for each configured keyword."""
    total_inserted = 0
    for keyword in KEYWORDS:
        try:
            result = ingest_keyword(keyword=keyword)
            total_inserted += result["inserted"]
            logger.info(
                "%s: fetched %d, inserted %d, skipped %d, failed %d (status=%s)",
                keyword,
                result["fetched"],
                result["inserted"],
                result["skipped"],
                result["failed"],
                result["status"],
            )
        except Exception:
            logger.exception("Error processing '%s'", keyword)
    logger.info("Total inserted across all keywords: %d", total_inserted)


def log_summary(**context):
    """Query PostgreSQL and log total job count and latest fetch timestamp."""
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT COUNT(*) AS total, MAX(fetched_at) AS last_fetched FROM jobs")
        ).fetchone()
    logger.info(
        "Ingestion summary — total jobs: %s, last fetched: %s",
        row.total,
        row.last_fetched,
    )


with DAG(
    dag_id="job_market_ingestion",
    description="Daily ingestion of job postings from Adzuna API",
    schedule_interval="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["jobs", "ingestion", "adzuna"],
) as dag:
    fetch_and_store = PythonOperator(
        task_id="fetch_and_store_jobs",
        python_callable=fetch_and_store,
    )
    log_ingestion_summary = PythonOperator(
        task_id="log_ingestion_summary",
        python_callable=log_summary,
    )

    fetch_and_store >> log_ingestion_summary
