-- Q1: Count accepted and quarantined records for all six domains.
-- This exact query was run before and after the no-new-files replay.
SELECT dataset, layer, row_count
FROM (
  SELECT 'students' AS dataset, 'accepted' AS layer, count(*) AS row_count FROM serverless_stable_febar_scottj_catalog.student_retention_bronze.students
  UNION ALL SELECT 'students', 'quarantine', count(*) FROM serverless_stable_febar_scottj_catalog.student_retention_bronze.students_quarantine
  UNION ALL SELECT 'enrollments', 'accepted', count(*) FROM serverless_stable_febar_scottj_catalog.student_retention_bronze.enrollments
  UNION ALL SELECT 'enrollments', 'quarantine', count(*) FROM serverless_stable_febar_scottj_catalog.student_retention_bronze.enrollments_quarantine
  UNION ALL SELECT 'attendance_events', 'accepted', count(*) FROM serverless_stable_febar_scottj_catalog.student_retention_bronze.attendance_events
  UNION ALL SELECT 'attendance_events', 'quarantine', count(*) FROM serverless_stable_febar_scottj_catalog.student_retention_bronze.attendance_events_quarantine
  UNION ALL SELECT 'engagement_events', 'accepted', count(*) FROM serverless_stable_febar_scottj_catalog.student_retention_bronze.engagement_events
  UNION ALL SELECT 'engagement_events', 'quarantine', count(*) FROM serverless_stable_febar_scottj_catalog.student_retention_bronze.engagement_events_quarantine
  UNION ALL SELECT 'financial_events', 'accepted', count(*) FROM serverless_stable_febar_scottj_catalog.student_retention_bronze.financial_events
  UNION ALL SELECT 'financial_events', 'quarantine', count(*) FROM serverless_stable_febar_scottj_catalog.student_retention_bronze.financial_events_quarantine
  UNION ALL SELECT 'student_outcomes', 'accepted', count(*) FROM serverless_stable_febar_scottj_catalog.student_retention_bronze.student_outcomes
  UNION ALL SELECT 'student_outcomes', 'quarantine', count(*) FROM serverless_stable_febar_scottj_catalog.student_retention_bronze.student_outcomes_quarantine
)
ORDER BY dataset, layer;

-- Q2: Verify quarantine reasons and operational metadata.
SELECT 'attendance_events' AS dataset, _violation_reason, count(*) AS row_count,
       count_if(_source_path IS NULL) AS missing_source_path,
       count_if(_ingested_at IS NULL) AS missing_ingested_at
FROM serverless_stable_febar_scottj_catalog.student_retention_bronze.attendance_events_quarantine
GROUP BY _violation_reason
UNION ALL
SELECT 'engagement_events', _violation_reason, count(*),
       count_if(_source_path IS NULL), count_if(_ingested_at IS NULL)
FROM serverless_stable_febar_scottj_catalog.student_retention_bronze.engagement_events_quarantine
GROUP BY _violation_reason
UNION ALL
SELECT 'financial_events', _violation_reason, count(*),
       count_if(_source_path IS NULL), count_if(_ingested_at IS NULL)
FROM serverless_stable_febar_scottj_catalog.student_retention_bronze.financial_events_quarantine
GROUP BY _violation_reason
ORDER BY dataset, _violation_reason;

-- Q3: Extract output counts and fail-update expectation metrics.
SELECT regexp_extract(origin.flow_name, '([^.]+)$', 1) AS flow_name,
       cast(details:flow_progress.metrics.num_output_rows AS BIGINT) AS output_rows,
       details:flow_progress.data_quality.expectations[0].name AS expectation_name,
       cast(details:flow_progress.data_quality.expectations[0].passed_records AS BIGINT) AS passed_records,
       cast(details:flow_progress.data_quality.expectations[0].failed_records AS BIGINT) AS failed_records
FROM event_log('b22af6b5-ff4b-47b3-a2b4-0d3945986ce7')
WHERE event_type = 'flow_progress'
  AND origin.update_id = '9a7a50ca-2f93-417d-a229-918e7735cc53'
  AND details:flow_progress.metrics.num_output_rows IS NOT NULL
ORDER BY flow_name;
