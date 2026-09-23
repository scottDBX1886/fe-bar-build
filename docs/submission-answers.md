# Submission Answers

## What is the business challenge you are solving?

Universities often have the signals needed to identify students at risk of stopping out—attendance, LMS engagement, missed assignments, financial holds, enrollment history, and prior outreach—but those signals arrive in separate systems and on different timelines. Advisors must manually reconcile them across large caseloads, which delays outreach and creates inconsistent prioritization. Executives, meanwhile, lack a governed aggregate view of risk concentration, intervention coverage, and estimated tuition exposure. The challenge is not simply predicting risk; it is creating a trusted, closed-loop operating workflow that moves from a changing signal to timely human action while protecting student-level data.

## How does your Databricks solution address this challenge?

The solution processes one deterministic synthetic day through a triggered Lakeflow medallion architecture. Bronze quarantines malformed inputs, Silver conforms daily student features, and a versioned MLflow model writes immutable risk-score history to Unity Catalog. Governed Gold products separate row-filtered advisor detail from aggregate-only executive metrics.

The Databricks App is the single business experience. Advisors see a prioritized caseload, factual student context, and evaluated GenAI briefings grounded in allowlisted fields. They record outreach and follow-up in Lakebase-owned transactional tables with idempotency and optimistic concurrency. Lakehouse Sync CDC returns those operational events to Unity Catalog, where Gold reconstructs current state and audit history. Executives see aggregate intervention coverage without student identifiers. An embedded Genie Agent answers governed questions in the signed-in user’s context and exposes generated SQL and source attachments.

## What AI tools did you use, and what was your workflow? What decisions and trade-offs did you have to make for your build?

I used Codex as the primary build assistant for design, implementation, test-first development, Databricks CLI automation, debugging, and evidence packaging. The solution itself uses a registered MLflow classifier for repeatable risk prioritization, a Databricks foundation-model endpoint for grounded advisor briefings, MLflow evaluation for safety/grounding/citation gates, and a curated Genie Agent for governed natural-language analysis inside the app.

The workflow was evidence-first and incremental: define data contracts and synthetic scenarios, write failing tests, implement each layer, deploy through a Databricks Asset Bundle, verify it live, and commit text-readable evidence before moving to the next task. The final workflow was run for consecutive synthetic days and replayed with identical parameters to prove idempotency.

Key decisions and trade-offs included:

- **Hybrid ML plus GenAI instead of GenAI-only:** ML provides reproducible scores, calibrated thresholds, versioning, and baseline comparison; GenAI summarizes governed facts but does not calculate risk.
- **Logistic regression instead of XGBoost:** both exceeded the synthetic demo thresholds, but logistic regression offered nearly equivalent top-K performance with simpler explanation and governance.
- **Triggered daily processing instead of continuous streaming:** it matches the university operating cadence and produces a clear, repeatable demo boundary.
- **Separate serving and transactional paths:** read-only Unity Catalog products synchronize to Lakebase for serving, while advisor writes use separate Lakebase-owned tables so a refresh can never overwrite intervention state.
- **On-behalf-of-user analytics for advisor and Genie access:** this preserves Unity Catalog row policies and signed-in identity rather than relying on UI hiding.
- **Databricks App as the single surface:** a separate dashboard was intentionally excluded to keep the requested workflow coherent and consumable in one place.
- **Degradable GenAI boundary:** data ingestion, scoring, and Gold publication are hard gates; a briefing failure remains visible but does not block governed data publication.

## What are the business outcomes and impact?

The demonstrated outcome is a governed signal-to-action workflow: advisors receive a prioritized daily queue with cited context, can record and reconcile outreach, and create a durable operational history; executives receive aggregate visibility into risk and intervention coverage without gaining student-level access. This can help an institution reduce time from signal to first outreach, improve advisor capacity allocation, increase intervention and follow-up coverage, and understand where retention risk and estimated next-term tuition exposure are concentrated.

The synthetic demonstration processes 20,000 current students, tracks 60,000 immutable daily risk records across three dates, and shows a concrete medium-to-high risk transition. The selected model achieved 0.9669 PR-AUC on deliberately designed synthetic validation signals, and the full workflow plus an identical incident-day replay completed successfully without duplicate logical records. The solution does **not** claim retained students, causal intervention impact, realized tuition, production accuracy, or institution-specific fairness. Those outcomes require a governed pilot using approved university data and agreed success thresholds.

## Conversation ID from where you built

`01a0c4e1-fc5a-78b1-9aca-338a110a2090`
