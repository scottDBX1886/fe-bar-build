# Build Decisions

This document records explicit environment and scope choices for the proactive student-retention demo. It contains resource identifiers, not credentials.

## Workspace

| Decision | Selected value | Rationale |
|---|---|---|
| Databricks CLI profile | `fe-bar` | Explicitly selected for this build; every CLI command must pass `--profile fe-bar`. |
| Workspace | `https://fevm-serverless-stable-febar-scottj.cloud.databricks.com` | Workspace configured by the selected profile. |
| Unity Catalog catalog | `serverless_stable_febar_scottj_catalog` | Dedicated managed workspace catalog explicitly approved for this build. |
| Schema prefix | `student_retention` | Produces distinct Bronze, Silver, Gold, ML, and CDC namespaces. |
| SQL warehouse | `Serverless Starter Warehouse` (`1dd756b73d046482`) | The available SQL warehouse in the selected workspace. |
| Lakebase | Create `student-retention` during Task 8 | No Lakebase projects currently exist; creation is deferred until its schema and ownership are ready. |

## Derived Unity Catalog Namespaces

- `serverless_stable_febar_scottj_catalog.student_retention_bronze`
- `serverless_stable_febar_scottj_catalog.student_retention_silver`
- `serverless_stable_febar_scottj_catalog.student_retention_gold`
- `serverless_stable_febar_scottj_catalog.student_retention_ml`
- `serverless_stable_febar_scottj_catalog.student_retention_cdc`

## Processing and Product Choices

- Triggered incremental processing; one demo run represents one synthetic day.
- Fully synthetic, FERPA-safe student data.
- Logistic-regression baseline plus XGBoost challenger.
- ML risk prediction plus grounded GenAI advisor assistance.
- Embedded Genie Agent inside the Databricks App.
- Native executive analytics in the app; no separate AI/BI dashboard in the initial scope.
- Advisor briefing endpoint: `databricks-glm-5-3`, selected after a live
  compatibility check accepted `temperature=0.1` and returned JSON in an
  optional `json` code fence. The endpoint does not reliably support native
  `response_format`; generation therefore enforces prompt-level JSON plus
  local fence stripping, schema validation, and bounded retries.
- Advisor briefing generation is limited to 50 scored students per daily run,
  uses `max_tokens=1200` to accommodate reasoning tokens, and reads only the
  governed `student_retention_gold.student_detail` surface.
- UC-to-Lakebase serving tables are read-only; interventions use separate Lakebase-owned tables.

## Deferred Resource IDs

The Lakebase project, branch, database, and Genie Agent identifiers will be
recorded here only after their task-specific discovery and explicit approval
gates.

## Governance Identity Gate

Task 6 publishes fail-closed row filtering through
`student_retention_gold.advisor_entitlements`. An identity receives no
student-level rows until it has an explicit advisor assignment; `*` is reserved
for controlled build verification and application administration.

The following production principals are intentionally not guessed:

| Principal | Status | Activation point |
|---|---|---|
| Advisor account group | Awaiting explicit selection | Before advisor user acceptance testing |
| Executive account group | Awaiting explicit selection | Before executive user acceptance testing |
| Fairness-audit account group | Awaiting explicit selection | Before restricted audit access is granted |
| Databricks App service principal | Not created yet | Task 11 app deployment |

`src/governance/policies.sql` contains least-privilege grants and explicit
revocations for these principals. They must be rendered only after the exact
names are approved. For Task 6 verification, the build owner
`scott.johnson@databricks.com` has a synthetic wildcard advisor entitlement;
the zero-row state was captured before that entitlement was inserted.
