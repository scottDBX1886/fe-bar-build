"""Live transaction contracts for the Lakebase intervention write model."""

from __future__ import annotations

import os
import subprocess
import uuid

import pytest


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LAKEBASE_INTEGRATION") != "1",
    reason="set RUN_LAKEBASE_INTEGRATION=1 to exercise the approved Lakebase project",
)


def _psql(sql: str, *, expect_success: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [
            "databricks",
            "psql",
            "--project",
            "student-retention",
            "--branch",
            "production",
            "--endpoint",
            "primary",
            "--profile",
            "fe-bar",
            "--",
            "-X",
            "-A",
            "-t",
            "-v",
            "ON_ERROR_STOP=1",
            "-d",
            "databricks_postgres",
            "-c",
            sql,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if expect_success and result.returncode != 0:
        pytest.fail(result.stderr)
    return result


def _create(intervention_id: str, idempotency_key: str) -> str:
    return _psql(
        f"""
        SELECT result_status || '|' || intervention_id || '|' || version
        FROM student_retention_app.create_intervention(
          '{intervention_id}'::uuid, 'STU-TASK8-001', 'ADV-TASK8-001',
          'outreach', 'high', 'advisor@example.test', '{idempotency_key}'
        );
        """
    ).stdout.strip()


def test_create_and_duplicate_idempotency_return_the_prior_result():
    intervention_id = str(uuid.uuid4())
    idempotency_key = f"create-{uuid.uuid4()}"

    assert _create(intervention_id, idempotency_key) == f"applied|{intervention_id}|1"
    assert _create(intervention_id, idempotency_key) == f"replayed|{intervention_id}|1"

    counts = _psql(
        f"""
        SELECT
          (SELECT count(*) FROM student_retention_app.interventions
           WHERE intervention_id = '{intervention_id}'::uuid) || '|' ||
          (SELECT count(*) FROM student_retention_app.intervention_events
           WHERE intervention_id = '{intervention_id}'::uuid);
        """
    ).stdout.strip()
    assert counts == "1|1"


def test_update_conflict_and_close_use_optimistic_concurrency():
    intervention_id = str(uuid.uuid4())
    _create(intervention_id, f"create-{uuid.uuid4()}")

    updated = _psql(
        f"""
        SELECT result_status || '|' || version
        FROM student_retention_app.transition_intervention(
          '{intervention_id}'::uuid, 1, 'follow_up_scheduled', 'pending_follow_up',
          'advisor@example.test', 'follow up', now() + interval '2 days', NULL,
          'update-{uuid.uuid4()}'
        );
        """
    ).stdout.strip()
    assert updated == "applied|2"

    stale = _psql(
        f"""
        SELECT result_status || '|' || version
        FROM student_retention_app.transition_intervention(
          '{intervention_id}'::uuid, 1, 'updated', 'in_progress',
          'advisor@example.test', NULL, NULL, NULL, 'stale-{uuid.uuid4()}'
        );
        """
    ).stdout.strip()
    assert stale == "conflict|2"

    closed = _psql(
        f"""
        SELECT result_status || '|' || version
        FROM student_retention_app.transition_intervention(
          '{intervention_id}'::uuid, 2, 'closed', 'closed',
          'advisor@example.test', 'resolved', NULL, 'student_contacted',
          'close-{uuid.uuid4()}'
        );
        """
    ).stdout.strip()
    assert closed == "applied|3"


def test_event_append_rolls_back_when_the_state_insert_fails():
    intervention_id = str(uuid.uuid4())
    _create(intervention_id, f"create-{uuid.uuid4()}")
    duplicate_key = f"duplicate-intervention-{uuid.uuid4()}"

    failed = _psql(
        f"""
        SELECT * FROM student_retention_app.create_intervention(
          '{intervention_id}'::uuid, 'STU-TASK8-002', 'ADV-TASK8-001',
          'outreach', 'high', 'advisor@example.test', '{duplicate_key}'
        );
        """,
        expect_success=False,
    )
    assert failed.returncode != 0

    assert (
        _psql(
            f"SELECT count(*) FROM student_retention_app.intervention_events "
            f"WHERE idempotency_key = '{duplicate_key}';"
        ).stdout.strip()
        == "0"
    )


def test_intervention_events_are_immutable():
    intervention_id = str(uuid.uuid4())
    _create(intervention_id, f"create-{uuid.uuid4()}")

    result = _psql(
        f"DELETE FROM student_retention_app.intervention_events "
        f"WHERE intervention_id = '{intervention_id}'::uuid;",
        expect_success=False,
    )
    assert result.returncode != 0
    assert "immutable" in result.stderr.lower()


def test_synced_gold_serving_tables_expose_select_only_reader_privileges():
    reader_role = _psql(
        "SELECT rolname FROM pg_roles "
        "WHERE rolname LIKE 'databricks_reader_%' ORDER BY rolname LIMIT 1;"
    ).stdout.strip()
    assert reader_role

    counts = _psql(
        """
        SELECT
          (SELECT count(*) FROM student_retention_gold.serving_executive_retention_metrics)
          || '|' ||
          (SELECT count(*) FROM student_retention_gold.serving_risk_trends);
        """
    ).stdout.strip()
    assert all(int(count) > 0 for count in counts.split("|"))

    privileges = _psql(
        f"""
        SELECT
          has_table_privilege('{reader_role}',
            'student_retention_gold.serving_executive_retention_metrics', 'SELECT')
          || '|' ||
          has_table_privilege('{reader_role}',
            'student_retention_gold.serving_executive_retention_metrics', 'INSERT')
          || '|' ||
          has_table_privilege('{reader_role}',
            'student_retention_gold.serving_executive_retention_metrics', 'UPDATE')
          || '|' ||
          has_table_privilege('{reader_role}',
            'student_retention_gold.serving_executive_retention_metrics', 'DELETE');
        """
    ).stdout.strip()
    assert privileges == "true|false|false|false"
