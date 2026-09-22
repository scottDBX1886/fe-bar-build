from pathlib import Path


PROTECTED_COLUMNS = {
    "synthetic_age_band",
    "synthetic_gender",
    "synthetic_first_generation",
    "synthetic_race_ethnicity",
}


def test_gold_defines_focused_products_and_required_dimensions():
    source = Path("src/pipelines/gold.py").read_text(encoding="utf-8")
    for product in (
        "advisor_caseload",
        "student_detail",
        "executive_retention_metrics",
        "risk_trends",
        "genie_retention",
    ):
        assert f'@dp.materialized_view(\n    name=_gold("{product}")' in source
    for dimension in (
        "program_code", "cohort_code", "advisor_id", "term_code",
        "score_date", "risk_tier", "intervention_status",
    ):
        assert dimension in source


def test_routine_gold_surfaces_do_not_reference_protected_attributes():
    source = Path("src/pipelines/gold.py").read_text(encoding="utf-8")
    for protected in PROTECTED_COLUMNS:
        assert protected not in source


def test_advisor_products_attach_enforced_row_filter():
    source = Path("src/pipelines/gold.py").read_text(encoding="utf-8")
    assert source.count("row_filter=ADVISOR_ROW_FILTER") >= 3
    policies = Path("src/governance/policies.sql").read_text(encoding="utf-8")
    assert "ALTER TABLE {{CATALOG}}.{{GOLD_SCHEMA}}.advisor_caseload" not in policies


def test_gold_uses_runtime_supported_timestamp_difference_api():
    source = Path("src/pipelines/gold.py").read_text(encoding="utf-8")
    assert "F.timestamp_diff(" in source
    assert "F.timestampdiff(" not in source


def test_governance_bootstrap_is_idempotent_and_creates_managed_volume():
    sql = Path("src/governance/bootstrap.sql").read_text(encoding="utf-8")
    assert "CREATE SCHEMA IF NOT EXISTS" in sql
    assert "CREATE VOLUME IF NOT EXISTS" in sql
    assert "ALTER TABLE" in sql
    assert "SET TBLPROPERTIES" in sql


def test_policies_are_fail_closed_and_keep_executives_aggregate_only():
    sql = Path("src/governance/policies.sql").read_text(encoding="utf-8")
    assert "advisor_entitlements" in sql
    assert "current_user()" in sql
    assert "advisor_row_filter" in sql
    assert "restricted_protected_audit" in sql
    assert "REVOKE SELECT ON TABLE {{CATALOG}}.{{GOLD_SCHEMA}}.student_detail" in sql
    assert "GRANT SELECT ON TABLE {{CATALOG}}.{{GOLD_SCHEMA}}.executive_retention_metrics" in sql
