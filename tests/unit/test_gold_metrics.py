from datetime import datetime, timezone

import pytest

from src.pipelines.gold_metrics import (
    at_risk_count,
    follow_up_completion_rate,
    intervention_coverage,
    retention_rate,
    time_to_first_intervention_days,
    top_k_caseload,
    tuition_exposure_estimate,
)


def test_retention_rate_uses_students_with_observed_outcomes():
    assert retention_rate(["PERSISTED", "STOP_OUT", "RETAINED"]) == pytest.approx(2 / 3)
    assert retention_rate([]) == 0.0


def test_at_risk_count_includes_medium_and_high_tiers():
    assert at_risk_count(["low", "medium", "high", "low"]) == 2


def test_top_k_caseload_orders_by_score_then_student_id():
    rows = [
        {"student_id": "S3", "risk_score": 0.7},
        {"student_id": "S2", "risk_score": 0.9},
        {"student_id": "S1", "risk_score": 0.9},
    ]
    assert [row["student_id"] for row in top_k_caseload(rows, 2)] == ["S1", "S2"]


def test_intervention_coverage_is_at_risk_students_with_an_intervention():
    rows = [
        {"risk_tier": "high", "intervention_status": "pending_follow_up"},
        {"risk_tier": "medium", "intervention_status": "closed"},
        {"risk_tier": "medium", "intervention_status": "not_started"},
        {"risk_tier": "low", "intervention_status": "open"},
    ]
    assert intervention_coverage(rows) == pytest.approx(2 / 3)


def test_time_to_first_intervention_uses_nonnegative_elapsed_days():
    utc = timezone.utc
    rows = [
        {"scored_at": datetime(2026, 1, 1, tzinfo=utc), "first_intervention_at": datetime(2026, 1, 3, tzinfo=utc)},
        {"scored_at": datetime(2026, 1, 5, tzinfo=utc), "first_intervention_at": datetime(2026, 1, 6, 12, tzinfo=utc)},
        {"scored_at": datetime(2026, 1, 8, tzinfo=utc), "first_intervention_at": None},
    ]
    assert time_to_first_intervention_days(rows) == pytest.approx(1.75)


def test_follow_up_completion_counts_only_due_followups():
    rows = [
        {"follow_up_due": True, "follow_up_completed": True},
        {"follow_up_due": True, "follow_up_completed": False},
        {"follow_up_due": False, "follow_up_completed": False},
    ]
    assert follow_up_completion_rate(rows) == 0.5


def test_tuition_exposure_is_estimated_only_for_currently_elevated_risk():
    rows = [
        {"risk_tier": "high", "synthetic_net_tuition_next_term": 7000},
        {"risk_tier": "medium", "synthetic_net_tuition_next_term": 5000},
        {"risk_tier": "low", "synthetic_net_tuition_next_term": 9000},
    ]
    assert tuition_exposure_estimate(rows) == {
        "amount": 12000.0,
        "is_estimate": True,
        "label": "estimated next-term net tuition exposure",
    }
