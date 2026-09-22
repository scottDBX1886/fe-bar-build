"""Plan and configure the two independent Task 8 Lakebase sync directions."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from typing import Mapping


@dataclass(frozen=True)
class SyncPlan:
    catalog: str
    uc_cdc_schema: str
    lakebase_catalog: str
    branch: str
    database: str
    postgres_database: str
    postgres_serving_schema: str
    postgres_write_schema: str
    serving_syncs: Mapping[str, str]

    def __post_init__(self) -> None:
        if self.postgres_serving_schema == self.postgres_write_schema:
            raise ValueError("serving and writeback schemas must be distinct")
        cdc_prefix = f"{self.catalog}.{self.uc_cdc_schema}."
        writeback_names = {"interventions", "intervention_events"}
        for target, source in self.serving_syncs.items():
            leaf = target.rsplit(".", 1)[-1]
            if source.startswith(cdc_prefix) or leaf in writeback_names:
                raise ValueError("sync loop: writeback history cannot feed a serving sync")


def build_sync_plan(
    *, catalog: str, schema_prefix: str, lakebase_catalog: str,
    branch: str, database: str,
) -> SyncPlan:
    serving_schema = f"{schema_prefix}_serving"
    gold = f"{catalog}.{schema_prefix}_gold"
    return SyncPlan(
        catalog=catalog,
        uc_cdc_schema=f"{schema_prefix}_cdc",
        lakebase_catalog=lakebase_catalog,
        branch=branch,
        database=database,
        postgres_database="databricks_postgres",
        postgres_serving_schema=serving_schema,
        postgres_write_schema=f"{schema_prefix}_app",
        serving_syncs={
            f"{lakebase_catalog}.{serving_schema}.executive_retention_metrics":
                f"{gold}.executive_retention_metrics",
            f"{lakebase_catalog}.{serving_schema}.risk_trends":
                f"{gold}.risk_trends",
        },
    )


def _run(command: list[str], *, profile: str) -> None:
    subprocess.run([*command, "--profile", profile], check=True)


def _exists(command: list[str], *, profile: str) -> bool:
    result = subprocess.run(
        [*command, "--profile", profile],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def configure(plan: SyncPlan, *, profile: str) -> None:
    """Create syncs from an already reviewed plan; existing resources are tolerated."""
    for target, source in plan.serving_syncs.items():
        if _exists(
            [
                "databricks", "postgres", "get-synced-table",
                f"synced_tables/{target}",
            ],
            profile=profile,
        ):
            continue
        payload = {
            "spec": {
                "source_table_full_name": source,
                "primary_key_columns": _primary_keys(target),
                "scheduling_policy": "TRIGGERED",
                "branch": plan.branch,
                "postgres_database": plan.postgres_database,
                "create_database_objects_if_missing": True,
                "new_pipeline_spec": {
                    "storage_catalog": plan.catalog,
                    "storage_schema": plan.uc_cdc_schema,
                },
            }
        }
        _run(
            [
                "databricks", "postgres", "create-synced-table", target,
                "--json", json.dumps(payload, separators=(",", ":")),
            ],
            profile=profile,
        )
    cdf_name = (
        f"{plan.database}/cdf-configs/student_retention_interventions"
    )
    if _exists(
        ["databricks", "postgres", "get-cdf-config", cdf_name],
        profile=profile,
    ):
        return
    _run(
        [
            "databricks", "postgres", "create-cdf-config", plan.database,
            plan.catalog, plan.uc_cdc_schema, plan.postgres_write_schema,
            "--cdf-config-id", "student_retention_interventions",
        ],
        profile=profile,
    )


def _primary_keys(target: str) -> list[str]:
    table = target.rsplit(".", 1)[-1]
    if table == "executive_retention_metrics":
        return [
            "program_code", "cohort_code", "term_code", "score_date",
            "risk_tier", "intervention_status",
        ]
    if table == "risk_trends":
        return [
            "program_code", "cohort_code", "term_code", "score_date",
            "risk_tier", "intervention_status",
        ]
    raise ValueError(f"no primary-key contract for {table}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema-prefix", required=True)
    parser.add_argument("--lakebase-catalog", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    plan = build_sync_plan(
        catalog=args.catalog,
        schema_prefix=args.schema_prefix,
        lakebase_catalog=args.lakebase_catalog,
        branch=args.branch,
        database=args.database,
    )
    print(json.dumps(asdict(plan), indent=2, sort_keys=True))
    if args.apply:
        configure(plan, profile=args.profile)


if __name__ == "__main__":
    main()
