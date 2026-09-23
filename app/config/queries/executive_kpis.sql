WITH latest AS (
  SELECT * FROM serverless_stable_febar_scottj_catalog.student_retention_gold.executive_retention_metrics
  WHERE score_date = (SELECT max(score_date) FROM serverless_stable_febar_scottj_catalog.student_retention_gold.executive_retention_metrics)
)
SELECT score_date,
       sum(student_count) AS student_count,
       sum(at_risk_count) AS at_risk_count,
       sum(student_count * retention_rate) / nullif(sum(student_count), 0) AS retention_rate,
       sum(student_count * intervention_coverage) / nullif(sum(student_count), 0) AS intervention_coverage,
       sum(student_count * time_to_first_intervention_days) / nullif(sum(student_count), 0) AS time_to_first_intervention_days,
       sum(student_count * follow_up_completion_rate) / nullif(sum(student_count), 0) AS follow_up_completion_rate,
       sum(estimated_next_term_net_tuition_exposure) AS estimated_next_term_net_tuition_exposure,
       max(data_freshness_at) AS data_freshness_at
FROM latest GROUP BY score_date
