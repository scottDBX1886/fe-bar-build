SELECT score_date, risk_tier,
       sum(student_count) AS student_count,
       sum(student_count * average_risk_score) / nullif(sum(student_count), 0) AS average_risk_score
FROM serverless_stable_febar_scottj_catalog.student_retention_gold.risk_trends
GROUP BY score_date, risk_tier ORDER BY score_date, risk_tier
