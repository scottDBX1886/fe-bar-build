"""Reusable Spark-column rules for Bronze acceptance and quarantine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F


@dataclass(frozen=True)
class BronzeRuleSet:
    primary_key: str
    event_time: str
    requires_student_id: bool = True


@dataclass(frozen=True)
class Classification:
    critical_valid: bool
    recoverable_valid: bool
    violation_reason: str | None


RULES = {
    "students": BronzeRuleSet("student_id", "record_effective_at", False),
    "enrollments": BronzeRuleSet("enrollment_id", "term_census_date"),
    "attendance_events": BronzeRuleSet("attendance_event_id", "event_at"),
    "engagement_events": BronzeRuleSet("engagement_event_id", "event_at"),
    "financial_events": BronzeRuleSet("financial_event_id", "event_at"),
    "student_outcomes": BronzeRuleSet("outcome_id", "next_term_census_date"),
}

ENGAGEMENT_EVENT_TYPES = ("LMS_LOGIN", "ASSIGNMENT", "ADVISING", "SUPPORT")


def _present(value: object) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def _as_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else None


def classify_record(
    dataset: str,
    record: Mapping[str, Any],
    *,
    today: date,
) -> Classification:
    """Classify one record with the same ordered rules used by Spark."""
    try:
        rules = RULES[dataset]
    except KeyError as error:
        raise ValueError(f"Unknown Bronze dataset: {dataset}") from error

    if not _present(record.get(rules.primary_key)):
        return Classification(False, False, "MISSING_PRIMARY_KEY")
    event_date = _as_date(record.get(rules.event_time))
    if event_date is None:
        return Classification(False, False, "INVALID_EVENT_TIMESTAMP")

    checks: list[tuple[str, bool]] = []
    if rules.requires_student_id:
        checks.append(("MISSING_STUDENT_ID", _present(record.get("student_id"))))
    run_date = _as_date(record.get("run_date"))
    checks.extend(
        [
            ("INVALID_RUN_DATE", run_date is not None and run_date <= today),
            (
                "EVENT_AFTER_RUN_DATE",
                run_date is not None and event_date <= run_date,
            ),
        ]
    )
    if dataset == "enrollments":
        gpa = record.get("cumulative_gpa")
        checks.append(
            ("GPA_OUT_OF_RANGE", isinstance(gpa, (int, float)) and 0 <= gpa <= 4)
        )
    if dataset == "financial_events":
        balance = record.get("balance_amount")
        checks.append(
            ("NEGATIVE_BALANCE", isinstance(balance, (int, float)) and balance >= 0)
        )
    if dataset == "engagement_events":
        checks.append(
            ("UNKNOWN_EVENT_TYPE", record.get("event_type") in ENGAGEMENT_EVENT_TYPES)
        )

    for reason, valid in checks:
        if not valid:
            return Classification(True, False, reason)
    return Classification(True, True, None)


def _nonempty(column_name: str) -> Column:
    return F.col(column_name).isNotNull() & (F.trim(F.col(column_name)) != "")


def _valid_or_false(condition: Column) -> Column:
    return F.coalesce(condition, F.lit(False))


def apply_quality_rules(frame: DataFrame, dataset: str) -> DataFrame:
    """Add critical/recoverable validity and one deterministic violation reason."""
    try:
        rules = RULES[dataset]
    except KeyError as error:
        raise ValueError(f"Unknown Bronze dataset: {dataset}") from error

    primary_key_valid = _nonempty(rules.primary_key)
    event_time_valid = F.col(rules.event_time).isNotNull()
    critical_valid = primary_key_valid & event_time_valid

    run_date_valid = F.col("run_date").isNotNull() & (
        F.col("run_date") <= F.current_date()
    )
    event_not_after_run_date = F.to_date(F.col(rules.event_time)) <= F.col("run_date")

    recoverable_checks: list[tuple[str, Column]] = [
        ("INVALID_RUN_DATE", run_date_valid),
        ("EVENT_AFTER_RUN_DATE", event_not_after_run_date),
    ]
    if rules.requires_student_id:
        recoverable_checks.insert(0, ("MISSING_STUDENT_ID", _nonempty("student_id")))
    if dataset == "enrollments":
        recoverable_checks.append(
            ("GPA_OUT_OF_RANGE", F.col("cumulative_gpa").between(0.0, 4.0))
        )
    if dataset == "financial_events":
        recoverable_checks.append(("NEGATIVE_BALANCE", F.col("balance_amount") >= 0.0))
    if dataset == "engagement_events":
        recoverable_checks.append(
            ("UNKNOWN_EVENT_TYPE", F.col("event_type").isin(*ENGAGEMENT_EVENT_TYPES))
        )

    recoverable_valid = F.lit(True)
    for _, condition in recoverable_checks:
        recoverable_valid = recoverable_valid & _valid_or_false(condition)

    reason = (
        F.when(~primary_key_valid, F.lit("MISSING_PRIMARY_KEY"))
        .when(~event_time_valid, F.lit("INVALID_EVENT_TIMESTAMP"))
    )
    for label, condition in recoverable_checks:
        reason = reason.when(~_valid_or_false(condition), F.lit(label))

    return (
        frame.withColumn("_is_critical_valid", _valid_or_false(critical_valid))
        .withColumn(
            "_is_recoverable_valid",
            _valid_or_false(critical_valid & recoverable_valid),
        )
        .withColumn("_violation_reason", reason.otherwise(F.lit(None).cast("string")))
    )
