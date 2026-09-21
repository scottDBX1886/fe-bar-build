"""Validated runtime configuration shared by Databricks workloads."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass


_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_LAYERS = ("bronze", "silver", "gold", "ml", "cdc")


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _identifier(name: str, value: str) -> str:
    if not _IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must be a valid Unity Catalog identifier")
    return value


@dataclass(frozen=True)
class RuntimeConfig:
    """Runtime values that identify this deployment's governed data."""

    catalog: str
    schema_prefix: str
    warehouse_id: str
    seed: int

    @classmethod
    def from_env(cls) -> RuntimeConfig:
        catalog = _identifier("RETENTION_CATALOG", _required("RETENTION_CATALOG"))
        schema_prefix = _identifier(
            "RETENTION_SCHEMA_PREFIX", _required("RETENTION_SCHEMA_PREFIX")
        )
        warehouse_id = _required("RETENTION_WAREHOUSE_ID")
        seed_value = _required("RETENTION_SEED")
        try:
            seed = int(seed_value)
        except ValueError as error:
            raise ValueError("RETENTION_SEED must be an integer") from error

        return cls(
            catalog=catalog,
            schema_prefix=schema_prefix,
            warehouse_id=warehouse_id,
            seed=seed,
        )

    def schema_name(self, layer: str) -> str:
        if layer not in _LAYERS:
            raise ValueError(f"Unknown layer: {layer}")
        return f"{self.schema_prefix}_{layer}"

    @property
    def bronze_schema(self) -> str:
        return self.schema_name("bronze")

    @property
    def silver_schema(self) -> str:
        return self.schema_name("silver")

    @property
    def gold_schema(self) -> str:
        return self.schema_name("gold")

    @property
    def ml_schema(self) -> str:
        return self.schema_name("ml")

    @property
    def cdc_schema(self) -> str:
        return self.schema_name("cdc")

    def table_name(self, layer: str, table: str) -> str:
        table_name = _identifier("table", table)
        return f"{self.catalog}.{self.schema_name(layer)}.{table_name}"
