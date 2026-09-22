"""Configuration contracts that prevent a Lakebase synchronization loop."""

from __future__ import annotations

import pytest

from scripts.configure_lakebase_sync import SyncPlan, build_sync_plan, configure


def test_sync_plan_uses_distinct_read_only_and_writeback_namespaces():
    plan = build_sync_plan(
        catalog="serverless_stable_febar_scottj_catalog",
        schema_prefix="student_retention",
        lakebase_catalog="student_retention_lakebase",
        branch="projects/student-retention/branches/production",
        database="projects/student-retention/branches/production/databases/databricks-postgres",
    )

    assert plan.postgres_serving_schema == "student_retention_serving"
    assert plan.postgres_write_schema == "student_retention_app"
    assert plan.uc_cdc_schema == "student_retention_cdc"
    assert plan.postgres_serving_schema != plan.postgres_write_schema
    assert all(
        target.startswith("student_retention_lakebase.student_retention_serving.")
        for target in plan.serving_syncs
    )
    assert set(plan.serving_syncs.values()) == {
        "serverless_stable_febar_scottj_catalog.student_retention_gold.executive_retention_metrics",
        "serverless_stable_febar_scottj_catalog.student_retention_gold.risk_trends",
    }


def test_sync_plan_rejects_a_writeback_table_as_a_serving_source():
    with pytest.raises(ValueError, match="sync loop"):
        SyncPlan(
            catalog="catalog",
            uc_cdc_schema="retention_cdc",
            lakebase_catalog="retention_lakebase",
            branch="projects/retention/branches/production",
            database="projects/retention/branches/production/databases/databricks-postgres",
            postgres_database="databricks_postgres",
            postgres_serving_schema="retention_serving",
            postgres_write_schema="retention_app",
            serving_syncs={
                "retention_lakebase.retention_serving.interventions":
                    "catalog.retention_cdc.lb_interventions_history"
            },
        )


def test_cdf_config_identifier_uses_the_lakebase_api_format(monkeypatch):
    commands = []
    plan = build_sync_plan(
        catalog="catalog",
        schema_prefix="retention",
        lakebase_catalog="retention_lakebase",
        branch="projects/retention/branches/production",
        database="projects/retention/branches/production/databases/databricks-postgres",
    )

    monkeypatch.setattr(
        "scripts.configure_lakebase_sync._exists",
        lambda command, *, profile: False,
    )
    monkeypatch.setattr(
        "scripts.configure_lakebase_sync._run",
        lambda command, *, profile: commands.append(command),
    )
    configure(plan, profile="test")

    assert commands[-1][-2:] == [
        "--cdf-config-id",
        "student_retention_interventions",
    ]


def test_configure_is_a_noop_when_both_sync_directions_exist(monkeypatch):
    creates = []
    plan = build_sync_plan(
        catalog="catalog",
        schema_prefix="retention",
        lakebase_catalog="retention_lakebase",
        branch="projects/retention/branches/production",
        database="projects/retention/branches/production/databases/databricks-postgres",
    )
    monkeypatch.setattr(
        "scripts.configure_lakebase_sync._exists",
        lambda command, *, profile: True,
        raising=False,
    )
    monkeypatch.setattr(
        "scripts.configure_lakebase_sync._run",
        lambda command, *, profile: creates.append(command),
    )

    configure(plan, profile="test")

    assert creates == []
