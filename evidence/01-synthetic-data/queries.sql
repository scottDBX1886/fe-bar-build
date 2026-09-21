-- Q1: Verify row counts for every generated source dataset.
SELECT 'students' AS dataset, count(*) AS rows
FROM read_files('/Volumes/serverless_stable_febar_scottj_catalog/student_retention_bronze/raw_data/students/run_date=2026-09-21', format => 'parquet')
UNION ALL SELECT 'enrollments', count(*) FROM read_files('/Volumes/serverless_stable_febar_scottj_catalog/student_retention_bronze/raw_data/enrollments/run_date=2026-09-21', format => 'parquet')
UNION ALL SELECT 'attendance_events', count(*) FROM read_files('/Volumes/serverless_stable_febar_scottj_catalog/student_retention_bronze/raw_data/attendance_events/run_date=2026-09-21', format => 'parquet')
UNION ALL SELECT 'engagement_events', count(*) FROM read_files('/Volumes/serverless_stable_febar_scottj_catalog/student_retention_bronze/raw_data/engagement_events/run_date=2026-09-21', format => 'parquet')
UNION ALL SELECT 'financial_events', count(*) FROM read_files('/Volumes/serverless_stable_febar_scottj_catalog/student_retention_bronze/raw_data/financial_events/run_date=2026-09-21', format => 'parquet')
UNION ALL SELECT 'student_outcomes', count(*) FROM read_files('/Volumes/serverless_stable_febar_scottj_catalog/student_retention_bronze/raw_data/student_outcomes/run_date=2026-09-21', format => 'parquet')
ORDER BY dataset;

-- Q2: Verify the deliberately nonuniform program distribution.
SELECT program_code,
       count(*) AS student_count,
       round(avg(synthetic_net_tuition_next_term), 2) AS avg_net_tuition
FROM read_files('/Volumes/serverless_stable_febar_scottj_catalog/student_retention_bronze/raw_data/students/run_date=2026-09-21', format => 'parquet')
GROUP BY program_code
ORDER BY student_count DESC;

-- Q3: Verify the embedded attendance incident.
SELECT story_segment,
       round(avg(CASE WHEN present_flag THEN 1.0 ELSE 0.0 END), 3) AS attendance_rate,
       count(*) AS event_count
FROM read_files('/Volumes/serverless_stable_febar_scottj_catalog/student_retention_bronze/raw_data/attendance_events/run_date=2026-09-21', format => 'parquet')
WHERE NOT is_injected_defect
GROUP BY story_segment
ORDER BY story_segment;

-- Q4: Verify realistic outcome imbalance and incident lift.
SELECT s.incident_cohort,
       count(*) AS outcome_count,
       round(avg(CASE WHEN o.stopout_flag THEN 1.0 ELSE 0.0 END), 3) AS stopout_rate
FROM read_files('/Volumes/serverless_stable_febar_scottj_catalog/student_retention_bronze/raw_data/student_outcomes/run_date=2026-09-21', format => 'parquet') o
JOIN read_files('/Volumes/serverless_stable_febar_scottj_catalog/student_retention_bronze/raw_data/students/run_date=2026-09-21', format => 'parquet') s
  USING (student_id)
GROUP BY s.incident_cohort
ORDER BY s.incident_cohort;

-- Q5: Verify child foreign keys, excluding intentional quarantine rows.
WITH students AS (
  SELECT student_id
  FROM read_files('/Volumes/serverless_stable_febar_scottj_catalog/student_retention_bronze/raw_data/students/run_date=2026-09-21', format => 'parquet')
)
SELECT 'enrollments' AS dataset, count(*) AS orphan_rows
FROM read_files('/Volumes/serverless_stable_febar_scottj_catalog/student_retention_bronze/raw_data/enrollments/run_date=2026-09-21', format => 'parquet') c
LEFT ANTI JOIN students s USING (student_id)
UNION ALL
SELECT 'attendance_events', count(*)
FROM read_files('/Volumes/serverless_stable_febar_scottj_catalog/student_retention_bronze/raw_data/attendance_events/run_date=2026-09-21', format => 'parquet') c
LEFT ANTI JOIN students s USING (student_id)
WHERE NOT c.is_injected_defect
UNION ALL
SELECT 'engagement_events', count(*)
FROM read_files('/Volumes/serverless_stable_febar_scottj_catalog/student_retention_bronze/raw_data/engagement_events/run_date=2026-09-21', format => 'parquet') c
LEFT ANTI JOIN students s USING (student_id)
WHERE NOT c.is_injected_defect
UNION ALL
SELECT 'financial_events', count(*)
FROM read_files('/Volumes/serverless_stable_febar_scottj_catalog/student_retention_bronze/raw_data/financial_events/run_date=2026-09-21', format => 'parquet') c
LEFT ANTI JOIN students s USING (student_id)
WHERE NOT c.is_injected_defect
UNION ALL
SELECT 'student_outcomes', count(*)
FROM read_files('/Volumes/serverless_stable_febar_scottj_catalog/student_retention_bronze/raw_data/student_outcomes/run_date=2026-09-21', format => 'parquet') c
LEFT ANTI JOIN students s USING (student_id)
ORDER BY dataset;

-- Q6: Calculate overflow-safe deterministic checksums before and after rerun.
SELECT 'students' AS dataset,
       sum(cast(xxhash64(student_id, program_code, advisor_id, incident_cohort) AS DECIMAL(38,0))) AS checksum
FROM read_files('/Volumes/serverless_stable_febar_scottj_catalog/student_retention_bronze/raw_data/students/run_date=2026-09-21', format => 'parquet')
UNION ALL SELECT 'enrollments', sum(cast(xxhash64(enrollment_id, student_id, term_code, cumulative_gpa) AS DECIMAL(38,0))) FROM read_files('/Volumes/serverless_stable_febar_scottj_catalog/student_retention_bronze/raw_data/enrollments/run_date=2026-09-21', format => 'parquet')
UNION ALL SELECT 'attendance_events', sum(cast(xxhash64(attendance_event_id, student_id, event_at, present_flag) AS DECIMAL(38,0))) FROM read_files('/Volumes/serverless_stable_febar_scottj_catalog/student_retention_bronze/raw_data/attendance_events/run_date=2026-09-21', format => 'parquet')
UNION ALL SELECT 'engagement_events', sum(cast(xxhash64(engagement_event_id, student_id, event_at, event_status) AS DECIMAL(38,0))) FROM read_files('/Volumes/serverless_stable_febar_scottj_catalog/student_retention_bronze/raw_data/engagement_events/run_date=2026-09-21', format => 'parquet')
UNION ALL SELECT 'financial_events', sum(cast(xxhash64(financial_event_id, student_id, event_at, balance_amount, financial_hold_flag) AS DECIMAL(38,0))) FROM read_files('/Volumes/serverless_stable_febar_scottj_catalog/student_retention_bronze/raw_data/financial_events/run_date=2026-09-21', format => 'parquet')
UNION ALL SELECT 'student_outcomes', sum(cast(xxhash64(outcome_id, student_id, stopout_flag) AS DECIMAL(38,0))) FROM read_files('/Volumes/serverless_stable_febar_scottj_catalog/student_retention_bronze/raw_data/student_outcomes/run_date=2026-09-21', format => 'parquet')
ORDER BY dataset;
