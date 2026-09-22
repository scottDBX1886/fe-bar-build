"""Behavioral contracts for grounded advisor briefings.

The checks intentionally exercise the public, dependency-free boundary.  A
change that exposes a protected field, accepts an uncited fact, or permits a
diagnostic/disciplinary/causal claim must fail here before an endpoint is used.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.genai.evaluate import (
    EvaluationGateFailure,
    assert_evaluation_gates,
    citation_coverage,
    prohibited_claim_check,
    unsupported_fact_check,
)
from src.genai.generate import (
    GenerationFailure,
    build_generation_input,
    failure_summary_record,
    generate_validated_summary,
    parse_model_response,
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
    """Dropping a citation or adding an unknown one must reject the response."""
    uncited = dict(CASES["valid_response"])
    uncited["briefing"] = "Attendance was 58% in the last 28 days."
    uncited["citations"] = []

    with pytest.raises(GenerationFailure, match="citation"):
        validate_summary(uncited, allowed_fact_ids=CASES["expected_fact_ids"])

    unknown_citation = dict(CASES["valid_response"])
    unknown_citation["briefing"] = "Student is employed [employment_status]."
    unknown_citation["citations"] = ["employment_status"]
    with pytest.raises(GenerationFailure, match="allowed"):
        validate_summary(unknown_citation, allowed_fact_ids=CASES["expected_fact_ids"])


def test_summary_rejects_a_factual_suggested_action_without_a_citation():
    """Moving an uncited student fact into the action cannot bypass grounding."""
    response = dict(CASES["valid_response"])
    response["suggested_action"] = "Discuss the student's 58% attendance rate."

    with pytest.raises(GenerationFailure, match="citation"):
        validate_summary(response, allowed_fact_ids=CASES["expected_fact_ids"])


@pytest.mark.parametrize(
    "claim",
    [
        "The student has depression [attendance_rate_28d].",
        "Recommend disciplinary probation [attendance_rate_28d].",
        "This outreach will cause retention [attendance_rate_28d].",
        "As a first-generation student, they need extra support [attendance_rate_28d].",
    ],
)
def test_summary_rejects_diagnostic_disciplinary_and_causal_claims(claim):
    """Prohibited advice must not be persisted even when it carries a citation."""
    response = dict(CASES["valid_response"])
    response["briefing"] = claim
    response["citations"] = ["attendance_rate_28d"]

    with pytest.raises(GenerationFailure, match="prohibited"):
        validate_summary(response, allowed_fact_ids=CASES["expected_fact_ids"])


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


def test_parser_accepts_one_json_fence_but_rejects_surrounding_prose():
    """Only the endpoint's optional single JSON fence may surround strict JSON."""
    body = json.dumps(CASES["valid_response"])
    parsed = parse_model_response(
        f"```json\n{body}\n```", allowed_fact_ids=CASES["expected_fact_ids"]
    )
    assert parsed["model_id"] == "databricks-glm-5-3"

    with pytest.raises(GenerationFailure, match="JSON"):
        parse_model_response(
            f"Here is the response:\n{body}",
            allowed_fact_ids=CASES["expected_fact_ids"],
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
    assert citation_coverage(valid, {"attendance_rate_28d", "missed_assignments_28d"}) == 1.0
    assert unsupported_fact_check(valid, {"attendance_rate_28d", "missed_assignments_28d"}) == {
        "passed": True,
        "unsupported_claims": []
    }
    assert prohibited_claim_check(valid) == {"passed": True, "matches": []}

    prohibited = dict(valid)
    prohibited["briefing"] = "This outreach will cause retention [attendance_rate_28d]."
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
