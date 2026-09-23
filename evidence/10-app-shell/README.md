# Task 11 — Databricks App Shell

## Deployment

- App resource: `dev-student-retention`
- URL: `https://dev-student-retention-7474646471228909.aws.databricksapps.com`
- Runtime: Databricks Apps / AppKit `0.57.0`
- Status: `RUNNING`
- Compute: `ACTIVE`

## Data-access paths

1. **Analytics** uses SQL warehouse `1dd756b73d046482` for governed aggregate queries. Task 12 adds the typed query files.
2. **Lakebase** uses `projects/student-retention/branches/production/databases/databricks-postgres` for operational serving and intervention write-back. Runtime logs confirm the `student_retention_app` schema is available.
3. **Genie** uses curated space `01f1b75b8eea15a8af20b1f773bb1b38`. The app requests `dashboards.genie`, so Genie runs on behalf of the signed-in user.

The shell exposes Executive Overview, Advisor Caseload, and Ask Genie destinations plus a `/api/whoami` identity endpoint backed by Databricks forwarded identity headers. Task 12 fills the executive/advisor workflows; Task 13 embeds the trusted Genie chat.

## Validation

- Official `databricks apps validate`: passed.
- TypeScript type checks: passed.
- ESLint and AppKit AST lint: passed.
- Production server and client build: passed.
- Strict root bundle validation: passed.
- Deployment package installation and build: passed.
- App startup and Lakebase schema bootstrap: passed.

The checked-in `tests/smoke.spec.ts` defines the deployed navigation contract. Browser tooling is intentionally not shipped with the Databricks App runtime.
