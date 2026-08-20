"""Daily job market ingestion DAG."""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.exceptions import AirflowFailException
from airflow.operators.python import PythonOperator
from dotenv import load_dotenv
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from ingestion.db import get_engine, get_watched_keywords
from ingestion.fetch_jobs import ingest_keyword
from ingestion.logging_config import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


def _min_keywords_succeeded(keyword_count: int) -> int:
    configured = os.getenv("INGESTION_MIN_KEYWORDS_SUCCEEDED")
    if configured is not None and configured.strip() != "":
        return int(configured)
    return keyword_count


def _min_total_inserted() -> int:
    return int(os.getenv("INGESTION_MIN_TOTAL_INSERTED", "0"))


def fetch_and_store(**context):
    """Fetch jobs from Adzuna for every row in watched_keywords."""
    keywords = get_watched_keywords()
    if not keywords:
        raise AirflowFailException(
            "No search terms in watched_keywords. Add at least one keyword before running ingest."
        )

    results = []
    failures: list[tuple[str, str]] = []

    for keyword in keywords:
        try:
            result = ingest_keyword(keyword=keyword)
            results.append(result)
            logger.info(
                "%s: fetched %d, inserted %d, updated %d, skipped %d, failed %d (status=%s)",
                keyword,
                result["fetched"],
                result["inserted"],
                result["updated"],
                result["skipped"],
                result["failed"],
                result["status"],
            )
        except Exception as exc:
            failures.append((keyword, str(exc)))
            logger.exception("Failed to ingest keyword '%s'", keyword)

    total_inserted = sum(result["inserted"] for result in results)
    logger.info("Total inserted across all keywords: %d", total_inserted)

    min_keywords = _min_keywords_succeeded(len(keywords))
    if len(results) < min_keywords:
        failed_keywords = ", ".join(keyword for keyword, _ in failures)
        raise AirflowFailException(
            f"Only {len(results)}/{len(keywords)} keywords succeeded; "
            f"minimum required is {min_keywords}. "
            f"Failed keywords: {failed_keywords or 'none'}"
        )

    min_inserted = _min_total_inserted()
    if total_inserted < min_inserted:
        raise AirflowFailException(
            f"Inserted {total_inserted} jobs across all keywords; "
            f"minimum required is {min_inserted}"
        )


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


default_args = {
    "owner": "data",
    "retries": int(os.getenv("AIRFLOW_INGESTION_RETRIES", "2")),
    "retry_delay": timedelta(minutes=int(os.getenv("AIRFLOW_INGESTION_RETRY_DELAY_MIN", "5"))),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(
        minutes=int(os.getenv("AIRFLOW_INGESTION_MAX_RETRY_DELAY_MIN", "30"))
    ),
}

with DAG(
    dag_id="job_market_ingestion",
    description="Daily ingestion of job postings from Adzuna API",
    schedule_interval="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
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
