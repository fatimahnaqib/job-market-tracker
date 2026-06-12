"""Data cleaning utilities for job records."""

from __future__ import annotations

import re

SKILLS = (
    "python", "sql", "spark", "kafka", "airflow", "aws", "gcp", "azure",
    "docker", "kubernetes", "postgresql", "mysql", "snowflake", "dbt",
    "pandas", "pyspark", "tableau", "power bi", "scala", "java",
    "javascript", "terraform", "redshift", "bigquery", "databricks",
)
REMOTE_KEYWORDS = (
    "remote", "work from home", "wfh", "fully distributed", "anywhere in the us",
)
TITLE_NOISE = (
    r"\s*-\s*Remote\s*$", r"\s*\(Remote\)\s*$", r"\s*US-\s*$", r"\s*-\s*USA\s*$",
)


def normalize_title(title: str) -> str:
    """Strip whitespace, remove common title suffix noise, and apply title case."""
    cleaned = (title or "").strip()
    for pattern in TITLE_NOISE:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip().title()


def normalize_salary(value) -> float | None:
    """Convert a salary value to float, or return None if missing or invalid."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = re.sub(r"[$£€¥,]", "", value.strip())
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def detect_remote(title: str, description: str) -> bool:
    """Return True if title or description contains a remote-work keyword."""
    text = f"{title or ''} {description or ''}".lower()
    return any(keyword in text for keyword in REMOTE_KEYWORDS)


def extract_skills(description: str) -> list[str]:
    """Return deduplicated lowercase skills found in a job description."""
    if not description:
        return []
    found = []
    for skill in SKILLS:
        if re.search(rf"\b{re.escape(skill)}\b", description, re.IGNORECASE):
            found.append(skill)
    return found


def clean_job(row: dict) -> dict:
    """Return a cleaned copy of a job dict with normalized fields and extracted skills."""
    title = row.get("title") or ""
    description = row.get("description") or ""
    return {
        **row,
        "title": normalize_title(title),
        "salary_min": normalize_salary(row.get("salary_min")),
        "salary_max": normalize_salary(row.get("salary_max")),
        "is_remote": detect_remote(title, description),
        "skills": extract_skills(description),
    }


if __name__ == "__main__":
    samples = [
        {
            "title": "  senior data engineer - Remote  ",
            "salary_min": "$120,000",
            "salary_max": "150000.50",
            "is_remote": False,
            "description": "Need Python, SQL, Spark, and AWS. Work from home 2 days/week.",
        },
        {
            "title": "Data Engineer",
            "salary_min": 130000.0,
            "salary_max": 160000.0,
            "is_remote": False,
            "description": "Python and PostgreSQL required. On-site in NYC.",
        },
    ]
    for i, job in enumerate(samples, 1):
        print(f"--- Sample {i} (before) ---")
        print(job)
        print(f"--- Sample {i} (after) ---")
        print(clean_job(job))
        print()
