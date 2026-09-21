from datetime import date, datetime

from src.pipelines.silver_features import (
    build_point_in_time_features,
    deduplicate_records,
    label_feature_as_of,
    reject_orphan_records,
)


def test_deduplication_uses_event_time_then_ingestion_time() -> None:
    records = [
        {"event_id": "E1", "event_at": datetime(2026, 9, 20, 9), "_ingested_at": datetime(2026, 9, 20, 10), "value": "old"},
        {"event_id": "E1", "event_at": datetime(2026, 9, 20, 9), "_ingested_at": datetime(2026, 9, 20, 11), "value": "winner"},
        {"event_id": "E2", "event_at": datetime(2026, 9, 19, 9), "_ingested_at": datetime(2026, 9, 20, 10), "value": "other"},
    ]

    deduplicated = deduplicate_records(
        records,
        key="event_id",
        event_time="event_at",
    )

    assert [row["event_id"] for row in deduplicated] == ["E1", "E2"]
    assert deduplicated[0]["value"] == "winner"


def test_orphan_child_records_are_rejected() -> None:
    records = [
        {"event_id": "E1", "student_id": "STU-1"},
        {"event_id": "E2", "student_id": "STU-MISSING"},
    ]

    accepted, rejected = reject_orphan_records(records, {"STU-1"})

    assert [row["event_id"] for row in accepted] == ["E1"]
    assert rejected == [{"event_id": "E2", "student_id": "STU-MISSING"}]


def test_point_in_time_features_exclude_future_and_stale_events() -> None:
    feature_as_of = datetime(2026, 9, 21, 23, 59, 59)
    attendance = [
        {"event_at": datetime(2026, 9, 1, 9), "present_flag": True},
        {"event_at": datetime(2026, 9, 20, 9), "present_flag": False},
        {"event_at": datetime(2026, 8, 20, 9), "present_flag": True},
        {"event_at": datetime(2026, 9, 22, 9), "present_flag": True},
    ]
    engagement = [
        {"event_at": datetime(2026, 9, 18, 14), "event_type": "LMS_LOGIN", "event_status": "COMPLETED"},
        {"event_at": datetime(2026, 9, 19, 14), "event_type": "ASSIGNMENT", "event_status": "MISSED"},
        {"event_at": datetime(2026, 6, 1, 14), "event_type": "SUPPORT", "event_status": "COMPLETED"},
        {"event_at": datetime(2026, 9, 10, 14), "event_type": "SUPPORT", "event_status": "COMPLETED"},
        {"event_at": datetime(2026, 9, 22, 14), "event_type": "ASSIGNMENT", "event_status": "MISSED"},
    ]
    financial = [
        {"event_at": datetime(2026, 9, 15), "balance_amount": 600.0, "balance_band": "MEDIUM", "financial_hold_flag": False},
        {"event_at": datetime(2026, 9, 20), "balance_amount": 3000.0, "balance_band": "HIGH", "financial_hold_flag": True},
        {"event_at": datetime(2026, 9, 22), "balance_amount": 0.0, "balance_band": "LOW", "financial_hold_flag": False},
    ]
    enrollments = [
        {"term_census_date": date(2025, 9, 8), "credits_attempted": 15, "credits_completed": 12, "cumulative_gpa": 2.8, "course_withdrawal_flag": True},
        {"term_census_date": date(2026, 1, 26), "credits_attempted": 12, "credits_completed": 12, "cumulative_gpa": 3.0, "course_withdrawal_flag": False},
        {"term_census_date": date(2026, 9, 22), "credits_attempted": 18, "credits_completed": 18, "cumulative_gpa": 3.4, "course_withdrawal_flag": False},
    ]

    features = build_point_in_time_features(
        feature_as_of=feature_as_of,
        attendance=attendance,
        engagement=engagement,
        financial=financial,
        enrollments=enrollments,
    )

    assert features["attendance_rate_28d"] == 0.5
    assert features["missed_assignments_28d"] == 1
    assert features["days_since_lms_activity"] == 3
    assert features["support_interactions_90d"] == 1
    assert features["financial_hold_flag"] is True
    assert features["current_balance_band"] == "HIGH"
    assert features["credits_attempted_current"] == 12
    assert features["credits_completed_prior"] == 12
    assert features["attempted_credit_trend"] == -3
    assert features["cumulative_gpa"] == 3.0
    assert features["withdrawal_count_prior"] == 1
    assert features["max_feature_event_at"] <= feature_as_of


def test_no_activity_defaults_are_explicit() -> None:
    features = build_point_in_time_features(
        feature_as_of=datetime(2026, 9, 21, 23, 59, 59),
        attendance=[],
        engagement=[],
        financial=[],
        enrollments=[],
    )

    assert features["attendance_rate_28d"] == 0.0
    assert features["days_since_lms_activity"] == 999
    assert features["current_balance_band"] == "NONE"
    assert features["financial_hold_flag"] is False
    assert features["max_feature_event_at"] is None


def test_label_cutoff_precedes_observation_date() -> None:
    assert label_feature_as_of(date(2026, 9, 7)) == datetime(2026, 9, 6, 23, 59, 59)
