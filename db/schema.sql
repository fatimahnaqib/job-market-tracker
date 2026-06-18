-- =============================================================================
-- Job Market Tracker
-- Defines the PostgreSQL schema for storing ingested job listings.
-- Date: 2026-06-11
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Step 1: Create database (run once manually)
-- Connect to the default `postgres` database, then execute:
-- -----------------------------------------------------------------------------
-- CREATE DATABASE job_tracker;

-- -----------------------------------------------------------------------------
-- Step 2: Connect to job_tracker, then run everything below.
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS jobs (
    -- Surrogate primary key for each stored job record
    id              SERIAL PRIMARY KEY,
    -- Adzuna's job ID; prevents duplicate inserts
    external_id     VARCHAR(100) UNIQUE NOT NULL,
    -- Job title as listed in the posting
    title           VARCHAR(255),
    -- Employer or company name
    company         VARCHAR(255),
    -- City, region, or work location string
    location        VARCHAR(255),
    -- Country code for the job location (e.g. US, GB)
    country         VARCHAR(10),
    -- Lower bound of the advertised salary range
    salary_min      NUMERIC(10,2),
    -- Upper bound of the advertised salary range
    salary_max      NUMERIC(10,2),
    -- Whether the role is remote or hybrid-friendly
    is_remote       BOOLEAN DEFAULT FALSE,
    -- Full text of the job posting
    description     TEXT,
    -- Link to the original job listing
    url             TEXT,
    -- When the job was published on the source site
    date_posted     TIMESTAMP,
    -- When this record was ingested into the database
    fetched_at      TIMESTAMP DEFAULT NOW(),
    -- Array of extracted skill keywords
    skills          TEXT[]
);

CREATE INDEX IF NOT EXISTS idx_jobs_external_id ON jobs (external_id);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    -- Unique identifier for each ingestion attempt
    run_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Search keyword used for this run
    keyword         VARCHAR(255) NOT NULL,
    -- Jobs returned by the source API
    fetched_count   INTEGER NOT NULL DEFAULT 0,
    -- New rows written to jobs
    inserted_count  INTEGER NOT NULL DEFAULT 0,
    -- Duplicate external_id rows skipped
    skipped_count   INTEGER NOT NULL DEFAULT 0,
    -- Rows that could not be inserted
    failed_count    INTEGER NOT NULL DEFAULT 0,
    -- running | success | partial | failed
    status          VARCHAR(20) NOT NULL,
    -- When the run started
    started_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    -- When the run finished (NULL while running)
    completed_at    TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ingestion_runs_keyword ON ingestion_runs (keyword);
CREATE INDEX IF NOT EXISTS idx_ingestion_runs_started_at ON ingestion_runs (started_at);

-- Verify the table was created
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'jobs'
ORDER BY ordinal_position;


-- =============================================
-- Migration: add skills column (run once if table already exists)
-- =============================================
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS skills TEXT[];

-- =============================================
-- Migration: ingestion_runs table (run once if table already exists)
-- =============================================
CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    keyword         VARCHAR(255) NOT NULL,
    fetched_count   INTEGER NOT NULL DEFAULT 0,
    inserted_count  INTEGER NOT NULL DEFAULT 0,
    skipped_count   INTEGER NOT NULL DEFAULT 0,
    failed_count    INTEGER NOT NULL DEFAULT 0,
    status          VARCHAR(20) NOT NULL,
    started_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ingestion_runs_keyword ON ingestion_runs (keyword);
CREATE INDEX IF NOT EXISTS idx_ingestion_runs_started_at ON ingestion_runs (started_at);
