# Proactive Student Retention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and prove an end-to-end Databricks student-retention demo that incrementally processes synthetic university activity, predicts stop-out risk, assists advisors, records interventions, and exposes governed analytics through an embedded Genie Agent.

**Architecture:** A Databricks Asset Bundle deploys a triggered Lakeflow medallion pipeline, serverless ML/GenAI jobs, and a Databricks App. Curated Unity Catalog tables synchronize read-only into Lakebase for serving, while separate Lakebase-owned intervention tables synchronize back to Unity Catalog as CDC history; the app is the single user surface.

**Tech Stack:** Python 3.12, PySpark, Lakeflow Spark Declarative Pipelines, Unity Catalog, MLflow 3, scikit-learn, XGBoost, SHAP, Databricks Foundation Model APIs, MLflow GenAI evaluation, Lakebase Postgres 17, AppKit with TypeScript/React, Genie Agent, pytest, Vitest, and Playwright.

**Spec:** `docs/superpowers/specs/2026-09-21-student-retention-design.md`

## Global Constraints

- Use fully synthetic, FERPA-safe data only; never commit real student, customer, institution, token, or secret data.
- Never auto-select a Databricks profile. Before remote work, show all profiles and workspace URLs, obtain the user's choice, and pass that literal profile with every Databricks CLI command.
- The user must explicitly select the Unity Catalog catalog/schema namespace, SQL warehouse, and whether to reuse or create a Lakebase project before any corresponding write.
- Use triggered incremental processing, not continuous processing.
- Use modern `pyspark.pipelines` APIs; do not introduce legacy `dlt` syntax.
- Train ML models on Databricks serverless compute and register them in Unity Catalog; do not train in the local agent process.
- Use an interpretable logistic-regression baseline and an XGBoost challenger; select the simplest model that meets the documented thresholds.
- Protected attributes may be used for fairness auditing only and must not be model features.
- The app must never modify UC-to-Lakebase synchronized serving tables.
- Lakebase interventions and intervention events are separate app-owned tables; Lakehouse Sync CDC is the only path back to Unity Catalog.
- Genie is embedded inside the app, runs on behalf of the signed-in user when supported, and exposes identity, generated SQL, streaming status, sources, and an AI verification notice.
- A separate AI/BI dashboard is out of scope.
- Every deployed capability must produce sanitized, text-readable execution evidence in `evidence/`.
- Each task ends with a short walkthrough: business purpose, Databricks capability, files changed, test evidence, and what the next task consumes.

## Planned File Structure

```text
databricks.yml                         Bundle entry point and environment variables
resources/
  student_pipeline.pipeline.yml       Lakeflow pipeline resource
  student_jobs.job.yml                generation, training, scoring, GenAI, and evidence tasks
  student_app.app.yml                 Databricks App resource
src/
  common/config.py                    validated runtime configuration
  synthetic/generate.py               deterministic synthetic activity generator
  pipelines/bronze.py                 raw incremental ingestion and quarantine
  pipelines/silver.py                 standardized events and point-in-time features
  pipelines/gold.py                   advisor, executive, and Genie data products
  pipelines/intervention_cdc.py       Lakebase CDC current-state reconstruction
  ml/train.py                         baseline/challenger training and model selection
  ml/score.py                         batch scoring, tiers, and explanations
  genai/generate.py                   grounded advisor-summary generation
  genai/evaluate.py                   MLflow GenAI quality evaluation
  governance/bootstrap.sql            schemas, volume, comments, and table properties
  governance/policies.sql             row filters, restricted views, and grants
  lakebase/schema.sql                 app-owned intervention schema
config/
  genie/space.json                    curated Genie Agent definition
  genie/benchmarks.json               representative Genie questions
scripts/
  configure_lakebase_sync.py          idempotent UC/Lakebase sync configuration
  capture_evidence.py                 sanitized evidence capture
app/
  client/src/App.tsx                  navigation and role-aware application shell
  client/src/pages/                   executive, caseload, student, intervention, Genie pages
  client/src/components/              focused reusable data and state components
  server/server.ts                    AppKit plugins and intervention endpoints
  server/interventions.ts             transactional Lakebase repository
  tests/                              Vitest and Playwright tests
tests/
  unit/                               local Python contract and transformation tests
  integration/                        remote result-contract checks
docs/
  build-decisions.md                  chosen workspace resources and assumptions
  data-contracts.md                   schemas, keys, grains, and ownership
  runbooks/demo.md                    scripted business demonstration
  runbooks/operations.md              deployment, monitoring, recovery, and fallback
  presentation/student-retention.md   business presentation source
evidence/README.md                    evidence index and sanitization rules
```

---

### Task 1: Record Environment Decisions and Scaffold the Bundle

**Files:**
- Create: `docs/build-decisions.md`
- Create: `databricks.yml`
- Create: `resources/student_pipeline.pipeline.yml`
- Create: `resources/student_jobs.job.yml`
- Create: `resources/student_app.app.yml`
- Create: `src/common/config.py`
- Create: `tests/unit/test_config.py`
- Create: `.gitignore`

**Interfaces:**
- Consumes: User-selected profile, catalog, namespace prefix, SQL warehouse, and Lakebase reuse/create decision.
- Produces: `RuntimeConfig.from_env()` and bundle variables consumed by every later task.

- [ ] **Step 1: Complete the explicit decision gate**

Run `databricks auth profiles`, present every profile and workspace URL, and ask the user to select one. With the selected profile passed literally, discover warehouses and existing Lakebase projects. Ask the user to select the catalog, namespace prefix, warehouse, and whether to reuse a named Lakebase project or create a new one. Record choices and rationales in `docs/build-decisions.md`; store no credentials.

- [ ] **Step 2: Write failing configuration tests**

Test that `RuntimeConfig.from_env()` requires `RETENTION_CATALOG`, `RETENTION_SCHEMA_PREFIX`, `RETENTION_WAREHOUSE_ID`, and `RETENTION_SEED`; validates UC identifiers with `^[A-Za-z_][A-Za-z0-9_]*$`; and derives the schema names `retention_bronze`, `retention_silver`, `retention_gold`, `retention_ml`, and `retention_cdc` from the selected prefix.

Run: `pytest tests/unit/test_config.py -v`  
Expected: FAIL because `src.common.config` does not exist.

- [ ] **Step 3: Implement the minimal typed runtime configuration**

Create a frozen `RuntimeConfig` dataclass with the four required inputs, identifier validation, explicit schema-name properties, and fully qualified table-name helpers. Do not read a Databricks profile from code; the profile is a CLI concern.

- [ ] **Step 4: Create the bundle skeleton**

Define bundle variables for catalog, schema prefix, warehouse ID, Lakebase resource paths, Genie space ID, and Foundation Model endpoint. Add `dev` and `prod` targets with distinct workspace roots and resource-name prefixes. Reference focused resource YAML files; do not define Lakebase synchronized tables as deprecated bundle resources.

- [ ] **Step 5: Verify locally and against the selected workspace**

Run: `pytest tests/unit/test_config.py -v`  
Expected: PASS.

Run: `databricks bundle validate --strict -t dev --profile "$DATABRICKS_PROFILE"` after setting `DATABRICKS_PROFILE` to the user-selected profile in the current shell.  
Expected: bundle summary with no validation errors and no remote mutation.

- [ ] **Step 6: Walk through and commit**

Explain why configuration is separated from credentials and why resource choices are explicit. Commit only the scaffold and tests with `chore: scaffold retention solution bundle`.

---

### Task 2: Define Data Contracts and Generate the Synthetic University Story

**Files:**
- Create: `docs/data-contracts.md`
- Create: `src/synthetic/generate.py`
- Create: `tests/unit/test_synthetic_contracts.py`
- Modify: `resources/student_jobs.job.yml`

**Interfaces:**
- Consumes: `RuntimeConfig`, selected catalog namespace, seed, and synthetic run date.
- Produces: Incremental Parquet files for students, enrollments, attendance, engagement, financial events, and outcomes under the selected UC Volume.

- [ ] **Step 1: Document grains, keys, and temporal rules**

For every source entity, document its primary key, foreign keys, event timestamp, expected cardinality, nullable fields, valid domains, and owner. Define the label as “not enrolled by the census date of the next major term” and define feature cutoffs that precede the label window.

- [ ] **Step 2: Write failing generator contract tests**

Test deterministic output for an identical seed/run date; unique student IDs; valid foreign keys; no event after its feature cutoff; non-uniform program and risk-signal distributions; and an embedded scenario where attendance, missed assignments, and a financial hold worsen for a coherent student cohort.

Run: `pytest tests/unit/test_synthetic_contracts.py -v`  
Expected: FAIL because the generator is absent.

- [ ] **Step 3: Implement distributed deterministic generation**

Use `spark.range`, Spark expressions, seeded hashes/randomness, and Pandas UDFs only where Faker is necessary. Generate parent students first, write them, then read them for child foreign-key joins. Do not use `collect`, driver loops over records, `cache`, or `persist`.

Generate enough event data for visible temporal patterns: 20,000 students, three academic terms, approximately 300,000 attendance events, 250,000 engagement events, and 40,000 financial events. Make the intervention story cohort small enough to inspect but large enough to affect aggregate KPIs.

- [ ] **Step 4: Add incremental-day behavior and quality defects**

Make `--run-date` write one immutable date partition. Re-running the same seed/date must produce identical records. Inject a small, tagged set of malformed records for quarantine demonstrations without contaminating valid outputs.

- [ ] **Step 5: Run local contract tests and a serverless generation job**

Run: `pytest tests/unit/test_synthetic_contracts.py -v`  
Expected: PASS.

Deploy and run the generator job with the selected profile. Verify row counts, distributions, referential integrity, and the embedded risk scenario using SQL warehouse queries.

- [ ] **Step 6: Capture evidence, walk through, and commit**

Save sanitized row counts, distribution queries, and representative synthetic records to `evidence/01-synthetic-data/`. Explain why synthetic-data realism comes from coherent conditional patterns rather than random names. Commit with `feat: generate synthetic student retention data`.

---

### Task 3: Build Bronze Incremental Ingestion and Quarantine

**Files:**
- Create: `src/pipelines/bronze.py`
- Create: `tests/unit/test_bronze_rules.py`
- Modify: `resources/student_pipeline.pipeline.yml`

**Interfaces:**
- Consumes: Incremental Parquet directories from Task 2.
- Produces: Bronze streaming tables plus quarantine tables with source path, ingestion timestamp, and violation reason.

- [ ] **Step 1: Write failing rule tests**

Express each validation rule as a pure Spark-column function and test valid, quarantined, and pipeline-failing cases. Required rules include nonempty IDs, valid event timestamps, GPA in `[0, 4]`, nonnegative balances, known event types, and valid run dates.

- [ ] **Step 2: Verify failure**

Run: `pytest tests/unit/test_bronze_rules.py -v`  
Expected: FAIL because Bronze rules are undefined.

- [ ] **Step 3: Implement modern Lakeflow streaming tables**

Use `from pyspark import pipelines as dp`, Auto Loader, explicit schemas, `_metadata.file_path`, and expectations. Publish one streaming table and one quarantine table per domain. Warn/drop recoverable malformed rows; fail the update when a missing primary key or unusable timestamp would make downstream state unsafe.

- [ ] **Step 4: Deploy and selectively refresh Bronze**

Validate, deploy, run the pipeline, and poll the update ID to a terminal result. Verify accepted/rejected counts and that replaying an already ingested partition does not duplicate records.

- [ ] **Step 5: Capture evidence, walk through, and commit**

Save the pipeline update result, expectation metrics, Bronze counts, and quarantine samples to `evidence/02-bronze/`. Commit with `feat: ingest student activity into bronze`.

---

### Task 4: Build Silver Standardization and Point-in-Time Features

**Files:**
- Create: `src/pipelines/silver.py`
- Create: `tests/unit/test_silver_features.py`
- Modify: `docs/data-contracts.md`

**Interfaces:**
- Consumes: Bronze domain tables.
- Produces: Deduplicated Silver domain tables, student daily snapshots, training labels, and model feature snapshots.

- [ ] **Step 1: Write failing temporal-feature tests**

Test deterministic deduplication, referential-integrity rejection, rolling attendance rate, late-assignment count, days since LMS activity, balance/hold state, attempted-credit trend, and proof that every feature uses events at or before `feature_as_of`.

- [ ] **Step 2: Verify failure**

Run: `pytest tests/unit/test_silver_features.py -v`  
Expected: FAIL because Silver transformations are absent.

- [ ] **Step 3: Implement Silver tables and feature snapshots**

Use streaming tables for standardized append-only events and materialized views for reusable joins/aggregations. Keep labels separate from features. Preserve protected audit attributes in a restricted table and exclude them from the model-feature column list.

- [ ] **Step 4: Validate temporal integrity remotely**

Run targeted tests and SQL checks for duplicates, orphan keys, future leakage, label balance, and feature null rates. Make the pipeline update fail if any feature timestamp exceeds its snapshot timestamp.

- [ ] **Step 5: Capture evidence, walk through, and commit**

Save schema, temporal-integrity queries, and representative feature snapshots to `evidence/03-silver/`. Commit with `feat: create point-in-time student features`.

---

### Task 5: Train, Evaluate, Register, and Batch-Score Risk Models

**Files:**
- Create: `src/ml/train.py`
- Create: `src/ml/score.py`
- Create: `tests/unit/test_ml_metrics.py`
- Create: `tests/integration/test_scoring_contract.py`
- Modify: `resources/student_jobs.job.yml`

**Interfaces:**
- Consumes: Silver feature snapshots and outcome labels.
- Produces: UC registered model with `@prod` alias, Gold risk-score history, risk tiers, and SHAP contributing factors.

- [ ] **Step 1: Write failing model-policy tests**

Test chronological split boundaries, exclusion of identifiers/labels/protected attributes, PR-AUC calculation, top-K recall/precision, calibration error, cohort false-positive/false-negative rates, and deterministic risk-tier boundaries.

- [ ] **Step 2: Verify failure**

Run: `pytest tests/unit/test_ml_metrics.py -v`  
Expected: FAIL because metric and policy functions are absent.

- [ ] **Step 3: Implement baseline, challenger, and business-rule comparator**

Train logistic regression and XGBoost using the same chronological split and preprocessing contract. Log parameters, signatures, inputs, metrics, plots, feature list, and seed with MLflow. Compare both models with a documented rule baseline. Select the simplest candidate that meets minimum PR-AUC, calibration, and top-K recall thresholds derived from the synthetic validation set.

- [ ] **Step 4: Register one selected artifact correctly**

Set `mlflow.set_registry_uri("databricks-uc")`, log only the selected final artifact as the registered version, and point the UC model alias `@prod` to it. Use aliases, never deprecated stages.

- [ ] **Step 5: Implement incremental batch scoring**

Load `models:/{config.catalog}.{config.ml_schema}.student_stopout_risk@prod` as a Spark UDF in the Databricks job, score the latest feature snapshots, calculate SHAP-based leading factors, and MERGE immutable score history by `(student_id, feature_as_of, model_version)`.

- [ ] **Step 6: Execute and validate on Databricks**

Run training on serverless Databricks compute. Assert that the structured task output includes model version, selected family, PR-AUC, top-K recall, calibration error, fairness-audit summary, and rows scored. Run `tests/integration/test_scoring_contract.py` against the produced Gold schema.

- [ ] **Step 7: Capture evidence, walk through, and commit**

Save model comparisons, selection rationale, registered version, fairness audit, and representative predictions to `evidence/04-ml/`. Explain why synthetic results prove workflow behavior rather than real-world accuracy. Commit with `feat: train and score stopout risk model`.

---

### Task 6: Build Gold Data Products and Governance Policies

**Files:**
- Create: `src/pipelines/gold.py`
- Create: `src/governance/bootstrap.sql`
- Create: `src/governance/policies.sql`
- Create: `tests/unit/test_gold_metrics.py`
- Create: `tests/integration/test_governance.py`

**Interfaces:**
- Consumes: Silver student/features/outcomes and Gold risk-score history.
- Produces: Advisor caseload, student detail, executive metrics, tuition exposure, and curated Genie views with enforced access boundaries.

- [x] **Step 1: Write failing metric tests**

Test retention rate, at-risk count, top-K caseload priority, intervention coverage, time-to-first-intervention, follow-up completion, and tuition exposure. Define tuition exposure as sum of synthetic next-term net tuition for currently elevated-risk students and label it as an estimate.

- [x] **Step 2: Implement focused Gold materialized views**

Create separate views for `advisor_caseload`, `student_detail`, `executive_retention_metrics`, `risk_trends`, and `genie_retention`. Retain program, cohort, advisor, term, score date, risk tier, and intervention status dimensions required by downstream consumers.

- [x] **Step 3: Implement governance bootstrap and policies**

Create schemas, managed Volume, comments, and table properties idempotently. Create restricted audit views for protected attributes. Apply row-level enforcement for advisor assignment and aggregate-only executive access using approved workspace groups recorded in `docs/build-decisions.md`; do not substitute UI-only filtering for data policy.

- [x] **Step 4: Verify grants and policy behavior**

Test allowed and denied queries for app service principal, advisor identity, and executive identity. Query lineage to prove source-to-Gold dependencies. Verify that protected attributes are absent from advisor, executive, and Genie surfaces.

- [x] **Step 5: Capture evidence, walk through, and commit**

Save metric query results, `SHOW GRANTS`, policy tests, and lineage rows to `evidence/05-gold-governance/`. Commit with `feat: publish governed retention data products`.

---

### Task 7: Generate and Evaluate Grounded Advisor Briefings

**Files:**
- Create: `src/genai/generate.py`
- Create: `src/genai/evaluate.py`
- Create: `tests/unit/test_genai_contract.py`
- Create: `tests/fixtures/genai_cases.json`
- Modify: `resources/student_jobs.job.yml`

**Interfaces:**
- Consumes: Governed risk score, allowed contributing factors, and approved factual student signals.
- Produces: Versioned advisor summaries with citations and MLflow GenAI evaluation results.

- [x] **Step 1: Write failing prompt/output contract tests**

Define a structured response with `briefing`, `suggested_action`, `citations`, `unsupported_claims`, `prompt_version`, and `model_id`. Test that the input builder excludes protected fields and raw unrestricted notes, every factual sentence references an allowed fact ID, and prohibited diagnostic/disciplinary/causal language is rejected.

- [x] **Step 2: Verify failure**

Run: `pytest tests/unit/test_genai_contract.py -v`  
Expected: FAIL because the GenAI contract is absent.

- [x] **Step 3: Implement constrained generation**

Call the user-selected Databricks Foundation Model endpoint from a Databricks job. Use JSON-structured output, low temperature, an allowlisted fact payload, retries for transient failures, and validation before persistence. A generation failure must leave risk scoring usable and store a visible failed status.

- [x] **Step 4: Implement MLflow GenAI evaluation**

Use `mlflow.genai.evaluate()` with nested `inputs`, a fixed synthetic dataset, built-in safety/guideline scorers, and deterministic custom checks for citation coverage, unsupported facts, and prohibited claims. Record named baseline results for regression comparison.

- [x] **Step 5: Execute, gate, and capture evidence**

Generate briefings for a bounded scored cohort. Require zero protected-field leakage, zero accepted unsupported claims, complete citation coverage for factual statements, and passing safety/guideline thresholds before publishing summaries.

- [x] **Step 6: Walk through and commit**

Save sanitized inputs, outputs, scorer results, and failures to `evidence/06-genai/`. Commit with `feat: add grounded advisor briefings`.

---

### Task 8: Provision Lakebase and Implement Safe Intervention Write-Back

**Files:**
- Create: `src/lakebase/schema.sql`
- Create: `scripts/configure_lakebase_sync.py`
- Create: `tests/integration/test_lakebase_transactions.py`
- Create: `tests/integration/test_intervention_cdc.py`

**Interfaces:**
- Consumes: User-approved Lakebase project/branch/database and governed Gold serving tables.
- Produces: Read-only synchronized serving tables, app-owned intervention tables, proven transaction semantics, and UC CDC history for the application layer built later.

- [ ] **Step 1: Confirm Lakebase resources before mutation**

List projects, branches, endpoints, and databases using the selected profile. Let the user confirm reuse or creation and the exact branch/database. Use a fresh app-owned schema so the deployed app service principal owns its write tables.

- [ ] **Step 2: Write failing transaction-contract tests**

Test create, update, close, duplicate idempotency key, stale version conflict, event append, rollback, and database rejection of any mutation targeting synchronized serving tables.

- [ ] **Step 3: Implement the Postgres schema**

Create `interventions` with an integer version and audit timestamps, and immutable `intervention_events` with a unique idempotency key. Add foreign-key and check constraints, practical indexes, and `REPLICA IDENTITY FULL` for Lakehouse Sync.

- [ ] **Step 4: Implement and prove transactional SQL operations**

Each state-transition test must update `interventions` with `WHERE version = expected_version` and append the corresponding event in the same transaction. Define the result contract later used by the application repository: conflict when no matching version is updated and the prior successful result for a repeated idempotency key.

- [ ] **Step 5: Configure both one-way syncs without a loop**

Enable CDF on the UC Gold serving source and create triggered UC-to-Lakebase synchronized tables. Configure schema-level Lakehouse Sync from the app-owned Postgres schema into the selected UC CDC schema. Verify the two paths use distinct source and destination objects.

- [ ] **Step 6: Verify round-trip behavior**

Write an intervention through the tested transaction helper, confirm it in Lakebase, wait for its append-only CDC record in Unity Catalog, and prove a serving-table refresh does not alter the app-owned intervention row.

- [ ] **Step 7: Capture evidence, walk through, and commit**

Save sanitized transaction output, sync status, CDC rows, and overwrite-protection result to `evidence/07-lakebase/`. Commit with `feat: add safe advisor intervention writeback`.

---

### Task 9: Reconstruct Intervention State and Metrics in Gold

**Files:**
- Create: `src/pipelines/intervention_cdc.py`
- Create: `tests/unit/test_intervention_cdc.py`
- Modify: `src/pipelines/gold.py`
- Modify: `tests/unit/test_gold_metrics.py`

**Interfaces:**
- Consumes: Lakebase `lb_interventions_history` and `lb_intervention_events_history` CDC tables.
- Produces: Current intervention state, immutable analytical event history, and refreshed executive/advisor metrics.

- [ ] **Step 1: Write failing CDC reconstruction tests**

Cover insert, update preimage/postimage, delete, duplicate delivery, out-of-order input ordered by Postgres LSN, and current-state selection by primary key. Verify deletes disappear from current state but remain in audit history.

- [ ] **Step 2: Implement deterministic CDC transformations**

Use `_pg_lsn` and `_sort_by` for ordering. Publish current-state and event-history views, then join them into intervention coverage, responsiveness, caseload urgency, and follow-up metrics.

- [ ] **Step 3: Refresh and verify Gold**

Run a selective pipeline refresh after a Lakebase write. Verify the advisor caseload and executive aggregate change exactly once and the student risk score remains unchanged by the intervention write.

- [ ] **Step 4: Capture evidence, walk through, and commit**

Save before/after queries and CDC reconstruction checks to `evidence/08-intervention-gold/`. Commit with `feat: integrate intervention history into gold`.

---

### Task 10: Create and Benchmark the Curated Genie Agent

**Files:**
- Create: `config/genie/space.json`
- Create: `config/genie/benchmarks.json`
- Create: `tests/integration/test_genie_benchmarks.py`

**Interfaces:**
- Consumes: Approved aggregate and advisor-scoped Gold views plus the selected SQL warehouse.
- Produces: Curated Genie Agent ID and benchmark transcripts for app embedding.

- [ ] **Step 1: Profile and approve Genie data sources**

Discover every candidate Gold table, verify descriptions and dimensions, and confirm that protected attributes and unrestricted student records are absent. Use aggregate sources for executive questions and governed advisor views for student-level questions.

- [ ] **Step 2: Define the serialized Agent configuration**

Include explicit table identifiers, business definitions, join guidance, time semantics, metric formulas, disallowed interpretations, and sample questions. Questions must include risk concentration, intervention coverage, follow-up backlog, program trends, and estimated tuition exposure with its synthetic-estimate caveat.

- [ ] **Step 3: Write benchmark tests before Agent creation**

Define expected tables, required filters, forbidden columns, and answer assertions for at least 12 questions. Include empty, ambiguous, and permission-denied cases.

- [ ] **Step 4: Create, query, and refine the Agent**

Create the Genie Agent only after the configuration review. Run every benchmark through the Conversation API, poll completion, inspect generated SQL, and revise instructions until all safety and correctness gates pass.

- [ ] **Step 5: Capture evidence, walk through, and commit**

Save questions, generated SQL, sanitized answers, and benchmark summary to `evidence/09-genie/`. Commit with `feat: add governed retention genie agent`.

---

### Task 11: Scaffold the AppKit Application and Data Access

**Files:**
- Create: `app/` using the current AppKit scaffold
- Modify: `resources/student_app.app.yml`
- Modify: `app/server/server.ts`
- Create: `app/client/src/lib/whoami.ts`
- Modify: `app/tests/smoke.spec.ts`

**Interfaces:**
- Consumes: Lakebase resources, SQL warehouse, Genie Agent, and app permissions.
- Produces: Deployable application shell with Analytics, Lakebase, and Genie plugins.

- [ ] **Step 1: Inspect the current AppKit manifest**

Run `databricks apps manifest` with the selected profile. Merge and report all template/plugin scaffolding rules. Derive exact feature and resource keys from the manifest; do not guess them.

- [ ] **Step 2: Scaffold with all required capabilities**

Use AppKit with Analytics for aggregate SQL, Lakebase for operational serving/write-back, and Genie for embedded chat. Supply the exact selected warehouse, branch/database resource paths, and Genie Agent resource. Use `--run none` so generated code can be reviewed before execution.

- [ ] **Step 3: Wire deployment identity and APIs**

Register `analytics()`, `lakebase`, and `genie()` using the installed AppKit signatures. Add `/api/whoami` using `x-forwarded-email` and `x-forwarded-user`. Configure `user_api_scopes: [dashboards.genie]` and truthfully display whether queries run OBO or as the service principal.

- [ ] **Step 4: Write shell smoke tests first**

Update Playwright selectors to require the navigation, authenticated identity badge, Executive Overview heading, Advisor Caseload heading, and Ask Genie entry. Keep smoke-test data below the 1 MB analytics-event limit.

- [ ] **Step 5: Validate and deploy the empty shell**

Run TypeScript checks, shell smoke tests, and `databricks apps validate`. Deploy before local Lakebase development so the service principal creates and owns its app schema. Analytics query type generation happens in Task 12 after its query files are defined.

- [ ] **Step 6: Walk through and commit**

Explain the three data-access paths and why each exists. Commit with `feat: scaffold retention advisor app`.

---

### Task 12: Build Executive and Advisor Application Workflows

**Files:**
- Create: `app/client/src/pages/ExecutiveOverview.tsx`
- Create: `app/client/src/pages/AdvisorCaseload.tsx`
- Create: `app/client/src/pages/StudentDetail.tsx`
- Create: `app/client/src/pages/InterventionWorkflow.tsx`
- Create: `app/client/src/components/DataState.tsx`
- Create: `app/config/queries/*.sql`
- Create: `app/server/interventions.ts`
- Create: `app/tests/interventions.test.ts`
- Create: `app/tests/pages.test.tsx`
- Modify: `app/tests/smoke.spec.ts`

**Interfaces:**
- Consumes: Gold aggregate queries, Lakebase serving tables, intervention APIs, and identity.
- Produces: Role-aware executive/advisor experiences and a complete intervention workflow.

- [ ] **Step 1: Write UI behavior tests before pages**

Test loading, empty, error, partial/stale, executive aggregate-only view, advisor assignment filtering, server pagination, student detail, successful intervention, version conflict, duplicate submission, and GenAI-summary failure fallback.

Test the Lakebase repository against the transaction result contract proven in Task 8 before adding HTTP endpoints.

- [ ] **Step 2: Build Executive Overview**

Compose KPI cards from published AppKit primitives. Each KPI includes unit, period, prior comparison, freshness, and source. Use line/bar charts with semantic tokens and honest scales for retention, risk, coverage, responsiveness, and estimated tuition exposure.

- [ ] **Step 3: Build Advisor Caseload and Student Detail**

Use server-side pagination/filtering and default sort by actionable risk plus follow-up urgency. Show risk history, contributing factors, cited GenAI briefing, governed facts, and intervention timeline without protected audit attributes.

- [ ] **Step 4: Build Intervention Workflow**

Implement `app/server/interventions.ts` so create/update/close endpoints execute the Task 8 transaction contract. Generate idempotency keys client-side per submitted action, send expected version, show 409 conflicts with a reload action, and never issue mutations to serving-table routes.

- [ ] **Step 5: Verify access and states**

Run Vitest and Playwright locally, then deployed smoke tests as representative executive and advisor identities where workspace test identities are available. Verify policy enforcement with direct query attempts in addition to UI assertions.

- [ ] **Step 6: Capture evidence, walk through, and commit**

Save test output and sanitized API/query results to `evidence/10-app-workflows/`. Commit with `feat: build executive and advisor workflows`.

---

### Task 13: Embed the Trusted Genie Experience

**Files:**
- Create: `app/client/src/pages/AskGenie.tsx`
- Create: `app/client/src/components/GeneratedSql.tsx`
- Create: `app/tests/genie.test.tsx`
- Modify: `app/tests/smoke.spec.ts`

**Interfaces:**
- Consumes: AppKit Genie plugin, authenticated identity, and curated Genie Agent.
- Produces: In-app natural-language analysis with complete trust and governance indicators.

- [ ] **Step 1: Write failing Genie trust tests**

Require identity badge, truthful OBO/service-principal disclosure, streaming status, error state, generated SQL card, source/result attachments, per-answer AI verification notice, and explicit empty/ambiguous state.

- [ ] **Step 2: Implement with supported AppKit components**

Use `GenieChat` for the standard experience or `useGenieChat` only if the trust requirements need a custom result layout. Give the container an explicit height and remove any custom/manual SSE proxy.

- [ ] **Step 3: Verify governance end to end**

Run benchmark prompts from the embedded page. Confirm generated SQL matches the curated sources and the signed-in user's access. Confirm an executive cannot retrieve student-level rows and an advisor cannot retrieve another advisor's caseload.

- [ ] **Step 4: Capture evidence, walk through, and commit**

Save sanitized embedded-chat transcripts, generated SQL, and test output to `evidence/11-app-genie/`. Commit with `feat: embed trusted genie experience`.

---

### Task 14: Orchestrate the Triggered Daily Workflow

**Files:**
- Modify: `resources/student_jobs.job.yml`
- Create: `tests/integration/test_daily_workflow.py`
- Create: `docs/runbooks/operations.md`

**Interfaces:**
- Consumes: All generation, pipeline, ML, GenAI, sync, and evidence tasks.
- Produces: One observable triggered workflow representing a new synthetic day.

- [ ] **Step 1: Write workflow contract tests**

Assert task dependencies: generate → Lakeflow update → train-if-requested → score → GenAI summaries → serving-sync check → CDC/Gold refresh → evidence capture. A routine daily run skips retraining unless the explicit retrain parameter is true.

- [ ] **Step 2: Configure task parameters and failure boundaries**

Pass run date, seed, catalog, schemas, and model alias explicitly. Make generation, ingestion, scoring, and Gold publication hard gates. Treat GenAI briefing generation as degradable while retaining visible failure status. Do not let Genie availability block pipeline completion.

- [ ] **Step 3: Implement operational monitoring and recovery**

Document update-ID polling, job result-state checks, UC-to-Lakebase sync status, Lakehouse Sync lag, safe rerun behavior, and the Lakehouse Sync Beta fallback export. Never prescribe a full refresh without explicit approval.

- [ ] **Step 4: Run two consecutive synthetic days**

Run day one, then the incident day. Verify incremental counts, one student's risk transition, an intervention write, CDC arrival, and updated aggregate coverage. Re-run the incident day to prove idempotency.

- [ ] **Step 5: Capture evidence, walk through, and commit**

Save structured task outputs and before/after SQL to `evidence/12-daily-workflow/`. Commit with `feat: orchestrate triggered retention workflow`.

---

### Task 15: Assemble the Demo, Evidence Index, and Business Presentation

**Files:**
- Create: `evidence/README.md`
- Create: `scripts/capture_evidence.py`
- Create: `docs/runbooks/demo.md`
- Create: `docs/presentation/student-retention.md`
- Create: `tests/unit/test_evidence_sanitizer.py`
- Create: `README.md`

**Interfaces:**
- Consumes: Successful deployed build and evidence from Tasks 2–14.
- Produces: Evaluator-readable repository, repeatable demo, and business-facing presentation source.

- [ ] **Step 1: Write failing sanitizer tests**

Test redaction of access tokens, OAuth credentials, workspace secrets, email-like test identities where required, and connection strings while preserving query results, model metrics, and resource IDs needed as evidence.

- [ ] **Step 2: Implement evidence capture and index**

Create a deterministic evidence index mapping every acceptance criterion to a text file, reproduction command, capture timestamp, selected workspace resource, and expected interpretation. Fail capture when secret-pattern scanning detects unsafe content.

- [ ] **Step 3: Write the demo runbook**

Script the exact narrative: ingest the incident day, inspect quality, observe risk movement, review grounded assistance, record outreach, verify CDC in Gold, view aggregate executive change, and ask Genie a governed question. Include recovery guidance and expected outputs at each checkpoint.

- [ ] **Step 4: Write the business presentation**

Lead with the retention problem and buyer KPIs, then current-state friction, solution workflow, business value, governed architecture, live demo story, evidence, limitations, and next steps. Clearly mark all metrics and financial values as synthetic.

- [ ] **Step 5: Run the final verification suite**

Run all Python, TypeScript, Vitest, Playwright, bundle validation, deployed workflow, policy tests, ML/GenAI evaluation, sync checks, and evidence secret scanning. Verify that the repository contains text—not screenshots alone—for every build domain.

- [ ] **Step 6: Perform the final demo and commit**

Execute the demo runbook without manual data repair. Record duration, deviations, and final evidence links. Commit with `docs: add retention demo evidence and presentation`.

## Completion Review

Before declaring the build complete:

1. Map every requirement in the approved spec to a passing task and evidence file.
2. Search the repository for placeholders, secrets, real identities, legacy `dlt` syntax, writes to synchronized serving tables, and unsupported causal claims.
3. Confirm every Databricks CLI transcript uses the user-selected profile explicitly.
4. Confirm model feature names and scoring schemas match the registered model signature.
5. Confirm Genie and app role tests prove data-policy enforcement rather than merely hiding UI elements.
6. Confirm the original setup brief, approved design, implementation plan, operator runbook, demo runbook, presentation, and evidence index tell one consistent business story.
