"""Pure point-in-time feature contracts shared by tests and Silver design."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Iterable, Mapping


Record = Mapping[str, Any]


def _timestamp(value: date | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, time.min)


def deduplicate_records(
    records: Iterable[Record],
    *,
    key: str,
    event_time: str,
) -> list[Record]:
    """Keep the deterministic latest record for each business key."""
    winners: dict[Any, Record] = {}
    for record in records:
        candidate_order = (
            _timestamp(record[event_time]),
            record.get("_ingested_at") or datetime.min,
            record.get("_source_path") or "",
        )
        current = winners.get(record[key])
        if current is None:
            winners[record[key]] = record
            continue
        current_order = (
            _timestamp(current[event_time]),
            current.get("_ingested_at") or datetime.min,
            current.get("_source_path") or "",
        )
        if candidate_order > current_order:
            winners[record[key]] = record
    return [winners[value] for value in sorted(winners)]


def reject_orphan_records(
    records: Iterable[Record], student_ids: set[str]
) -> tuple[list[Record], list[Record]]:
    accepted: list[Record] = []
    rejected: list[Record] = []
    for record in records:
        (accepted if record.get("student_id") in student_ids else rejected).append(record)
    return accepted, rejected


def label_feature_as_of(label_observed_on: date) -> datetime:
    return datetime.combine(label_observed_on - timedelta(days=1), time.max.replace(microsecond=0))


def _eligible(records: Iterable[Record], field: str, cutoff: datetime) -> list[Record]:
    return [record for record in records if _timestamp(record[field]) <= cutoff]


def build_point_in_time_features(
    *,
    feature_as_of: datetime,
    attendance: Iterable[Record],
    engagement: Iterable[Record],
    financial: Iterable[Record],
    enrollments: Iterable[Record],
) -> dict[str, Any]:
    """Calculate leakage-safe student signals from facts known by the cutoff."""
    attendance_rows = _eligible(attendance, "event_at", feature_as_of)
    engagement_rows = _eligible(engagement, "event_at", feature_as_of)
    financial_rows = _eligible(financial, "event_at", feature_as_of)
    enrollment_rows = _eligible(enrollments, "term_census_date", feature_as_of)

    attendance_start = feature_as_of - timedelta(days=28)
    recent_attendance = [
        row for row in attendance_rows if _timestamp(row["event_at"]) > attendance_start
    ]
    attendance_rate = (
        sum(bool(row["present_flag"]) for row in recent_attendance) / len(recent_attendance)
        if recent_attendance
        else 0.0
    )

    recent_engagement_start = feature_as_of - timedelta(days=28)
    missed_assignments = sum(
        1
        for row in engagement_rows
        if _timestamp(row["event_at"]) > recent_engagement_start
        and row.get("event_type") == "ASSIGNMENT"
        and row.get("event_status") == "MISSED"
    )
    last_lms = max(
        (
            _timestamp(row["event_at"])
            for row in engagement_rows
            if row.get("event_type") == "LMS_LOGIN"
        ),
        default=None,
    )
    support_start = feature_as_of - timedelta(days=90)
    support_interactions = sum(
        1
        for row in engagement_rows
        if _timestamp(row["event_at"]) > support_start
        and row.get("event_type") == "SUPPORT"
    )

    latest_financial = max(
        financial_rows,
        key=lambda row: _timestamp(row["event_at"]),
        default=None,
    )
    ordered_enrollments = sorted(
        enrollment_rows, key=lambda row: _timestamp(row["term_census_date"])
    )
    current_enrollment = ordered_enrollments[-1] if ordered_enrollments else None
    prior_enrollments = ordered_enrollments[:-1]
    previous_enrollment = prior_enrollments[-1] if prior_enrollments else None

    used_times = [
        *(_timestamp(row["event_at"]) for row in attendance_rows),
        *(_timestamp(row["event_at"]) for row in engagement_rows),
        *(_timestamp(row["event_at"]) for row in financial_rows),
        *(_timestamp(row["term_census_date"]) for row in enrollment_rows),
    ]

    return {
        "attendance_rate_28d": round(attendance_rate, 6),
        "missed_assignments_28d": missed_assignments,
        "days_since_lms_activity": (
            (feature_as_of.date() - last_lms.date()).days if last_lms else 999
        ),
        "support_interactions_90d": support_interactions,
        "financial_hold_flag": bool(
            latest_financial and latest_financial.get("financial_hold_flag")
        ),
        "current_balance_band": (
            latest_financial.get("balance_band", "NONE") if latest_financial else "NONE"
        ),
        "credits_attempted_current": (
            int(current_enrollment.get("credits_attempted", 0)) if current_enrollment else 0
        ),
        "credits_completed_prior": sum(
            int(row.get("credits_completed", 0)) for row in prior_enrollments
        ),
        "attempted_credit_trend": (
            int(current_enrollment.get("credits_attempted", 0))
            - int(previous_enrollment.get("credits_attempted", 0))
            if current_enrollment and previous_enrollment
            else 0
        ),
        "cumulative_gpa": (
            float(current_enrollment.get("cumulative_gpa", 0.0))
            if current_enrollment
            else 0.0
        ),
        "withdrawal_count_prior": sum(
            bool(row.get("course_withdrawal_flag")) for row in prior_enrollments
        ),
        "max_feature_event_at": max(used_times, default=None),
    }
