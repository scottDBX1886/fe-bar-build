-- Idempotent Task 6 namespace, volume, metadata, and row-filter bootstrap.
CREATE SCHEMA IF NOT EXISTS {{CATALOG}}.{{BRONZE_SCHEMA}}
COMMENT 'Synthetic landing and Bronze ingestion layer';

CREATE SCHEMA IF NOT EXISTS {{CATALOG}}.{{SILVER_SCHEMA}}
COMMENT 'Validated and point-in-time-safe student data';

CREATE SCHEMA IF NOT EXISTS {{CATALOG}}.{{GOLD_SCHEMA}}
COMMENT 'Governed student-retention data products';

CREATE SCHEMA IF NOT EXISTS {{CATALOG}}.{{ML_SCHEMA}}
COMMENT 'Unity Catalog models and ML artifacts';

CREATE SCHEMA IF NOT EXISTS {{CATALOG}}.{{CDC_SCHEMA}}
COMMENT 'Lakebase change history reserved for intervention writeback';

CREATE VOLUME IF NOT EXISTS {{CATALOG}}.{{GOLD_SCHEMA}}.governance_artifacts
COMMENT 'Managed non-sensitive artifacts for governance verification';

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{GOLD_SCHEMA}}.advisor_entitlements (
  user_identity STRING NOT NULL,
  advisor_id STRING NOT NULL,
  granted_at TIMESTAMP NOT NULL,
  granted_by STRING NOT NULL,
  CONSTRAINT advisor_entitlements_pk PRIMARY KEY (user_identity, advisor_id) NOT ENFORCED
)
USING DELTA
COMMENT 'Explicit user-to-synthetic-advisor assignments used by the fail-closed row filter'
TBLPROPERTIES ('quality' = 'gold', 'data_classification' = 'restricted');

CREATE OR REPLACE FUNCTION {{CATALOG}}.{{GOLD_SCHEMA}}.advisor_row_filter(requested_advisor_id STRING)
RETURNS BOOLEAN
COMMENT 'Allow only explicitly entitled advisor assignments; no entitlement means no rows'
RETURN EXISTS (
  SELECT 1
  FROM {{CATALOG}}.{{GOLD_SCHEMA}}.advisor_entitlements entitlement
  WHERE entitlement.user_identity = current_user()
    AND (entitlement.advisor_id = requested_advisor_id OR entitlement.advisor_id = '*')
);

ALTER TABLE {{CATALOG}}.{{GOLD_SCHEMA}}.student_risk_score_history
SET TBLPROPERTIES (
  'quality' = 'gold',
  'data_product' = 'immutable_risk_history',
  'delta.enableChangeDataFeed' = 'true'
);

COMMENT ON TABLE {{CATALOG}}.{{GOLD_SCHEMA}}.student_risk_score_history IS
'Immutable student stop-out risk score history keyed by student, feature time, and model version';
