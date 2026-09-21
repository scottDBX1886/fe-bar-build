from datetime import date, datetime

import pytest

from src.pipelines.bronze_rules import classify_record


def classify(dataset: str, **record: object):
    return classify_record(dataset, record, today=date(2026, 9, 21))


def test_valid_enrollment_is_accepted() -> None:
    result = classify(
        "enrollments",
        enrollment_id="ENR-1",
        student_id="STU-1",
        term_census_date=date(2026, 9, 7),
        cumulative_gpa=3.2,
        run_date=date(2026, 9, 21),
    )

    assert result.critical_valid is True
    assert result.recoverable_valid is True
    assert result.violation_reason is None


@pytest.mark.parametrize("cumulative_gpa", [-0.1, 4.1])
def test_out_of_range_gpa_is_quarantined(cumulative_gpa: float) -> None:
    result = classify(
        "enrollments",
        enrollment_id="ENR-1",
        student_id="STU-1",
        term_census_date=date(2026, 9, 7),
        cumulative_gpa=cumulative_gpa,
        run_date=date(2026, 9, 21),
    )

    assert result.critical_valid is True
    assert result.recoverable_valid is False
    assert result.violation_reason == "GPA_OUT_OF_RANGE"


def test_negative_balance_is_quarantined() -> None:
    result = classify(
        "financial_events",
        financial_event_id="FIN-1",
        student_id="STU-1",
        event_at=datetime(2026, 9, 20, 12),
        balance_amount=-0.01,
        run_date=date(2026, 9, 21),
    )

    assert result.recoverable_valid is False
    assert result.violation_reason == "NEGATIVE_BALANCE"


def test_unknown_engagement_event_type_is_quarantined() -> None:
    result = classify(
        "engagement_events",
        engagement_event_id="ENG-1",
        student_id="STU-1",
        event_at=datetime(2026, 9, 20, 12),
        event_type="UNKNOWN",
        run_date=date(2026, 9, 21),
    )

    assert result.recoverable_valid is False
    assert result.violation_reason == "UNKNOWN_EVENT_TYPE"


def test_missing_foreign_student_id_is_quarantined() -> None:
    result = classify(
        "attendance_events",
        attendance_event_id="ATT-1",
        student_id=None,
        event_at=datetime(2026, 9, 20, 9),
        run_date=date(2026, 9, 21),
    )

    assert result.critical_valid is True
    assert result.recoverable_valid is False
    assert result.violation_reason == "MISSING_STUDENT_ID"


@pytest.mark.parametrize(
    ("event_id", "event_at", "reason"),
    [
        (None, datetime(2026, 9, 20, 9), "MISSING_PRIMARY_KEY"),
        ("ATT-1", None, "INVALID_EVENT_TIMESTAMP"),
    ],
)
def test_unsafe_attendance_record_is_pipeline_failing(
    event_id: str | None,
    event_at: datetime | None,
    reason: str,
) -> None:
    result = classify(
        "attendance_events",
        attendance_event_id=event_id,
        student_id="STU-1",
        event_at=event_at,
        run_date=date(2026, 9, 21),
    )

    assert result.critical_valid is False
    assert result.violation_reason == reason


def test_event_after_run_date_is_quarantined() -> None:
    result = classify(
        "attendance_events",
        attendance_event_id="ATT-1",
        student_id="STU-1",
        event_at=datetime(2026, 9, 22, 9),
        run_date=date(2026, 9, 21),
    )

    assert result.recoverable_valid is False
    assert result.violation_reason == "EVENT_AFTER_RUN_DATE"


def test_invalid_run_date_is_quarantined() -> None:
    result = classify(
        "students",
        student_id="STU-1",
        record_effective_at=datetime(2026, 9, 21),
        run_date=None,
    )

    assert result.critical_valid is True
    assert result.recoverable_valid is False
    assert result.violation_reason == "INVALID_RUN_DATE"


def test_unknown_dataset_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown Bronze dataset"):
        classify("unknown", id="1")
