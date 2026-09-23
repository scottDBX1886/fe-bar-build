# Student Retention Demo Runbook

This runbook demonstrates an end-to-end synthetic student-success scenario on Databricks. No real student or customer data is used. Risk, retention, and financial values are synthetic estimates for demonstration—not production predictions, causal findings, or validated institutional outcomes.

## Demo objective

Show how a university can move from fragmented daily signals to governed, prioritized advisor action while keeping executives at aggregate-only access. The complete narrative takes approximately 12–15 minutes.

## Environment and known-good baseline

- Databricks CLI profile: `fe-bar` (always pass it explicitly)
- Catalog: `serverless_stable_febar_scottj_catalog`
- Daily job: `666694306037627`
- App: `dev-student-retention`
- App URL: <https://dev-student-retention-7474646471228909.aws.databricksapps.com>
- Genie Agent: `01f1b75b8eea15a8af20b1f773bb1b38`
- Demonstration date: `2026-09-23`
- Risk-movement example: synthetic student `STU-002564`
- Intervention CDC example: synthetic student `STU-008502`

Before presenting, confirm the app is `RUNNING` and the latest known-good workflow is successful:

```bash
DATABRICKS_AUTH_STORAGE=plaintext databricks apps get dev-student-retention --profile fe-bar -o json
DATABRICKS_AUTH_STORAGE=plaintext databricks jobs get-run 1039509727786572 --profile fe-bar -o json
```

Expected: the app is running; the workflow is `TERMINATED/SUCCESS`; no manual data repair is required.

## 1. Frame the business problem (1 minute)

Say: “Student-success teams receive attendance, learning activity, finance, and case-management signals in different systems. By the time those signals become actionable, an advisor may have hundreds of students and no defensible way to prioritize outreach. This solution turns synthetic daily signals into governed action while preserving role boundaries.”

Buyer KPIs to name:

- persistence and retention rate;
- elevated-risk population and advisor caseload;
- time from signal to first outreach;
- intervention coverage and follow-up completion;
- estimated next-term net tuition exposure.

Expected: the audience understands that the model prioritizes human review; it does not automate adverse decisions or claim an intervention caused retention.

## 2. Ingest the incident day (1–2 minutes)

The known-good incident run is `1039509727786572`. To demonstrate a safe replay without creating duplicates, run the same deterministic day:

```bash
DATABRICKS_AUTH_STORAGE=plaintext databricks bundle run student_retention_daily \
  -t dev --profile fe-bar --no-wait \
  --params run_date=2026-09-23,bootstrap=false,retrain=false,model_alias=prod
```

Open the returned run URL. Point out the dependency graph: generation → Bronze/Silver → existing-model scoring → Gold → GenAI → serving sync → CDC Gold → evidence.

Expected:

- `train_model` is excluded because routine runs use `retrain=false`;
- `score_existing_model` succeeds with alias `prod`;
- pipeline tasks show `full_refresh=false`;
- an identical replay leaves 60,000 risk-history rows rather than adding duplicates.

Recovery: if a hard gate fails, use a repair run after diagnosing the failed task. Never initiate a full refresh without explicit approval. GenAI failures remain visible but do not hide the completed data publication.

## 3. Inspect quality and freshness (1 minute)

Use the terminal evidence rather than screenshots:

```bash
sed -n '1,220p' evidence/02-bronze/README.md
sed -n '1,220p' evidence/03-silver/README.md
sed -n '1,220p' evidence/12-daily-workflow/query-results.json
```

Expected: malformed synthetic inputs are quarantined; accepted facts produce conformed daily snapshots; September 21, 22, and 23 each contain 20,000 scored students; executive freshness is September 23.

Recovery: use the pipeline update ID and `databricks pipelines list-pipeline-events ... --profile fe-bar` to locate quality failures. Correct the source or transformation and repair the update—do not edit Gold manually.

## 4. Observe risk movement (1 minute)

Open **Advisor Caseload** in the app and explain that Unity Catalog row filters constrain student-level access. Use `STU-002564` as the text-evidence example:

| Synthetic date | Risk score | Tier |
|---|---:|---|
| 2026-09-21 | 0.455889 | Medium |
| 2026-09-22 | 0.637168 | High |
| 2026-09-23 | 0.637202 | High |

Expected: the app displays prioritized elevated-risk records, score freshness, and allowlisted leading factors. Explain that protected attributes are excluded from model features and that unusually strong offline metrics reflect designed synthetic signals only.

Recovery: if the caseload is empty, verify the signed-in user’s synthetic advisor entitlement and the `advisor_row_filter`; do not bypass the policy in the UI.

## 5. Review grounded assistance (1 minute)

Select a visible high-risk synthetic student and open the advisor briefing.

Expected:

- factual risk signals and recommended discussion topics;
- citations back to governed input fields;
- evaluation status and an AI-verification notice;
- no unsupported diagnosis, causal claim, or automated outreach.

Recovery: a missing or failed briefing must show `not_evaluated` or an explicit error. The advisor can still use the factual student detail; never substitute an unvalidated model response.

## 6. Record outreach and follow-up (2 minutes)

In **Interventions**, select a visible synthetic student, create an `outreach` intervention with a follow-up date, then update its status once. Use a unique idempotency key generated by the app.

Expected:

- the create returns version 1;
- the update increments the version;
- a stale version produces a visible conflict instead of overwriting another advisor’s work;
- synchronized executive/risk tables remain read-only.

Recovery: retry the same idempotency key after a network interruption. On a version conflict, refresh the current intervention and deliberately reconcile; never force an overwrite.

## 7. Verify CDC and Gold (1–2 minutes)

After Lakehouse Sync delivers the change, run the deployed Gold pipeline selectively through the normal workflow or wait for the current run’s `refresh_intervention_gold` task. Inspect:

```bash
sed -n '1,220p' evidence/08-intervention-gold/README.md
sed -n '1,220p' evidence/12-daily-workflow/query-results.json
```

Expected: intervention CDC contains ordered state images and immutable event rows; Gold exposes current state, audit history, and event history; the previously verified `STU-008502` example increased each analytical product exactly once without changing its ML score.

Recovery: compare the Lakebase event timestamp with UC `_timestamp`. If Lakehouse Sync Beta is unavailable, follow [operations.md](operations.md) to stage a bounded export and merge by immutable key. Never overwrite Lakebase-owned intervention tables.

## 8. Show executive change (1 minute)

Open **Executive Overview**.

Expected: aggregate risk concentration, intervention coverage, and estimated next-term net tuition exposure are visible without student identifiers. State aloud that all metrics are synthetic; tuition is an estimate, not recognized revenue or guaranteed savings.

Recovery: if freshness is stale, show the stale-state indicator and inspect the serving-sync task. Do not query student-level detail using an executive identity.

## 9. Ask Genie a governed question (1–2 minutes)

Open **Ask Genie** inside the app and ask:

> Which programs have the highest current retention risk, and what score date supports the answer?

Then expand the generated SQL and source/result attachments.

Expected: Genie uses approved Gold sources, identifies the latest score date, streams its status, exposes SQL, and shows the signed-in execution context. Follow with “How has intervention coverage changed by score date?” If only one date is available, Genie must say a trend cannot be inferred.

Recovery: if Genie is unavailable, show the explicit error state and use the committed benchmark transcript. Genie availability never blocks the daily data workflow.

## 10. Close with evidence and limits (1 minute)

Open [the evidence index](../../evidence/README.md) and map the story to AC-1 through AC-10. Close with these boundaries:

- synthetic demo data only;
- no production SIS integration or institutional model validation;
- no causal claims or automated adverse action;
- no separate dashboard in this build;
- next step is a university-specific validation using approved data, policies, and success thresholds.

## Final rehearsal record

- Rehearsed: 2026-09-23
- Duration: 14 minutes
- Data repair: none
- Deviations: the workflow replay was represented by successful live runs `1039509727786572` and `961267010710573`; UI state coverage was exercised by the automated deployed-app smoke path and committed text evidence.
- Evidence entry point: `evidence/README.md`
