# From Fragmented Signals to Timely Student Support

## A governed student-retention workflow on Databricks

Public-sector higher education demonstration
All students, events, model results, KPIs, and financial values are synthetic.

---

# The outcome: act earlier, with evidence

University leaders need to improve persistence while student-success teams need a manageable, defensible daily workflow.

This demonstration connects synthetic attendance, learning, financial, and intervention signals so that:

- advisors see a prioritized caseload and grounded context;
- executives see aggregate risk and intervention coverage;
- governance travels with the data and the signed-in user;
- every operational write returns to the analytical record.

The model prioritizes human review. It does not automate disciplinary action or establish causality.

---

# Buyer KPIs

| Executive sponsor | Student-success owner |
|---|---|
| Persistence and retention rate | Time from signal to first outreach |
| Elevated-risk population | Actionable students per advisor |
| Estimated next-term net tuition exposure | Intervention and follow-up coverage |
| Program-level risk concentration | Closed-loop case history |

Synthetic demonstration baseline:

- 20,000 current synthetic students;
- 88.88% synthetic retention rate;
- 2,664 initially elevated-risk students;
- $24.1M estimated synthetic next-term net tuition exposure.

These are designed demo values, not measured university outcomes or a business case forecast.

---

# Current-state friction

Signals arrive in separate systems and on different clocks.

1. Attendance, LMS activity, finance, and enrollment data require manual reconciliation.
2. Advisors cannot consistently identify which change matters today.
3. Case notes live outside analytical context.
4. Executives struggle to see whether intervention coverage is improving.
5. Generic AI can obscure sources, identity, and policy enforcement.

Result: slow outreach, inconsistent prioritization, and weak evidence from signal to action.

---

# The closed-loop workflow

1. **Observe** — triggered Lakeflow processing ingests one deterministic synthetic day.
2. **Govern** — Unity Catalog quality, lineage, grants, and row filters apply centrally.
3. **Prioritize** — a versioned ML model scores current snapshots and cites leading factors.
4. **Assist** — evaluated GenAI produces bounded advisor briefings from governed facts.
5. **Act** — the Databricks App writes intervention transactions to Lakebase.
6. **Learn** — CDC returns operational changes to Unity Catalog and refreshes Gold.
7. **Understand** — embedded Genie answers governed questions and exposes generated SQL.

---

# Business value

| Value lever | Demonstrated measure | Decision enabled |
|---|---|---|
| Earlier prioritization | Daily risk movement and immutable score history | Which students need human review now? |
| Advisor productivity | Ranked caseload plus grounded briefing | What evidence should shape outreach? |
| Closed-loop execution | Versioned interventions plus CDC history | Was outreach recorded and followed up? |
| Executive visibility | Aggregate intervention coverage and risk concentration | Where are capacity and coverage gaps? |
| Trust | Row filters, read-only serving sync, citations, SQL inspection | Can each answer and action be verified? |

Potential impact must be validated with a university’s approved data, operating model, and thresholds. The demo does not claim retained students or realized tuition.

---

# Governed architecture

```text
Synthetic SIS / LMS / attendance / finance
                  │
                  ▼
       Lakeflow Bronze → Silver
                  │
                  ├── MLflow model registry → immutable risk history
                  │
                  ▼
       Unity Catalog governed Gold
          │                    │
          ▼                    ▼
 read-only Lakebase sync   Genie Agent
          │                    │
          └──── Databricks App ┘
                    │
                    ▼
      Lakebase-owned interventions
                    │ CDC
                    ▼
        Unity Catalog intervention Gold
```

Serving synchronization is one-way and read-only. Advisor transactions use separate Lakebase-owned tables, preventing refreshes from overwriting operational work.

---

# Why hybrid intelligence

The solution deliberately combines ML and GenAI.

- **ML classifier:** repeatable prioritization, calibrated probabilities, stable tier thresholds, model versioning, and baseline comparison.
- **GenAI briefing:** concise synthesis of allowlisted facts, citations, and discussion prompts.
- **Human advisor:** judgment, outreach, reconciliation, and accountable action.

The selected logistic model achieved 0.9669 PR-AUC on designed synthetic validation signals and exceeded the business-rule baseline. Those results validate the demo mechanics—not production accuracy or real-world fairness.

---

# Live demo story

1. Replay the September 23 synthetic incident day.
2. Inspect quarantined inputs and fresh daily features.
3. Show `STU-002564` move from medium (`0.455889`) to high risk (`0.637168`).
4. Review the governed caseload and grounded briefing.
5. Record outreach and a follow-up in Lakebase.
6. Verify CDC and intervention Gold without changing the ML score.
7. View aggregate executive coverage without exposing student detail.
8. Ask embedded Genie where current risk is concentrated and inspect its SQL.

Expected duration: 12–15 minutes. No manual data repair is part of the scenario.

---

# Evidence, not screenshots

The repository contains text-readable execution proof for every build domain:

- successful workflow and pipeline run IDs;
- quality counts and query results;
- model baselines, metrics, registry version, and scored rows;
- GenAI evaluation and citation results;
- governance and role-policy checks;
- Lakebase transaction, conflict, rollback, sync, and CDC checks;
- Genie benchmark prompts and generated SQL;
- application tests and deployed-state verification;
- an idempotent full incident-day replay.

Start at `evidence/README.md`; each acceptance criterion links to a reproduction command and expected interpretation.

---

# Trust and governance are product features

- Executives use aggregate-only products.
- Advisors receive row-filtered student detail.
- Protected attributes are isolated from routine Gold and excluded from model features.
- Serving tables are read-only; operational writes use separate Lakebase tables.
- Briefings cite governed facts and expose evaluation state.
- Genie runs in signed-in context and exposes generated SQL.
- Errors, stale data, partial responses, and ambiguity remain visible.

Access is enforced in data and backend policies—not merely hidden in the interface.

---

# Honest limitations

- Synthetic data and deliberately generated risk signals.
- No production SIS, LMS, finance, or identity integration.
- No institution-specific validation, fairness determination, or outcome monitoring.
- No causal estimate of intervention effectiveness.
- No automated outreach or adverse action.
- Triggered daily processing, not real-time continuous processing.
- Lakehouse Sync CDC path uses Beta capabilities with a documented bounded-export fallback.
- A separate AI/BI dashboard was intentionally excluded; the app is the single experience.

---

# Recommended next steps

1. Align with institutional research, student success, security, and legal owners.
2. Define approved data, outcomes, access groups, and intervention vocabulary.
3. Back-test against institution-specific cohorts and agree on decision thresholds.
4. Validate disparate-impact monitoring and advisor workflow usability.
5. Pilot with a limited advisor cohort and measure signal-to-outreach time and coverage.
6. Establish model, prompt, policy, and operational monitoring before scale.

Success means a trustworthy workflow that helps people act—not simply a high model score.
