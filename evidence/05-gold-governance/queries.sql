-- Q1: Prove advisor-facing materialized views fail closed without entitlement.
SELECT
  (SELECT count(*) FROM serverless_stable_febar_scottj_catalog.student_retention_gold.advisor_caseload) AS advisor_rows_without_entitlement,
  (SELECT count(*) FROM serverless_stable_febar_scottj_catalog.student_retention_gold.student_detail) AS detail_rows_without_entitlement,
  (SELECT count(*) FROM serverless_stable_febar_scottj_catalog.student_retention_gold.genie_retention) AS genie_rows_without_entitlement,
  (SELECT count(*) FROM serverless_stable_febar_scottj_catalog.student_retention_gold.executive_retention_metrics) AS executive_aggregate_rows;

-- Q2: Idempotently entitle only the current build identity for policy verification.
MERGE INTO serverless_stable_febar_scottj_catalog.student_retention_gold.advisor_entitlements AS target
USING (
  SELECT current_user() AS user_identity, '*' AS advisor_id,
         current_timestamp() AS granted_at, current_user() AS granted_by
) AS source
ON target.user_identity = source.user_identity AND target.advisor_id = source.advisor_id
WHEN NOT MATCHED THEN INSERT *;

-- Q3: Validate final product counts and executive metric semantics.
SELECT
  (SELECT count(*) FROM serverless_stable_febar_scottj_catalog.student_retention_gold.advisor_caseload) AS advisor_caseload_rows,
  (SELECT count(*) FROM serverless_stable_febar_scottj_catalog.student_retention_gold.student_detail) AS student_detail_rows,
  (SELECT count(*) FROM serverless_stable_febar_scottj_catalog.student_retention_gold.executive_retention_metrics) AS executive_metric_rows,
  (SELECT count(*) FROM serverless_stable_febar_scottj_catalog.student_retention_gold.risk_trends) AS risk_trend_rows,
  (SELECT count(*) FROM serverless_stable_febar_scottj_catalog.student_retention_gold.genie_retention) AS genie_rows,
  sum(student_count) AS students,
  sum(at_risk_count) AS at_risk_students,
  round(sum(retention_rate * student_count) / sum(student_count), 6) AS retention_rate,
  round(sum(estimated_next_term_net_tuition_exposure), 2) AS estimated_tuition_exposure,
  max(tuition_exposure_is_estimate) AS tuition_is_estimate,
  round(max(intervention_coverage), 6) AS intervention_coverage
FROM serverless_stable_febar_scottj_catalog.student_retention_gold.executive_retention_metrics;

-- Q4: Protected audit fields must be absent from every routine Gold product.
SELECT table_name, column_name
FROM serverless_stable_febar_scottj_catalog.information_schema.columns
WHERE table_schema = 'student_retention_gold'
  AND table_name IN ('advisor_caseload', 'student_detail', 'executive_retention_metrics', 'risk_trends', 'genie_retention')
  AND column_name IN ('synthetic_age_band', 'synthetic_gender', 'synthetic_first_generation', 'synthetic_race_ethnicity')
ORDER BY table_name, column_name;

-- Q5: Inspect current direct and inherited schema grants.
SHOW GRANTS ON SCHEMA serverless_stable_febar_scottj_catalog.student_retention_gold;

-- Q6: Prove source-to-Gold lineage for the five products.
SELECT source_table_full_name, target_table_full_name, max(event_time) AS latest_event
FROM system.access.table_lineage
WHERE event_date >= current_date() - 2
  AND target_table_full_name IN (
    'serverless_stable_febar_scottj_catalog.student_retention_gold.advisor_caseload',
    'serverless_stable_febar_scottj_catalog.student_retention_gold.student_detail',
    'serverless_stable_febar_scottj_catalog.student_retention_gold.executive_retention_metrics',
    'serverless_stable_febar_scottj_catalog.student_retention_gold.risk_trends',
    'serverless_stable_febar_scottj_catalog.student_retention_gold.genie_retention'
  )
GROUP BY source_table_full_name, target_table_full_name
ORDER BY target_table_full_name, source_table_full_name
LIMIT 100;
