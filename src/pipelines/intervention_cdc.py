"""Deterministic reconstruction contracts for Lakebase CDC history."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Mapping


Row = Mapping[str, Any]


def _position(row: Row) -> tuple[int, int]:
    return int(row["_pg_lsn"]), int(row["_sort_by"])


def _delivery_key(row: Row, primary_key: str) -> tuple[Any, str, int, int]:
    lsn, sort_by = _position(row)
    return row[primary_key], str(row["_pg_change_type"]), lsn, sort_by


def reconstruct_current_interventions(rows: Iterable[Row]) -> list[Row]:
    current: dict[Any, Row] = {}
    for row in reconstruct_intervention_audit(rows):
        change_type = row["_pg_change_type"]
        if change_type == "update_preimage":
            continue
        key = row["intervention_id"]
        if change_type == "delete":
            current.pop(key, None)
        elif change_type in {"insert", "update_postimage"}:
            current[key] = row
    return [current[key] for key in sorted(current, key=repr)]


def reconstruct_intervention_audit(rows: Iterable[Row]) -> list[Row]:
    unique: dict[tuple[Any, str, int, int], Row] = {}
    for row in rows:
        unique.setdefault(_delivery_key(row, "intervention_id"), row)
    return sorted(unique.values(), key=_position)


def reconstruct_event_history(rows: Iterable[Row]) -> list[Row]:
    events: dict[Any, Row] = {}
    for row in sorted(rows, key=_position):
        if row["_pg_change_type"] == "insert":
            events.setdefault(row["event_id"], row)
    return sorted(events.values(), key=_position)


def summarize_student_interventions(
    current_rows: Iterable[Row], event_rows: Iterable[Row], *, now: datetime
) -> list[dict[str, Any]]:
    event_types: dict[Any, set[str]] = {}
    for event in event_rows:
        event_types.setdefault(event["intervention_id"], set()).add(
            str(event["event_type"])
        )

    by_student: dict[str, list[Row]] = {}
    for row in current_rows:
        by_student.setdefault(str(row["student_id"]), []).append(row)

    summaries = []
    for student_id in sorted(by_student):
        interventions = by_student[student_id]
        selected = max(
            interventions,
            key=lambda row: (
                row["status"] != "closed",
                row["updated_at"],
                int(row["version"]),
                *_position(row),
            ),
        )
        follow_up_due = any(
            row["status"] != "closed"
            and row.get("next_follow_up_at") is not None
            and row["next_follow_up_at"] <= now
            for row in interventions
        )
        follow_up_completed = any(
            {"follow_up_scheduled", "closed"}.issubset(
                event_types.get(row["intervention_id"], set())
            )
            for row in interventions
        )
        summaries.append(
            {
                "student_id": student_id,
                "intervention_status": selected["status"],
                "intervention_priority": selected["priority"],
                "first_intervention_at": min(
                    row["created_at"] for row in interventions
                ),
                "follow_up_due": follow_up_due,
                "follow_up_completed": follow_up_completed,
            }
        )
    return summaries


def intervention_audit_dataframe(history):
    """Deduplicate CDC delivery while retaining every ordered change image."""
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    delivery = Window.partitionBy(
        "intervention_id", "_pg_change_type", "_pg_lsn", "_sort_by"
    ).orderBy(F.col("_timestamp").desc())
    return (
        history.withColumn("_delivery_rank", F.row_number().over(delivery))
        .filter(F.col("_delivery_rank") == 1)
        .drop("_delivery_rank")
    )


def current_interventions_dataframe(history):
    """Select the last state-bearing image for each non-deleted intervention."""
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    state_order = Window.partitionBy("intervention_id").orderBy(
        F.col("_pg_lsn").desc(), F.col("_sort_by").desc()
    )
    return (
        intervention_audit_dataframe(history)
        .filter(F.col("_pg_change_type") != "update_preimage")
        .withColumn("_state_rank", F.row_number().over(state_order))
        .filter(
            (F.col("_state_rank") == 1) & (F.col("_pg_change_type") != "delete")
        )
        .drop("_state_rank")
    )


def intervention_event_history_dataframe(history):
    """Return one immutable insert image per intervention event."""
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    event_order = Window.partitionBy("event_id").orderBy(
        F.col("_pg_lsn").desc(), F.col("_sort_by").desc()
    )
    return (
        history.filter(F.col("_pg_change_type") == "insert")
        .withColumn("_event_rank", F.row_number().over(event_order))
        .filter(F.col("_event_rank") == 1)
        .drop("_event_rank")
    )


def student_intervention_summary_dataframe(current, events):
    """Collapse intervention state and event facts to one operational row per student."""
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    event_flags = events.groupBy("intervention_id").agg(
        F.max(
            F.when(F.col("event_type") == "follow_up_scheduled", 1).otherwise(0)
        ).alias("_follow_up_scheduled"),
        F.max(F.when(F.col("event_type") == "closed", 1).otherwise(0)).alias(
            "_closed_event"
        ),
    )
    enriched = current.join(event_flags, "intervention_id", "left").fillna(
        {"_follow_up_scheduled": 0, "_closed_event": 0}
    )
    selected = Window.partitionBy("student_id").orderBy(
        F.when(F.col("status") != "closed", 1).otherwise(0).desc(),
        F.col("updated_at").desc(),
        F.col("version").desc(),
        F.col("_pg_lsn").desc(),
        F.col("_sort_by").desc(),
    )
    student = Window.partitionBy("student_id")
    return (
        enriched.withColumn("_selected_rank", F.row_number().over(selected))
        .withColumn("first_intervention_at", F.min("created_at").over(student))
        .withColumn(
            "follow_up_due",
            F.max(
                F.when(
                    (F.col("status") != "closed")
                    & F.col("next_follow_up_at").isNotNull()
                    & (F.col("next_follow_up_at") <= F.current_timestamp()),
                    1,
                ).otherwise(0)
            ).over(student).cast("boolean"),
        )
        .withColumn(
            "follow_up_completed",
            F.max(
                F.when(
                    (F.col("_follow_up_scheduled") == 1)
                    & (F.col("_closed_event") == 1),
                    1,
                ).otherwise(0)
            ).over(student).cast("boolean"),
        )
        .filter(F.col("_selected_rank") == 1)
        .select(
            "student_id",
            F.col("status").alias("intervention_status"),
            F.col("priority").alias("intervention_priority"),
            "first_intervention_at",
            "follow_up_due",
            "follow_up_completed",
        )
    )
