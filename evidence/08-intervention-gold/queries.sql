-- Before/after aggregate contract.
SELECT
  (SELECT count(*) FROM serverless_stable_febar_scottj_catalog.student_retention_gold.intervention_current_state)
    AS current_interventions,
  (SELECT count(*) FROM serverless_stable_febar_scottj_catalog.student_retention_gold.intervention_event_history)
    AS event_count,
  (SELECT sum(student_count) FROM serverless_stable_febar_scottj_catalog.student_retention_gold.executive_retention_metrics)
    AS students,
  (SELECT sum(at_risk_count) FROM serverless_stable_febar_scottj_catalog.student_retention_gold.executive_retention_metrics)
    AS at_risk,
  (SELECT sum(intervention_coverage * at_risk_count)
   FROM serverless_stable_febar_scottj_catalog.student_retention_gold.executive_retention_metrics)
    AS covered;

-- Risk score and intervention status verification.
SELECT student_id, advisor_id, risk_score, risk_tier, intervention_status
FROM serverless_stable_febar_scottj_catalog.student_retention_gold.advisor_caseload
ORDER BY risk_score DESC, student_id
LIMIT 1;

-- CDC audit and immutable event uniqueness.
SELECT _pg_change_type, count(*) AS rows
FROM serverless_stable_febar_scottj_catalog.student_retention_gold.intervention_state_history
GROUP BY _pg_change_type
ORDER BY _pg_change_type;

SELECT count(*) AS event_rows, count(DISTINCT event_id) AS distinct_events
FROM serverless_stable_febar_scottj_catalog.student_retention_gold.intervention_event_history;
