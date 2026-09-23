-- @param studentId STRING
SELECT *
FROM serverless_stable_febar_scottj_catalog.student_retention_gold.student_detail
WHERE student_id = :studentId
ORDER BY score_date DESC LIMIT 1
