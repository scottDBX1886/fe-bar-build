SELECT
  generation_run_id,
  generation_status,
  evaluation_status,
  COUNT(*) AS row_count,
  MIN(CASE WHEN generation_status = 'succeeded' AND size(citations) > 0 THEN 1 ELSE 0 END)
    AS all_successes_have_citations,
  SUM(CASE WHEN size(unsupported_claims) > 0 THEN 1 ELSE 0 END)
    AS rows_with_unsupported_claims,
  regexp_replace(coalesce(error_message, 'none'), 'STU-[A-Z0-9-]+', '[REDACTED_STUDENT_ID]')
    AS sanitized_error
FROM serverless_stable_febar_scottj_catalog.student_retention_gold.advisor_summaries
WHERE generation_run_id = '94547bb4e746dad5bf41a9a906e22ff51c786ed8668e6a6547fc8d540a7b9cfe'
GROUP BY ALL
ORDER BY generation_status;
