"""Incrementally score the latest student snapshot into immutable Gold history."""

from __future__ import annotations

import argparse
from typing import Any


def score_registered_model(
    *, catalog: str, schema_prefix: str, model_version: str | None = None,
    model_alias: str = "prod",
) -> int:
    import mlflow
    from mlflow import MlflowClient
    from pyspark.sql import functions as F
    from pyspark.sql.types import ArrayType, DoubleType, StringType, StructField, StructType

    spark = globals().get("spark")
    if spark is None:
        from pyspark.sql import SparkSession

        spark = SparkSession.builder.getOrCreate()

    model_name = f"{catalog}.{schema_prefix}_ml.student_stopout_risk"
    model_uri = f"models:/{model_name}@{model_alias}"
    resolved_version = model_version or str(
        MlflowClient(registry_uri="databricks-uc")
        .get_model_version_by_alias(model_name, model_alias)
        .version
    )
    result_type = StructType(
        [
            StructField("risk_score", DoubleType(), True),
            StructField("leading_factors", ArrayType(StringType(), True), True),
        ]
    )
    predict = mlflow.pyfunc.spark_udf(spark, model_uri=model_uri, result_type=result_type)

    source = f"{catalog}.{schema_prefix}_silver.student_daily_snapshots"
    target = f"{catalog}.{schema_prefix}_gold.student_risk_score_history"
    features = spark.read.table(source)
    latest = features.filter(
        F.col("feature_as_of") == features.agg(F.max("feature_as_of")).first()[0]
    )
    excluded = {
        "student_id", "advisor_id", "feature_as_of", "max_feature_event_at",
        "synthetic_net_tuition_next_term",
    }
    model_columns = [column for column in latest.columns if column not in excluded]
    scored = (
        latest.withColumn("prediction", predict(F.struct(*[F.col(c) for c in model_columns])))
        .select(
            "student_id",
            "feature_as_of",
            F.lit(resolved_version).alias("model_version"),
            F.col("prediction.risk_score").alias("risk_score"),
            F.when(F.col("prediction.risk_score") >= 0.6, F.lit("high"))
            .when(F.col("prediction.risk_score") >= 0.3, F.lit("medium"))
            .otherwise(F.lit("low"))
            .alias("risk_tier"),
            F.col("prediction.leading_factors").alias("leading_factors"),
            F.current_timestamp().alias("scored_at"),
        )
    )
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema_prefix}_gold")
    if not spark.catalog.tableExists(target):
        scored.limit(0).write.format("delta").saveAsTable(target)
        spark.sql(f"ALTER TABLE {target} SET TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')")

    scored.createOrReplaceTempView("_student_risk_scores_to_insert")
    spark.sql(
        f"""
        MERGE INTO {target} AS target
        USING _student_risk_scores_to_insert AS source
          ON target.student_id = source.student_id
         AND target.feature_as_of = source.feature_as_of
         AND target.model_version = source.model_version
        WHEN NOT MATCHED THEN INSERT *
        """
    )
    return scored.count()


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema-prefix", required=True)
    parser.add_argument("--model-version")
    parser.add_argument("--model-alias", default="prod")
    return parser.parse_args()


if __name__ == "__main__":
    args = _arguments()
    print(score_registered_model(**vars(args)))
