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
- Apache Airflow
- Streamlit (coming soon)

## Project structure

```
job-market-tracker/
├── airflow/
│   └── dags/
│       ├── __init__.py             # Package marker for Airflow DAGs
│       └── job_ingestion_dag.py    # Daily scheduled job ingestion DAG
├── db/
│   ├── schema.sql          # PostgreSQL database and jobs table definition
│   ├── queries.sql         # Analytical queries against the jobs table
│   └── analysis.sql        # Advanced SQL analysis with CTEs and window functions
├── ingestion/
│   ├── __init__.py         # Package marker for the ingestion module
│   ├── fetch_jobs.py       # Adzuna API fetch and PostgreSQL insert logic
│   └── clean_jobs.py       # Data cleaning and skill extraction utilities
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

## Airflow scheduling

Set `AIRFLOW_HOME` to the project's `airflow/` folder before running any Airflow commands:

```bash
export AIRFLOW_HOME="$(pwd)/airflow"
```

### Initialize the Airflow database

```bash
airflow db init
```

### Start the webserver and scheduler

Run each command in a separate terminal (with `.venv` activated and `AIRFLOW_HOME` set):

```bash
airflow webserver --port 8080
```

```bash
airflow scheduler
```

Open the UI at [http://localhost:8080](http://localhost:8080) and find the `job_market_ingestion` DAG.

**Can't find the DAG?**

1. Confirm `AIRFLOW_HOME` is set in **both** terminals before starting the webserver and scheduler:
   ```bash
   export AIRFLOW_HOME="$(pwd)/airflow"
   ```
   If this is missing, Airflow uses `~/airflow` instead and your DAG won't appear.

2. Search the DAGs page for `job_market_ingestion` (use the search box at the top).

3. New DAGs are **paused by default** — look for a gray toggle in the left column and switch it **on**.

4. Example DAGs can clutter the list. This project sets `load_examples = False` in `airflow/airflow.cfg`. Restart the webserver and scheduler after changing config:
   ```bash
   airflow dags list | grep job_market
   ```
   You should see one line: `job_market_ingestion`.

5. Check for import errors:
   ```bash
   airflow dags list-import-errors
   ```

### Trigger the DAG manually

From the Airflow UI, toggle the DAG on and click **Trigger DAG**.

Or from the terminal:

```bash
airflow dags trigger job_market_ingestion
```

The DAG runs two tasks in order: `fetch_and_store_jobs` (fetches four keyword searches from Adzuna) then `log_ingestion_summary` (logs total rows and latest `fetched_at` from PostgreSQL).

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

## Key Findings

- SQL and Python are the top 2 most in-demand skills across all postings
- Director-level roles average $192k vs $126k for generic Data Engineer titles
- Only 4% of data engineer roles are listed as remote
- Azure, PySpark, and Airflow are the fastest-rising skills in job descriptions

## Roadmap

- [x] Phase 1: Data ingestion + PostgreSQL storage
- [x] Phase 2: Data cleaning + skill extraction
- [x] Phase 3: SQL trend analysis
- [x] Phase 4: Apache Airflow scheduling
- [ ] Phase 5: Streamlit dashboard

---

**Author:** Fatimah Naqib
