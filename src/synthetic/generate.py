"""Generate deterministic, story-driven synthetic university source data."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

if __package__:
    from .contracts import DATASET_CONTRACTS, source_partition_path
else:
    from contracts import DATASET_CONTRACTS, source_partition_path


@dataclass(frozen=True)
class GenerationPlan:
    run_date: date
    bootstrap: bool
    row_counts: dict[str, int]


def build_generation_plan(run_date: date, *, bootstrap: bool) -> GenerationPlan:
    if bootstrap:
        row_counts = {
            name: contract.expected_rows
            for name, contract in DATASET_CONTRACTS.items()
        }
    else:
        row_counts = {
            "students": 0,
            "enrollments": 0,
            "attendance_events": 10_000,
            "engagement_events": 8_000,
            "financial_events": 1_000,
            "student_outcomes": 0,
        }
    return GenerationPlan(run_date=run_date, bootstrap=bootstrap, row_counts=row_counts)


def _bucket(*columns: F.Column, modulo: int = 10_000) -> F.Column:
    return F.pmod(F.xxhash64(*columns), F.lit(modulo))


def _student_id(index: F.Column) -> F.Column:
    return F.format_string("STU-%06d", index)


def _incident_cohort(index: F.Column, seed: int) -> F.Column:
    return F.pmod(index * F.lit(1_103_515_245) + F.lit(seed * 12_345), 10_000) < 150


def _risk_bucket(index: F.Column, seed: int) -> F.Column:
    return F.pmod(index * F.lit(2_654_435_761) + F.lit(seed * 2_246_822_519), 10_000)


def _program(bucket: F.Column) -> F.Column:
    return (
        F.when(bucket < 3_000, "BUS")
        .when(bucket < 5_500, "ARTS")
        .when(bucket < 7_500, "STEM")
        .when(bucket < 9_000, "HEALTH")
        .otherwise("EDU")
    )


def build_students(spark: SparkSession, count: int, seed: int, run_date: date) -> DataFrame:
    base = spark.range(count, numPartitions=8).withColumnRenamed("id", "student_index")
    profile_bucket = _bucket(F.col("student_index"), F.lit(seed))
    tuition_bucket = _bucket(F.col("student_index"), F.lit(seed + 1))
    return base.select(
        _student_id(F.col("student_index")).alias("student_id"),
        F.col("student_index"),
        _program(profile_bucket).alias("program_code"),
        F.concat(F.lit("ADV-"), F.lpad((F.col("student_index") % 40).cast("string"), 3, "0")).alias("advisor_id"),
        F.when(profile_bucket < 7_500, "IN_STATE")
        .when(profile_bucket < 9_000, "OUT_OF_STATE")
        .otherwise("INTERNATIONAL")
        .alias("residency_status"),
        F.when(profile_bucket < 2_200, "FIRST_YEAR")
        .when(profile_bucket < 4_700, "SOPHOMORE")
        .when(profile_bucket < 7_300, "JUNIOR")
        .otherwise("SENIOR")
        .alias("academic_level"),
        F.when(profile_bucket < 2_800, "18-20")
        .when(profile_bucket < 7_800, "21-24")
        .otherwise("25+")
        .alias("synthetic_age_band"),
        F.when(profile_bucket < 5_200, "WOMAN")
        .when(profile_bucket < 9_600, "MAN")
        .otherwise("NONBINARY_OR_UNDISCLOSED")
        .alias("synthetic_gender"),
        (profile_bucket % 5 == 0).alias("synthetic_first_generation"),
        F.when(profile_bucket < 4_500, "GROUP_A")
        .when(profile_bucket < 7_200, "GROUP_B")
        .when(profile_bucket < 9_000, "GROUP_C")
        .otherwise("GROUP_D")
        .alias("synthetic_race_ethnicity"),
        F.round(F.lit(4_500.0) + F.pow(tuition_bucket.cast("double") / 10_000.0, 2) * 13_500.0, 2).alias(
            "synthetic_net_tuition_next_term"
        ),
        _incident_cohort(F.col("student_index"), seed).alias("incident_cohort"),
        F.to_timestamp(F.lit(f"{run_date.isoformat()} 00:00:00")).alias("record_effective_at"),
        F.lit(run_date.isoformat()).cast("date").alias("run_date"),
        F.lit(False).alias("is_injected_defect"),
    )


def build_enrollments(spark: SparkSession, count: int, seed: int, run_date: date) -> DataFrame:
    base = spark.range(count, numPartitions=16)
    student_index = F.pmod(F.col("id"), 20_000)
    term_index = F.floor(F.col("id") / 20_000).cast("int")
    performance = F.floor(_risk_bucket(student_index, seed) / 10)
    attempted = F.lit(12) + F.pmod(student_index, 7)
    dropped = F.when(performance < 120, 6).when(performance < 300, 3).otherwise(0)
    gpa = F.round(F.least(F.lit(4.0), F.lit(1.6) + performance.cast("double") / 420.0), 2)
    return base.select(
        F.format_string("ENR-%08d", F.col("id")).alias("enrollment_id"),
        _student_id(student_index).alias("student_id"),
        F.element_at(F.array(F.lit("2025FA"), F.lit("2026SP"), F.lit("2026FA")), term_index + 1).alias("term_code"),
        F.element_at(
            F.array(F.lit("2025-09-08"), F.lit("2026-01-26"), F.lit("2026-09-07")),
            term_index + 1,
        ).cast("date").alias("term_census_date"),
        attempted.alias("credits_attempted"),
        F.greatest(F.lit(0), attempted - dropped).alias("credits_completed"),
        gpa.alias("term_gpa"),
        gpa.alias("cumulative_gpa"),
        F.when(gpa < 2.0, "PROBATION").otherwise("GOOD_STANDING").alias("academic_standing"),
        (dropped > 0).alias("course_withdrawal_flag"),
        F.lit(run_date.isoformat()).cast("date").alias("run_date"),
        F.lit(False).alias("is_injected_defect"),
    )


def build_attendance(
    spark: SparkSession, count: int, seed: int, run_date: date, *, bootstrap: bool
) -> DataFrame:
    partitions = 32 if bootstrap else 8
    base = spark.range(count, numPartitions=partitions)
    student_index = F.pmod(F.col("id") * 17 + F.lit(seed), 20_000)
    day_span = 300 if bootstrap else 1
    days_ago = F.pmod(F.col("id") * 13 + F.lit(seed), day_span)
    event_date = F.date_sub(F.lit(run_date.isoformat()).cast("date"), days_ago.cast("int"))
    incident = _incident_cohort(student_index, seed) & (event_date >= F.lit("2026-09-08").cast("date"))
    risk_bucket = _risk_bucket(student_index, seed)
    present_threshold = (
        F.when(incident, 5_800).when(risk_bucket < 1_500, 7_500).otherwise(9_100)
    )
    injected = F.col("id") >= F.lit(max(0, count - 10))
    return base.select(
        F.format_string("ATT-%010d", F.col("id") + F.lit(0 if bootstrap else 1_000_000_000)).alias(
            "attendance_event_id"
        ),
        F.when(injected, F.lit(None).cast("string")).otherwise(_student_id(student_index)).alias("student_id"),
        F.concat(F.lit("COURSE-"), F.lpad(F.pmod(student_index, 120).cast("string"), 3, "0")).alias("course_id"),
        F.to_timestamp(F.concat_ws(" ", event_date.cast("string"), F.lit("09:00:00"))).alias("event_at"),
        (_bucket(F.col("id"), F.lit(seed + 20)) < present_threshold).alias("present_flag"),
        F.when(incident, "INCIDENT_PATTERN").otherwise("BASELINE").alias("story_segment"),
        F.lit(run_date.isoformat()).cast("date").alias("run_date"),
        injected.alias("is_injected_defect"),
    )


def build_engagement(
    spark: SparkSession, count: int, seed: int, run_date: date, *, bootstrap: bool
) -> DataFrame:
    partitions = 32 if bootstrap else 8
    base = spark.range(count, numPartitions=partitions)
    student_index = F.pmod(F.col("id") * 19 + F.lit(seed), 20_000)
    day_span = 300 if bootstrap else 1
    days_ago = F.pmod(F.col("id") * 11 + F.lit(seed), day_span)
    event_date = F.date_sub(F.lit(run_date.isoformat()).cast("date"), days_ago.cast("int"))
    incident = _incident_cohort(student_index, seed) & (event_date >= F.lit("2026-09-08").cast("date"))
    risk_bucket = _risk_bucket(student_index, seed)
    event_bucket = _bucket(F.col("id"), F.lit(seed + 30), modulo=100)
    event_type = (
        F.when(event_bucket < 58, "LMS_LOGIN")
        .when(event_bucket < 85, "ASSIGNMENT")
        .when(event_bucket < 94, "ADVISING")
        .otherwise("SUPPORT")
    )
    missed = (event_type == "ASSIGNMENT") & (
        _bucket(F.col("id"), F.lit(seed + 31), modulo=100)
        < F.when(incident, 45).when(risk_bucket < 1_500, 25).otherwise(8)
    )
    injected = F.col("id") >= F.lit(max(0, count - 10))
    return base.select(
        F.format_string("ENG-%010d", F.col("id") + F.lit(0 if bootstrap else 1_000_000_000)).alias(
            "engagement_event_id"
        ),
        F.when(injected, F.lit(None).cast("string")).otherwise(_student_id(student_index)).alias("student_id"),
        event_type.alias("event_type"),
        F.when(missed, "MISSED").otherwise("COMPLETED").alias("event_status"),
        F.to_timestamp(F.concat_ws(" ", event_date.cast("string"), F.lit("14:00:00"))).alias("event_at"),
        F.when(incident, "INCIDENT_PATTERN").otherwise("BASELINE").alias("story_segment"),
        F.lit(run_date.isoformat()).cast("date").alias("run_date"),
        injected.alias("is_injected_defect"),
    )


def build_financial_events(
    spark: SparkSession, count: int, seed: int, run_date: date, *, bootstrap: bool
) -> DataFrame:
    base = spark.range(count, numPartitions=16 if bootstrap else 4)
    student_index = F.pmod(F.col("id") * 23 + F.lit(seed), 20_000)
    day_span = 300 if bootstrap else 1
    event_date = F.date_sub(
        F.lit(run_date.isoformat()).cast("date"),
        F.pmod(F.col("id") * 7 + F.lit(seed), day_span).cast("int"),
    )
    incident = _incident_cohort(student_index, seed) & (event_date >= F.lit("2026-09-08").cast("date"))
    risk_bucket = _risk_bucket(student_index, seed)
    balance_bucket = _bucket(F.col("id"), F.lit(seed + 40), modulo=1_000)
    balance = F.round(F.pow(balance_bucket.cast("double") / 1_000.0, 3) * 8_000.0, 2)
    hold = (incident & (balance_bucket < 650)) | (risk_bucket < 800) | (balance_bucket < 70)
    injected = F.col("id") >= F.lit(max(0, count - 5))
    return base.select(
        F.format_string("FIN-%09d", F.col("id") + F.lit(0 if bootstrap else 100_000_000)).alias(
            "financial_event_id"
        ),
        F.when(injected, F.lit(None).cast("string")).otherwise(_student_id(student_index)).alias("student_id"),
        event_date.cast("timestamp").alias("event_at"),
        balance.alias("balance_amount"),
        F.when(balance < 500, "LOW").when(balance < 2_500, "MEDIUM").otherwise("HIGH").alias("balance_band"),
        hold.alias("financial_hold_flag"),
        F.when(hold, "PAST_DUE_BALANCE").otherwise(F.lit(None).cast("string")).alias("hold_reason"),
        F.when(balance_bucket < 8_600, "AID_COMPLETE").otherwise("AID_INCOMPLETE").alias("aid_status"),
        F.lit(run_date.isoformat()).cast("date").alias("run_date"),
        injected.alias("is_injected_defect"),
    )


def build_outcomes(spark: SparkSession, count: int, seed: int, run_date: date) -> DataFrame:
    base = spark.range(count, numPartitions=16)
    student_index = F.pmod(F.col("id"), 20_000)
    label_term_index = F.floor(F.col("id") / 20_000).cast("int")
    latent_risk = _risk_bucket(student_index, seed)
    incident = _incident_cohort(student_index, seed) & (label_term_index == 1)
    stopout_threshold = F.when(incident, 5_200).otherwise(1_050)
    stopped_out = latent_risk < stopout_threshold
    return base.select(
        F.format_string("OUT-%08d", F.col("id")).alias("outcome_id"),
        _student_id(student_index).alias("student_id"),
        F.element_at(F.array(F.lit("2026SP"), F.lit("2026FA")), label_term_index + 1).alias("label_term_code"),
        F.element_at(F.array(F.lit("2026-01-26"), F.lit("2026-09-07")), label_term_index + 1)
        .cast("date")
        .alias("next_term_census_date"),
        (~stopped_out).alias("enrolled_by_census_flag"),
        stopped_out.alias("stopout_flag"),
        F.when(stopped_out & (latent_risk < 250), "WITHDRAWAL")
        .when(stopped_out, "STOP_OUT")
        .otherwise("PERSISTED")
        .alias("outcome_status"),
        F.lit(run_date.isoformat()).cast("date").alias("run_date"),
        F.lit(False).alias("is_injected_defect"),
    )


def _write(df: DataFrame, path: str) -> int:
    df.write.mode("overwrite").parquet(path)
    return df.sparkSession.read.parquet(path).count()


def generate(
    spark: SparkSession,
    *,
    catalog: str,
    schema_prefix: str,
    run_date: date,
    seed: int,
    bootstrap: bool,
) -> dict[str, int]:
    bronze_schema = f"{schema_prefix}_bronze"
    volume = "raw_data"
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{bronze_schema}")
    spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{bronze_schema}.{volume}")
    plan = build_generation_plan(run_date, bootstrap=bootstrap)

    builders = {
        "students": lambda count: build_students(spark, count, seed, run_date),
        "enrollments": lambda count: build_enrollments(spark, count, seed, run_date),
        "attendance_events": lambda count: build_attendance(
            spark, count, seed, run_date, bootstrap=bootstrap
        ),
        "engagement_events": lambda count: build_engagement(
            spark, count, seed, run_date, bootstrap=bootstrap
        ),
        "financial_events": lambda count: build_financial_events(
            spark, count, seed, run_date, bootstrap=bootstrap
        ),
        "student_outcomes": lambda count: build_outcomes(spark, count, seed, run_date),
    }

    written: dict[str, int] = {}
    for dataset, count in plan.row_counts.items():
        if count == 0:
            written[dataset] = 0
            continue
        path = source_partition_path(
            catalog=catalog,
            schema=bronze_schema,
            volume=volume,
            dataset=dataset,
            run_date=run_date,
        )
        written[dataset] = _write(builders[dataset](count), path)
    return written


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema-prefix", required=True)
    parser.add_argument("--run-date", type=date.fromisoformat, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--bootstrap", choices=("true", "false"), default="false")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    spark = SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
    counts = generate(
        spark,
        catalog=args.catalog,
        schema_prefix=args.schema_prefix,
        run_date=args.run_date,
        seed=args.seed,
        bootstrap=args.bootstrap == "true",
    )
    print(json.dumps({"run_date": args.run_date.isoformat(), "rows": counts}, sort_keys=True))


if __name__ == "__main__":
    main()
