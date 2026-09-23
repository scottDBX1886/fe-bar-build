# Task 14 — Triggered Daily Workflow

Verified 2026-09-23 against Databricks profile `fe-bar` and job `666694306037627`.

## Delivered

- One parameterized, triggered workflow spanning deterministic generation, Bronze/Silver, conditional training, scoring, Gold, GenAI, serving sync, intervention CDC refresh, and terminal evidence.
- Routine runs explicitly skip retraining and score with the requested registered-model alias.
- Generation, ingestion, scoring, and Gold publication are hard gates. GenAI remains visible but degradable, and Genie availability is outside the pipeline dependency graph.
- Operational checks cover UC-to-Lakebase synchronized-table state, CDC-derived Gold refresh, aggregate freshness, and bounded record counts.
- The runbook documents monitoring, recovery, safe reruns, the Lakehouse Sync fallback, and the prohibition on unapproved full refreshes.

## Live run evidence

- Day one: run `718159461653978`, `2026-09-22`, successful.
- Snapshot-date repair: run `1026689789179684`, successful.
- Incident day: run `1039509727786572`, `2026-09-23`, successful.
- Identical incident-day rerun: run `961267010710573`, successful.

The incident-day run selected `score_existing_model`; the training branch was excluded as intended. All mandatory tasks and both GenAI tasks succeeded. Serving synchronization and the final CDC/Gold refresh also succeeded.

## Incremental behavior

Risk history contains exactly 20,000 distinct students for each of September 21, 22, and 23 (60,000 immutable rows total). Student `STU-002564` provides a concrete transition:

- September 21: medium, `0.455889`
- September 22: high, `0.637168`
- September 23: high, `0.637202`

Intervention CDC contains 38 state-change images and 32 immutable event rows. Executive Gold contains 16 current aggregate rows with a latest score date of September 23.

## Idempotency

Before and after rerunning September 23 with identical parameters, all logical counts were unchanged:

| Product | Before | After |
|---|---:|---:|
| Risk history | 60,000 | 60,000 |
| Advisor summaries | 55 | 55 |
| Executive metrics | 16 | 16 |
| Intervention CDC | 38 | 38 |
| Intervention-event CDC | 32 | 32 |

The executive freshness timestamp also remained `2026-09-23T21:14:17.153603`, confirming the rerun did not manufacture a new logical publication.
