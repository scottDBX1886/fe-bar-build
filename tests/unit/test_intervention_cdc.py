from __future__ import annotations

from datetime import datetime, timezone

from src.pipelines.intervention_cdc import (
    reconstruct_current_interventions,
    reconstruct_event_history,
    reconstruct_intervention_audit,
    summarize_student_interventions,
)


def _change(
    intervention_id: bytes,
    change_type: str,
    lsn: int,
    sort_by: int,
    *,
    version: int,
    status: str,
) -> dict[str, object]:
    return {
        "intervention_id": intervention_id,
        "_pg_change_type": change_type,
        "_pg_lsn": lsn,
        "_sort_by": sort_by,
        "version": version,
        "status": status,
    }


def test_current_state_uses_lsn_and_sort_key_for_update_postimages():
    intervention_id = b"intervention-a"
    rows = [
        _change(intervention_id, "update_postimage", 20, 4, version=2, status="in_progress"),
        _change(intervention_id, "insert", 10, 1, version=1, status="open"),
        _change(intervention_id, "update_preimage", 20, 3, version=1, status="open"),
    ]

    assert reconstruct_current_interventions(rows) == [
        _change(intervention_id, "update_postimage", 20, 4, version=2, status="in_progress")
    ]


def test_current_state_removes_deleted_keys_and_deduplicates_delivery():
    deleted_id = b"deleted"
    retained_id = b"retained"
    retained = _change(retained_id, "insert", 15, 2, version=1, status="open")
    deletion = _change(deleted_id, "delete", 30, 6, version=2, status="closed")
    rows = [
        deletion,
        retained,
        _change(deleted_id, "insert", 10, 1, version=1, status="open"),
        dict(retained),
        dict(deletion),
    ]

    assert reconstruct_current_interventions(rows) == [retained]


def test_intervention_audit_retains_delete_and_orders_out_of_order_input():
    intervention_id = b"intervention-a"
    insert = _change(intervention_id, "insert", 10, 1, version=1, status="open")
    preimage = _change(
        intervention_id, "update_preimage", 20, 3, version=1, status="open"
    )
    postimage = _change(
        intervention_id, "update_postimage", 20, 4, version=2, status="closed"
    )
    deletion = _change(intervention_id, "delete", 30, 5, version=2, status="closed")

    assert reconstruct_intervention_audit(
        [deletion, postimage, dict(postimage), insert, preimage]
    ) == [insert, preimage, postimage, deletion]


def test_event_history_is_one_immutable_row_per_event_in_commit_order():
    first = {
        "event_id": 7,
        "intervention_id": b"intervention-a",
        "event_type": "created",
        "_pg_change_type": "insert",
        "_pg_lsn": 100,
        "_sort_by": 11,
    }
    second = {
        "event_id": 8,
        "intervention_id": b"intervention-a",
        "event_type": "closed",
        "_pg_change_type": "insert",
        "_pg_lsn": 120,
        "_sort_by": 12,
    }

    assert reconstruct_event_history([second, dict(first), first]) == [first, second]


def test_student_summary_prioritizes_active_work_and_tracks_follow_up_completion():
    utc = timezone.utc
    active_id = b"active"
    closed_id = b"closed"
    current = [
        {
            "intervention_id": closed_id,
            "student_id": "STU-1",
            "status": "closed",
            "priority": "urgent",
            "created_at": datetime(2026, 1, 1, tzinfo=utc),
            "updated_at": datetime(2026, 1, 5, tzinfo=utc),
            "next_follow_up_at": None,
            "version": 3,
            "_pg_lsn": 30,
            "_sort_by": 5,
        },
        {
            "intervention_id": active_id,
            "student_id": "STU-1",
            "status": "pending_follow_up",
            "priority": "high",
            "created_at": datetime(2026, 1, 2, tzinfo=utc),
            "updated_at": datetime(2026, 1, 4, tzinfo=utc),
            "next_follow_up_at": datetime(2026, 1, 9, tzinfo=utc),
            "version": 2,
            "_pg_lsn": 20,
            "_sort_by": 4,
        },
    ]
    events = [
        {"intervention_id": closed_id, "event_type": "follow_up_scheduled"},
        {"intervention_id": closed_id, "event_type": "closed"},
    ]

    assert summarize_student_interventions(
        current, events, now=datetime(2026, 1, 10, tzinfo=utc)
    ) == [
        {
            "student_id": "STU-1",
            "intervention_status": "pending_follow_up",
            "intervention_priority": "high",
            "first_intervention_at": datetime(2026, 1, 1, tzinfo=utc),
            "follow_up_due": True,
            "follow_up_completed": True,
        }
    ]
