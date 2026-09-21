from datetime import date

import pytest

from src.synthetic.contracts import (
    DATASET_CONTRACTS,
    MODEL_FEATURES,
    PROTECTED_AUDIT_FIELDS,
    is_incident_cohort,
    risk_propensity_score,
    source_partition_path,
    stopout_probability,
    student_id,
)
from src.synthetic.generate import build_generation_plan


EXPECTED_DATASETS = {
    "students",
    "enrollments",
    "attendance_events",
    "engagement_events",
    "financial_events",
    "student_outcomes",
}


def test_dataset_contracts_define_keys_grain_and_event_time() -> None:
    assert set(DATASET_CONTRACTS) == EXPECTED_DATASETS

    for contract in DATASET_CONTRACTS.values():
        assert contract.primary_key
        assert contract.grain
        assert contract.expected_rows > 0
        assert contract.event_time_column


def test_child_contracts_reference_students() -> None:
    child_names = EXPECTED_DATASETS - {"students"}

    for name in child_names:
        assert DATASET_CONTRACTS[name].foreign_keys["student_id"] == (
            "students",
            "student_id",
        )


def test_student_id_is_stable_and_unique_for_adjacent_indexes() -> None:
    first = student_id(17)

    assert first == student_id(17)
    assert first != student_id(18)
    assert first == "STU-000017"


def test_incident_cohort_is_deterministic_and_non_uniform() -> None:
    membership = [is_incident_cohort(index, seed=20260921) for index in range(20_000)]

    assert membership == [
        is_incident_cohort(index, seed=20260921) for index in range(20_000)
    ]
    assert 200 <= sum(membership) <= 400


def test_risk_propensity_is_deterministic_bounded_and_varied() -> None:
    scores = [risk_propensity_score(index, seed=20260921) for index in range(1_000)]

    assert scores == [
        risk_propensity_score(index, seed=20260921) for index in range(1_000)
    ]
    assert all(0.0 <= score < 1.0 for score in scores)
    assert len(set(scores)) > 900


def test_incident_signals_raise_stopout_probability() -> None:
    stable = stopout_probability(
        attendance_rate=0.94,
        missed_assignments=0,
        financial_hold=False,
        cumulative_gpa=3.2,
        days_since_lms_activity=1,
    )
    incident = stopout_probability(
        attendance_rate=0.58,
        missed_assignments=4,
        financial_hold=True,
        cumulative_gpa=2.1,
        days_since_lms_activity=12,
    )

    assert 0.0 <= stable <= 1.0
    assert 0.0 <= incident <= 1.0
    assert incident - stable >= 0.45


def test_model_features_exclude_protected_audit_fields() -> None:
    assert set(MODEL_FEATURES).isdisjoint(PROTECTED_AUDIT_FIELDS)


def test_source_partition_path_is_immutable_by_dataset_and_run_date() -> None:
    path = source_partition_path(
        catalog="serverless_stable_febar_scottj_catalog",
        schema="student_retention_bronze",
        volume="raw_data",
        dataset="attendance_events",
        run_date=date(2026, 9, 21),
    )

    assert path == (
        "/Volumes/serverless_stable_febar_scottj_catalog/"
        "student_retention_bronze/raw_data/attendance_events/run_date=2026-09-21"
    )


@pytest.mark.parametrize("dataset", ["unknown", "student-events"])
def test_source_partition_path_rejects_unknown_dataset(dataset: str) -> None:
    with pytest.raises(ValueError, match="dataset"):
        source_partition_path(
            catalog="serverless_stable_febar_scottj_catalog",
            schema="student_retention_bronze",
            volume="raw_data",
            dataset=dataset,
            run_date=date(2026, 9, 21),
        )


def test_bootstrap_generation_plan_matches_contract_counts() -> None:
    plan = build_generation_plan(date(2026, 9, 21), bootstrap=True)

    assert plan.run_date == date(2026, 9, 21)
    assert plan.row_counts == {
        name: contract.expected_rows for name, contract in DATASET_CONTRACTS.items()
    }


def test_daily_generation_plan_only_adds_incremental_events() -> None:
    plan = build_generation_plan(date(2026, 9, 22), bootstrap=False)

    assert plan.row_counts == {
        "students": 0,
        "enrollments": 0,
        "attendance_events": 10_000,
        "engagement_events": 8_000,
        "financial_events": 1_000,
        "student_outcomes": 0,
    }
