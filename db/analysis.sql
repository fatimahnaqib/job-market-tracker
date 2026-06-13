-- =============================================
-- Q1: most in-demand skills across all jobs
-- =============================================
SELECT
    skill,
    COUNT(*) AS job_count
FROM jobs
CROSS JOIN LATERAL UNNEST(skills) AS skill
GROUP BY skill
ORDER BY job_count DESC
LIMIT 15;


-- =============================================
-- Q2: average salary by job title (top 10 best paying)
-- =============================================
SELECT
    LOWER(title) AS title,
    COUNT(*) AS posting_count,
    ROUND(AVG(salary_min), 2) AS avg_salary_min
FROM jobs
WHERE salary_min IS NOT NULL
GROUP BY LOWER(title)
ORDER BY avg_salary_min DESC
LIMIT 10;


-- =============================================
-- Q3: remote vs non-remote salary comparison
-- =============================================
SELECT
    is_remote,
    COUNT(*) AS job_count,
    ROUND(AVG(salary_min), 2) AS avg_salary
FROM jobs
WHERE salary_min IS NOT NULL
GROUP BY is_remote
ORDER BY is_remote DESC;


-- =============================================
-- Q4: top skills by company (CTE required)
-- =============================================
WITH company_job_counts AS (
    SELECT
        company
    FROM jobs
    WHERE company IS NOT NULL
    GROUP BY company
    HAVING COUNT(*) > 1
),
company_skills AS (
    SELECT
        j.company,
        skill
    FROM jobs j
    CROSS JOIN LATERAL UNNEST(j.skills) AS skill
    INNER JOIN company_job_counts cjc ON j.company = cjc.company
)
SELECT
    company,
    skill,
    COUNT(*) AS skill_count
FROM company_skills
GROUP BY company, skill
ORDER BY company, skill_count DESC;


-- =============================================
-- Q5: job posting volume by week (CTE required)
-- =============================================
WITH weekly_postings AS (
    SELECT
        DATE_TRUNC('week', date_posted) AS week_start,
        COUNT(*) AS job_count
    FROM jobs
    WHERE date_posted IS NOT NULL
    GROUP BY DATE_TRUNC('week', date_posted)
)
SELECT
    week_start,
    job_count
FROM weekly_postings
ORDER BY week_start DESC;


-- =============================================
-- Q6: salary range width per company (window function)
-- =============================================
SELECT
    company,
    title,
    salary_max - salary_min AS salary_range,
    ROUND(
        AVG(salary_max - salary_min) OVER (PARTITION BY company),
        2
    ) AS company_avg_range
FROM jobs
WHERE salary_min IS NOT NULL
  AND salary_max IS NOT NULL
ORDER BY company_avg_range DESC;


-- =============================================
-- Q7: running total of jobs ingested over time (window function)
-- =============================================
SELECT
    fetched_at::DATE AS fetched_date,
    title,
    company,
    SUM(1) OVER (ORDER BY fetched_at) AS running_total
FROM jobs
WHERE fetched_at IS NOT NULL
ORDER BY fetched_at;


-- =============================================
-- Q8: companies offering both remote and non-remote roles
-- =============================================
WITH company_remote_status AS (
    SELECT
        company,
        COUNT(*) FILTER (WHERE is_remote = TRUE) AS remote_count,
        COUNT(*) FILTER (WHERE is_remote = FALSE) AS non_remote_count,
        COUNT(*) AS total_jobs
    FROM jobs
    WHERE company IS NOT NULL
    GROUP BY company
    HAVING COUNT(*) FILTER (WHERE is_remote = TRUE) >= 1
       AND COUNT(*) FILTER (WHERE is_remote = FALSE) >= 1
)
SELECT
    company,
    remote_count,
    non_remote_count,
    total_jobs
FROM company_remote_status
ORDER BY total_jobs DESC;
