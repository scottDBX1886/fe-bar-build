"""Render and execute idempotent governance SQL on Databricks serverless compute."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


_PLACEHOLDER = re.compile(r"\{\{[A-Z_]+\}\}")
_PRINCIPAL_GRANTS_MARKER = "-- PRINCIPAL GRANTS REQUIRE EXPLICIT APPROVAL"


def render_sql(template: str, *, catalog: str, schema_prefix: str) -> str:
    replacements = {
        "{{CATALOG}}": catalog,
        "{{BRONZE_SCHEMA}}": f"{schema_prefix}_bronze",
        "{{SILVER_SCHEMA}}": f"{schema_prefix}_silver",
        "{{GOLD_SCHEMA}}": f"{schema_prefix}_gold",
        "{{ML_SCHEMA}}": f"{schema_prefix}_ml",
        "{{CDC_SCHEMA}}": f"{schema_prefix}_cdc",
    }
    rendered = template
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)
    unresolved = sorted(set(_PLACEHOLDER.findall(rendered)))
    if unresolved:
        raise ValueError(f"unresolved SQL placeholders: {unresolved}")
    return rendered


def sql_statements(sql: str) -> list[str]:
    """Split SQL on terminators outside string literals after removing line comments."""
    uncommented = "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--")
    )
    statements: list[str] = []
    current: list[str] = []
    in_string = False
    index = 0
    while index < len(uncommented):
        character = uncommented[index]
        if character == "'":
            if in_string and index + 1 < len(uncommented) and uncommented[index + 1] == "'":
                current.extend(["'", "'"])
                index += 2
                continue
            in_string = not in_string
        if character == ";" and not in_string:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(character)
        index += 1
    trailing = "".join(current).strip()
    if trailing:
        statements.append(trailing)
    return statements


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema-prefix", required=True)
    parser.add_argument("--bundle-root", required=True)
    parser.add_argument("--mode", choices=("bootstrap", "core-policies"), required=True)
    return parser.parse_args()


def main(args: argparse.Namespace) -> dict[str, object]:
    spark = globals().get("spark")
    if spark is None:
        from pyspark.sql import SparkSession

        spark = SparkSession.builder.getOrCreate()

    filename = "bootstrap.sql" if args.mode == "bootstrap" else "policies.sql"
    template = (Path(args.bundle_root) / "src" / "governance" / filename).read_text(
        encoding="utf-8"
    )
    if args.mode == "core-policies":
        template = template.split(_PRINCIPAL_GRANTS_MARKER, maxsplit=1)[0]
    rendered = render_sql(
        template, catalog=args.catalog, schema_prefix=args.schema_prefix
    )
    statements = sql_statements(rendered)
    for statement in statements:
        spark.sql(statement).collect()
    output = {"mode": args.mode, "statements_executed": len(statements)}
    dbutils = globals().get("dbutils")
    if dbutils is not None:
        dbutils.notebook.exit(json.dumps(output))
    return output


if __name__ == "__main__":
    print(json.dumps(main(_arguments())))
