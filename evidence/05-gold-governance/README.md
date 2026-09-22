# Governed Gold Data Products Evidence

**Workspace profile:** `fe-bar`

**Gold schema:** `serverless_stable_febar_scottj_catalog.student_retention_gold`

All student records and outcomes are synthetic. No real student or customer data is present.

## Build Claim Proven

Task 6 publishes five focused Gold products from Silver facts and immutable ML
risk history: advisor caseload, student detail, executive retention metrics,
risk trends, and a curated Genie surface. Unity Catalog lineage records all
four inputs for each product.

Advisor, student-detail, and Genie materialized views have an attached Unity
Catalog row filter. The filter is fail-closed: the build identity received zero
student-level rows before an entitlement and the expected rows after an
explicit synthetic wildcard entitlement. Protected audit attributes occur only
in `restricted_protected_audit` and are absent from every routine Gold surface.

## Metric Results

| Measure | Result |
|---|---:|
| Current students | 20,000 |
| Elevated-risk students | 2,664 |
| Retention rate | 88.88% |
| Estimated next-term net tuition exposure | $24,096,114.71 |
| Intervention coverage | 0% |

Intervention coverage is correctly zero because Lakebase intervention
writeback begins in Task 8. Tuition exposure is explicitly labeled as an
estimate and uses only synthetic next-term net tuition for currently medium-
or high-risk students.

## Product Row Counts

- `advisor_caseload`: 2,664 elevated-risk students
- `student_detail`: 20,000 students
- `executive_retention_metrics`: 15 dimensional aggregates
- `risk_trends`: 15 dimensional aggregates
- `genie_retention`: 20,000 governed student facts

## Governance Status

The implementation does not invent account groups or misidentify an unrelated
service principal. Exact advisor, executive, and fairness-audit groups were not
previously selected, and the Databricks App service principal will not exist
until Task 11. Their least-privilege grants and explicit revocations are ready
in `src/governance/policies.sql` but remain unapplied. This gate is recorded in
`docs/build-decisions.md`.

Current schema grants show only pre-existing catalog-level owners/managers.
Consequently, the evidence proves the row-policy behavior and aggregate-versus-
student surface design, but does not claim cross-identity user acceptance tests
for principals that do not yet exist.

## Evidence Map

- `run-output.json`: governance bootstrap, Gold pipeline, and core policy runs
- `queries.sql`: metric, row-policy, protected-field, grant, and lineage queries
- `query-results.json`: sanitized statement results and row-filter metadata
- `verification.txt`: TDD, local, bundle, remote, and package verification
