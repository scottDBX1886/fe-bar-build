"""Synthetic source contracts and deterministic business-story helpers."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DatasetContract:
    primary_key: tuple[str, ...]
    foreign_keys: dict[str, tuple[str, str]]
    grain: str
    event_time_column: str
    expected_rows: int


_STUDENT_FOREIGN_KEY = {"student_id": ("students", "student_id")}

DATASET_CONTRACTS = {
    "students": DatasetContract(
        primary_key=("student_id",),
        foreign_keys={},
        grain="one current synthetic student",
        event_time_column="record_effective_at",
        expected_rows=20_000,
    ),
    "enrollments": DatasetContract(
        primary_key=("enrollment_id",),
        foreign_keys=_STUDENT_FOREIGN_KEY,
        grain="one student per academic term",
        event_time_column="term_census_date",
        expected_rows=60_000,
    ),
    "attendance_events": DatasetContract(
        primary_key=("attendance_event_id",),
        foreign_keys=_STUDENT_FOREIGN_KEY,
        grain="one student-course meeting",
        event_time_column="event_at",
        expected_rows=300_000,
    ),
    "engagement_events": DatasetContract(
        primary_key=("engagement_event_id",),
        foreign_keys=_STUDENT_FOREIGN_KEY,
        grain="one LMS or student-support interaction",
        event_time_column="event_at",
        expected_rows=250_000,
    ),
    "financial_events": DatasetContract(
        primary_key=("financial_event_id",),
        foreign_keys=_STUDENT_FOREIGN_KEY,
        grain="one student financial-status change",
        event_time_column="event_at",
        expected_rows=40_000,
    ),
    "student_outcomes": DatasetContract(
        primary_key=("outcome_id",),
        foreign_keys=_STUDENT_FOREIGN_KEY,
        grain="one student per label term",
        event_time_column="next_term_census_date",
        expected_rows=40_000,
    ),
}

PROTECTED_AUDIT_FIELDS = (
    "synthetic_age_band",
    "synthetic_gender",
    "synthetic_first_generation",
    "synthetic_race_ethnicity",
)

MODEL_FEATURES = (
    "attendance_rate_28d",
    "missed_assignments_28d",
    "days_since_lms_activity",
    "financial_hold_flag",
    "current_balance_band",
    "credits_attempted_current",
    "credits_completed_prior",
    "cumulative_gpa",
    "withdrawal_count_prior",
    "support_interactions_90d",
    "program_code",
    "academic_level",
    "residency_status",
)

_UC_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def student_id(index: int) -> str:
    if index < 0:
        raise ValueError("student index must be nonnegative")
    return f"STU-{index:06d}"


def is_incident_cohort(index: int, seed: int) -> bool:
    """Select a stable, dispersed cohort comprising about 1.5% of students."""
    bucket = (index * 1_103_515_245 + seed * 12_345) % 10_000
    return bucket < 150


def risk_propensity_score(index: int, seed: int) -> float:
    """Return a stable latent propensity used across signals and outcomes."""
    bucket = (index * 2_654_435_761 + seed * 2_246_822_519) % 10_000
    return bucket / 10_000.0


def stopout_probability(
    *,
    attendance_rate: float,
    missed_assignments: int,
    financial_hold: bool,
    cumulative_gpa: float,
    days_since_lms_activity: int,
) -> float:
    """Return a bounded synthetic label probability from pre-census signals."""
    log_odds = (
        -3.0
        + (0.85 - attendance_rate) * 5.0
        + missed_assignments * 0.35
        + int(financial_hold) * 0.9
        + max(0.0, 2.8 - cumulative_gpa) * 0.4
        + days_since_lms_activity * 0.06
    )
    return 1.0 / (1.0 + math.exp(-log_odds))


def source_partition_path(
    *,
    catalog: str,
    schema: str,
    volume: str,
    dataset: str,
    run_date: date,
) -> str:
    if dataset not in DATASET_CONTRACTS:
        raise ValueError(f"Unknown dataset: {dataset}")
    for label, identifier in (
        ("catalog", catalog),
        ("schema", schema),
        ("volume", volume),
    ):
        if not _UC_IDENTIFIER.fullmatch(identifier):
            raise ValueError(f"Invalid {label} identifier: {identifier}")
    return (
        f"/Volumes/{catalog}/{schema}/{volume}/{dataset}/"
        f"run_date={run_date.isoformat()}"
    )
