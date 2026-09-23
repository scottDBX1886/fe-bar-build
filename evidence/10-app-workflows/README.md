# Task 12 — Executive and Advisor Workflows

Verified 2026-09-23 against Databricks profile `fe-bar`.

## Delivered

- Executive aggregate KPIs, freshness context, responsiveness, follow-up, risk trend, and estimated tuition exposure.
- Advisor caseload with governed OBO queries, risk filtering, server-side `LIMIT`/`OFFSET`, and actionable sorting.
- Governed student detail with protected audit fields excluded and a deterministic briefing fallback.
- Lakebase intervention create/transition repository using the Task 8 idempotency and optimistic-concurrency functions.
- Immutable intervention event timeline and visible loading, empty, error, and stale/partial states.

## Access decision

The platform rejected online-table synchronization for `advisor_caseload` because the source carries row/column security. The implementation therefore uses AppKit `.obo.sql` queries for advisor caseload and student detail. Unity Catalog evaluates those reads as the signed-in user. Executive aggregate queries use the app service principal. Lakebase remains the system of record only for intervention transactions; no route mutates synchronized serving tables.

## Deployment

- App: `dev-student-retention`
- Deployment: `01f1b78320b9177582f21afca22caa2f`
- State: `RUNNING`
- URL: <https://dev-student-retention-7474646471228909.aws.databricksapps.com>
- User scopes: `sql`, `dashboards.genie`

Local browser setup was intentionally omitted because this app is deployed to Databricks Apps. Platform validation, deployment state, logs, unit tests, TypeScript, lint, production build, and strict bundle validation provide the Task 12 evidence.
