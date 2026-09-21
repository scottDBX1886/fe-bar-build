-- Q1: Verify immutable-key uniqueness and prediction completeness.
SELECT count(*) AS row_count,
       count(DISTINCT student_id, feature_as_of, model_version) AS unique_keys,
       count_if(risk_score IS NULL) AS null_scores,
       count_if(leading_factors IS NULL OR size(leading_factors) = 0) AS missing_factors,
       count_if(risk_tier IS NULL) AS null_tiers,
       count(DISTINCT risk_tier) AS tier_count,
       min(risk_score) AS min_score,
       max(risk_score) AS max_score,
       count(DISTINCT model_version) AS model_versions
FROM serverless_stable_febar_scottj_catalog.student_retention_gold.student_risk_score_history;

-- Q2: Verify tier distribution by immutable model version.
SELECT model_version, risk_tier, count(*) AS students,
       round(avg(risk_score), 6) AS avg_score
FROM serverless_stable_febar_scottj_catalog.student_retention_gold.student_risk_score_history
GROUP BY model_version, risk_tier
ORDER BY model_version, risk_tier;

-- Q3: Representative synthetic predictions with student identifiers hashed.
SELECT substring(sha2(student_id, 256), 1, 12) AS synthetic_student_hash,
       feature_as_of, model_version, round(risk_score, 6) AS risk_score,
       risk_tier, leading_factors
FROM serverless_stable_febar_scottj_catalog.student_retention_gold.student_risk_score_history
ORDER BY risk_score DESC
LIMIT 5;

-- Q4: Verify the Delta table supports downstream one-way CDC synchronization.
DESCRIBE DETAIL serverless_stable_febar_scottj_catalog.student_retention_gold.student_risk_score_history;
