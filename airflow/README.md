# Airflow

Local Airflow setup for the `job_market_ingestion` DAG.

## Install

Install dependencies from the project root (with your virtual environment activated):

```bash
pip install -r requirements.txt
```

**macOS Apple Silicon (M1/M2) with Python 3.9:**
If you see a `google-re2` build error, install Airflow with the official constraints file:

```bash
pip install "apache-airflow>=2.8,<3.0" \
  --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.8.1/constraints-3.9.txt"
```
