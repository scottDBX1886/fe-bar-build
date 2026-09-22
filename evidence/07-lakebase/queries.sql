SELECT 'interventions' AS source_table, COUNT(*) AS cdc_rows, MAX(_timestamp) AS latest_sync
FROM serverless_stable_febar_scottj_catalog.student_retention_cdc.lb_interventions_history
UNION ALL
SELECT 'intervention_events', COUNT(*), MAX(_timestamp)
FROM serverless_stable_febar_scottj_catalog.student_retention_cdc.lb_intervention_events_history;

SELECT
  i.student_id,
  i.status,
  i.version,
  i._pg_change_type,
  e.event_type,
  e.idempotency_key,
  e.result_version
FROM serverless_stable_febar_scottj_catalog.student_retention_cdc.lb_interventions_history i
JOIN serverless_stable_febar_scottj_catalog.student_retention_cdc.lb_intervention_events_history e
  ON i.intervention_id = e.intervention_id
WHERE i.student_id = 'STU-TASK8-ROUNDTRIP'
ORDER BY e._sort_by;
