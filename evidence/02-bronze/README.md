# Bronze Ingestion and Quarantine Evidence

**Workspace profile:** `fe-bar`

**Pipeline:** `b22af6b5-ff4b-47b3-a2b4-0d3945986ce7`

**Target:** `serverless_stable_febar_scottj_catalog.student_retention_bronze`

All records are synthetic. No real student or customer data is present.

## Build Claim Proven

This package proves implementation-plan Task 3: six Parquet domains are
incrementally ingested through Auto Loader into governed Bronze streaming
tables; unsafe primary keys and event timestamps are enforced as pipeline-
failing expectations; recoverable defects are preserved in domain quarantine
tables with a reason, source path, and ingestion timestamp; and replaying the
same source files does not duplicate data.

## Pipeline Updates

| Purpose | Update ID | Result |
|---|---|---|
| Initial incremental ingestion | `9a7a50ca-2f93-417d-a229-918e7735cc53` | `COMPLETED` |
| No-new-files replay | `b00a6a7d-e565-49f3-80a6-9b49602608f0` | `COMPLETED` |

Neither update was a full refresh. The replay retained exactly the same table
counts, demonstrating Auto Loader checkpoint idempotency for already-seen files.

## Accepted and Quarantined Rows

| Dataset | Accepted | Quarantined |
|---|---:|---:|
| students | 20,000 | 0 |
| enrollments | 60,000 | 0 |
| attendance_events | 299,990 | 10 |
| engagement_events | 249,990 | 10 |
| financial_events | 39,995 | 5 |
| student_outcomes | 40,000 | 0 |

All 25 injected defects were retained in quarantine with reason
`MISSING_STUDENT_ID`. Every quarantined row had a populated `_source_path` and
`_ingested_at`; no malformed record was silently discarded.

## Safety Expectations

Each accepted table enforced a modern Lakeflow `expect_or_fail` rule requiring
a nonempty domain primary key and usable business event timestamp. Event-log
metrics report 609,975 passed records and zero failed records across the six
accepted tables. The quarantine tables carry the recoverable foreign-key
defects separately, so downstream state stays usable without losing evidence.

## Evidence Map

- `run-output.json` records both terminal pipeline updates.
- `queries.sql` contains the exact validation queries.
- `query-results.json` retains raw rows and statement IDs.
- `verification.txt` records local, bundle, remote, and package checks.
