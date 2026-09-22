"""Generate versioned advisor briefings from the governed Gold detail surface.

This module intentionally never reads raw notes or protected-audit data, and it
never writes to a risk-score table.  A bad endpoint response is represented as
a failed advisor summary so the scoring product remains available.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any


MODEL_ID = "databricks-glm-5-3"
PROMPT_VERSION = "advisor-briefing-v2"
TEMPERATURE = 0.1
MAX_TOKENS = 1200
DEFAULT_COHORT_LIMIT = 50

# These are the only signals that can enter a prompt.  An explicit allowlist is
# safer than trying to enumerate every restricted source field.
APPROVED_FACT_FIELDS = (
    "attendance_rate_28d",
    "missed_assignments_28d",
    "days_since_lms_activity",
    "financial_hold_flag",
    "cumulative_gpa",
)
REQUIRED_RESPONSE_FIELDS = {
    "briefing",
    "suggested_action",
    "citations",
    "unsupported_claims",
    "prompt_version",
    "model_id",
}
PROHIBITED_PATTERNS = (
    r"\b(diagnos(?:e|ed|is|tic)|depression|anxiety|adhd|mental health)\b",
    r"\b(disciplin(?:ary|e|ed)|punish|punishment|probation|suspend|suspension|expel|expulsion)\b",
    r"\b(will|would|can|shall|may)\s+(cause|ensure|guarantee|improve|increase)\s+(?:the )?(?:student )?(?:to )?(retain|retention|persistence)\b",
    r"\b(first[ -]generation|gender|race|ethnicity|age band|residency status|female|male|nonbinary)\b",
)
_OPTIONAL_JSON_FENCE = re.compile(r"\A```json\s*\n?(.*?)\n?```\s*\Z", re.DOTALL)
ALLOWED_ACTIONS = {
    "offer_supportive_check_in": "Offer a supportive check-in and ask whether the student would like help identifying next steps.",
    "offer_resource_navigation": "Offer to help the student identify and navigate available support resources.",
    "ask_about_barriers": "Invite the student to discuss any barriers they would like support addressing.",
}


class GenerationFailure(ValueError):
    """A response could not safely become an advisor-facing briefing."""


def _json_value(value: Any) -> Any:
    """Normalize Spark values without allowing arbitrary object serialization."""
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _require_endpoint(endpoint: str) -> None:
    if endpoint != MODEL_ID:
        raise ValueError(f"Task 7 requires the approved endpoint: {MODEL_ID}")


def _fact_values_equal(actual: Any, expected: Any) -> bool:
    """Compare values with JSON semantics, avoiding Python's ``False == 0``."""
    return json.dumps(actual, sort_keys=True, separators=(",", ":")) == json.dumps(
        expected, sort_keys=True, separators=(",", ":")
    )


def _allowed_fact_map(
    *,
    allowed_facts: Sequence[Mapping[str, Any]] | None,
    allowed_fact_ids: Sequence[str] | set[str] | None,
) -> dict[str, Any | None]:
    if allowed_facts is not None:
        result: dict[str, Any | None] = {}
        for fact in allowed_facts:
            if set(fact) != {"id", "value"} or not isinstance(fact["id"], str):
                raise GenerationFailure("allowed facts must contain id and value")
            result[fact["id"]] = fact["value"]
        return result
    return {fact_id: None for fact_id in (allowed_fact_ids or [])}


def build_generation_input(student_detail: Mapping[str, Any]) -> dict[str, Any]:
    """Create a minimal prompt payload from approved Gold fields only."""
    risk_score = float(student_detail["risk_score"])
    if not math.isfinite(risk_score):
        raise GenerationFailure("risk_score must be finite")
    facts = [
        {"id": "risk_score", "value": risk_score},
        {"id": "risk_tier", "value": str(student_detail["risk_tier"])},
    ] + [
        {"id": field, "value": _json_value(student_detail[field])}
        for field in APPROVED_FACT_FIELDS
        if field in student_detail and student_detail[field] is not None
    ]
    allowed_ids = {fact["id"] for fact in facts}
    contributing_factors = [
        factor
        for factor in student_detail.get("leading_factors", []) or []
        if factor in allowed_ids
    ]
    return {
        "student_id": str(student_detail["student_id"]),
        "risk_score": risk_score,
        "risk_tier": str(student_detail["risk_tier"]),
        "contributing_factors": contributing_factors,
        "facts": facts,
    }


def _messages(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    system = (
        "You write concise advisor briefings. Return exactly one JSON object and no prose. "
        "Required keys are briefing, suggested_action, citations, unsupported_claims, "
        "prompt_version, and model_id. briefing is a non-empty JSON array of objects with "
        "exactly fact_id and fact_value, copied exactly from supplied facts. citations must "
        "be the matching unique fact_id array. suggested_action must be one of "
        f"{sorted(ALLOWED_ACTIONS)}. Do not diagnose, recommend discipline, infer protected "
        "traits, or claim an action causes retention. Set unsupported_claims to []."
    )
    request = {
        "prompt_version": PROMPT_VERSION,
        "model_id": MODEL_ID,
        "student": payload,
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(request, sort_keys=True)},
    ]


def _briefing_sentences(briefing: str) -> list[str]:
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", briefing) if sentence.strip()]


def render_briefing(facts: Sequence[Mapping[str, Any]]) -> str:
    """Render the sole advisor-visible factual wording from verified fact values."""
    rendered: list[str] = []
    for fact in facts:
        fact_id, value = fact["fact_id"], fact["fact_value"]
        if fact_id == "risk_score":
            rendered.append(f"Current governed risk score is {value:.2f} [{fact_id}].")
        elif fact_id == "risk_tier":
            rendered.append(f"Current governed risk tier is {value} [{fact_id}].")
        elif fact_id == "attendance_rate_28d":
            rendered.append(f"Attendance was {value:.0%} in the last 28 days [{fact_id}].")
        elif fact_id == "missed_assignments_28d":
            rendered.append(f"{value} assignments were missed in the last 28 days [{fact_id}].")
        elif fact_id == "days_since_lms_activity":
            rendered.append(f"Most recent LMS activity was {value} days ago [{fact_id}].")
        elif fact_id == "financial_hold_flag":
            sentence = "A financial hold is active" if value else "No financial hold is active"
            rendered.append(f"{sentence} [{fact_id}].")
        elif fact_id == "cumulative_gpa":
            rendered.append(f"Cumulative GPA is {value:.2f} [{fact_id}].")
        else:  # Validate before persistence makes this unreachable.
            raise GenerationFailure(f"cannot render unapproved fact: {fact_id}")
    return " ".join(rendered)


def prohibited_matches(response: Mapping[str, Any]) -> list[str]:
    text = f"{response.get('briefing', '')} {response.get('suggested_action', '')}"
    return [pattern for pattern in PROHIBITED_PATTERNS if re.search(pattern, text, re.IGNORECASE)]


def validate_summary(
    response: Mapping[str, Any], *,
    allowed_facts: Sequence[Mapping[str, Any]] | None = None,
    allowed_fact_ids: Sequence[str] | set[str] | None = None,
) -> dict[str, Any]:
    """Validate the complete output schema and grounding contract before storage."""
    if not isinstance(response, Mapping):
        raise GenerationFailure("response must be a JSON object")
    if set(response) != REQUIRED_RESPONSE_FIELDS:
        raise GenerationFailure("response fields must exactly match the briefing schema")
    if not isinstance(response["briefing"], list) or not response["briefing"]:
        raise GenerationFailure("briefing must be a non-empty list of structured facts")
    if response["suggested_action"] not in ALLOWED_ACTIONS:
        raise GenerationFailure("suggested_action must be an approved action code")
    if not isinstance(response["citations"], list) or not all(
        isinstance(item, str) for item in response["citations"]
    ):
        raise GenerationFailure("citations must be a list of fact IDs")
    if not isinstance(response["unsupported_claims"], list) or not all(
        isinstance(item, str) for item in response["unsupported_claims"]
    ):
        raise GenerationFailure("unsupported_claims must be a list of strings")
    if response["unsupported_claims"]:
        raise GenerationFailure("unsupported claims cannot be accepted")
    if response["prompt_version"] != PROMPT_VERSION:
        raise GenerationFailure("prompt_version does not match the governed prompt")
    if response["model_id"] != MODEL_ID:
        raise GenerationFailure("model_id does not match the selected endpoint")

    allowed = _allowed_fact_map(allowed_facts=allowed_facts, allowed_fact_ids=allowed_fact_ids)
    briefing_ids: list[str] = []
    for item in response["briefing"]:
        if not isinstance(item, Mapping) or set(item) != {"fact_id", "fact_value"}:
            raise GenerationFailure("briefing facts require exactly fact_id and fact_value")
        fact_id = item["fact_id"]
        if not isinstance(fact_id, str) or fact_id not in allowed:
            raise GenerationFailure("briefing fact is not an allowed fact ID")
        expected = allowed[fact_id]
        if expected is not None and not _fact_values_equal(item["fact_value"], expected):
            raise GenerationFailure("briefing fact value must exactly match the supplied fact")
        briefing_ids.append(fact_id)
    if len(set(briefing_ids)) != len(briefing_ids):
        raise GenerationFailure("briefing facts must not repeat")
    if not briefing_ids:
        raise GenerationFailure("briefing requires at least one citation")
    if response["citations"] != briefing_ids:
        raise GenerationFailure("citations must exactly match briefing fact IDs")
    if matches := prohibited_matches(response):
        raise GenerationFailure(f"prohibited claim: {matches[0]}")
    return dict(response)


def parse_model_response(
    raw: str, *, allowed_facts: Sequence[Mapping[str, Any]] | None = None,
    allowed_fact_ids: Sequence[str] | set[str] | None = None,
) -> dict[str, Any]:
    """Parse strict JSON, accepting only a single optional ``json`` code fence."""
    if not isinstance(raw, str):
        raise GenerationFailure("model response must be text JSON")
    fenced = _OPTIONAL_JSON_FENCE.fullmatch(raw)
    candidate = fenced.group(1) if fenced else raw
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as error:
        raise GenerationFailure("model response is not strict JSON") from error
    return validate_summary(parsed, allowed_facts=allowed_facts, allowed_fact_ids=allowed_fact_ids)


def generate_validated_summary(
    payload: Mapping[str, Any],
    *,
    complete: Callable[[list[dict[str, str]]], str],
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Retry invalid/transient completions and return only a validated summary."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least one")
    messages = _messages(payload)
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            summary = parse_model_response(
                complete(messages), allowed_facts=payload["facts"]
            )
            return {
                **summary,
                "generation_status": "succeeded",
                "generation_attempts": attempt,
            }
        except Exception as error:  # endpoint and validation failures both stay isolated
            last_error = error
    raise GenerationFailure(f"generation failed after {max_attempts} attempts: {last_error}")


def _completion_text(response: Any) -> str:
    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError, TypeError) as error:
        raise GenerationFailure("endpoint response did not contain a completion") from error
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, Mapping) else str(part) for part in content
        )
    raise GenerationFailure("endpoint completion content was not text")


def databricks_completer(endpoint: str = MODEL_ID) -> Callable[[list[dict[str, str]]], str]:
    """Build the low-temperature Foundation Model call without native JSON mode.

    The selected endpoint ignores/rejects ``response_format``.  Prompt-level
    JSON instructions plus local parsing are therefore the governing contract.
    """
    _require_endpoint(endpoint)
    from databricks.sdk import WorkspaceClient

    client = WorkspaceClient()

    def complete(messages: list[dict[str, str]]) -> str:
        response = client.serving_endpoints.query(
            name=endpoint,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        return _completion_text(response)

    return complete


def failure_summary_record(
    *, student_id: str, feature_as_of: Any, model_version: str, error: Exception,
    generation_run_id: str = "unknown",
) -> dict[str, Any]:
    """Create a visible, non-scoring failure record for a governed summary."""
    timestamp = datetime.now(timezone.utc)
    summary_key = hashlib.sha256(
        f"{student_id}|{feature_as_of}|{model_version}|{PROMPT_VERSION}|{MODEL_ID}".encode()
    ).hexdigest()
    return {
        "summary_key": summary_key,
        "student_id": student_id,
        "feature_as_of": feature_as_of,
        "model_version": str(model_version),
        "generation_run_id": generation_run_id,
        "summary_version": PROMPT_VERSION,
        "prompt_version": PROMPT_VERSION,
        "model_id": MODEL_ID,
        "briefing": None,
        "suggested_action": None,
        "citations": [],
        "unsupported_claims": [],
        "generation_status": "failed",
        "evaluation_status": "not_evaluated",
        "generation_attempts": 0,
        "error_message": str(error)[:2000],
        "generated_at": timestamp,
        # Explicitly absent: no risk score or risk mutation belongs in this table.
        "risk_score": None,
    }


def _summary_record(student: Mapping[str, Any], summary: Mapping[str, Any]) -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc)
    key_material = (
        f"{student['student_id']}|{student['feature_as_of']}|"
        f"{student['model_version']}|{PROMPT_VERSION}|{MODEL_ID}"
    )
    return {
        "summary_key": hashlib.sha256(key_material.encode()).hexdigest(),
        "student_id": str(student["student_id"]),
        "feature_as_of": student["feature_as_of"],
        "model_version": str(student["model_version"]),
        "generation_run_id": str(student["generation_run_id"]),
        "summary_version": PROMPT_VERSION,
        "prompt_version": summary["prompt_version"],
        "model_id": summary["model_id"],
        "briefing": render_briefing(summary["briefing"]),
        "suggested_action": ALLOWED_ACTIONS[summary["suggested_action"]],
        "citations": summary["citations"],
        "unsupported_claims": summary["unsupported_claims"],
        "generation_status": summary["generation_status"],
        "evaluation_status": "pending",
        "generation_attempts": summary["generation_attempts"],
        "error_message": None,
        "generated_at": timestamp,
        "risk_score": None,
    }


def _summary_schema() -> Any:
    """Use an explicit nullable schema so an all-failure first run is writable."""
    from pyspark.sql.types import (
        ArrayType, IntegerType, StringType, StructField, StructType, TimestampType,
    )

    return StructType([
        StructField("summary_key", StringType(), False),
        StructField("student_id", StringType(), False),
        StructField("feature_as_of", TimestampType(), True),
        StructField("model_version", StringType(), False),
        StructField("generation_run_id", StringType(), False),
        StructField("summary_version", StringType(), False),
        StructField("prompt_version", StringType(), False),
        StructField("model_id", StringType(), False),
        StructField("briefing", StringType(), True),
        StructField("suggested_action", StringType(), True),
        StructField("citations", ArrayType(StringType(), containsNull=False), False),
        StructField("unsupported_claims", ArrayType(StringType(), containsNull=False), False),
        StructField("generation_status", StringType(), False),
        StructField("evaluation_status", StringType(), False),
        StructField("generation_attempts", IntegerType(), False),
        StructField("error_message", StringType(), True),
        StructField("generated_at", TimestampType(), False),
    ])


def _schema_sql_type(field: Any) -> str:
    """Render the Spark type accepted by ``ALTER TABLE ADD COLUMNS``."""
    return field.dataType.simpleString().upper()


def ensure_summary_schema(spark: Any, *, target: str, schema: Any) -> None:
    """Add only absent contract columns to a pre-existing summary table."""
    existing = {field.name for field in spark.table(target).schema.fields}
    missing = [field for field in schema.fields if field.name not in existing]
    if not missing:
        return
    columns = ", ".join(
        f"{field.name} {_schema_sql_type(field)}" for field in missing
    )
    spark.sql(f"ALTER TABLE {target} ADD COLUMNS ({columns})")


def persist_summaries(spark: Any, *, target: str, records: list[dict[str, Any]]) -> None:
    """Idempotently persist a prompt-versioned summary status table."""
    if not records:
        return
    # ``risk_score`` is intentionally dropped: summaries cannot overwrite,
    # re-score, or become a source of truth for the governed risk product.
    schema = _summary_schema()
    frame = spark.createDataFrame(records, schema=schema).drop("risk_score")
    if not spark.catalog.tableExists(target):
        frame.limit(0).write.format("delta").saveAsTable(target)
    else:
        ensure_summary_schema(spark, target=target, schema=schema)
    frame.createOrReplaceTempView("_advisor_summary_upserts")
    spark.sql(
        f"""
        MERGE INTO {target} AS target
        USING _advisor_summary_upserts AS source
          ON target.summary_key = source.summary_key
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
        """
    )


def publish_generation_run_id(
    generation_run_id: str, *, task_values: Any | None = None
) -> None:
    """Publish the cohort identity through the supported Databricks runtime API."""
    if task_values is None:
        try:
            from databricks.sdk.runtime import dbutils

            task_values = dbutils.jobs.taskValues
        except Exception as error:
            raise RuntimeError("Databricks task values are required for evaluation handoff") from error
    try:
        task_values.set(key="generation_run_id", value=generation_run_id)
    except Exception as error:
        raise RuntimeError("failed to publish generation_run_id task value") from error


def persist_and_publish_generation(
    spark: Any, *, target: str, records: list[dict[str, Any]],
    generation_run_id: str, task_values: Any | None = None,
) -> None:
    """Persist a cohort before publishing the exact identity evaluation must use."""
    persist_summaries(spark, target=target, records=records)
    publish_generation_run_id(generation_run_id, task_values=task_values)


def generate_advisor_summaries(
    *, catalog: str, schema_prefix: str, cohort_limit: int, endpoint: str = MODEL_ID,
    max_attempts: int = 3, task_values: Any | None = None,
) -> int:
    """Generate a bounded cohort from Gold ``student_detail`` only."""
    _require_endpoint(endpoint)
    if cohort_limit < 1 or cohort_limit > DEFAULT_COHORT_LIMIT:
        raise ValueError(f"cohort_limit must be between 1 and {DEFAULT_COHORT_LIMIT}")
    from pyspark.sql import SparkSession, functions as F

    spark = globals().get("spark") or SparkSession.builder.getOrCreate()
    source = f"{catalog}.{schema_prefix}_gold.student_detail"
    target = f"{catalog}.{schema_prefix}_gold.advisor_summaries"
    cohort = (
        spark.read.table(source)
        .orderBy(F.col("risk_score").desc(), F.col("student_id"))
        .limit(cohort_limit)
    )
    students = [row.asDict(recursive=True) for row in cohort.toLocalIterator()]
    cohort_material = [
        f"{row['student_id']}|{row['feature_as_of']}|{row['model_version']}" for row in students
    ]
    generation_run_id = hashlib.sha256(
        f"{PROMPT_VERSION}|{MODEL_ID}|{'|'.join(cohort_material)}".encode()
    ).hexdigest()
    complete = databricks_completer(endpoint)
    records: list[dict[str, Any]] = []
    for student in students:
        student["generation_run_id"] = generation_run_id
        try:
            summary = generate_validated_summary(
                build_generation_input(student), complete=complete, max_attempts=max_attempts
            )
            records.append(_summary_record(student, summary))
        except Exception as error:
            records.append(
                failure_summary_record(
                    student_id=str(student["student_id"]),
                    feature_as_of=student["feature_as_of"],
                    model_version=str(student["model_version"]),
                    error=error,
                    generation_run_id=generation_run_id,
                )
            )
    persist_and_publish_generation(
        spark,
        target=target,
        records=records,
        generation_run_id=generation_run_id,
        task_values=task_values,
    )
    return len(records)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema-prefix", required=True)
    parser.add_argument("--cohort-limit", type=int, default=DEFAULT_COHORT_LIMIT)
    parser.add_argument("--endpoint", default=MODEL_ID)
    parser.add_argument("--max-attempts", type=int, default=3)
    return parser.parse_args()


if __name__ == "__main__":
    print(generate_advisor_summaries(**vars(_arguments())))
