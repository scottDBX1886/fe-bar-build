-- Render placeholders only after principals are explicitly approved and recorded.
-- Advisor access is fail-closed through advisor_row_filter, advisor_entitlements, and current_user().
CREATE OR REPLACE VIEW {{CATALOG}}.{{GOLD_SCHEMA}}.restricted_protected_audit
COMMENT 'Restricted fairness-audit attributes; never exposed to advisor, executive, app, or Genie surfaces'
AS
SELECT student_id, synthetic_age_band, synthetic_gender,
       synthetic_first_generation, synthetic_race_ethnicity,
       record_effective_at, run_date
FROM {{CATALOG}}.{{SILVER_SCHEMA}}.student_protected_audit;

-- PRINCIPAL GRANTS REQUIRE EXPLICIT APPROVAL
GRANT USE CATALOG ON CATALOG {{CATALOG}} TO `{{ADVISOR_GROUP}}`;
GRANT USE SCHEMA ON SCHEMA {{CATALOG}}.{{GOLD_SCHEMA}} TO `{{ADVISOR_GROUP}}`;
GRANT SELECT ON TABLE {{CATALOG}}.{{GOLD_SCHEMA}}.advisor_caseload TO `{{ADVISOR_GROUP}}`;
GRANT SELECT ON TABLE {{CATALOG}}.{{GOLD_SCHEMA}}.student_detail TO `{{ADVISOR_GROUP}}`;
GRANT SELECT ON TABLE {{CATALOG}}.{{GOLD_SCHEMA}}.genie_retention TO `{{ADVISOR_GROUP}}`;

GRANT USE CATALOG ON CATALOG {{CATALOG}} TO `{{EXECUTIVE_GROUP}}`;
GRANT USE SCHEMA ON SCHEMA {{CATALOG}}.{{GOLD_SCHEMA}} TO `{{EXECUTIVE_GROUP}}`;
GRANT SELECT ON TABLE {{CATALOG}}.{{GOLD_SCHEMA}}.executive_retention_metrics TO `{{EXECUTIVE_GROUP}}`;
GRANT SELECT ON TABLE {{CATALOG}}.{{GOLD_SCHEMA}}.risk_trends TO `{{EXECUTIVE_GROUP}}`;
REVOKE SELECT ON TABLE {{CATALOG}}.{{GOLD_SCHEMA}}.student_detail FROM `{{EXECUTIVE_GROUP}}`;
REVOKE SELECT ON TABLE {{CATALOG}}.{{GOLD_SCHEMA}}.advisor_caseload FROM `{{EXECUTIVE_GROUP}}`;
REVOKE SELECT ON TABLE {{CATALOG}}.{{GOLD_SCHEMA}}.genie_retention FROM `{{EXECUTIVE_GROUP}}`;

GRANT USE CATALOG ON CATALOG {{CATALOG}} TO `{{APP_SERVICE_PRINCIPAL}}`;
GRANT USE SCHEMA ON SCHEMA {{CATALOG}}.{{GOLD_SCHEMA}} TO `{{APP_SERVICE_PRINCIPAL}}`;
GRANT SELECT ON TABLE {{CATALOG}}.{{GOLD_SCHEMA}}.advisor_caseload TO `{{APP_SERVICE_PRINCIPAL}}`;
GRANT SELECT ON TABLE {{CATALOG}}.{{GOLD_SCHEMA}}.student_detail TO `{{APP_SERVICE_PRINCIPAL}}`;
GRANT SELECT ON TABLE {{CATALOG}}.{{GOLD_SCHEMA}}.executive_retention_metrics TO `{{APP_SERVICE_PRINCIPAL}}`;
GRANT SELECT ON TABLE {{CATALOG}}.{{GOLD_SCHEMA}}.risk_trends TO `{{APP_SERVICE_PRINCIPAL}}`;

GRANT USE CATALOG ON CATALOG {{CATALOG}} TO `{{FAIRNESS_AUDIT_GROUP}}`;
GRANT USE SCHEMA ON SCHEMA {{CATALOG}}.{{GOLD_SCHEMA}} TO `{{FAIRNESS_AUDIT_GROUP}}`;
GRANT SELECT ON VIEW {{CATALOG}}.{{GOLD_SCHEMA}}.restricted_protected_audit TO `{{FAIRNESS_AUDIT_GROUP}}`;

REVOKE SELECT ON VIEW {{CATALOG}}.{{GOLD_SCHEMA}}.restricted_protected_audit FROM `{{ADVISOR_GROUP}}`;
REVOKE SELECT ON VIEW {{CATALOG}}.{{GOLD_SCHEMA}}.restricted_protected_audit FROM `{{EXECUTIVE_GROUP}}`;
REVOKE SELECT ON VIEW {{CATALOG}}.{{GOLD_SCHEMA}}.restricted_protected_audit FROM `{{APP_SERVICE_PRINCIPAL}}`;
