# Student Retention Daily Workflow Runbook

## Purpose and normal operation

`student_retention_daily` is the single triggered workflow for advancing the synthetic retention solution by one day. It generates deterministic source events, updates the Bronze/Silver pipeline, optionally retrains the model, scores the current snapshot, publishes Gold, generates and evaluates advisor briefings, checks Lakebase serving sync, refreshes intervention CDC-derived Gold, and emits bounded operational evidence.

Routine runs use `bootstrap=false`, `retrain=false`, and `model_alias=prod`. Retraining is never implicit. Genie availability is not a workflow dependency; Genie reads the published Gold layer independently.

```bash
DATABRICKS_AUTH_STORAGE=plaintext databricks bundle run student_retention_daily \
  -t dev --profile fe-bar \
  --params run_date=2026-09-22,bootstrap=false,retrain=false,model_alias=prod
```

Use a new synthetic date for normal advancement. Reusing a date is an idempotency check, not a way to create another day.

## Monitoring

Get the run ID from `bundle run` output, then inspect the job and every task:

```bash
DATABRICKS_AUTH_STORAGE=plaintext databricks jobs get-run RUN_ID -o json --profile fe-bar
DATABRICKS_AUTH_STORAGE=plaintext databricks jobs get-run-output RUN_ID -o json --profile fe-bar
```

For Lakeflow pipeline tasks, copy the update ID from the task output and poll it:

```bash
DATABRICKS_AUTH_STORAGE=plaintext databricks pipelines get-update PIPELINE_ID UPDATE_ID --profile fe-bar
DATABRICKS_AUTH_STORAGE=plaintext databricks pipelines list-pipeline-events PIPELINE_ID \
  --filter "update_id = 'UPDATE_ID'" --profile fe-bar
```

A job is successful only when its lifecycle is `TERMINATED` and result state is `SUCCESS`. A successful parent run does not replace inspection of the degradable `generate_advisor_briefings` and `evaluate_advisor_briefings` task states.

## Synchronization checks

UC-to-Lakebase serving sync is independent from Lakebase-to-UC CDC. Check both serving tables:

```bash
DATABRICKS_AUTH_STORAGE=plaintext databricks postgres get-synced-table \
  synced_tables/serverless_stable_febar_scottj_catalog.student_retention_gold.serving_executive_retention_metrics \
  --profile fe-bar
DATABRICKS_AUTH_STORAGE=plaintext databricks postgres get-synced-table \
  synced_tables/serverless_stable_febar_scottj_catalog.student_retention_gold.serving_risk_trends \
  --profile fe-bar
```

Healthy serving state is `SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE`. For CDC lag, compare the latest Lakebase intervention event timestamp with `_timestamp` in `student_retention_cdc.lb_intervention_events_history`. Lag is observable and does not justify mutating synchronized serving tables.

## Failure boundaries and recovery

- Generation, Bronze/Silver, scoring, and both Gold updates are hard gates. Fix the failed task and use “Repair run” when possible.
- Advisor briefing generation/evaluation is degradable. Downstream synchronization checks continue with `ALL_DONE`, while the failed task remains visible.
- A requested training failure must not fall back silently to the old model. The `score_after_train` branch remains blocked.
- A routine run uses `score_existing_model` and never creates a model version.
- Never run a pipeline full refresh without explicit approval. Both job pipeline tasks set `full_refresh: false`.
- Safe reruns use the same parameters and date. Source keys, scoring merge keys, summary keys, and CDC identities prevent duplicate logical records.

If Lakehouse Sync Beta is unavailable or delayed, export a bounded CDC snapshot from the Lakebase-owned `student_retention_app` tables into a new staging object, then merge it into the UC CDC history by immutable event/idempotency key. Do not point a serving sync at CDC history, and do not overwrite app-owned Lakebase tables.

## Explicit retraining

Use only after model review or a planned refresh:

```bash
DATABRICKS_AUTH_STORAGE=plaintext databricks bundle run student_retention_daily \
  -t dev --profile fe-bar \
  --params run_date=2026-09-23,bootstrap=false,retrain=true,model_alias=prod
```

Confirm the new registered version passes evaluation, receives the requested alias, and is the version recorded in new risk-history rows.
