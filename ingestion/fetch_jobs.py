"""Fetch job listings from external sources."""

import os
from datetime import datetime

import requests
from dateutil import parser as date_parser
from dotenv import load_dotenv
from sqlalchemy import text

from ingestion.clean_jobs import clean_job
from ingestion.db import (
    complete_ingestion_run,
    get_engine,
    start_ingestion_run,
)
from ingestion.logging_config import get_logger, setup_logging

load_dotenv()

logger = get_logger(__name__)

INSERT_JOB = text("""
INSERT INTO jobs (external_id, title, company, location, country,
                  salary_min, salary_max, is_remote, description, url,
                  date_posted, fetched_at, skills)
VALUES (:external_id, :title, :company, :location, :country,
        :salary_min, :salary_max, :is_remote, :description, :url,
        :date_posted, :fetched_at, :skills)
ON CONFLICT (external_id) DO NOTHING
RETURNING external_id
""")


def fetch_jobs(keyword="data engineer", country="us", results_per_page=50):
    """Fetch job postings from the Adzuna API.

    Args:
        keyword: Search term passed to the API as `what`.
        country: Two-letter country code for the Adzuna jobs endpoint.
        results_per_page: Number of results to request per page.

    Returns:
        List of raw job dictionaries on success (may be empty), or None on error.
    """
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        logger.error("ADZUNA_APP_ID and ADZUNA_APP_KEY must be set in .env")
        return None

    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": results_per_page,
        "what": keyword,
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.HTTPError:
        logger.error("HTTP %s from Adzuna API for keyword '%s'", response.status_code, keyword)
        return []
    except requests.RequestException as exc:
        logger.error("Adzuna API request failed for keyword '%s': %s", keyword, exc)
        return []
    except ValueError:
        logger.error("Failed to decode JSON response from Adzuna API for keyword '%s'", keyword)
        return []

    results = data.get("results", [])
    logger.info("Fetched %d jobs for keyword '%s'", len(results), keyword)
    return results


def _row_from_job(job: dict) -> dict:
    area = (job.get("location") or {}).get("area") or []
    created = job.get("created")
    raw = {
        "external_id": str(job.get("id", "")),
        "title": job.get("title"),
        "company": (job.get("company") or {}).get("display_name"),
        "location": (job.get("location") or {}).get("display_name"),
        "country": area[0] if area else None,
        "salary_min": job.get("salary_min"),
        "salary_max": job.get("salary_max"),
        "description": job.get("description"),
        "url": job.get("redirect_url"),
        "date_posted": date_parser.parse(created) if created else None,
        "fetched_at": datetime.utcnow(),
    }
    return clean_job(raw)


def save_jobs(jobs: list):
    """Insert job records into PostgreSQL, skipping duplicates by external_id.

    Returns:
        Tuple of (inserted, skipped, failed) counts.
    """
    try:
        engine = get_engine()
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 0, 0, len(jobs)

    inserted = skipped = failed = 0

    with engine.begin() as conn:
        for job in jobs:
            try:
                row = _row_from_job(job)
                if not row["external_id"]:
                    logger.warning("Skipping job with missing id")
                    failed += 1
                    continue
                result = conn.execute(INSERT_JOB, row)
                if result.fetchone():
                    inserted += 1
                else:
                    skipped += 1
            except Exception as exc:
                logger.error("Error inserting job %s: %s", job.get("id", "unknown"), exc)
                failed += 1

    logger.info("Inserted: %d, Skipped: %d, Failed: %d", inserted, skipped, failed)
    return inserted, skipped, failed


def _resolve_status(fetched: int, inserted: int, skipped: int, failed: int) -> str:
    if failed > 0:
        return "partial" if inserted > 0 or skipped > 0 else "failed"
    return "success"


def ingest_keyword(keyword: str, country: str = "us") -> dict:
    """Fetch, persist, and record a single keyword ingestion run."""
    engine = get_engine()
    run_id = start_ingestion_run(keyword, engine=engine)
    try:
        jobs = fetch_jobs(keyword=keyword, country=country)
        fetched = len(jobs)
        inserted, skipped, failed = save_jobs(jobs)
        status = _resolve_status(fetched, inserted, skipped, failed)
        complete_ingestion_run(
            run_id,
            fetched_count=fetched,
            inserted_count=inserted,
            skipped_count=skipped,
            failed_count=failed,
            status=status,
            engine=engine,
        )
        return {
            "run_id": run_id,
            "keyword": keyword,
            "fetched": fetched,
            "inserted": inserted,
            "skipped": skipped,
            "failed": failed,
            "status": status,
        }
    except Exception:
        complete_ingestion_run(
            run_id,
            fetched_count=0,
            inserted_count=0,
            skipped_count=0,
            failed_count=0,
            status="failed",
            engine=engine,
        )
        raise


if __name__ == "__main__":
    setup_logging()
    result = ingest_keyword("data engineer")
    logger.info(
        "Run %s finished — status=%s fetched=%d inserted=%d skipped=%d failed=%d",
        result["run_id"],
        result["status"],
        result["fetched"],
        result["inserted"],
        result["skipped"],
        result["failed"],
    )
