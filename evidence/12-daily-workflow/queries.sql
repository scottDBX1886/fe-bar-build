-- Daily snapshot completeness and idempotency baseline.
SELECT
  CAST(feature_as_of AS DATE) AS score_date,
  count(*) AS row_count,
  count(DISTINCT student_id) AS student_count
FROM serverless_stable_febar_scottj_catalog.student_retention_gold.student_risk_score_history
GROUP BY CAST(feature_as_of AS DATE)
ORDER BY score_date;

-- One deterministic example of a risk-tier transition across the three demo days.
WITH scores AS (
  SELECT
    student_id,
    CAST(feature_as_of AS DATE) AS score_date,
    risk_score,
    risk_tier,
    lag(risk_tier) OVER (PARTITION BY student_id ORDER BY feature_as_of) AS prior_tier
  FROM serverless_stable_febar_scottj_catalog.student_retention_gold.student_risk_score_history
  WHERE CAST(feature_as_of AS DATE) BETWEEN DATE '2026-09-21' AND DATE '2026-09-23'
), chosen AS (
  SELECT student_id
  FROM scores
  WHERE prior_tier IS NOT NULL AND risk_tier <> prior_tier
  ORDER BY student_id
  LIMIT 1
)
SELECT scores.student_id, score_date, round(risk_score, 6) AS risk_score, risk_tier
FROM scores
JOIN chosen USING (student_id)
ORDER BY score_date;

-- Intervention CDC arrival.
SELECT count(*) AS row_count, max(_timestamp) AS latest_cdc_at
FROM serverless_stable_febar_scottj_catalog.student_retention_cdc.lb_interventions_history;

SELECT count(*) AS row_count, max(_timestamp) AS latest_cdc_at
FROM serverless_stable_febar_scottj_catalog.student_retention_cdc.lb_intervention_events_history;

-- Aggregate coverage and freshness.
SELECT
  count(*) AS row_count,
  max(score_date) AS latest_score_date,
  max(data_freshness_at) AS latest_freshness_at
FROM serverless_stable_febar_scottj_catalog.student_retention_gold.executive_retention_metrics;
