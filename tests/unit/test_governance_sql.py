import pytest

from src.governance.apply import render_sql, sql_statements


def test_render_sql_replaces_all_known_identifiers():
    rendered = render_sql(
        "SELECT * FROM {{CATALOG}}.{{GOLD_SCHEMA}}.x",
        catalog="demo",
        schema_prefix="retention",
    )
    assert rendered == "SELECT * FROM demo.retention_gold.x"


def test_render_sql_rejects_unresolved_placeholders():
    with pytest.raises(ValueError, match="unresolved"):
        render_sql("GRANT SELECT TO {{GROUP}}", catalog="demo", schema_prefix="retention")


def test_sql_statements_removes_comments_and_splits_commands():
    assert sql_statements("-- setup\nCREATE SCHEMA x;\n\nCREATE TABLE x.y (id INT);") == [
        "CREATE SCHEMA x",
        "CREATE TABLE x.y (id INT)",
    ]
