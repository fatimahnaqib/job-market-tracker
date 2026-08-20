"""Fetch job listings from external sources."""

import os
import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

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

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

INSERT_JOB = text("""
INSERT INTO jobs (external_id, title, company, location, country,
                  salary_min, salary_max, is_remote, description, url,
                  date_posted, fetched_at, skills)
VALUES (:external_id, :title, :company, :location, :country,
        :salary_min, :salary_max, :is_remote, :description, :url,
        :date_posted, :fetched_at, :skills)
ON CONFLICT (external_id) DO UPDATE SET
    title = EXCLUDED.title,
    company = EXCLUDED.company,
    location = EXCLUDED.location,
    country = EXCLUDED.country,
    salary_min = EXCLUDED.salary_min,
    salary_max = EXCLUDED.salary_max,
    is_remote = EXCLUDED.is_remote,
    description = EXCLUDED.description,
    url = EXCLUDED.url,
    date_posted = EXCLUDED.date_posted,
    skills = EXCLUDED.skills,
    fetched_at = EXCLUDED.fetched_at
WHERE jobs.title IS DISTINCT FROM EXCLUDED.title
   OR jobs.company IS DISTINCT FROM EXCLUDED.company
   OR jobs.location IS DISTINCT FROM EXCLUDED.location
   OR jobs.country IS DISTINCT FROM EXCLUDED.country
   OR jobs.salary_min IS DISTINCT FROM EXCLUDED.salary_min
   OR jobs.salary_max IS DISTINCT FROM EXCLUDED.salary_max
   OR jobs.is_remote IS DISTINCT FROM EXCLUDED.is_remote
   OR jobs.description IS DISTINCT FROM EXCLUDED.description
   OR jobs.url IS DISTINCT FROM EXCLUDED.url
   OR jobs.date_posted IS DISTINCT FROM EXCLUDED.date_posted
   OR jobs.skills IS DISTINCT FROM EXCLUDED.skills
RETURNING (xmax = 0) AS inserted
""")


class AdzunaAPIError(Exception):
    """Raised when the Adzuna API cannot return job results after retries."""

    def __init__(self, message: str, *, status_code: int | None = None, keyword: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.keyword = keyword


def _backoff_seconds(attempt: int, base_delay: float, max_delay: float) -> float:
    delay = min(base_delay * (2 ** attempt), max_delay)
    return delay + random.uniform(0, 1)


def _retry_after_seconds(response: requests.Response) -> float | None:
    raw = response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(raw)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError):
            return None


def _request_json(url: str, params: dict, *, keyword: str, timeout: int = 30) -> dict:
    """GET JSON from the Adzuna API with exponential backoff and rate-limit handling."""
    max_retries = int(os.getenv("ADZUNA_MAX_RETRIES", "3"))
    base_delay = float(os.getenv("ADZUNA_RETRY_BASE_DELAY_SEC", "2"))
    max_delay = float(os.getenv("ADZUNA_RETRY_MAX_DELAY_SEC", "60"))
    attempts = max_retries + 1

    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            # trust_env=False skips macOS SystemConfiguration proxy lookup
            # (urllib._scproxy.get_proxy_settings), which can hang indefinitely
            # when multiple Airflow task processes call it concurrently.
            with requests.Session() as session:
                session.trust_env = False
                response = session.get(url, params=params, timeout=timeout)
            status = response.status_code

            if status in RETRYABLE_STATUS_CODES:
                if attempt < max_retries:
                    delay = _retry_after_seconds(response) or _backoff_seconds(
                        attempt, base_delay, max_delay
                    )
                    logger.warning(
                        "Adzuna API returned HTTP %s for keyword '%s' "
                        "(attempt %d/%d), retrying in %.1fs",
                        status,
                        keyword,
                        attempt + 1,
                        attempts,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                raise AdzunaAPIError(
                    f"HTTP {status} from Adzuna API for keyword '{keyword}' "
                    f"after {attempts} attempts",
                    status_code=status,
                    keyword=keyword,
                )

            if not response.ok:
                raise AdzunaAPIError(
                    f"HTTP {status} from Adzuna API for keyword '{keyword}'",
                    status_code=status,
                    keyword=keyword,
                )

            try:
                return response.json()
            except ValueError as exc:
                last_error = exc
                if attempt < max_retries:
                    delay = _backoff_seconds(attempt, base_delay, max_delay)
                    logger.warning(
                        "Invalid JSON from Adzuna API for keyword '%s' "
                        "(attempt %d/%d), retrying in %.1fs",
                        keyword,
                        attempt + 1,
                        attempts,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                raise AdzunaAPIError(
                    f"Invalid JSON response from Adzuna API for keyword '{keyword}' "
                    f"after {attempts} attempts",
                    keyword=keyword,
                ) from exc

        except requests.RequestException as exc:
            last_error = exc
            if attempt < max_retries:
                delay = _backoff_seconds(attempt, base_delay, max_delay)
                logger.warning(
                    "Adzuna API request failed for keyword '%s': %s "
                    "(attempt %d/%d), retrying in %.1fs",
                    keyword,
                    exc,
                    attempt + 1,
                    attempts,
                    delay,
                )
                time.sleep(delay)
                continue
            raise AdzunaAPIError(
                f"Adzuna API request failed for keyword '{keyword}' "
                f"after {attempts} attempts: {exc}",
                keyword=keyword,
            ) from exc

    raise AdzunaAPIError(
        f"Adzuna API request failed for keyword '{keyword}' after {attempts} attempts",
        keyword=keyword,
    ) from last_error


def fetch_jobs(
    keyword="data engineer",
    country="us",
    results_per_page=50,
    max_pages=None,
    page_delay_sec=None,
):
    """Fetch job postings from the Adzuna API, paging until a cap or last page.

    Args:
        keyword: Search term passed to the API as `what`.
        country: Two-letter country code for the Adzuna jobs endpoint.
        results_per_page: Number of results to request per page.
        max_pages: Max pages to request. Defaults to ADZUNA_MAX_PAGES (5).
        page_delay_sec: Pause between pages. Defaults to ADZUNA_PAGE_DELAY_SEC (1).

    Returns:
        List of raw job dictionaries (may be empty when the API returns no matches).

    Raises:
        AdzunaAPIError: On missing credentials, transport errors, or non-recoverable
            HTTP responses after retries are exhausted.
    """
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise AdzunaAPIError("ADZUNA_APP_ID and ADZUNA_APP_KEY must be set in .env")

    if max_pages is None:
        max_pages = int(os.getenv("ADZUNA_MAX_PAGES", "5"))
    if page_delay_sec is None:
        page_delay_sec = float(os.getenv("ADZUNA_PAGE_DELAY_SEC", "1"))
    if max_pages < 1:
        raise ValueError("max_pages must be >= 1")

    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": results_per_page,
        "what": keyword,
    }

    jobs = []
    seen_ids = set()
    pages_fetched = 0

    for page in range(1, max_pages + 1):
        if page > 1 and page_delay_sec > 0:
            time.sleep(page_delay_sec)

        url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
        data = _request_json(url, params, keyword=keyword)
        page_results = data.get("results") or []
        pages_fetched += 1

        new_on_page = 0
        for job in page_results:
            job_id = job.get("id")
            if job_id is not None:
                if job_id in seen_ids:
                    continue
                seen_ids.add(job_id)
            jobs.append(job)
            new_on_page += 1

        logger.info(
            "Fetched page %d/%d for keyword '%s': %d jobs (%d new)",
            page,
            max_pages,
            keyword,
            len(page_results),
            new_on_page,
        )

        if not page_results or len(page_results) < results_per_page:
            break
        total = data.get("count")
        if isinstance(total, int) and len(jobs) >= total:
            break

    logger.info(
        "Fetched %d jobs across %d page(s) for keyword '%s'",
        len(jobs),
        pages_fetched,
        keyword,
    )
    return jobs


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
    """Insert new jobs, refresh rows that changed, skip unchanged duplicates.

    Returns:
        Tuple of (inserted, updated, skipped, failed) counts.
    """
    try:
        engine = get_engine()
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 0, 0, 0, len(jobs)

    inserted = updated = skipped = failed = 0

    with engine.begin() as conn:
        for job in jobs:
            try:
                row = _row_from_job(job)
                if not row["external_id"]:
                    logger.warning("Skipping job with missing id")
                    failed += 1
                    continue
                result = conn.execute(INSERT_JOB, row)
                saved = result.fetchone()
                if saved is None:
                    skipped += 1
                elif saved.inserted:
                    inserted += 1
                else:
                    updated += 1
            except Exception as exc:
                logger.error("Error inserting job %s: %s", job.get("id", "unknown"), exc)
                failed += 1

    logger.info(
        "Inserted: %d, Updated: %d, Skipped: %d, Failed: %d",
        inserted,
        updated,
        skipped,
        failed,
    )
    return inserted, updated, skipped, failed


def _resolve_status(inserted: int, updated: int, skipped: int, failed: int) -> str:
    if failed > 0:
        return "partial" if inserted > 0 or updated > 0 or skipped > 0 else "failed"
    return "success"


def ingest_keyword(keyword: str, country: str = "us") -> dict:
    """Fetch, persist, and record a single keyword ingestion run."""
    engine = get_engine()
    run_id = start_ingestion_run(keyword, engine=engine)
    try:
        jobs = fetch_jobs(keyword=keyword, country=country)
        fetched = len(jobs)
        inserted, updated, skipped, failed = save_jobs(jobs)
        status = _resolve_status(inserted, updated, skipped, failed)
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
            "updated": updated,
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
        "Run %s finished — status=%s fetched=%d inserted=%d updated=%d skipped=%d failed=%d",
        result["run_id"],
        result["status"],
        result["fetched"],
        result["inserted"],
        result["updated"],
        result["skipped"],
        result["failed"],
    )
