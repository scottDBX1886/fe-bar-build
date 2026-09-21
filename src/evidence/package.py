"""Validate standardized, sanitized execution-evidence packages."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


REQUIRED_FILES = frozenset(
    {
        "README.md",
        "manifest.json",
        "run-output.json",
        "queries.sql",
        "query-results.json",
        "verification.txt",
    }
)
JSON_FILES = frozenset({"manifest.json", "run-output.json", "query-results.json"})

_SECRET_PATTERNS = (
    re.compile(r"\bdapi[a-zA-Z0-9]{20,}\b"),
    re.compile(r"authorization\s*:\s*bearer\s+\S+", re.IGNORECASE),
    re.compile(r"client_secret\s*[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"postgres(?:ql)?://[^\s:/]+:[^\s@]+@", re.IGNORECASE),
)


class EvidenceValidationError(ValueError):
    """Raised when an evidence package is incomplete or unsafe."""


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvidenceValidationError(f"Invalid JSON in {path.name}: {error}") from error


def _validate_manifest(manifest: Any, package: Path) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise EvidenceValidationError("manifest.json must contain a JSON object")

    for field in ("schema_version", "task", "captured_at", "profile", "artifacts"):
        if field not in manifest:
            raise EvidenceValidationError(f"manifest.json is missing {field}")

    if manifest["schema_version"] != "1.0":
        raise EvidenceValidationError("manifest.json schema_version must be 1.0")
    if not isinstance(manifest["task"], str) or not manifest["task"]:
        raise EvidenceValidationError("manifest.json task must be a nonempty string")
    if not isinstance(manifest["profile"], str) or not manifest["profile"]:
        raise EvidenceValidationError("manifest.json profile must be a nonempty string")
    try:
        datetime.fromisoformat(str(manifest["captured_at"]).replace("Z", "+00:00"))
    except ValueError as error:
        raise EvidenceValidationError("manifest.json captured_at must be ISO-8601") from error

    artifacts = manifest["artifacts"]
    if not isinstance(artifacts, list) or not all(isinstance(item, str) for item in artifacts):
        raise EvidenceValidationError("manifest.json artifacts must be a string array")
    listed = set(artifacts)
    if not REQUIRED_FILES.issubset(listed):
        missing = sorted(REQUIRED_FILES - listed)
        raise EvidenceValidationError(f"manifest artifacts omit required files: {missing}")
    absent = sorted(item for item in listed if not (package / item).is_file())
    if absent:
        raise EvidenceValidationError(f"manifest artifacts reference absent files: {absent}")
    return manifest


def _scan_for_secrets(package: Path, artifacts: list[str]) -> None:
    for relative_path in artifacts:
        path = package / relative_path
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise EvidenceValidationError(f"Cannot inspect {relative_path}: {error}") from error
        for pattern in _SECRET_PATTERNS:
            if pattern.search(content):
                raise EvidenceValidationError(
                    f"Potential secret detected in evidence artifact: {relative_path}"
                )


def validate_evidence_package(package: Path) -> dict[str, Any]:
    package = Path(package)
    missing = sorted(name for name in REQUIRED_FILES if not (package / name).is_file())
    if missing:
        raise EvidenceValidationError(f"Missing required evidence files: {missing}")

    parsed = {name: _load_json(package / name) for name in JSON_FILES}
    manifest = _validate_manifest(parsed["manifest.json"], package)
    _scan_for_secrets(package, manifest["artifacts"])
    return manifest
