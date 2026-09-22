"""Generate versioned advisor briefings from the governed Gold detail surface.

This module intentionally never reads raw notes or protected-audit data, and it
never writes to a risk-score table.  A bad endpoint response is represented as
a failed advisor summary so the scoring product remains available.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any


MODEL_ID = "databricks-glm-5-3"
PROMPT_VERSION = "advisor-briefing-v1"
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
    r"\bdiagnos(?:e|ed|is|tic)\b",
    r"\b(depression|anxiety|mental health disorder)\b",
    r"\bdisciplin(?:ary|e|ed)\b",
    r"\b(probation|suspend|suspension|expel|expulsion)\b",
    r"\b(will|would|can)\s+(cause|ensure|guarantee)\s+(?:the )?(?:student )?(?:to )?(retain|retention|persistence)\b",
    r"\b(first[ -]generation|gender|race|ethnicity|age band|residency status)\b",
)
_CITATION = re.compile(r"\[([A-Za-z][A-Za-z0-9_]*)\]")
_OPTIONAL_JSON_FENCE = re.compile(r"\A```json\s*\n?(.*?)\n?```\s*\Z", re.DOTALL)


class GenerationFailure(ValueError):
    """A response could not safely become an advisor-facing briefing."""


def _json_value(value: Any) -> Any:
    """Normalize Spark values without allowing arbitrary object serialization."""
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def build_generation_input(student_detail: Mapping[str, Any]) -> dict[str, Any]:
    """Create a minimal prompt payload from approved Gold fields only."""
    facts = [
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
        "risk_score": float(student_detail["risk_score"]),
        "risk_tier": str(student_detail["risk_tier"]),
        "contributing_factors": contributing_factors,
        "facts": facts,
    }


def _messages(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    fact_ids = [fact["id"] for fact in payload["facts"]]
    system = (
        "You write concise advisor briefings. Return exactly one JSON object and no prose. "
        "Required keys are briefing, suggested_action, citations, unsupported_claims, "
        "prompt_version, and model_id. Cite every factual briefing sentence with an "
        "inline [fact_id] from the supplied facts; citations must list exactly those IDs. "
        "Do not diagnose, recommend discipline, infer protected traits, or claim an "
        "action causes retention. Set unsupported_claims to [] only when every claim is "
        "supported."
    )
    request = {
        "prompt_version": PROMPT_VERSION,
        "model_id": MODEL_ID,
        "allowed_fact_ids": fact_ids,
        "student": payload,
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(request, sort_keys=True)},
    ]


def _briefing_sentences(briefing: str) -> list[str]:
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", briefing) if sentence.strip()]


def _contains_student_fact(sentence: str) -> bool:
    """Identify factual signal language in an otherwise action-oriented sentence."""
    return bool(
        re.search(
            r"\b(attendance|assignments?|lms|activity|financial hold|gpa|risk score|risk tier)\b|\d+%",
            sentence,
            re.IGNORECASE,
        )
    )


def prohibited_matches(response: Mapping[str, Any]) -> list[str]:
    text = f"{response.get('briefing', '')} {response.get('suggested_action', '')}"
    return [pattern for pattern in PROHIBITED_PATTERNS if re.search(pattern, text, re.IGNORECASE)]


def validate_summary(
    response: Mapping[str, Any], *, allowed_fact_ids: Sequence[str] | set[str]
) -> dict[str, Any]:
    """Validate the complete output schema and grounding contract before storage."""
    if not isinstance(response, Mapping):
        raise GenerationFailure("response must be a JSON object")
    if set(response) != REQUIRED_RESPONSE_FIELDS:
        raise GenerationFailure("response fields must exactly match the briefing schema")
    if not isinstance(response["briefing"], str) or not response["briefing"].strip():
        raise GenerationFailure("briefing must be a non-empty string")
    if not isinstance(response["suggested_action"], str) or not response["suggested_action"].strip():
        raise GenerationFailure("suggested_action must be a non-empty string")
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

    allowed = set(allowed_fact_ids)
    cited = _CITATION.findall(
        f"{response['briefing']} {response['suggested_action']}"
    )
    if not cited:
        raise GenerationFailure("briefing requires at least one citation")
    if any(fact_id not in allowed for fact_id in cited):
        raise GenerationFailure("citation is not an allowed fact ID")
    if set(response["citations"]) != set(cited) or len(response["citations"]) != len(set(cited)):
        raise GenerationFailure("citations must exactly match inline citations")
    for sentence in _briefing_sentences(response["briefing"]):
        if not _CITATION.search(sentence):
            raise GenerationFailure("every factual briefing sentence requires a citation")
    for sentence in _briefing_sentences(response["suggested_action"]):
        if _contains_student_fact(sentence) and not _CITATION.search(sentence):
            raise GenerationFailure("every factual suggested_action sentence requires a citation")
    if matches := prohibited_matches(response):
        raise GenerationFailure(f"prohibited claim: {matches[0]}")
    return dict(response)


def parse_model_response(raw: str, *, allowed_fact_ids: Sequence[str] | set[str]) -> dict[str, Any]:
    """Parse strict JSON, accepting only a single optional ``json`` code fence."""
    if not isinstance(raw, str):
        raise GenerationFailure("model response must be text JSON")
    fenced = _OPTIONAL_JSON_FENCE.fullmatch(raw)
    candidate = fenced.group(1) if fenced else raw
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as error:
        raise GenerationFailure("model response is not strict JSON") from error
    return validate_summary(parsed, allowed_fact_ids=allowed_fact_ids)


def generate_validated_summary(
    payload: Mapping[str, Any],
    *,
    complete: Callable[[list[dict[str, str]]], str],
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Retry invalid/transient completions and return only a validated summary."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least one")
    allowed_fact_ids = [fact["id"] for fact in payload["facts"]]
    messages = _messages(payload)
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            summary = parse_model_response(
                complete(messages), allowed_fact_ids=allowed_fact_ids
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
    *, student_id: str, feature_as_of: Any, model_version: str, error: Exception
) -> dict[str, Any]:
    """Create a visible, non-scoring failure record for a governed summary."""
    timestamp = datetime.now(timezone.utc)
    summary_key = hashlib.sha256(
        f"{student_id}|{feature_as_of}|{model_version}|{PROMPT_VERSION}".encode()
    ).hexdigest()
    return {
        "summary_key": summary_key,
        "student_id": student_id,
        "feature_as_of": feature_as_of,
        "model_version": str(model_version),
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
        f"{student['model_version']}|{PROMPT_VERSION}"
    )
    return {
        "summary_key": hashlib.sha256(key_material.encode()).hexdigest(),
        "student_id": str(student["student_id"]),
        "feature_as_of": student["feature_as_of"],
        "model_version": str(student["model_version"]),
        "summary_version": PROMPT_VERSION,
        "prompt_version": summary["prompt_version"],
        "model_id": summary["model_id"],
        "briefing": summary["briefing"],
        "suggested_action": summary["suggested_action"],
        "citations": summary["citations"],
        "unsupported_claims": summary["unsupported_claims"],
        "generation_status": summary["generation_status"],
        "evaluation_status": "pending",
        "generation_attempts": summary["generation_attempts"],
        "error_message": None,
        "generated_at": timestamp,
        "risk_score": None,
    }


def persist_summaries(spark: Any, *, target: str, records: list[dict[str, Any]]) -> None:
    """Idempotently persist a prompt-versioned summary status table."""
    if not records:
        return
    from pyspark.sql import functions as F

    # ``risk_score`` is intentionally dropped: summaries cannot overwrite,
    # re-score, or become a source of truth for the governed risk product.
    frame = spark.createDataFrame(records).drop("risk_score")
    if not spark.catalog.tableExists(target):
        frame.limit(0).write.format("delta").saveAsTable(target)
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


def generate_advisor_summaries(
    *, catalog: str, schema_prefix: str, cohort_limit: int, endpoint: str = MODEL_ID, max_attempts: int = 3
) -> int:
    """Generate a bounded cohort from Gold ``student_detail`` only."""
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
    complete = databricks_completer(endpoint)
    records: list[dict[str, Any]] = []
    for row in cohort.toLocalIterator():
        student = row.asDict(recursive=True)
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
                )
            )
    persist_summaries(spark, target=target, records=records)
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
