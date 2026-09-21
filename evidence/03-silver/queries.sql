-- Q1: Verify Silver row counts and unique business keys.
SELECT dataset, row_count, duplicate_keys
FROM (
  SELECT 'students' AS dataset, count(*) AS row_count, count(*) - count(DISTINCT student_id) AS duplicate_keys FROM serverless_stable_febar_scottj_catalog.student_retention_silver.students
  UNION ALL SELECT 'enrollments', count(*), count(*) - count(DISTINCT enrollment_id) FROM serverless_stable_febar_scottj_catalog.student_retention_silver.enrollments
  UNION ALL SELECT 'attendance_events', count(*), count(*) - count(DISTINCT attendance_event_id) FROM serverless_stable_febar_scottj_catalog.student_retention_silver.attendance_events
  UNION ALL SELECT 'engagement_events', count(*), count(*) - count(DISTINCT engagement_event_id) FROM serverless_stable_febar_scottj_catalog.student_retention_silver.engagement_events
  UNION ALL SELECT 'financial_events', count(*), count(*) - count(DISTINCT financial_event_id) FROM serverless_stable_febar_scottj_catalog.student_retention_silver.financial_events
  UNION ALL SELECT 'student_outcomes', count(*), count(*) - count(DISTINCT outcome_id) FROM serverless_stable_febar_scottj_catalog.student_retention_silver.student_outcomes
  UNION ALL SELECT 'student_daily_snapshots', count(*), count(*) - count(DISTINCT student_id, feature_as_of) FROM serverless_stable_febar_scottj_catalog.student_retention_silver.student_daily_snapshots
  UNION ALL SELECT 'model_feature_snapshots', count(*), count(*) - count(DISTINCT student_id, feature_as_of) FROM serverless_stable_febar_scottj_catalog.student_retention_silver.model_feature_snapshots
  UNION ALL SELECT 'training_labels', count(*), count(*) - count(DISTINCT outcome_id) FROM serverless_stable_febar_scottj_catalog.student_retention_silver.training_labels
  UNION ALL SELECT 'student_protected_audit', count(*), count(*) - count(DISTINCT student_id) FROM serverless_stable_febar_scottj_catalog.student_retention_silver.student_protected_audit
  UNION ALL SELECT 'referential_quarantine', count(*), 0 FROM serverless_stable_febar_scottj_catalog.student_retention_silver.referential_quarantine
)
ORDER BY dataset;

-- Q2: Verify temporal integrity, feature completeness, and label alignment.
SELECT count(*) AS feature_rows,
       count_if(max_feature_event_at > feature_as_of) AS future_feature_rows,
       count_if(attendance_rate_28d IS NULL) AS null_attendance_rate,
       count_if(missed_assignments_28d IS NULL) AS null_missed_assignments,
       count_if(days_since_lms_activity IS NULL) AS null_lms_recency,
       count_if(financial_hold_flag IS NULL) AS null_financial_hold,
       count_if(cumulative_gpa IS NULL) AS null_gpa,
       (SELECT count(*) FROM serverless_stable_febar_scottj_catalog.student_retention_silver.training_labels WHERE feature_as_of >= label_observed_at) AS invalid_label_cutoffs,
       (SELECT count(*) FROM serverless_stable_febar_scottj_catalog.student_retention_silver.training_labels l LEFT ANTI JOIN serverless_stable_febar_scottj_catalog.student_retention_silver.model_feature_snapshots f USING (student_id, feature_as_of)) AS labels_without_features
FROM serverless_stable_febar_scottj_catalog.student_retention_silver.model_feature_snapshots;

-- Q3: Verify label balance and chronological split inputs.
SELECT label_term_code, count(*) AS labels, sum(stopout_label) AS stopouts,
       round(avg(stopout_label), 4) AS stopout_rate,
       min(feature_as_of) AS feature_as_of,
       min(label_observed_at) AS label_observed_at
FROM serverless_stable_febar_scottj_catalog.student_retention_silver.training_labels
GROUP BY label_term_code
ORDER BY label_term_code;

-- Q4: Prove protected fields and labels are absent from model features.
SELECT column_name
FROM serverless_stable_febar_scottj_catalog.information_schema.columns
WHERE table_schema = 'student_retention_silver'
  AND table_name = 'model_feature_snapshots'
  AND column_name IN (
    'stopout_label', 'outcome_status', 'synthetic_age_band', 'synthetic_gender',
    'synthetic_first_generation', 'synthetic_race_ethnicity', 'incident_cohort'
  )
ORDER BY column_name;

-- Q5: Representative fully synthetic feature snapshots.
SELECT student_id, feature_as_of, program_code,
       round(attendance_rate_28d, 3) AS attendance_rate_28d,
       missed_assignments_28d, days_since_lms_activity,
       financial_hold_flag, current_balance_band,
       credits_attempted_current, credits_completed_prior,
       attempted_credit_trend, cumulative_gpa,
       withdrawal_count_prior, support_interactions_90d,
       max_feature_event_at
FROM serverless_stable_febar_scottj_catalog.student_retention_silver.model_feature_snapshots
WHERE student_id IN ('STU-000042', 'STU-000124', 'STU-000185')
ORDER BY student_id, feature_as_of;
