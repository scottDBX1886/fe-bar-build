# Student Retention Data Contracts

## Contract Principles

- Every record is synthetic and reproducible from a documented seed.
- Master student records are generated before child records; child foreign keys are created by joining to the persisted master table.
- Every event has a business event timestamp and a generator `run_date` partition.
- A feature snapshot may use only events whose business timestamp is at or before `feature_as_of`.
- Protected audit attributes are stored separately and are never model features.
- Re-running the same seed and run date replaces the same immutable source partition with identical records.

## Synthetic Story

The baseline population contains realistic variation in program, cohort, residency, academic preparation, engagement, and financial circumstances. A deterministic incident cohort of roughly 1.5% of students experiences a coherent deterioration during the demonstration window: attendance falls, missed assignments rise, LMS activity stops, and some students receive a financial hold. The pattern raises stop-out risk without making outcomes perfectly predictable.

The financial story uses synthetic next-term net tuition. “Tuition exposure” is the sum of that amount for students currently classified as elevated risk. It is an operational estimate, not audited revenue or a causal forecast.

## Source Datasets

| Dataset | Grain | Primary key | Business event time | Expected bootstrap rows | Purpose |
|---|---|---|---|---:|---|
| `students` | One current synthetic student | `student_id` | `record_effective_at` | 20,000 | Program, cohort, advisor, tuition, and restricted fairness-audit attributes |
| `enrollments` | One student per academic term | `enrollment_id` | `term_census_date` | 60,000 | Credit load, completion, GPA, withdrawals, and academic standing |
| `attendance_events` | One student-course meeting | `attendance_event_id` | `event_at` | 300,000 | Present/absent behavior and recent attendance trends |
| `engagement_events` | One LMS or student-support interaction | `engagement_event_id` | `event_at` | 250,000 | LMS activity, assignment submission, advising, and support usage |
| `financial_events` | One student financial-status change | `financial_event_id` | `event_at` | 40,000 | Balance band, aid state, payment activity, and holds |
| `student_outcomes` | One student per label term | `outcome_id` | `next_term_census_date` | 40,000 | Next-term enrollment, persistence, stop-out, and withdrawal labels |

All five child datasets reference `students.student_id`.

## Domain Rules

### Students

- `student_id` uses `STU-` plus a six-digit synthetic sequence.
- Programs are deliberately skewed; they are not sampled uniformly.
- Advisor assignment is deterministic and distributes each program across multiple advisors.
- Protected audit fields are `synthetic_age_band`, `synthetic_gender`, `synthetic_first_generation`, and `synthetic_race_ethnicity`.
- `synthetic_net_tuition_next_term` is positive and right-skewed.

### Enrollments

- Terms are ordered chronologically and each feature cutoff precedes the following label census date.
- GPA is in `[0, 4]`; attempted and completed credits are nonnegative; completed credits cannot exceed attempted credits.
- Academic standing and withdrawal status are consistent with GPA and completed credits.

### Attendance and Engagement

- Attendance is correlated with prior academic standing and incident-cohort state.
- Assignment and LMS events are internally consistent: a missed assignment has no submission timestamp.
- The incident cohort deteriorates only after the documented incident start date, preserving valid historical training periods.

### Financial Events

- Balances are nonnegative and right-skewed.
- A hold has a documented reason and effective time.
- Financial friction affects risk but does not deterministically set the outcome.

### Outcomes

- The stop-out label means the student is not enrolled by the census date of the next major term.
- Outcome generation uses a bounded probability derived from pre-census signals plus deterministic noise.
- The expected positive class is intentionally imbalanced, not 50/50.

## Model Feature Allowlist

- `attendance_rate_28d`
- `missed_assignments_28d`
- `days_since_lms_activity`
- `financial_hold_flag`
- `current_balance_band`
- `credits_attempted_current`
- `credits_completed_prior`
- `cumulative_gpa`
- `withdrawal_count_prior`
- `support_interactions_90d`
- `program_code`
- `academic_level`
- `residency_status`

## Silver Point-in-Time Contract

Silver publishes deduplicated domain tables, an isolated
`student_protected_audit` table, `training_labels`, operational
`student_daily_snapshots`, and label-aligned `model_feature_snapshots`.

For training, `feature_as_of` is 23:59:59 on the day before the next-term
census date. Labels are stored only in `training_labels`; model feature rows do
not contain the label, outcome status, protected audit attributes, or the
synthetic incident-cohort marker.

| Feature | Point-in-time definition |
|---|---|
| `attendance_rate_28d` | Mean of attendance flags strictly within the preceding 28 days and no later than `feature_as_of` |
| `missed_assignments_28d` | Count of missed assignment events in the same preceding 28-day window |
| `days_since_lms_activity` | Calendar days since the latest LMS login known at the cutoff; `999` means no prior login |
| `support_interactions_90d` | Support interactions strictly within the preceding 90 days |
| `financial_hold_flag`, `current_balance_band` | Latest financial state at or before the cutoff |
| `credits_attempted_current`, `cumulative_gpa` | Latest enrollment state at or before the cutoff |
| `credits_completed_prior`, `withdrawal_count_prior` | Totals from enrollment terms preceding the current term |
| `attempted_credit_trend` | Current attempted credits minus the immediately preceding term |

`max_feature_event_at` is retained as a leakage-audit column, and the pipeline
fails if it exceeds `feature_as_of`. Missing activity receives explicit neutral
defaults instead of silently disappearing from the training population.

Identifiers, labels, post-cutoff events, advisor identity, and protected audit attributes are excluded.

## Incremental Layout

Raw records are written as Parquet to:

```text
/Volumes/<catalog>/<bronze_schema>/raw_data/<dataset>/run_date=YYYY-MM-DD
```

The bootstrap run creates the master population and historical terms. Later triggered runs append one new synthetic day of activity. A small tagged group of malformed records is written to dedicated input rows so Bronze quarantine behavior can be demonstrated without changing valid business aggregates.

## Advisor Briefing Contract

Advisor generation reads only
`<catalog>.<schema_prefix>_gold.student_detail`. The prompt includes the
governed risk score and tier, allowlisted model contributing-factor IDs, and
only these factual signal IDs when populated: `attendance_rate_28d`,
`missed_assignments_28d`, `days_since_lms_activity`, `financial_hold_flag`,
and `cumulative_gpa`. It does not receive protected audit attributes, raw
unrestricted notes, labels, or any other source fields.

Responses must be a strict JSON object containing `briefing`,
`suggested_action`, `citations`, `unsupported_claims`, `prompt_version`, and
`model_id`. Every briefing sentence has an inline citation to an allowlisted
fact ID; accepted responses have no unsupported claims. Diagnostic,
disciplinary, protected-trait, and retention-causality content is rejected.

`<catalog>.<schema_prefix>_gold.advisor_summaries` is versioned by prompt
version and idempotent summary key. It records model ID, citations, generation
and evaluation status, timestamp, and visible error text. Generated summaries
remain `evaluation_status = 'pending'` and are not publishable until the named
MLflow gates pass; a failed gate is visibly marked `failed`. It contains no
risk score and does not modify `student_risk_score_history`; endpoint or
validation failure produces a `generation_status = 'failed'` record instead.
