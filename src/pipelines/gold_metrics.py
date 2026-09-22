"""Pure business-metric contracts used by governed Gold products."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence


ELEVATED_RISK_TIERS = frozenset({"medium", "high"})
ACTIVE_INTERVENTION_STATUSES = frozenset({"open", "in_progress", "completed"})


def retention_rate(outcomes: Sequence[str]) -> float:
    """Share of observed outcomes that are retained."""
    return (
        sum(outcome in {"PERSISTED", "RETAINED"} for outcome in outcomes) / len(outcomes)
        if outcomes
        else 0.0
    )


def at_risk_count(risk_tiers: Iterable[str]) -> int:
    """Count students currently assigned an elevated operational risk tier."""
    return sum(tier in ELEVATED_RISK_TIERS for tier in risk_tiers)


def top_k_caseload(rows: Iterable[Mapping[str, Any]], k: int) -> list[Mapping[str, Any]]:
    """Prioritize a bounded caseload deterministically by risk then student ID."""
    if k < 0:
        raise ValueError("k must not be negative")
    return sorted(rows, key=lambda row: (-float(row["risk_score"]), str(row["student_id"])))[:k]


def intervention_coverage(rows: Iterable[Mapping[str, Any]]) -> float:
    """Share of elevated-risk students with an active or completed intervention."""
    elevated = [row for row in rows if row["risk_tier"] in ELEVATED_RISK_TIERS]
    if not elevated:
        return 0.0
    covered = sum(row.get("intervention_status") in ACTIVE_INTERVENTION_STATUSES for row in elevated)
    return covered / len(elevated)


def time_to_first_intervention_days(rows: Iterable[Mapping[str, Any]]) -> float:
    """Average elapsed days from scoring to first intervention among contacted students."""
    elapsed = []
    for row in rows:
        first = row.get("first_intervention_at")
        if first is None:
            continue
        days = (first - row["scored_at"]).total_seconds() / 86_400
        if days >= 0:
            elapsed.append(days)
    return sum(elapsed) / len(elapsed) if elapsed else 0.0


def follow_up_completion_rate(rows: Iterable[Mapping[str, Any]]) -> float:
    """Share of due follow-ups marked complete."""
    due = [row for row in rows if bool(row.get("follow_up_due"))]
    return sum(bool(row.get("follow_up_completed")) for row in due) / len(due) if due else 0.0


def tuition_exposure_estimate(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Estimate next-term net tuition associated with currently elevated risk."""
    amount = sum(
        float(row.get("synthetic_net_tuition_next_term") or 0.0)
        for row in rows
        if row["risk_tier"] in ELEVATED_RISK_TIERS
    )
    return {
        "amount": amount,
        "is_estimate": True,
        "label": "estimated next-term net tuition exposure",
    }
