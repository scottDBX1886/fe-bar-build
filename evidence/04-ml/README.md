# Stop-Out Risk Model Evidence

**Workspace profile:** `fe-bar`

**Model:** `serverless_stable_febar_scottj_catalog.student_retention_ml.student_stopout_risk@prod`

**Gold history:** `serverless_stable_febar_scottj_catalog.student_retention_gold.student_risk_score_history`

All records and evaluation cohorts are synthetic. No real student or customer data is present.

## Build Claim Proven

Task 5 trained logistic-regression and XGBoost classifiers on the earlier term,
validated them on the later term, and compared both with a documented business
rule. Logistic regression was selected because it was the simplest trained
model meeting all operational thresholds. Only the selected family was logged
as the final artifact and registered in Unity Catalog; version 2 has alias
`prod`.

The registered model was loaded through an MLflow Spark UDF and scored the
latest 20,000 synthetic snapshots. Gold stores insert-only history keyed by
`(student_id, feature_as_of, model_version)`, with deterministic risk tiers and
SHAP-style leading factors. Change Data Feed is enabled for later one-way
Lakebase synchronization; Gold remains the system of record.

## Validation Results

| Candidate | PR-AUC | Top-10% recall | Top-10% precision | Calibration error |
|---|---:|---:|---:|---:|
| Business rule | 0.5313 | 0.5378 | 0.5980 | 0.3030 |
| Logistic regression | **0.9669** | 0.8961 | 0.9965 | 0.0216 |
| XGBoost | 0.9589 | **0.8993** | **1.0000** | **0.0071** |

The small top-K gain from XGBoost did not justify its additional complexity;
logistic regression exceeded PR-AUC, recall, and calibration gates by wide
margins. These unusually strong values prove that the deliberately generated
signals and workflow behave as designed. They are not evidence of accuracy on
real students or of causal relationships.

## Fairness Audit

Protected synthetic attributes were joined only after prediction for audit and
were never model features. Across the audited groups, false-positive-rate gaps
were below 0.009 and false-negative-rate gaps were below 0.037. These results
exercise disparity reporting; they do not establish real-world fairness.

## Gold Verification

- 20,000 history rows and 20,000 unique immutable keys
- zero null scores, tiers, or leading-factor arrays
- all three deterministic tiers represented
- all persisted scores are within `[0, 1]`
- one persisted model version (`2`) in this scoring snapshot

## Evidence Map

- `run-output.json`: terminal serverless job and structured model output
- `queries.sql`: exact independent Gold validation queries
- `query-results.json`: statement IDs and sanitized results
- `verification.txt`: TDD, local, deployment, remote, and package checks
