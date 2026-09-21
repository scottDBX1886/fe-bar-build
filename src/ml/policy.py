"""Dependency-light model policy and evaluation functions."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence


EXCLUDED_FEATURES = frozenset(
    {
        "student_id",
        "advisor_id",
        "feature_as_of",
        "max_feature_event_at",
        "label_observed_at",
        "label_term_code",
        "outcome_id",
        "stopout_label",
        "outcome_status",
        "synthetic_age_band",
        "synthetic_gender",
        "synthetic_first_generation",
        "synthetic_race_ethnicity",
        "incident_cohort",
        "synthetic_net_tuition_next_term",
    }
)


def chronological_split(
    rows: Iterable[Mapping[str, Any]], timestamp_column: str
) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]]]:
    """Use the latest distinct snapshot as validation and all prior snapshots as training."""
    materialized = list(rows)
    periods = sorted({row[timestamp_column] for row in materialized})
    if len(periods) < 2:
        raise ValueError("chronological split requires at least two distinct periods")
    boundary = periods[-1]
    return (
        [row for row in materialized if row[timestamp_column] < boundary],
        [row for row in materialized if row[timestamp_column] == boundary],
    )


def feature_columns(columns: Iterable[str]) -> list[str]:
    """Return model-eligible fields in source order."""
    return [column for column in columns if column not in EXCLUDED_FEATURES]


def _validate_binary_inputs(y_true: Sequence[int], scores: Sequence[float]) -> None:
    if len(y_true) != len(scores) or not y_true:
        raise ValueError("labels and scores must be nonempty and equal length")
    if any(label not in (0, 1) for label in y_true):
        raise ValueError("labels must be binary")


def pr_auc(y_true: Sequence[int], scores: Sequence[float]) -> float:
    """Compute non-interpolated average precision, a PR-AUC summary."""
    _validate_binary_inputs(y_true, scores)
    positives = sum(y_true)
    if positives == 0:
        return 0.0
    ranked = sorted(enumerate(scores), key=lambda item: (-item[1], item[0]))
    true_positives = 0
    precision_at_positive: list[float] = []
    for rank, (index, _) in enumerate(ranked, start=1):
        if y_true[index] == 1:
            true_positives += 1
            precision_at_positive.append(true_positives / rank)
    return sum(precision_at_positive) / positives


def top_k_metrics(
    y_true: Sequence[int], scores: Sequence[float], *, k: int
) -> dict[str, float | int]:
    """Measure case-finding performance at a fixed advisor capacity."""
    _validate_binary_inputs(y_true, scores)
    if k < 1 or k > len(y_true):
        raise ValueError("k must be between one and the number of rows")
    selected = sorted(range(len(scores)), key=lambda index: (-scores[index], index))[:k]
    true_positives = sum(y_true[index] for index in selected)
    positives = sum(y_true)
    return {
        "k": k,
        "recall": true_positives / positives if positives else 0.0,
        "precision": true_positives / k,
    }


def calibration_error(
    y_true: Sequence[int], scores: Sequence[float], *, bins: int = 10
) -> float:
    """Compute weighted expected calibration error over equal-width bins."""
    _validate_binary_inputs(y_true, scores)
    if bins < 1 or any(score < 0.0 or score > 1.0 for score in scores):
        raise ValueError("bins must be positive and scores must be probabilities")
    grouped: dict[int, list[int]] = defaultdict(list)
    for index, score in enumerate(scores):
        grouped[min(int(score * bins), bins - 1)].append(index)
    total = len(y_true)
    return sum(
        (len(indices) / total)
        * abs(
            sum(scores[index] for index in indices) / len(indices)
            - sum(y_true[index] for index in indices) / len(indices)
        )
        for indices in grouped.values()
    )


def cohort_error_rates(
    y_true: Sequence[int], y_pred: Sequence[int], cohorts: Sequence[str]
) -> dict[str, dict[str, float | int]]:
    """Report per-cohort FPR and FNR for fairness auditing, not model inputs."""
    if not y_true or len(y_true) != len(y_pred) or len(y_true) != len(cohorts):
        raise ValueError("labels, predictions, and cohorts must be nonempty and equal length")
    result: dict[str, dict[str, float | int]] = {}
    for cohort in sorted(set(cohorts)):
        indices = [index for index, value in enumerate(cohorts) if value == cohort]
        negatives = sum(y_true[index] == 0 for index in indices)
        positives = sum(y_true[index] == 1 for index in indices)
        false_positives = sum(y_true[index] == 0 and y_pred[index] == 1 for index in indices)
        false_negatives = sum(y_true[index] == 1 and y_pred[index] == 0 for index in indices)
        result[cohort] = {
            "count": len(indices),
            "false_positive_rate": false_positives / negatives if negatives else 0.0,
            "false_negative_rate": false_negatives / positives if positives else 0.0,
        }
    return result


def risk_tier(score: float) -> str:
    """Map a probability to a stable operational tier."""
    if score < 0.0 or score > 1.0:
        raise ValueError("risk score must be between zero and one")
    if score >= 0.6:
        return "high"
    if score >= 0.3:
        return "medium"
    return "low"
