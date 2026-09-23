# Governed Student Retention on Databricks

An end-to-end public-sector higher-education demonstration that turns synthetic daily student signals into governed advisor action and aggregate executive insight. The build combines Lakeflow, Unity Catalog, MLflow, evaluated GenAI, Lakebase, a curated Genie Agent, and a Databricks App.

All students, events, outcomes, risk scores, KPIs, and financial values are synthetic. This project does not contain customer data and does not claim production accuracy, causal intervention impact, or realized tuition.

## Business story

Student-success teams often reconcile attendance, LMS, finance, enrollment, and intervention data manually. This solution creates a closed loop:

```text
daily signals → governed features → risk prioritization → advisor action
      ↑                                                   │
      └──────── executive aggregates ← UC CDC ← Lakebase ─┘
```

- Advisors use row-filtered caseloads, factual student context, and grounded briefings.
- Executives use aggregate-only risk, retention, coverage, and estimated tuition metrics.
- Intervention transactions stay in Lakebase-owned tables and return to Unity Catalog through CDC.
- Embedded Genie answers governed questions inside the app and exposes generated SQL.

## Start here

- [Evidence index](evidence/README.md) — acceptance criteria, reproduction commands, resource IDs, and text-readable proof
- [Demo runbook](docs/runbooks/demo.md) — 12–15 minute end-to-end business demonstration
- [Submission deck](docs/presentation/student-retention.pptx) — Databricks-branded PowerPoint
- [Submission deck PDF](docs/presentation/student-retention.pdf) — portable presentation copy
- [Presentation source](docs/presentation/student-retention.md) — outcome-led narrative source
- [Operations runbook](docs/runbooks/operations.md) — monitoring, recovery, sync, and safe reruns
- [Approved design](docs/superpowers/specs/2026-09-21-student-retention-design.md)
- [Implementation plan](docs/superpowers/plans/2026-09-21-student-retention-implementation.md)

## Architecture

| Layer | Role |
|---|---|
| Synthetic sources | Deterministic SIS, attendance, engagement, finance, and outcomes |
| Lakeflow | Triggered Bronze/Silver ingestion, quality, conformance, and Gold publication |
| Unity Catalog | Lineage, grants, row filtering, protected-data isolation, and governed products |
| MLflow | Baseline comparison, training, evaluation, registry alias, and immutable scoring history |
| GenAI | Strictly validated, cited advisor briefings with MLflow evaluation |
| Lakebase | Read-only serving replicas plus separate transactional intervention tables |
| Genie Agent | Governed natural-language analysis over curated Gold sources |
| Databricks App | Executive, advisor, intervention, and embedded Genie workflows |

## Deployed development resources

- Profile: `fe-bar`
- Catalog: `serverless_stable_febar_scottj_catalog`
- Daily job: `666694306037627`
- App: `dev-student-retention`
- Genie Agent: `01f1b75b8eea15a8af20b1f773bb1b38`

The selected profile must always be passed explicitly; commands in this repository do not depend on a default Databricks profile.

## Verification

```bash
pytest -q
cd app && npm test
cd app && npx playwright test tests/smoke.spec.ts
DATABRICKS_AUTH_STORAGE=plaintext databricks bundle validate --strict -t dev --profile fe-bar
python scripts/capture_evidence.py --captured-at 2026-09-23T22:00:00Z
```

Environment-gated tests require their documented deployed services and credentials. See the evidence package for the exact live runs and results used for this build.

## Scope boundaries

The demonstration excludes a separate AI/BI dashboard, real student data, production source integration, real-time continuous processing, automated outreach, adverse-action automation, causal claims, and institution-specific production validation.
