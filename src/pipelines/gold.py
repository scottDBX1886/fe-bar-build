"""Focused, governed Gold products for retention operations and analytics."""

from __future__ import annotations

from pyspark import pipelines as dp
from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

from intervention_cdc import (
    current_interventions_dataframe,
    intervention_audit_dataframe,
    intervention_event_history_dataframe,
    student_intervention_summary_dataframe,
)


CATALOG = spark.conf.get("retention.catalog")
SCHEMA_PREFIX = spark.conf.get("retention.schema_prefix")
SILVER_SCHEMA = f"{SCHEMA_PREFIX}_silver"
GOLD_SCHEMA = f"{SCHEMA_PREFIX}_gold"
CDC_SCHEMA = f"{SCHEMA_PREFIX}_cdc"
ADVISOR_ROW_FILTER = f"ROW FILTER {CATALOG}.{GOLD_SCHEMA}.advisor_row_filter ON (advisor_id)"


def _silver(table: str) -> str:
    return f"{CATALOG}.{SILVER_SCHEMA}.{table}"


def _gold(table: str) -> str:
    return f"{CATALOG}.{GOLD_SCHEMA}.{table}"


def _cdc(table: str) -> str:
    return f"{CATALOG}.{CDC_SCHEMA}.{table}"


def _intervention_audit() -> DataFrame:
    return intervention_audit_dataframe(
        spark.read.table(_cdc("lb_interventions_history"))
    )


def _current_interventions() -> DataFrame:
    return current_interventions_dataframe(
        spark.read.table(_cdc("lb_interventions_history"))
    )


def _intervention_events() -> DataFrame:
    return intervention_event_history_dataframe(
        spark.read.table(_cdc("lb_intervention_events_history"))
    )


@dp.materialized_view(
    name=_gold("intervention_state_history"),
    comment="Ordered Lakebase intervention CDC audit with duplicate delivery removed.",
    cluster_by=["advisor_id", "student_id", "_pg_lsn"],
    table_properties={"quality": "gold", "data_product": "intervention_audit"},
    row_filter=ADVISOR_ROW_FILTER,
)
def intervention_state_history() -> DataFrame:
    return _intervention_audit().select(
        "_pg_change_type", "_pg_lsn", "_pg_xid",
        F.col("_timestamp").cast("timestamp").alias("_timestamp"), "_sort_by",
        "intervention_id", "student_id", "advisor_id", "intervention_type",
        "priority", "status", "next_follow_up_at", "outcome", "version",
        "created_at", "updated_at", "closed_at",
    )


@dp.materialized_view(
    name=_gold("intervention_current_state"),
    comment="Current non-deleted intervention state reconstructed from ordered CDC.",
    cluster_by=["advisor_id", "student_id", "status"],
    table_properties={"quality": "gold", "data_product": "intervention_current"},
    row_filter=ADVISOR_ROW_FILTER,
)
def intervention_current_state() -> DataFrame:
    return _current_interventions().select(
        "intervention_id", "student_id", "advisor_id", "intervention_type",
        "priority", "status", "next_follow_up_at", "outcome", "version",
        "created_at", "updated_at", "closed_at", "_pg_lsn", "_sort_by",
    )


@dp.materialized_view(
    name=_gold("intervention_event_history"),
    comment="Immutable analytical intervention events reconstructed from Lakebase CDC.",
    cluster_by=["advisor_id", "student_id", "event_at"],
    table_properties={"quality": "gold", "data_product": "intervention_events"},
    row_filter=ADVISOR_ROW_FILTER,
)
def intervention_event_history() -> DataFrame:
    identities = (
        _intervention_audit()
        .withColumn(
            "_identity_rank",
            F.row_number().over(
                Window.partitionBy("intervention_id").orderBy(
                    F.col("_pg_lsn").desc(), F.col("_sort_by").desc()
                )
            ),
        )
        .filter(F.col("_identity_rank") == 1)
        .select("intervention_id", "student_id", "advisor_id")
    )
    return _intervention_events().join(
        identities, "intervention_id", "inner"
    ).select(
        "event_id", "intervention_id", "student_id", "advisor_id", "event_type",
        "event_at", "note", "prior_status", "new_status", "result_version",
        "_pg_lsn", "_sort_by",
        F.col("_timestamp").cast("timestamp").alias("_timestamp"),
    )


def _student_interventions() -> DataFrame:
    return student_intervention_summary_dataframe(
        spark.read.table(_gold("intervention_current_state")),
        spark.read.table(_gold("intervention_event_history")),
    )


def _latest_scores() -> DataFrame:
    order = Window.partitionBy("student_id").orderBy(
        F.col("feature_as_of").desc(),
        F.col("scored_at").desc(),
        F.col("model_version").cast("long").desc(),
    )
    return (
        spark.read.table(_gold("student_risk_score_history"))
        .withColumn("_score_rank", F.row_number().over(order))
        .filter(F.col("_score_rank") == 1)
        .drop("_score_rank")
    )


def _student_context() -> DataFrame:
    scores = _latest_scores().alias("r")
    features = spark.read.table(_silver("student_daily_snapshots")).alias("f")
    enrollment = (
        spark.read.table(_silver("enrollments"))
        .groupBy("student_id")
        .agg(
            F.min_by("term_code", "term_census_date").alias("cohort_code"),
            F.max_by("term_code", "term_census_date").alias("term_code"),
        )
        .alias("e")
    )
    outcome_order = Window.partitionBy("student_id").orderBy(
        F.col("next_term_census_date").desc(), F.col("outcome_id").desc()
    )
    outcomes = (
        spark.read.table(_silver("student_outcomes"))
        .withColumn("_outcome_rank", F.row_number().over(outcome_order))
        .filter(F.col("_outcome_rank") == 1)
        .select("student_id", "label_term_code", "outcome_status")
        .alias("o")
    )
    base = (
        scores.join(
            features,
            (F.col("r.student_id") == F.col("f.student_id"))
            & (F.col("r.feature_as_of") == F.col("f.feature_as_of")),
            "inner",
        )
        .join(enrollment, F.col("r.student_id") == F.col("e.student_id"), "left")
        .join(outcomes, F.col("r.student_id") == F.col("o.student_id"), "left")
        .select(
            F.col("r.student_id").alias("student_id"),
            F.col("f.advisor_id").alias("advisor_id"),
            F.col("f.program_code").alias("program_code"),
            F.col("f.academic_level").alias("academic_level"),
            F.col("e.cohort_code").alias("cohort_code"),
            F.coalesce(F.col("o.label_term_code"), F.col("e.term_code")).alias("term_code"),
            F.to_date(F.col("r.feature_as_of")).alias("score_date"),
            F.col("r.feature_as_of").alias("feature_as_of"),
            F.col("r.scored_at").alias("scored_at"),
            F.col("r.model_version").alias("model_version"),
            F.col("r.risk_score").alias("risk_score"),
            F.col("r.risk_tier").alias("risk_tier"),
            F.col("r.leading_factors").alias("leading_factors"),
            F.col("o.outcome_status").alias("outcome_status"),
            F.col("f.attendance_rate_28d").alias("attendance_rate_28d"),
            F.col("f.missed_assignments_28d").alias("missed_assignments_28d"),
            F.col("f.days_since_lms_activity").alias("days_since_lms_activity"),
            F.col("f.financial_hold_flag").alias("financial_hold_flag"),
            F.col("f.cumulative_gpa").alias("cumulative_gpa"),
            F.col("f.synthetic_net_tuition_next_term").alias(
                "synthetic_net_tuition_next_term"
            ),
        )
    )
    return (
        base.alias("b")
        .join(
            _student_interventions().alias("i"),
            F.col("b.student_id") == F.col("i.student_id"),
            "left",
        )
        .select(
            "b.*",
            F.coalesce(F.col("i.intervention_status"), F.lit("not_started")).alias(
                "intervention_status"
            ),
            F.col("i.intervention_priority").alias("intervention_priority"),
            F.col("i.first_intervention_at").alias("first_intervention_at"),
            F.coalesce(F.col("i.follow_up_due"), F.lit(False)).alias("follow_up_due"),
            F.coalesce(F.col("i.follow_up_completed"), F.lit(False)).alias(
                "follow_up_completed"
            ),
        )
    )


@dp.materialized_view(
    name=_gold("advisor_caseload"),
    comment="Current elevated-risk caseload, governed by advisor assignment.",
    cluster_by=["advisor_id", "risk_tier", "score_date"],
    table_properties={"quality": "gold", "data_product": "advisor_operations"},
    row_filter=ADVISOR_ROW_FILTER,
)
def advisor_caseload() -> DataFrame:
    priority = Window.partitionBy("advisor_id").orderBy(
        F.col("risk_score").desc(), F.col("student_id")
    )
    return (
        _student_context()
        .filter(F.col("risk_tier").isin("medium", "high"))
        .withColumn("caseload_priority", F.row_number().over(priority))
        .select(
            "student_id", "advisor_id", "program_code", "cohort_code", "term_code",
            "score_date", "risk_score", "risk_tier", "leading_factors",
            "intervention_status", "intervention_priority", "first_intervention_at",
            "follow_up_due", "follow_up_completed", "caseload_priority", "scored_at",
        )
    )


@dp.materialized_view(
    name=_gold("student_detail"),
    comment="Governed student risk detail and allowlisted factual signals.",
    cluster_by=["advisor_id", "student_id", "score_date"],
    table_properties={"quality": "gold", "data_product": "student_detail"},
    row_filter=ADVISOR_ROW_FILTER,
)
def student_detail() -> DataFrame:
    return _student_context().drop("synthetic_net_tuition_next_term")


@dp.materialized_view(
    name=_gold("executive_retention_metrics"),
    comment="Aggregate-only retention, risk, intervention, and estimated tuition metrics.",
    cluster_by=["score_date", "program_code", "cohort_code"],
    table_properties={
        "quality": "gold",
        "data_product": "executive_aggregate",
        "tuition_exposure_semantics": "estimate",
    },
)
def executive_retention_metrics() -> DataFrame:
    dimensions = [
        "program_code", "cohort_code", "term_code", "score_date", "risk_tier",
        "intervention_status",
    ]
    return _student_context().groupBy(*dimensions).agg(
        F.countDistinct("student_id").alias("student_count"),
        F.sum(F.when(F.col("risk_tier").isin("medium", "high"), 1).otherwise(0)).alias(
            "at_risk_count"
        ),
        F.avg(F.when(F.col("outcome_status").isin("PERSISTED", "RETAINED"), 1.0).otherwise(0.0)).alias(
            "retention_rate"
        ),
        F.avg(
            F.when(
                F.col("risk_tier").isin("medium", "high"),
                F.when(F.col("intervention_status") != "not_started", 1.0).otherwise(0.0),
            )
        ).alias("intervention_coverage"),
        F.avg(
            F.when(
                F.col("first_intervention_at").isNotNull(),
                F.timestamp_diff("SECOND", F.col("scored_at"), F.col("first_intervention_at"))
                / F.lit(86400.0),
            )
        ).alias("time_to_first_intervention_days"),
        F.avg(
            F.when(
                F.col("follow_up_due"), F.col("follow_up_completed").cast("double")
            )
        ).alias("follow_up_completion_rate"),
        F.sum(
            F.when(
                F.col("risk_tier").isin("medium", "high"),
                F.col("synthetic_net_tuition_next_term"),
            ).otherwise(0.0)
        ).alias("estimated_next_term_net_tuition_exposure"),
        F.lit(True).alias("tuition_exposure_is_estimate"),
        F.max("scored_at").alias("data_freshness_at"),
    )


@dp.materialized_view(
    name=_gold("risk_trends"),
    comment="Aggregate risk distribution by business dimensions and score date.",
    cluster_by=["score_date", "risk_tier", "program_code"],
    table_properties={"quality": "gold", "data_product": "risk_trends"},
)
def risk_trends() -> DataFrame:
    return _student_context().groupBy(
        "program_code", "cohort_code", "term_code", "score_date", "risk_tier",
        "intervention_status",
    ).agg(
        F.countDistinct("student_id").alias("student_count"),
        F.avg("risk_score").alias("average_risk_score"),
        F.min("risk_score").alias("minimum_risk_score"),
        F.max("risk_score").alias("maximum_risk_score"),
    )


@dp.materialized_view(
    name=_gold("genie_retention"),
    comment="Curated advisor-level analytical facts for the embedded Genie experience.",
    cluster_by=["advisor_id", "score_date", "risk_tier"],
    table_properties={"quality": "gold", "data_product": "genie_curated"},
    row_filter=ADVISOR_ROW_FILTER,
)
def genie_retention() -> DataFrame:
    return _student_context().select(
        "student_id", "advisor_id", "program_code", "cohort_code", "term_code",
        "score_date", "risk_score", "risk_tier", "leading_factors",
        "intervention_status", "intervention_priority", "follow_up_due",
        "follow_up_completed", "outcome_status",
    )
