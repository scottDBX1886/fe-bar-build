from datetime import datetime

import pytest

from src.ml.policy import (
    calibration_error,
    chronological_split,
    cohort_error_rates,
    feature_columns,
    pr_auc,
    risk_tier,
    top_k_metrics,
)


def test_chronological_split_never_trains_on_validation_period():
    rows = [
        {"feature_as_of": datetime(2026, 9, 6), "value": 2},
        {"feature_as_of": datetime(2026, 1, 25), "value": 1},
        {"feature_as_of": datetime(2026, 9, 6), "value": 3},
    ]

    train, validation = chronological_split(rows, "feature_as_of")

    assert {row["value"] for row in train} == {1}
    assert {row["value"] for row in validation} == {2, 3}
    assert max(row["feature_as_of"] for row in train) < min(
        row["feature_as_of"] for row in validation
    )


def test_feature_policy_excludes_ids_labels_timestamps_and_protected_attributes():
    columns = [
        "student_id", "feature_as_of", "stopout_label", "label_observed_at",
        "synthetic_gender", "synthetic_race_ethnicity", "advisor_id",
        "attendance_rate_28d", "cumulative_gpa", "program_code",
    ]

    assert feature_columns(columns) == [
        "attendance_rate_28d", "cumulative_gpa", "program_code"
    ]


def test_pr_auc_uses_precision_recall_curve_for_imbalanced_classification():
    assert pr_auc([1, 0, 1, 0], [0.9, 0.8, 0.7, 0.1]) == pytest.approx(5 / 6)


def test_top_k_metrics_are_deterministic_at_exact_capacity():
    result = top_k_metrics([1, 0, 1, 0, 1], [0.9, 0.8, 0.7, 0.6, 0.5], k=2)
    assert result == {"k": 2, "recall": pytest.approx(1 / 3), "precision": 0.5}


def test_calibration_error_is_weighted_by_bin_population():
    assert calibration_error([0, 0, 1, 1], [0.1, 0.2, 0.7, 0.9], bins=2) == pytest.approx(0.175)


def test_cohort_error_rates_report_false_positive_and_false_negative_rates():
    rates = cohort_error_rates(
        [0, 1, 0, 1], [1, 0, 0, 1], ["A", "A", "B", "B"]
    )
    assert rates == {
        "A": {"count": 2, "false_positive_rate": 1.0, "false_negative_rate": 1.0},
        "B": {"count": 2, "false_positive_rate": 0.0, "false_negative_rate": 0.0},
    }


@pytest.mark.parametrize(
    ("score", "expected"),
    [(0.0, "low"), (0.2999, "low"), (0.3, "medium"), (0.5999, "medium"), (0.6, "high"), (1.0, "high")],
)
def test_risk_tier_boundaries(score, expected):
    assert risk_tier(score) == expected


def test_risk_tier_rejects_invalid_probability():
    with pytest.raises(ValueError):
        risk_tier(1.01)
