# Silver Point-in-Time Feature Evidence

**Workspace profile:** `fe-bar`

**Pipeline:** `b22af6b5-ff4b-47b3-a2b4-0d3945986ce7`

**Silver schema:** `serverless_stable_febar_scottj_catalog.student_retention_silver`

All records are synthetic. No real student or customer data is present.

## Build Claim Proven

This package proves implementation-plan Task 4: the Bronze domains are
standardized and deterministically keyed in Silver, unknown student references
are isolated, labels and protected audit fields are separated from model
features, and point-in-time feature snapshots use only facts available at or
before their declared cutoff.

## Pipeline Update

Update `7ca01d94-25e1-40f9-8d47-922ff3d36200` completed successfully without a
full refresh. The update created six Silver domain streaming tables, restricted
audit data, referential quarantine, training labels, 20,000 operational daily
snapshots, and 40,000 label-aligned model snapshots.

## Integrity Summary

- All six Silver domain primary keys have zero duplicates.
- Both snapshot tables have zero duplicate `(student_id, feature_as_of)` keys.
- `referential_quarantine` contains zero unexpected orphans.
- All 40,000 labels have a matching model feature snapshot.
- Zero feature rows have `max_feature_event_at > feature_as_of`.
- Zero label rows have a cutoff at or after label observation.
- Selected operational feature columns contain zero nulls.
- The model feature table contains no labels, outcome state, protected audit
  attributes, or synthetic incident-cohort marker.

## Label Timeline

| Label term | Rows | Stop-outs | Rate | Feature cutoff | Label observed |
|---|---:|---:|---:|---|---|
| 2026SP | 20,000 | 2,100 | 10.50% | 2026-01-25 23:59:59 | 2026-01-26 00:00:00 |
| 2026FA | 20,000 | 2,224 | 11.12% | 2026-09-06 23:59:59 | 2026-09-07 00:00:00 |

This remains an intentionally imbalanced synthetic classification problem. The
rates prove workflow behavior and do not predict real-university performance.

## Feature Semantics

Attendance and missed assignments use preceding 28-day windows; support uses a
90-day window; LMS recency uses the latest known login; financial and academic
state use the latest eligible record. The `999` LMS-recency sentinel explicitly
means no known prior login. Full definitions are in `docs/data-contracts.md`.

## Evidence Map

- `run-output.json` records the terminal pipeline update.
- `queries.sql` contains the exact integrity and sample queries.
- `query-results.json` retains raw results and statement IDs.
- `verification.txt` records local, bundle, remote, and package checks.
