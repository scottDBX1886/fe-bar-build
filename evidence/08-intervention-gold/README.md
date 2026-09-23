# Task 9 intervention CDC-to-Gold evidence

Task 9 reconstructs governed intervention products from the two Lakebase CDC
history tables. Ordering uses Postgres `_pg_lsn` followed by `_sort_by`, exact
deliveries are deduplicated, update preimages remain in the audit view, deletes
are excluded from current state, and immutable events are unique by `event_id`.

The deployed Gold pipeline publishes `intervention_state_history`,
`intervention_current_state`, and `intervention_event_history`. Advisor-facing
products use the current state to expose intervention status, priority, first
intervention time, due follow-up, and completed follow-up signals.

The end-to-end verification created one sanitized intervention for synthetic
student `STU-008502`. After a selective refresh, current state and event history
each increased exactly once, executive intervention coverage increased by one
student, and the model-produced risk score did not change.
