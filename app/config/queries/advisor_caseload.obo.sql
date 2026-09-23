-- @param riskTier STRING
-- @param pageSize INT
-- @param pageOffset INT
SELECT *, count(*) OVER() AS total_count
FROM serverless_stable_febar_scottj_catalog.student_retention_gold.advisor_caseload
WHERE (:riskTier = '' OR risk_tier = :riskTier)
ORDER BY caseload_priority DESC, follow_up_due DESC, risk_score DESC
LIMIT :pageSize OFFSET :pageOffset
