# Sanitized Genie benchmark transcripts

## Current retention risk

Status: `COMPLETED`  
Rows: 5  
Source: `serverless_stable_febar_scottj_catalog.student_retention_gold.risk_trends`

```sql
WITH latest_date AS (
  SELECT MAX(score_date) AS score_date
  FROM serverless_stable_febar_scottj_catalog.student_retention_gold.risk_trends
), program_risk AS (
  SELECT rt.program_code, SUM(rt.student_count) AS elevated_risk_students
  FROM serverless_stable_febar_scottj_catalog.student_retention_gold.risk_trends rt
  INNER JOIN latest_date ld ON rt.score_date = ld.score_date
  WHERE rt.risk_tier IN ('medium', 'high')
  GROUP BY rt.program_code
)
SELECT program_code, elevated_risk_students,
       RANK() OVER (ORDER BY elevated_risk_students DESC) AS risk_rank
FROM program_risk
ORDER BY risk_rank
```

## Intervention coverage over time

Status: `COMPLETED`  
Rows: 1  
Source: `serverless_stable_febar_scottj_catalog.student_retention_gold.executive_retention_metrics`

```sql
SELECT score_date,
       try_divide(SUM(intervention_coverage * at_risk_count),
                  NULLIF(SUM(at_risk_count), 0)) AS intervention_coverage
FROM serverless_stable_febar_scottj_catalog.student_retention_gold.executive_retention_metrics
WHERE risk_tier IN ('medium', 'high')
GROUP BY score_date
ORDER BY score_date
```

Genie returned one score date and correctly disclosed that no change over time was visible.
