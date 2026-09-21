# Proactive Student Retention Solution Design

**Status:** Approved for implementation planning  
**Date:** 2026-09-21  
**Source brief:** `docs/background/setup`

## 1. Purpose

Build an end-to-end Databricks demonstration that helps a university identify students at risk of stopping out, helps student-success advisors take timely action, and gives executives a governed view of retention risk and intervention coverage.

The solution is decision support, not automated decision-making. Advisors retain responsibility for interventions. All student records are synthetic and must not identify a real student, institution, or customer.

## 2. Business Outcome

The demo addresses a specific higher-education problem: universities often recognize stop-out risk after the most useful intervention window has passed. Data is fragmented across academic, attendance, learning-management, engagement, and financial systems, while advisor activity is often stored separately from analytical data.

The solution will demonstrate how a university can:

- identify currently enrolled students whose observable behavior indicates elevated stop-out risk;
- prioritize a finite advisor caseload using risk and follow-up urgency;
- explain the governed facts contributing to a prediction;
- record and monitor interventions in an operational workflow;
- measure intervention coverage and associated student outcomes; and
- let business users explore curated retention data using natural language.

Primary business KPIs are next-term retention rate, at-risk student count, advisor intervention coverage, time to first intervention, follow-up completion, and estimated tuition revenue exposed to stop-out risk. Any tuition exposure shown in the demo is an estimate based on explicit synthetic assumptions, not a causal or audited financial forecast.

## 3. Users and Decisions

### Student-success advisor

The advisor needs to decide whom to contact, why outreach is warranted, what action to take, and when to follow up. The advisor sees only their assigned student caseload and the governed facts needed to support an intervention.

### Executive sponsor

The dean or vice president of student success needs to understand retention trends, risk concentration, intervention coverage, operational responsiveness, and estimated tuition exposure. Executive views use aggregate information and do not expose student-level records.

## 4. Required Databricks Capabilities

The build will use every required capability from the source brief:

- **Lakeflow Spark Declarative Pipelines:** Incrementally ingest, validate, standardize, and curate synthetic data using a Bronze/Silver/Gold medallion architecture.
- **Unity Catalog:** Govern tables, models, lineage, access, and sensitive fields.
- **Lakebase Postgres Autoscaling:** Serve low-latency student-risk data and persist advisor interventions.
- **ML and GenAI:** Use ML for risk estimation and GenAI for grounded advisor briefings and outreach suggestions.
- **Genie Agent:** Answer natural-language questions over curated Gold tables.
- **Databricks App:** Provide the complete executive, advisor, intervention, and Genie experience in one application.

Deployment resources will be expressed as a Databricks Asset Bundle wherever the current product supports them. Lakebase synchronized-table or Lakehouse Sync resources that are not supported by bundles will be configured with documented CLI steps and explicit profile selection.

## 5. Architecture

The triggered incremental processing cadence represents a new day of synthetic university activity on each demo run.

```text
Synthetic source files
        |
        v
Lakeflow Bronze -> Silver -> Gold -> ML scoring -> governed risk Gold
        |                                      |
        |                                      v
        |                           Lakebase read-only serving tables
        |                                      |
        |                                      v
        |                               Databricks App
        |                                      |
        |                           advisor write-back only
        |                                      v
        |                         Lakebase intervention tables
        |                                      |
        |                          Lakehouse Sync CDC (Beta)
        |                                      v
        +------------------------- UC CDC history
                                               |
                                               v
                                  Lakeflow intervention Gold

Curated Gold tables -> Genie Agent -> embedded Genie experience in the app
```

### Data ownership boundary

Unity Catalog Gold student-risk tables synchronize into Lakebase as read-only serving tables. The application must never insert, update, or delete records in those synchronized tables.

Advisor write-back uses separate Lakebase-owned tables, including current interventions and append-only intervention events. Lakehouse Sync captures those Postgres changes into separate Unity Catalog CDC history tables. Lakeflow derives current intervention state and analytical Gold outputs from that history.

No pipeline writes a derived Unity Catalog table back onto the Lakebase-owned intervention tables. This separation prevents refreshes from overwriting advisor changes or creating a synchronization loop.

Lakehouse Sync is a Beta dependency. The build documentation must identify its prerequisites, limitations, monitoring procedure, and a reproducible fallback export path if it is unavailable in the selected workspace.

## 6. Synthetic Data Model

The generator will create internally consistent, FERPA-safe records with embedded temporal patterns that make the demo useful without pretending to reproduce a real university population.

| Entity | Purpose | Representative fields |
|---|---|---|
| `students` | Governed student profile | synthetic student ID, program, cohort, residency, advisor assignment, protected audit attributes |
| `enrollments` | Academic status and outcomes | term, credits attempted/completed, course activity, grades, withdrawals, academic standing |
| `attendance_events` | Time-varying attendance signals | course, event date, present/absent status |
| `engagement_events` | Learning and support engagement | LMS activity, assignment submission, advising/support interaction |
| `financial_events` | Financial-friction signals | balance band, hold status, aid status, payment activity |
| `student_outcomes` | Supervised-learning label source | next-term enrollment, persistence, stop-out, withdrawal |
| `student_risk_scores` | Governed prediction output | probability, tier, score time, feature snapshot time, model version, contributing factors |
| `advisor_summaries` | Grounded GenAI output | cited facts, briefing, suggested action, prompt version, generation status |
| `interventions` | Current operational workflow state | owner, type, priority, status, next follow-up, version, audit timestamps |
| `intervention_events` | Immutable operational audit trail | intervention ID, event type, actor, timestamp, note, prior/new status, idempotency key |
| `retention_metrics` | Executive and Genie measures | cohort, program, period, retention, risk, coverage, responsiveness, tuition exposure |

Synthetic direct identifiers remain synthetic. Sensitive and protected attributes are isolated, access-controlled, and available for fairness auditing only. They are excluded from ML features and are not displayed in the normal advisor workflow.

## 7. Medallion Data Flow

### Bronze

Bronze streaming tables ingest new source files incrementally and retain source metadata, ingestion timestamps, and rescued data. Expectations quarantine malformed identifiers, invalid timestamps, impossible academic values, and schema violations.

### Silver

Silver tables standardize identifiers and event time, deduplicate events, validate referential integrity, and create point-in-time student feature snapshots. Feature computation must use only facts available at or before each snapshot timestamp.

Lakebase CDC history enters a separate operational Bronze/Silver path. The CDC sequence fields establish deterministic order, deletes are honored, and Silver exposes both current intervention state and full intervention history.

### Gold

Gold publishes focused data products rather than one oversized table:

- advisor caseload and student detail;
- model-ready feature snapshots;
- governed risk scores and explanations;
- intervention current state and event history;
- intervention coverage and responsiveness;
- retention and estimated tuition-exposure metrics; and
- curated Genie-facing analytical views.

Gold retains the cohort, program, advisor, time, risk, and intervention dimensions used by the app and Genie.

## 8. ML Risk Model

### Target and scoring population

The target is: **the student is not enrolled by the census date of the next major academic term**. The scoring population contains students actively enrolled as of the scoring date. Features use only information available on or before that date.

### Training and selection

Logistic regression provides an interpretable baseline. A gradient-boosted tree is the challenger. Training, validation, and test sets are split chronologically. Model selection chooses the simplest candidate that satisfies documented validation thresholds; complexity alone is not a success criterion.

### Evaluation

Evaluation reports:

- precision-recall area under the curve for the imbalanced target;
- recall and precision within the top-K students that the synthetic advisor team has capacity to contact;
- probability calibration;
- ROC-AUC as a secondary comparison metric;
- false-positive and false-negative rates across relevant cohorts; and
- comparison with a simple business-rule baseline.

Protected attributes are used only to audit model behavior. Each prediction stores the model version, scoring timestamp, feature snapshot timestamp, probability, tier, and SHAP-based contributing factors.

Synthetic-data metrics demonstrate engineering behavior and evaluation practice; they must never be presented as evidence of expected performance at a real university.

## 9. GenAI Advisor Assistance

GenAI receives a constrained payload containing the governed risk score, model contributing factors, and an allowlist of factual student signals. It produces a concise advisor briefing and a suggested outreach action.

GenAI must not calculate or modify risk, diagnose a student, make disciplinary recommendations, infer protected traits, or claim that an intervention will cause retention. Output must cite the supplied facts. Unsupported statements are rejected or visibly flagged.

Evaluation checks factual grounding, citation coverage, prohibited claims, output structure, and consistency on a fixed test set. Every stored response includes its prompt version, model identifier, generation timestamp, citations, and evaluation status.

## 10. Genie Agent

The curated Genie Agent queries only approved Gold tables or views. Its instructions define business terms, measures, joins, time semantics, and sample questions for both executive and advisor analytical needs.

The app embeds Genie using the supported AppKit integration. Genie requests run on behalf of the signed-in user when the required `dashboards.genie` user scope is configured, so Unity Catalog permissions continue to govern results.

The UI must show:

- authenticated identity and truthful execution identity;
- streaming and error status;
- generated SQL and returned data sources;
- an AI-generated-result verification notice; and
- explicit empty or ambiguous-result handling.

Genie cannot query unrestricted student data for executive users. Its accessible data must follow the same role and row-level policy as the rest of the app.

## 11. Databricks App Experience

The application is the single business-facing entry point. It uses an analytic workspace with a shared navigation shell.

### Executive Overview

Show aggregate retention, risk, tuition exposure, intervention coverage, and responsiveness. Every KPI includes unit, period, comparison, freshness, and source. Charts use honest and comparable scales, and colors encode only risk, status, or variance.

### Advisor Caseload

Show the signed-in advisor's assigned students using server-side pagination, sorting, and filtering. Default ordering combines actionable risk and follow-up urgency rather than ranking by risk alone.

### Student Detail

Show risk history, leading factors, cited advisor briefing, recent governed facts, and the intervention timeline. Sensitive fairness-audit attributes are hidden from the routine advisor experience.

### Intervention Workflow

Allow an advisor to create outreach, record disposition, schedule follow-up, add notes, and close an intervention with an outcome. Writes use Lakebase transactions, idempotency keys, audit fields, and optimistic concurrency.

### Ask Genie

Embed the curated Genie experience within the application rather than sending users to a separate surface. The page implements all trust and governance requirements in Section 10.

### Application states

Every data surface handles loading, empty, error, partial, and stale states explicitly. Large result sets use server-side operations. Long-running actions show progress and actionable retry guidance.

A separate AI/BI dashboard is outside the initial scope.

## 12. Governance and Security

- Use separate Unity Catalog schemas for Bronze, Silver, Gold, ML/GenAI artifacts, and Lakebase CDC history where appropriate.
- Grant executives aggregate access and advisors only the student-level access required for their assignments.
- Enforce row-level restrictions in governed data rather than relying only on hidden UI elements.
- Restrict protected attributes to the fairness-audit workflow.
- Record lineage from synthetic source through Gold outputs, predictions, and serving tables.
- Grant the Databricks App service principal only the resources and privileges it requires.
- Prefer on-behalf-of-user execution for Genie and disclose the execution identity in the UI.
- Store no secrets, access tokens, real student data, or customer-identifying content in the repository.

## 13. Reliability and Error Handling

- Quarantine recoverable data-quality violations and fail a pipeline update when unsafe data would reach scoring or serving.
- Record input, accepted, rejected, and output counts plus freshness for every triggered run.
- Make triggered processing idempotent so reprocessing the same synthetic day does not duplicate events.
- Monitor UC-to-Lakebase serving synchronization independently from Lakebase-to-UC CDC synchronization.
- Surface stale serving data and delayed intervention CDC in operational status views.
- Use transactions and optimistic concurrency for intervention writes.
- Preserve append-only intervention events even when current state changes.
- Treat GenAI failure as a degraded state: risk scoring and advisor workflow remain available without a generated briefing.
- Treat Genie failure as isolated from the core advisor workflow.

## 14. Testing Strategy

### Data and pipeline tests

Test generator determinism, schema contracts, referential integrity, expectation behavior, deduplication, CDC ordering, idempotency, Gold calculations, and replay of a previously processed synthetic day.

### ML tests

Test point-in-time feature correctness, leakage prevention, deterministic training, metric calculation, threshold selection, fairness-audit output, model serialization, and scoring schema compatibility.

### GenAI and Genie tests

Run a fixed GenAI evaluation set covering grounded answers, missing facts, prohibited recommendations, citations, and malformed output. Validate Genie with representative executive and advisor questions, generated SQL inspection, permission boundaries, and expected empty/ambiguous cases.

### Lakebase and synchronization tests

Test create/update/close intervention flows, duplicate idempotency keys, concurrent edits, audit history, read-only serving protection, CDC arrival, and reconstruction of current state in Unity Catalog.

### Application tests

Test executive aggregation, advisor assignment boundaries, caseload filtering, student detail, intervention write-back, stale/error states, Genie trust indicators, and a deployed end-to-end smoke path.

## 15. Text-Readable Execution Evidence

The repository must contain readable evidence that the solution ran. Screenshots and recordings can supplement but cannot replace text evidence.

Commit evidence for:

- synthetic data generation counts and representative sanitized records;
- Lakeflow update status, expectation results, and table row counts;
- Unity Catalog table/query results and lineage notes;
- ML training parameters, baseline/challenger metrics, selected model, and representative predictions;
- GenAI evaluation results and grounded sample briefings;
- Lakebase write-back transactions and CDC records arriving in Unity Catalog;
- Genie questions, generated SQL, and answer excerpts;
- application validation, automated tests, deployment status, and smoke-test output; and
- the complete demo scenario described below.

Evidence files must exclude secrets and ephemeral tokens and should be reproducible from documented commands.

## 16. Demonstration Scenario

The scripted demonstration follows one coherent student-success story:

1. Trigger ingestion of a new synthetic day containing reduced attendance, missed assignments, and a new financial hold.
2. Show Lakeflow quality checks and updated feature snapshots.
3. Show the model moving a synthetic student into an elevated risk tier with cited contributing factors.
4. Open the advisor caseload and grounded GenAI briefing in the app.
5. Record outreach and a follow-up intervention.
6. Show the Lakebase write, its CDC history arriving in Unity Catalog, and the refreshed intervention Gold table.
7. Show aggregate executive intervention coverage without exposing the student record.
8. Ask Genie a governed question about risk concentration or intervention coverage and inspect the generated SQL.

## 17. Deliverables

- Databricks Asset Bundle configuration and source code;
- synthetic data generator and documented seed/scenario controls;
- Lakeflow pipeline definitions and quality expectations;
- Unity Catalog objects and governance configuration;
- ML training, registration, evaluation, and batch-scoring workflow;
- governed GenAI generation and evaluation workflow;
- Lakebase schema, serving sync, write-back, and CDC configuration;
- curated Genie Agent configuration and validation questions;
- Databricks App with executive, advisor, intervention, and embedded Genie experiences;
- automated tests and text-readable execution evidence;
- demo runbook and operator setup guide; and
- business presentation deck exported to an accepted attachable format.

## 18. Scope Boundaries

The initial build excludes a separate AI/BI dashboard, real student data, production SIS integration, real-time continuous processing, mobile-specific design, automated outreach, prescriptive disciplinary action, causal claims about intervention effectiveness, and production-grade institutional model validation.

## 19. Acceptance Criteria

The design is implemented when:

1. A triggered run incrementally processes a new synthetic day through Bronze, Silver, and Gold with visible quality evidence.
2. A versioned model produces reproducible risk scores and meets documented demo thresholds against both a logistic baseline and business-rule baseline.
3. A grounded GenAI briefing cites governed input facts and passes the fixed evaluation set.
4. The app enforces executive aggregate access and advisor assignment boundaries.
5. An advisor can create and update an intervention without modifying any synchronized serving table.
6. Intervention CDC appears in Unity Catalog and produces correct current-state and analytical Gold outputs.
7. The embedded Genie Agent answers representative governed questions and exposes its generated SQL and execution identity.
8. All major paths handle loading, empty, error, partial, and stale states.
9. The repository contains text-readable execution evidence for every required build domain.
10. The demo runbook completes the scenario in Section 16, and the business deck leads with outcomes and quantified synthetic KPIs.
