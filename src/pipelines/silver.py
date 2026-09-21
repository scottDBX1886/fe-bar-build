"""Silver standardization and leakage-safe point-in-time feature snapshots."""

from __future__ import annotations

from pyspark import pipelines as dp
from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F


CATALOG = spark.conf.get("retention.catalog")
SCHEMA_PREFIX = spark.conf.get("retention.schema_prefix")
BRONZE_SCHEMA = f"{SCHEMA_PREFIX}_bronze"
SILVER_SCHEMA = f"{SCHEMA_PREFIX}_silver"


def _bronze(table: str) -> str:
    return f"{CATALOG}.{BRONZE_SCHEMA}.{table}"


def _silver(table: str) -> str:
    return f"{CATALOG}.{SILVER_SCHEMA}.{table}"


DOMAIN_CONFIG = {
    "students": ("student_id", "record_effective_at"),
    "enrollments": ("enrollment_id", "term_census_date"),
    "attendance_events": ("attendance_event_id", "event_at"),
    "engagement_events": ("engagement_event_id", "event_at"),
    "financial_events": ("financial_event_id", "event_at"),
    "student_outcomes": ("outcome_id", "next_term_census_date"),
}

PROTECTED_AUDIT_FIELDS = (
    "synthetic_age_band",
    "synthetic_gender",
    "synthetic_first_generation",
    "synthetic_race_ethnicity",
)


def _publish_silver_domain(dataset: str, primary_key: str, event_time: str) -> None:
    source_view = f"_{dataset}_silver_changes"
    target = _silver(dataset)

    @dp.temporary_view(name=source_view)
    def standardized_changes() -> DataFrame:
        source = spark.readStream.table(_bronze(dataset))
        if dataset != "students":
            student_keys = spark.read.table(_bronze("students")).select("student_id").distinct()
            source = source.join(F.broadcast(student_keys), "student_id", "inner")
        columns_to_drop = ["_rescued_data", "is_injected_defect"]
        if dataset == "students":
            columns_to_drop.extend([*PROTECTED_AUDIT_FIELDS, "incident_cohort"])
        return source.drop(*columns_to_drop).withColumn("_silvered_at", F.current_timestamp())

    dp.create_streaming_table(
        name=target,
        comment=f"Deduplicated, referentially valid Silver {dataset}.",
        cluster_by=["student_id"],
        table_properties={"quality": "silver"},
    )
    dp.create_auto_cdc_flow(
        target=target,
        source=source_view,
        keys=[primary_key],
        sequence_by=F.struct(
            F.col(event_time).cast("timestamp"),
            F.col("_ingested_at"),
            F.col("_source_path"),
        ),
        stored_as_scd_type=1,
        name=f"{dataset}_deduplicate",
    )


for _dataset, (_primary_key, _event_time) in DOMAIN_CONFIG.items():
    _publish_silver_domain(_dataset, _primary_key, _event_time)


@dp.materialized_view(
    name=_silver("student_protected_audit"),
    comment="Restricted fairness-audit attributes, isolated from model features.",
    cluster_by=["student_id"],
    table_properties={"quality": "silver", "data_classification": "restricted"},
)
def student_protected_audit() -> DataFrame:
    window = Window.partitionBy("student_id").orderBy(
        F.col("record_effective_at").desc(),
        F.col("_ingested_at").desc(),
        F.col("_source_path").desc(),
    )
    return (
        spark.read.table(_bronze("students"))
        .withColumn("_dedup_rank", F.row_number().over(window))
        .filter(F.col("_dedup_rank") == 1)
        .select("student_id", *PROTECTED_AUDIT_FIELDS, "record_effective_at", "run_date")
    )


@dp.materialized_view(
    name=_silver("referential_quarantine"),
    comment="Unexpected child records whose student key is absent from accepted Bronze students.",
    cluster_by=["dataset", "student_id"],
    table_properties={"quality": "silver_quarantine"},
)
def referential_quarantine() -> DataFrame:
    student_keys = spark.read.table(_bronze("students")).select("student_id").distinct()
    rejected = None
    for dataset, (primary_key, _) in DOMAIN_CONFIG.items():
        if dataset == "students":
            continue
        domain_rejected = (
            spark.read.table(_bronze(dataset))
            .join(student_keys, "student_id", "left_anti")
            .select(
                F.lit(dataset).alias("dataset"),
                F.col(primary_key).cast("string").alias("record_id"),
                "student_id",
                F.lit("UNKNOWN_STUDENT_ID").alias("violation_reason"),
                "_source_path",
                "_ingested_at",
            )
        )
        rejected = domain_rejected if rejected is None else rejected.unionByName(domain_rejected)
    return rejected


@dp.materialized_view(
    name=_silver("training_labels"),
    comment="Outcome labels isolated from model features with a preceding feature cutoff.",
    cluster_by=["feature_as_of", "student_id"],
    table_properties={"quality": "silver"},
)
@dp.expect_or_fail(
    "feature_cutoff_precedes_label",
    "feature_as_of < label_observed_at",
)
def training_labels() -> DataFrame:
    outcomes = spark.read.table(_silver("student_outcomes"))
    feature_date = F.date_sub(F.col("next_term_census_date"), 1)
    return outcomes.select(
        "outcome_id",
        "student_id",
        "label_term_code",
        F.to_timestamp(F.concat(feature_date.cast("string"), F.lit(" 23:59:59"))).alias(
            "feature_as_of"
        ),
        F.col("next_term_census_date").cast("timestamp").alias("label_observed_at"),
        F.col("stopout_flag").cast("int").alias("stopout_label"),
        "outcome_status",
    )


def _point_in_time_features(snapshots: DataFrame) -> DataFrame:
    base = snapshots.select("student_id", "feature_as_of").dropDuplicates()
    key_columns = ["student_id", "feature_as_of"]

    attendance = spark.read.table(_silver("attendance_events")).alias("a")
    attendance_agg = (
        base.alias("s")
        .join(
            attendance,
            (F.col("s.student_id") == F.col("a.student_id"))
            & (F.col("a.event_at") <= F.col("s.feature_as_of"))
            & (F.col("a.event_at") > F.col("s.feature_as_of") - F.expr("INTERVAL 28 DAYS")),
            "left",
        )
        .groupBy(F.col("s.student_id"), F.col("s.feature_as_of"))
        .agg(
            F.coalesce(F.avg(F.col("a.present_flag").cast("double")), F.lit(0.0)).alias(
                "attendance_rate_28d"
            ),
            F.max("a.event_at").alias("max_attendance_event_at"),
        )
    )

    engagement = spark.read.table(_silver("engagement_events")).alias("e")
    engagement_agg = (
        base.alias("s")
        .join(
            engagement,
            (F.col("s.student_id") == F.col("e.student_id"))
            & (F.col("e.event_at") <= F.col("s.feature_as_of")),
            "left",
        )
        .groupBy(F.col("s.student_id"), F.col("s.feature_as_of"))
        .agg(
            F.sum(
                F.when(
                    (F.col("e.event_at") > F.col("s.feature_as_of") - F.expr("INTERVAL 28 DAYS"))
                    & (F.col("e.event_type") == "ASSIGNMENT")
                    & (F.col("e.event_status") == "MISSED"),
                    1,
                ).otherwise(0)
            ).alias("missed_assignments_28d"),
            F.sum(
                F.when(
                    (F.col("e.event_at") > F.col("s.feature_as_of") - F.expr("INTERVAL 90 DAYS"))
                    & (F.col("e.event_type") == "SUPPORT"),
                    1,
                ).otherwise(0)
            ).alias("support_interactions_90d"),
            F.max(F.when(F.col("e.event_type") == "LMS_LOGIN", F.col("e.event_at"))).alias(
                "last_lms_activity_at"
            ),
            F.max("e.event_at").alias("max_engagement_event_at"),
        )
        .withColumn(
            "days_since_lms_activity",
            F.coalesce(
                F.datediff(F.to_date("feature_as_of"), F.to_date("last_lms_activity_at")),
                F.lit(999),
            ),
        )
    )

    financial = spark.read.table(_silver("financial_events")).alias("f")
    financial_window = Window.partitionBy("s.student_id", "s.feature_as_of").orderBy(
        F.col("f.event_at").desc_nulls_last(), F.col("f.financial_event_id").desc_nulls_last()
    )
    financial_latest = (
        base.alias("s")
        .join(
            financial,
            (F.col("s.student_id") == F.col("f.student_id"))
            & (F.col("f.event_at") <= F.col("s.feature_as_of")),
            "left",
        )
        .withColumn("_financial_rank", F.row_number().over(financial_window))
        .filter(F.col("_financial_rank") == 1)
        .select(
            F.col("s.student_id").alias("student_id"),
            F.col("s.feature_as_of").alias("feature_as_of"),
            F.coalesce(F.col("f.financial_hold_flag"), F.lit(False)).alias(
                "financial_hold_flag"
            ),
            F.coalesce(F.col("f.balance_band"), F.lit("NONE")).alias(
                "current_balance_band"
            ),
            F.col("f.event_at").alias("max_financial_event_at"),
        )
    )

    enrollments = spark.read.table(_silver("enrollments")).alias("n")
    enrollment_window = Window.partitionBy("s.student_id", "s.feature_as_of").orderBy(
        F.col("n.term_census_date").desc_nulls_last(), F.col("n.enrollment_id").desc_nulls_last()
    )
    ranked_enrollments = (
        base.alias("s")
        .join(
            enrollments,
            (F.col("s.student_id") == F.col("n.student_id"))
            & (F.col("n.term_census_date") <= F.to_date(F.col("s.feature_as_of"))),
            "left",
        )
        .withColumn("_enrollment_rank", F.row_number().over(enrollment_window))
    )
    enrollment_agg = ranked_enrollments.groupBy(
        F.col("s.student_id"), F.col("s.feature_as_of")
    ).agg(
        F.coalesce(
            F.max(F.when(F.col("_enrollment_rank") == 1, F.col("n.credits_attempted"))),
            F.lit(0),
        ).alias("credits_attempted_current"),
        F.coalesce(
            F.sum(F.when(F.col("_enrollment_rank") > 1, F.col("n.credits_completed")).otherwise(0)),
            F.lit(0),
        ).alias("credits_completed_prior"),
        F.coalesce(
            F.max(F.when(F.col("_enrollment_rank") == 1, F.col("n.credits_attempted")))
            - F.max(F.when(F.col("_enrollment_rank") == 2, F.col("n.credits_attempted"))),
            F.lit(0),
        ).alias("attempted_credit_trend"),
        F.coalesce(
            F.max(F.when(F.col("_enrollment_rank") == 1, F.col("n.cumulative_gpa"))),
            F.lit(0.0),
        ).alias("cumulative_gpa"),
        F.sum(
            F.when(
                (F.col("_enrollment_rank") > 1) & F.col("n.course_withdrawal_flag"), 1
            ).otherwise(0)
        ).alias("withdrawal_count_prior"),
        F.max(F.col("n.term_census_date").cast("timestamp")).alias("max_enrollment_event_at"),
    )

    students = spark.read.table(_silver("students")).select(
        "student_id",
        "program_code",
        "academic_level",
        "residency_status",
        "advisor_id",
        "synthetic_net_tuition_next_term",
    )
    return (
        base.join(students, "student_id", "inner")
        .join(attendance_agg, key_columns, "left")
        .join(engagement_agg, key_columns, "left")
        .join(financial_latest, key_columns, "left")
        .join(enrollment_agg, key_columns, "left")
        .withColumn(
            "max_feature_event_at",
            F.greatest(
                "max_attendance_event_at",
                "max_engagement_event_at",
                "max_financial_event_at",
                "max_enrollment_event_at",
            ),
        )
        .drop(
            "max_attendance_event_at",
            "max_engagement_event_at",
            "max_financial_event_at",
            "max_enrollment_event_at",
            "last_lms_activity_at",
        )
    )


@dp.materialized_view(
    name=_silver("student_daily_snapshots"),
    comment="Operational point-in-time student features for each source run date.",
    cluster_by=["feature_as_of", "student_id"],
    table_properties={"quality": "silver"},
)
@dp.expect_or_fail(
    "daily_snapshot_has_no_future_events",
    "max_feature_event_at IS NULL OR max_feature_event_at <= feature_as_of",
)
def student_daily_snapshots() -> DataFrame:
    students = spark.read.table(_silver("students"))
    snapshots = students.select(
        "student_id",
        F.to_timestamp(F.concat(F.col("run_date").cast("string"), F.lit(" 23:59:59"))).alias(
            "feature_as_of"
        ),
    )
    return _point_in_time_features(snapshots)


@dp.materialized_view(
    name=_silver("model_feature_snapshots"),
    comment="Label-aligned model features containing no labels or protected attributes.",
    cluster_by=["feature_as_of", "student_id"],
    table_properties={"quality": "silver", "feature_contract": "student_stopout_v1"},
)
@dp.expect_or_fail(
    "model_snapshot_has_no_future_events",
    "max_feature_event_at IS NULL OR max_feature_event_at <= feature_as_of",
)
def model_feature_snapshots() -> DataFrame:
    label_cutoffs = spark.read.table(_silver("training_labels")).select(
        "student_id", "feature_as_of"
    )
    return _point_in_time_features(label_cutoffs)
