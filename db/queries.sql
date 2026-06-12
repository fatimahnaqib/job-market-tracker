-- =============================================
-- Q1: Top 10 companies hiring data engineers
-- =============================================
SELECT
    company,
    COUNT(*) AS job_count
FROM jobs
GROUP BY company
ORDER BY job_count DESC
LIMIT 10;


-- =============================================
-- Q2: Remote vs non-remote breakdown
-- =============================================
SELECT
    is_remote,
    COUNT(*) AS job_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS percentage
FROM jobs
GROUP BY is_remote
ORDER BY is_remote DESC;


-- =============================================
-- Q3: Salary insights
-- =============================================
SELECT
    MIN(salary_min) AS min_salary_min,
    MAX(salary_min) AS max_salary_min,
    AVG(salary_min) AS avg_salary_min,
    MIN(salary_max) AS min_salary_max,
    MAX(salary_max) AS max_salary_max,
    AVG(salary_max) AS avg_salary_max
FROM jobs
WHERE salary_min IS NOT NULL;


-- =============================================
-- Q4: Top 10 locations hiring
-- =============================================
SELECT
    location,
    COUNT(*) AS job_count
FROM jobs
GROUP BY location
ORDER BY job_count DESC
LIMIT 10;


-- =============================================
-- Q5: Jobs posted per day
-- =============================================
SELECT
    DATE_TRUNC('day', date_posted)::DATE AS posted_date,
    COUNT(*) AS job_count
FROM jobs
WHERE date_posted IS NOT NULL
GROUP BY DATE_TRUNC('day', date_posted)::DATE
ORDER BY posted_date DESC;
