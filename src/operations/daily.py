"""Fail-fast operational checks and structured evidence for the daily workflow."""

from __future__ import annotations

import argparse
import json
from typing import Any


SERVING_TABLES = (
    "serving_executive_retention_metrics",
    "serving_risk_trends",
)


def check_serving_sync(*, catalog: str, schema_prefix: str) -> dict[str, Any]:
    """Verify both approved UC-to-Lakebase sync resources are online."""
    from databricks.sdk import WorkspaceClient

    client = WorkspaceClient().api_client
    statuses: dict[str, str] = {}
    for table in SERVING_TABLES:
        name = f"synced_tables/{catalog}.{schema_prefix}_gold.{table}"
        payload = client.do("GET", f"/api/2.0/postgres/{name}")
        status = str(payload.get("status", {}).get("detailed_state", "UNKNOWN"))
        statuses[table] = status
        if status != "SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE":
            raise RuntimeError(f"{table} sync is not online: {status}")
    return {"serving_sync": statuses}


def capture_evidence(*, catalog: str, schema_prefix: str, run_date: str) -> dict[str, Any]:
    """Capture bounded operational counts without exporting student-level data."""
    from pyspark.sql import SparkSession

    spark = globals().get("spark") or SparkSession.builder.getOrCreate()
    gold = f"{catalog}.{schema_prefix}_gold"
    cdc = f"{catalog}.{schema_prefix}_cdc"
    queries = {
        "risk_history_rows": f"SELECT count(*) value FROM {gold}.student_risk_score_history",
        "executive_metric_rows": f"SELECT count(*) value FROM {gold}.executive_retention_metrics",
        "advisor_summary_rows": f"SELECT count(*) value FROM {gold}.advisor_summaries",
        "intervention_cdc_rows": f"SELECT count(*) value FROM {cdc}.lb_interventions_history",
        "intervention_event_cdc_rows": f"SELECT count(*) value FROM {cdc}.lb_intervention_events_history",
    }
    counts = {key: int(spark.sql(sql).first()["value"]) for key, sql in queries.items()}
    freshness = spark.sql(
        f"SELECT max(data_freshness_at) value FROM {gold}.executive_retention_metrics"
    ).first()["value"]
    return {
        "run_date": run_date,
        "counts": counts,
        "executive_freshness": freshness.isoformat() if freshness else None,
    }


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("serving-sync-check", "capture-evidence"), required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema-prefix", required=True)
    parser.add_argument("--run-date", default="")
    return parser.parse_args()


if __name__ == "__main__":
    args = _arguments()
    if args.mode == "serving-sync-check":
        result = check_serving_sync(catalog=args.catalog, schema_prefix=args.schema_prefix)
    else:
        result = capture_evidence(
            catalog=args.catalog, schema_prefix=args.schema_prefix, run_date=args.run_date
        )
    print(json.dumps(result, default=str, sort_keys=True))
