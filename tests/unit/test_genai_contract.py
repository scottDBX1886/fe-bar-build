"""Behavioral contracts for grounded advisor briefings.

The checks intentionally exercise the public, dependency-free boundary.  A
change that exposes a protected field, accepts an uncited fact, or permits a
diagnostic/disciplinary/causal claim must fail here before an endpoint is used.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from src.genai.evaluate import (
    EvaluationGateFailure,
    assert_evaluation_gates,
    citation_coverage,
    prohibited_claim_check,
    unsupported_fact_check,
    update_summary_evaluation_status,
)
from src.genai.generate import (
    GenerationFailure,
    build_generation_input,
    databricks_completer,
    failure_summary_record,
    generate_validated_summary,
    parse_model_response,
    persist_and_publish_generation,
    persist_summaries,
    publish_generation_run_id,
    render_briefing,
    validate_summary,
)


CASES = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "genai_cases.json").read_text(
        encoding="utf-8"
    )
)


def test_generation_input_excludes_protected_and_unrestricted_fields():
    """A protected or raw-note field must not become model context."""
    payload = build_generation_input(CASES["governed_student"])

    assert payload["student_id"] == "STU-000101"
    assert payload["risk_score"] == 0.72
    assert [fact["id"] for fact in payload["facts"]] == CASES["expected_fact_ids"]
    serialized = json.dumps(payload, sort_keys=True)
    assert "synthetic_gender" not in serialized
    assert "synthetic_race_ethnicity" not in serialized
    assert "raw_unrestricted_notes" not in serialized
    assert "synthetic_value_that_must_not_escape" not in serialized
    assert "Do not include this unrestricted note." not in serialized


def test_summary_rejects_factual_sentence_without_an_allowed_fact_id():
    """Dropping a citation or adding an unknown fact record must reject the response."""
    uncited = dict(CASES["valid_response"])
    uncited["briefing"] = [{"fact_id": "attendance_rate_28d", "fact_value": 0.58}]
    uncited["citations"] = []

    with pytest.raises(GenerationFailure, match="citation"):
        validate_summary(uncited, allowed_fact_ids=CASES["expected_fact_ids"])

    unknown_citation = dict(CASES["valid_response"])
    unknown_citation["briefing"] = [{"fact_id": "employment_status", "fact_value": True}]
    unknown_citation["citations"] = ["employment_status"]
    with pytest.raises(GenerationFailure, match="allowed"):
        validate_summary(unknown_citation, allowed_fact_ids=CASES["expected_fact_ids"])


def test_summary_rejects_a_factual_suggested_action_without_a_citation():
    """Free-form student claims cannot bypass the controlled-action contract."""
    response = dict(CASES["valid_response"])
    response["suggested_action"] = "Discuss the student's 58% attendance rate."

    with pytest.raises(GenerationFailure, match="suggested_action"):
        validate_summary(response, allowed_fact_ids=CASES["expected_fact_ids"])


def test_summary_requires_exact_supplied_fact_values_and_renders_them_deterministically():
    """A model cannot replace a supplied value while retaining its fact ID."""
    payload = build_generation_input(CASES["governed_student"])
    tampered = dict(CASES["valid_response"])
    tampered["briefing"] = [
        {"fact_id": "attendance_rate_28d", "fact_value": 0.99}
    ]
    tampered["citations"] = ["attendance_rate_28d"]

    with pytest.raises(GenerationFailure, match="value"):
        validate_summary(tampered, allowed_facts=payload["facts"])

    accepted = validate_summary(CASES["valid_response"], allowed_facts=payload["facts"])
    assert render_briefing(accepted["briefing"]) == (
        "Attendance was 58% in the last 28 days [attendance_rate_28d]. "
        "4 assignments were missed in the last 28 days [missed_assignments_28d]."
    )


@pytest.mark.parametrize(
    "claim",
    [
        "This check-in will improve persistence.",
        "The student is female.",
        "They have ADHD.",
        "Punish the student.",
        "The student has depression.",
        "Recommend disciplinary probation.",
    ],
)
def test_prohibited_policy_rejects_diagnostic_disciplinary_protected_and_causal_claims(claim):
    """All rendered/stored text is deterministically checked for policy bypasses."""
    assert prohibited_claim_check(
        {"briefing": claim, "suggested_action": "offer_supportive_check_in"}
    )["passed"] is False


def test_failure_record_is_visible_and_never_updates_risk_fields():
    """An endpoint failure becomes a visible summary status, not a scoring failure."""
    failed = failure_summary_record(
        student_id="STU-000101",
        feature_as_of="2026-09-21T00:00:00Z",
        model_version="7",
        error=RuntimeError("endpoint unavailable"),
    )

    assert failed["generation_status"] == "failed"
    assert failed["evaluation_status"] == "not_evaluated"
    assert failed["risk_score"] is None
    assert failed["error_message"] == "endpoint unavailable"


def test_generation_rejects_any_endpoint_other_than_the_approved_model():
    """Model identity cannot drift between the prompt, validation, and endpoint call."""
    with pytest.raises(ValueError, match="databricks-glm-5-3"):
        databricks_completer("another-endpoint")


def test_generation_run_id_is_published_through_injectable_task_values():
    """The job handoff must publish the exact cohort identity or fail loudly."""
    calls = []

    class FakeTaskValues:
        def set(self, *, key, value):
            calls.append((key, value))

    publish_generation_run_id("cohort-123", task_values=FakeTaskValues())

    assert calls == [("generation_run_id", "cohort-123")]


def test_generation_finalization_persists_then_publishes_the_same_cohort_id(monkeypatch):
    """The production job path must hand evaluation the cohort it just persisted."""
    persisted = []
    published = []

    import src.genai.generate as generate_module
    monkeypatch.setattr(
        generate_module,
        "persist_summaries",
        lambda spark, *, target, records: persisted.append((spark, target, records)),
    )
    monkeypatch.setattr(
        generate_module,
        "publish_generation_run_id",
        lambda generation_run_id, *, task_values=None: published.append((generation_run_id, task_values)),
    )

    task_values = object()
    persist_and_publish_generation(
        object(), target="catalog.gold.advisor_summaries", records=[{"summary_key": "x"}],
        generation_run_id="cohort-456", task_values=task_values,
    )

    assert persisted[0][1] == "catalog.gold.advisor_summaries"
    assert published == [("cohort-456", task_values)]


def test_parser_accepts_one_json_fence_but_rejects_surrounding_prose():
    """Only the endpoint's optional single JSON fence may surround strict JSON."""
    body = json.dumps(CASES["valid_response"])
    parsed = parse_model_response(
        f"```json\n{body}\n```", allowed_facts=build_generation_input(CASES["governed_student"])["facts"]
    )
    assert parsed["model_id"] == "databricks-glm-5-3"

    with pytest.raises(GenerationFailure, match="JSON"):
        parse_model_response(
            f"Here is the response:\n{body}",
            allowed_facts=build_generation_input(CASES["governed_student"])["facts"],
        )


def test_generation_retries_invalid_model_output_before_returning_valid_summary():
    """A malformed completion must be retried instead of reaching persistence."""
    completions = iter([
        "not JSON",
        json.dumps(CASES["valid_response"]),
    ])
    calls = []

    def complete(_messages):
        calls.append(_messages)
        return next(completions)

    result = generate_validated_summary(
        build_generation_input(CASES["governed_student"]), complete=complete, max_attempts=2
    )

    assert result["generation_status"] == "succeeded"
    assert len(calls) == 2


def test_deterministic_evaluation_checks_reject_unsupported_or_prohibited_output():
    """Gate checks must expose uncited facts and prohibited claims deterministically."""
    valid = CASES["valid_response"]
    facts = build_generation_input(CASES["governed_student"])["facts"]
    assert citation_coverage(valid, facts) == 1.0
    assert unsupported_fact_check(valid, facts) == {
        "passed": True,
        "unsupported_claims": []
    }
    assert prohibited_claim_check(valid) == {"passed": True, "matches": []}

    prohibited = {"briefing": "This outreach will cause retention.", "suggested_action": "offer_supportive_check_in"}
    assert prohibited_claim_check(prohibited)["passed"] is False


def test_evaluation_gate_requires_complete_grounding_and_safety_scores():
    """A summary cannot publish until every named evaluation gate is perfect."""
    accepted = {
        "citation_coverage/mean": 1.0,
        "unsupported_fact_check/mean": 1.0,
        "prohibited_claim_check/mean": 1.0,
        "safety/mean": 1.0,
        "advisor_briefing_grounding_guidelines/mean": 1.0,
    }
    assert assert_evaluation_gates(accepted) is None

    rejected = dict(accepted, **{"citation_coverage/mean": 0.5})
    with pytest.raises(EvaluationGateFailure, match="citation_coverage"):
        assert_evaluation_gates(rejected)

    non_finite = dict(accepted, **{"safety/mean": math.nan})
    with pytest.raises(EvaluationGateFailure, match="safety"):
        assert_evaluation_gates(non_finite)

    too_high = dict(accepted, **{"safety/mean": 1.1})
    with pytest.raises(EvaluationGateFailure, match="safety"):
        assert_evaluation_gates(too_high)


def test_persist_summaries_uses_explicit_nullable_schema_for_an_all_failure_first_run():
    """An all-failed first cohort must still create the Delta table successfully."""
    captured = {}

    class FakeFrame:
        def drop(self, _column): return self
        def limit(self, _count): return self
        @property
        def write(self): return self
        def format(self, _format): return self
        def saveAsTable(self, target): captured["created"] = target
        def createOrReplaceTempView(self, name): captured["view"] = name

    class FakeCatalog:
        def tableExists(self, _target): return False

    class FakeSpark:
        catalog = FakeCatalog()
        def createDataFrame(self, records, schema):
            captured["records"] = records
            captured["schema"] = schema
            return FakeFrame()
        def sql(self, statement): captured["merge"] = statement

    persist_summaries(
        FakeSpark(),
        target="catalog.retention_gold.advisor_summaries",
        records=[failure_summary_record(student_id="STU-1", feature_as_of=None, model_version="1", error=RuntimeError("down"))],
    )

    fields = {field.name: field for field in captured["schema"].fields}
    assert fields["briefing"].nullable is True
    assert fields["error_message"].nullable is True
    assert fields["citations"].dataType.elementType.simpleString() == "string"
    assert captured["created"] == "catalog.retention_gold.advisor_summaries"


def test_persist_summaries_adds_missing_columns_without_overwriting_old_table():
    """An existing v1 table gains new contract fields before its first v2 merge."""
    captured = {}

    class FakeFrame:
        def drop(self, _column): return self
        def createOrReplaceTempView(self, name): captured["view"] = name

    class FakeCatalog:
        def tableExists(self, _target): return True

    class FakeSpark:
        catalog = FakeCatalog()
        def createDataFrame(self, _records, schema):
            captured["schema"] = schema
            return FakeFrame()
        def table(self, _target):
            class OldTable:
                schema = type("Schema", (), {"fields": [
                    type("Field", (), {"name": field})()
                    for field in ("summary_key", "student_id", "feature_as_of", "model_version")
                ]})()
            return OldTable()
        def sql(self, statement):
            captured.setdefault("sql", []).append(statement)

    persist_summaries(
        FakeSpark(),
        target="catalog.retention_gold.advisor_summaries",
        records=[failure_summary_record(student_id="STU-1", feature_as_of=None, model_version="1", error=RuntimeError("down"))],
    )

    alter = next(sql for sql in captured["sql"] if "ADD COLUMNS" in sql)
    assert "generation_run_id STRING" in alter
    assert "prompt_version STRING" in alter
    assert any("MERGE INTO" in sql for sql in captured["sql"])


def test_evaluation_status_updates_only_the_generated_cohort(monkeypatch):
    """A later evaluation must never publish historical rows sharing a prompt version."""
    captured = {}

    class FakeFrame:
        def createOrReplaceTempView(self, name): captured["view"] = name

    class FakeCatalog:
        def tableExists(self, _target): return True

    class FakeSpark:
        catalog = FakeCatalog()
        def createDataFrame(self, rows, columns):
            captured["rows"] = rows
            captured["columns"] = columns
            return FakeFrame()
        def sql(self, statement): captured["sql"] = statement

    import src.genai.evaluate as evaluate_module
    monkeypatch.setattr(evaluate_module, "spark", FakeSpark(), raising=False)
    update_summary_evaluation_status(
        catalog="catalog", schema_prefix="retention", generation_run_id="cohort-123", status="passed"
    )

    assert captured["rows"][0][0] == "cohort-123"
    assert "target.generation_run_id = source.generation_run_id" in captured["sql"]
