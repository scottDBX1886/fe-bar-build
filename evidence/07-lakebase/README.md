# Task 8 Lakebase intervention writeback evidence

The dedicated Postgres 17 Autoscaling project, operational intervention schema,
transaction functions, and Lakebase-to-Unity-Catalog CDC path are deployed and
verified in the `fe-bar` workspace.

Live tests prove create, update, close, optimistic version conflicts, duplicate
idempotency replay, transactional rollback, and immutable event history. The
sanitized round-trip intervention arrived in both Unity Catalog CDC history
tables.

The reverse serving path is also verified. Two snapshot-mode synchronized
tables were created directly in the existing Unity Catalog Gold schema and are
available in the `student_retention_gold` Postgres schema. No separate catalog
was required. Both sources are materialized views, so snapshot scheduling is
used because materialized views do not support Change Data Feed.

The Lakebase reader role has SELECT and lacks INSERT, UPDATE, and DELETE on the
serving tables. After both serving snapshots completed, the app-owned sanitized
round-trip intervention remained `open` at version 1. The serving and writeback
schemas are distinct, so a serving refresh cannot target intervention state.
