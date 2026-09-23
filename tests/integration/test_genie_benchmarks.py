from __future__ import annotations

import json
import re
from pathlib import Path


SPACE = json.loads(Path("config/genie/space.json").read_text(encoding="utf-8"))
BENCHMARKS = json.loads(
    Path("config/genie/benchmarks.json").read_text(encoding="utf-8")
)

APPROVED_SOURCES = {
    "serverless_stable_febar_scottj_catalog.student_retention_gold.executive_retention_metrics",
    "serverless_stable_febar_scottj_catalog.student_retention_gold.risk_trends",
    "serverless_stable_febar_scottj_catalog.student_retention_gold.advisor_caseload",
    "serverless_stable_febar_scottj_catalog.student_retention_gold.genie_retention",
}
PROTECTED_COLUMNS = {
    "synthetic_age_band",
    "synthetic_gender",
    "synthetic_first_generation",
    "synthetic_race_ethnicity",
}


def test_space_uses_only_approved_governed_sources_with_column_context():
    tables = SPACE["data_sources"]["tables"]
    assert {table["identifier"] for table in tables} == APPROVED_SOURCES
    assert tables == sorted(tables, key=lambda table: table["identifier"])
    assert all(table.get("column_configs") for table in tables)
    assert all(
        table["column_configs"]
        == sorted(table["column_configs"], key=lambda column: column["column_name"])
        for table in tables
    )


def test_space_excludes_protected_fields_and_includes_required_question_families():
    serialized = json.dumps(SPACE).lower()
    assert PROTECTED_COLUMNS.isdisjoint(serialized.split('"'))
    questions = " ".join(
        question["question"][0].lower()
        for question in SPACE["config"]["sample_questions"]
    )
    for phrase in (
        "risk concentration",
        "intervention coverage",
        "follow-up backlog",
        "program trends",
        "tuition exposure",
    ):
        assert phrase in questions


def test_instructions_are_bounded_and_require_the_synthetic_tuition_caveat():
    instructions = SPACE["instructions"]["text_instructions"]
    assert len(instructions) == 1
    content = "\n".join(instructions[0]["content"])
    assert len(content) < 2_000
    assert "synthetic estimate" in content.lower()
    assert "protected" in content.lower()


def test_benchmark_suite_covers_at_least_twelve_and_special_cases():
    cases = BENCHMARKS["cases"]
    assert len(cases) >= 12
    assert {case["kind"] for case in cases} >= {
        "sql",
        "empty",
        "clarification",
        "permission_denied",
    }
    assert len({case["id"] for case in cases}) == len(cases)


def test_sql_benchmarks_are_read_only_checked_and_never_request_protected_columns():
    for case in BENCHMARKS["cases"]:
        assert set(case["expected_tables"]).issubset(APPROVED_SOURCES)
        assert PROTECTED_COLUMNS.issubset(set(case["forbidden_columns"]))
        answer_sql = case.get("answer_sql")
        if answer_sql is None:
            continue
        normalized = answer_sql.strip().lower()
        assert re.match(r"^(select|with)\b", normalized)
        assert not re.search(
            r"\b(create|alter|drop|insert|update|delete|merge|copy)\b", normalized
        )
        assert not any(column in normalized for column in PROTECTED_COLUMNS)
