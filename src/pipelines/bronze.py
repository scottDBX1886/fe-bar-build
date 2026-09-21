"""Incremental Bronze ingestion and quarantine for synthetic university data."""

from __future__ import annotations

from pyspark import pipelines as dp
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from bronze_rules import RULES, apply_quality_rules


CATALOG = spark.conf.get("retention.catalog")
SCHEMA_PREFIX = spark.conf.get("retention.schema_prefix")
SOURCE_ROOT = f"/Volumes/{CATALOG}/{SCHEMA_PREFIX}_bronze/raw_data"

SCHEMAS = {
    "students": """
        student_id STRING, student_index BIGINT, program_code STRING,
        advisor_id STRING, residency_status STRING, academic_level STRING,
        synthetic_age_band STRING, synthetic_gender STRING,
        synthetic_first_generation BOOLEAN, synthetic_race_ethnicity STRING,
        synthetic_net_tuition_next_term DOUBLE, incident_cohort BOOLEAN,
        record_effective_at TIMESTAMP, run_date DATE,
        is_injected_defect BOOLEAN, _rescued_data STRING
    """,
    "enrollments": """
        enrollment_id STRING, student_id STRING, term_code STRING,
        term_census_date DATE, credits_attempted BIGINT,
        credits_completed BIGINT, term_gpa DOUBLE, cumulative_gpa DOUBLE,
        academic_standing STRING, course_withdrawal_flag BOOLEAN,
        run_date DATE, is_injected_defect BOOLEAN, _rescued_data STRING
    """,
    "attendance_events": """
        attendance_event_id STRING, student_id STRING, course_id STRING,
        event_at TIMESTAMP, present_flag BOOLEAN, story_segment STRING,
        run_date DATE, is_injected_defect BOOLEAN, _rescued_data STRING
    """,
    "engagement_events": """
        engagement_event_id STRING, student_id STRING, event_type STRING,
        event_status STRING, event_at TIMESTAMP, story_segment STRING,
        run_date DATE, is_injected_defect BOOLEAN, _rescued_data STRING
    """,
    "financial_events": """
        financial_event_id STRING, student_id STRING, event_at TIMESTAMP,
        balance_amount DOUBLE, balance_band STRING,
        financial_hold_flag BOOLEAN, hold_reason STRING, aid_status STRING,
        run_date DATE, is_injected_defect BOOLEAN, _rescued_data STRING
    """,
    "student_outcomes": """
        outcome_id STRING, student_id STRING, label_term_code STRING,
        next_term_census_date DATE, enrolled_by_census_flag BOOLEAN,
        stopout_flag BOOLEAN, outcome_status STRING, run_date DATE,
        is_injected_defect BOOLEAN, _rescued_data STRING
    """,
}


def _source_stream(dataset: str) -> DataFrame:
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "parquet")
        .option("cloudFiles.includeExistingFiles", "true")
        .option("cloudFiles.schemaEvolutionMode", "rescue")
        .option("rescuedDataColumn", "_rescued_data")
        .schema(SCHEMAS[dataset])
        .load(f"{SOURCE_ROOT}/{dataset}")
        .withColumn("_source_path", F.col("_metadata.file_path"))
        .withColumn("_ingested_at", F.current_timestamp())
    )


def _classified_stream(dataset: str) -> DataFrame:
    classified = apply_quality_rules(_source_stream(dataset), dataset)
    return (
        classified.withColumn(
            "_violation_reason",
            F.when(F.col("_rescued_data").isNotNull(), F.lit("RESCUED_DATA"))
            .otherwise(F.col("_violation_reason")),
        )
        .withColumn(
            "_is_recoverable_valid",
            F.col("_is_recoverable_valid") & F.col("_rescued_data").isNull(),
        )
    )


def _publish_domain(dataset: str) -> None:
    classified_name = f"_{dataset}_classified"
    quarantine_name = f"{dataset}_quarantine"
    critical_rule = RULES[dataset]

    @dp.temporary_view(name=classified_name)
    def classified() -> DataFrame:
        return _classified_stream(dataset)

    @dp.table(
        name=dataset,
        comment=f"Accepted incremental Bronze records for {dataset}.",
        table_properties={"quality": "bronze"},
    )
    @dp.expect_or_fail(
        f"{dataset}_safe_state",
        (
            f"{critical_rule.primary_key} IS NOT NULL "
            f"AND trim({critical_rule.primary_key}) <> '' "
            f"AND {critical_rule.event_time} IS NOT NULL"
        ),
    )
    def accepted() -> DataFrame:
        frame = spark.readStream.table(classified_name)
        return frame.filter(
            F.col("_is_recoverable_valid") | ~F.col("_is_critical_valid")
        ).drop("_is_critical_valid", "_is_recoverable_valid", "_violation_reason")

    @dp.table(
        name=quarantine_name,
        comment=f"Recoverable malformed Bronze records for {dataset}.",
        table_properties={"quality": "bronze_quarantine"},
    )
    def quarantine() -> DataFrame:
        return (
            spark.readStream.table(classified_name)
            .filter(F.col("_is_critical_valid") & ~F.col("_is_recoverable_valid"))
            .drop("_is_critical_valid", "_is_recoverable_valid")
        )


for _dataset in SCHEMAS:
    _publish_domain(_dataset)
