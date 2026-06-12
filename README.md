# Job Market Tracker

A data pipeline that ingests job postings from the Adzuna API, stores them in PostgreSQL, and supports SQL-based market analysis.

## What it does

- Fetches live job postings from the Adzuna API by keyword and country
- Maps API fields to a PostgreSQL `jobs` table and inserts records with deduplication on `external_id`
- Skips duplicate listings on re-runs using `ON CONFLICT DO NOTHING`
- Includes ready-to-run SQL queries for company, location, salary, and posting trends

## Tech stack

- Python
- PostgreSQL
- SQLAlchemy
- Apache Airflow (coming soon)
- Streamlit (coming soon)

## Project structure

```
job-market-tracker/
├── db/
│   ├── schema.sql          # PostgreSQL database and jobs table definition
│   └── queries.sql         # Analytical queries against the jobs table
├── ingestion/
│   ├── __init__.py         # Package marker for the ingestion module
│   └── fetch_jobs.py       # Adzuna API fetch and PostgreSQL insert logic
├── .env.example            # Template for environment variables
├── .gitignore              # Ignores secrets, virtual env, and Python cache files
├── requirements.txt        # Python dependencies
└── README.md               # Project documentation
```

## Setup

### a. Clone the repo

```bash
git clone https://github.com/fatimahnaqib/job-market-tracker.git
cd job-market-tracker
```

### b. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # macOS / Linux
# .venv\Scripts\activate    # Windows
```

### c. Install dependencies

```bash
pip install -r requirements.txt
```

### d. Configure environment variables

```bash
cp .env.example .env
```

Fill in `.env` with your values:

| Variable | Description |
|----------|-------------|
| `DB_HOST` | PostgreSQL host (e.g. `localhost`) |
| `DB_PORT` | PostgreSQL port (e.g. `5432`) |
| `DB_NAME` | Database name (`job_tracker`) |
| `DB_USER` | PostgreSQL username |
| `DB_PASSWORD` | PostgreSQL password |
| `ADZUNA_APP_ID` | Adzuna API application ID |
| `ADZUNA_APP_KEY` | Adzuna API application key |

Get Adzuna credentials at [developer.adzuna.com](https://developer.adzuna.com/).

### e. Create the database and run the schema

```bash
# Connect to PostgreSQL and create the database (run once)
psql -U postgres -c "CREATE DATABASE job_tracker;"

# Apply the schema
psql -U postgres -d job_tracker -f db/schema.sql
```

### f. Run the ingestion script

```bash
python -m ingestion.fetch_jobs
```

## Sample output

```
Jobs returned: 50
Inserted: 50, Skipped: 0
```

## SQL analysis

Queries live in `db/queries.sql`. Run the full file with:

```bash
psql -U postgres -d job_tracker -f db/queries.sql
```

| Query | What it answers |
|-------|-----------------|
| Q1 | Which companies have the most data engineer openings |
| Q2 | How many jobs are remote vs non-remote, with percentages |
| Q3 | Min, max, and average salary ranges where salary data exists |
| Q4 | Which locations have the highest number of job postings |
| Q5 | How many jobs were posted each day, most recent first |

## Roadmap

- [x] Phase 1: Data ingestion + PostgreSQL storage
- [ ] Phase 2: Data cleaning + skill extraction
- [ ] Phase 3: SQL trend analysis
- [ ] Phase 4: Apache Airflow scheduling
- [ ] Phase 5: Streamlit dashboard

---

**Author:** Fatimah Naqib
