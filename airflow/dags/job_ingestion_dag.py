"""Daily job market ingestion DAG."""

import os
import sys
from datetime import datetime
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from ingestion.fetch_jobs import fetch_jobs, save_jobs

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
            jobs = fetch_jobs(keyword=keyword)
            inserted, _ = save_jobs(jobs)
            total_inserted += inserted
            print(f"{keyword}: fetched {len(jobs)}, inserted {inserted}")
        except Exception as exc:
            print(f"Error processing '{keyword}': {exc}")
    print(f"Total inserted across all keywords: {total_inserted}")


def log_summary(**context):
    """Query PostgreSQL and log total job count and latest fetch timestamp."""
    engine = create_engine(
        f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
        f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT COUNT(*) AS total, MAX(fetched_at) AS last_fetched FROM jobs")
        ).fetchone()
    print(f"Ingestion summary — total jobs: {row.total}, last fetched: {row.last_fetched}")


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
