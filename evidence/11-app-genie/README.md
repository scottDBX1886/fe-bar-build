# Task 13 — Trusted Embedded Genie

Verified 2026-09-23 against Databricks profile `fe-bar` and curated Genie Agent `01f1b75b8eea15a8af20b1f773bb1b38`.

## Delivered

- Embedded Genie conversation inside the Databricks App; no external Genie navigation is required.
- On-behalf-of-user execution with the `dashboards.genie` scope and signed-in identity disclosure.
- Native AppKit streaming, conversation history, result/source attachments, and retryable error state.
- Inspectable generated-SQL card for the latest answer.
- Persistent AI-verification notice on every assistant answer.
- Explicit initial empty state and ambiguous-answer guidance.

## Benchmark summary

Two representative prompts completed successfully. Their generated SQL used only approved Unity Catalog Gold sources:

1. “Which programs have the highest current retention risk?”
   - Source: `student_retention_gold.risk_trends`
   - Result: five programs ranked using the latest score date.
2. “How has intervention coverage changed by score date?”
   - Source: `student_retention_gold.executive_retention_metrics`
   - Result: one available score date; Genie explicitly stated that no change over time could be inferred.

The second result demonstrates the required ambiguity behavior: the experience does not claim a trend when the governed data contains only one date.

## Governance

Genie runs with each signed-in user’s Databricks permissions. The curated Agent contains only approved Gold sources, and the application exposes generated SQL and source/result attachments for verification. Existing policy evidence covers executive denial of student-level sources and advisor row filtering. Dedicated alternate workspace identities were not available for an additional UI impersonation test.

## Deployment

- App: `dev-student-retention`
- Deployment: `01f1b784971b12948841023a12ec9b65`
- State: `RUNNING`
- URL: <https://dev-student-retention-7474646471228909.aws.databricksapps.com>
