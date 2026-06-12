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
    fetched_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jobs_external_id ON jobs (external_id);

-- Verify the table was created
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'jobs'
ORDER BY ordinal_position;
