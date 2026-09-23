# Student Retention Evidence Index

All records and business values in this demonstration are synthetic. Evidence is text-readable, sanitized, and reproducible against the explicitly selected `fe-bar` profile.

| Criterion | Requirement | Evidence | Reproduction command | Captured at | Resource | Expected interpretation |
|---|---|---|---|---|---|---|
| AC-1 | A triggered run incrementally publishes Bronze, Silver, and Gold with quality evidence. | 12-daily-workflow/README.md | databricks jobs get-run 1039509727786572 --profile fe-bar -o json | 2026-09-23T22:00:00Z | Lakeflow Job 666694306037627 | The incident-day run and identical rerun succeed without duplicate logical records. |
| AC-2 | A versioned model beats documented baselines and produces reproducible scores. | 04-ml/README.md | pytest -q tests/unit/test_ml_model.py tests/integration/test_scoring_contract.py | 2026-09-23T22:00:00Z | UC model student_retention_ml.student_stopout_risk | Evaluation, registry alias, immutable scoring, and explanations meet the demo contract. |
| AC-3 | Grounded advisor briefings cite governed facts and pass the fixed evaluation set. | 06-genai/README.md | pytest -q tests/unit/test_genai_contract.py | 2026-09-23T22:00:00Z | MLflow advisor briefing evaluation | Briefings are factual, bounded, traceable, and evaluated. |
| AC-4 | The app enforces executive aggregate and advisor assignment boundaries. | 10-app-workflows/verification.txt | cd app && npx playwright test tests/smoke.spec.ts | 2026-09-23T22:00:00Z | Databricks App dev-student-retention | Authorization is enforced by governed data policies and backend identity, not UI hiding. |
| AC-5 | An advisor can write interventions without modifying synchronized serving tables. | 07-lakebase/README.md | RUN_LAKEBASE_INTEGRATION=1 pytest -q tests/integration/test_lakebase_transactions.py | 2026-09-23T22:00:00Z | Lakebase student_retention_app | Transactional writes stay in app-owned tables; synchronized serving tables remain read-only. |
| AC-6 | Intervention CDC reaches Unity Catalog and produces current-state and history Gold outputs. | 08-intervention-gold/README.md | pytest -q tests/unit/test_intervention_cdc.py tests/integration/test_intervention_cdc.py | 2026-09-23T22:00:00Z | UC student_retention_cdc and student_retention_gold | Ordered, deduplicated CDC supports correct analytical state and event history. |
| AC-7 | Embedded Genie answers governed questions and exposes SQL and execution identity. | 11-app-genie/README.md | cd app && npx playwright test tests/smoke.spec.ts | 2026-09-23T22:00:00Z | Genie Agent 01f1b75b8eea15a8af20b1f773bb1b38 | Answers use approved Gold sources with visible trust indicators. |
| AC-8 | Major app paths represent loading, empty, error, partial, and stale states. | 10-app-shell/verification.txt | cd app && npx playwright test tests/smoke.spec.ts | 2026-09-23T22:00:00Z | Databricks App dev-student-retention | The app communicates operational state instead of silently failing. |
| AC-9 | Every required build domain has text-readable execution evidence. | README.md | python scripts/capture_evidence.py --captured-at 2026-09-23T22:00:00Z | 2026-09-23T22:00:00Z | Repository evidence/ tree | The secret-safe index links every acceptance criterion to reproducible text evidence. |
| AC-10 | The demo tells one complete scenario and the deck leads with synthetic business outcomes. | ../docs/runbooks/demo.md; ../docs/presentation/student-retention.md | pytest -q && cd app && npx playwright test tests/smoke.spec.ts | 2026-09-23T22:00:00Z | Deployed retention solution | The evaluator can repeat the business workflow and distinguish synthetic estimates from claims. |

## Domain index

1. Synthetic generation — `01-synthetic-data/`
2. Bronze ingestion and quality — `02-bronze/`
3. Silver conformance and features — `03-silver/`
4. ML training, evaluation, registry, and scoring — `04-ml/`
5. Gold products and governance — `05-gold-governance/`
6. Grounded GenAI and evaluation — `06-genai/`
7. Lakebase serving and transactional write-back — `07-lakebase/`
8. Intervention CDC and analytical Gold — `08-intervention-gold/`
9. Curated Genie Agent — `09-genie/`
10. Databricks App shell and workflows — `10-app-shell/`, `10-app-workflows/`
11. Trusted embedded Genie — `11-app-genie/`
12. Triggered daily workflow — `12-daily-workflow/`
