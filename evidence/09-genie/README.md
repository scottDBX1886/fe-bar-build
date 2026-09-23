# Task 10 — Governed Retention Genie Agent

## Deployed agent

- Title: `Student Retention Advisor`
- Space ID: `01f1b75b8eea15a8af20b1f773bb1b38`
- SQL warehouse: `1dd756b73d046482`
- Description: Governed retention-risk and intervention analytics for executives and advisors, using aggregate Gold metrics and advisor-row-filtered student views.

The dev bundle records the space ID for the later embedded-app task.

## Governed source boundary

Only these approved Unity Catalog Gold objects are attached:

- `serverless_stable_febar_scottj_catalog.student_retention_gold.advisor_caseload`
- `serverless_stable_febar_scottj_catalog.student_retention_gold.executive_retention_metrics`
- `serverless_stable_febar_scottj_catalog.student_retention_gold.genie_retention`
- `serverless_stable_febar_scottj_catalog.student_retention_gold.risk_trends`

Protected demographic fields are not exposed. Aggregate executive questions and advisor-scoped student questions use separate sources, and no cross-grain joins are configured.

## Verification result

- 12/12 canonical read-only SQL statements passed Databricks SQL `EXPLAIN`.
- 14/14 live Genie conversations completed successfully.
- Weighted coverage, retention, and trend formulas were generated correctly.
- Tuition exposure was labeled as a synthetic estimate.
- Empty-result questions returned truthful zero-row answers.
- The ambiguous student question requested clarification without SQL.
- The protected-demographics question was refused without SQL.
- Student `STU-008502` resolved to high risk, open intervention status, and risk score `0.9999929444166079`.

## Identity limitation

The live benchmark ran as the workspace operator. Consequently, the operator can observe more than one advisor and more than one row with `caseload_priority = 1`. That does not invalidate the semantic benchmark, but it is not proof of end-user on-behalf-of row filtering. OBO identity and advisor isolation remain an explicit app integration test for Tasks 11–13.

See `benchmark-results.json` for the sanitized case-level results and `verification.txt` for the validation record.
