"""Fetch job listings from external sources."""

import os
from datetime import datetime

import requests
from dateutil import parser as date_parser
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from ingestion.clean_jobs import clean_job

load_dotenv()

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
        List of raw job dictionaries from the API response, or an empty list on error.
    """
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        print("Error: ADZUNA_APP_ID and ADZUNA_APP_KEY must be set in .env")
        return []

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
        print(f"Error: HTTP {response.status_code} from Adzuna API")
        return []
    except requests.RequestException as exc:
        print(f"Error: request failed — {exc}")
        return []
    except ValueError:
        print("Error: failed to decode JSON response from Adzuna API")
        return []

    return data.get("results", [])


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
    """Insert job records into PostgreSQL, skipping duplicates by external_id."""
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    name = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    if not all([host, port, name, user, password]):
        print("Error: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD must be set in .env")
        return 0, 0

    engine = create_engine(f"postgresql://{user}:{password}@{host}:{port}/{name}")
    inserted = skipped = 0

    with engine.connect() as conn:
        for job in jobs:
            try:
                row = _row_from_job(job)
                if not row["external_id"]:
                    print(f"Error inserting job: missing id")
                    continue
                result = conn.execute(INSERT_JOB, row)
                if result.fetchone():
                    inserted += 1
                else:
                    skipped += 1
            except Exception as exc:
                print(f"Error inserting job {job.get('id', 'unknown')}: {exc}")
        conn.commit()

    print(f"Inserted: {inserted}, Skipped: {skipped}")
    return inserted, skipped


if __name__ == "__main__":
    jobs = fetch_jobs()
    print(f"Jobs returned: {len(jobs)}")
    for job in jobs[:3]:
        row = _row_from_job(job)
        print(f"- {row['title']} @ {row['company']}")
        print(f"  Skills: {row['skills']}")
    save_jobs(jobs)
