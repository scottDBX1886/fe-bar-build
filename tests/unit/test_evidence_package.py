import json
from pathlib import Path

import pytest

from src.evidence.package import EvidenceValidationError, validate_evidence_package


REQUIRED_FILES = {
    "README.md": "# Evidence\n",
    "manifest.json": json.dumps(
        {
            "schema_version": "1.0",
            "task": "02-synthetic-data",
            "captured_at": "2026-09-21T12:00:00Z",
            "profile": "fe-bar",
            "artifacts": [
                "README.md",
                "manifest.json",
                "run-output.json",
                "queries.sql",
                "query-results.json",
                "verification.txt",
            ],
        }
    ),
    "run-output.json": json.dumps({"state": "SUCCESS"}),
    "queries.sql": "SELECT 1;\n",
    "query-results.json": json.dumps({"state": "SUCCEEDED", "rows": [[1]]}),
    "verification.txt": "tests: PASS\n",
}


def write_package(root: Path) -> None:
    root.mkdir()
    for name, content in REQUIRED_FILES.items():
        (root / name).write_text(content, encoding="utf-8")


def test_valid_package_returns_manifest(tmp_path: Path) -> None:
    package = tmp_path / "02-synthetic-data"
    write_package(package)

    manifest = validate_evidence_package(package)

    assert manifest["task"] == "02-synthetic-data"


def test_package_requires_every_standard_file(tmp_path: Path) -> None:
    package = tmp_path / "02-synthetic-data"
    write_package(package)
    (package / "query-results.json").unlink()

    with pytest.raises(EvidenceValidationError, match="query-results.json"):
        validate_evidence_package(package)


@pytest.mark.parametrize("filename", ["manifest.json", "run-output.json", "query-results.json"])
def test_package_rejects_invalid_json(tmp_path: Path, filename: str) -> None:
    package = tmp_path / "02-synthetic-data"
    write_package(package)
    (package / filename).write_text("not json", encoding="utf-8")

    with pytest.raises(EvidenceValidationError, match=filename):
        validate_evidence_package(package)


def test_manifest_artifact_index_must_match_files(tmp_path: Path) -> None:
    package = tmp_path / "02-synthetic-data"
    write_package(package)
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"].remove("verification.txt")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(EvidenceValidationError, match="artifacts"):
        validate_evidence_package(package)


@pytest.mark.parametrize(
    "secret",
    [
        "dapi" + "0123456789abcdef0123456789abcdef",
        "Authorization: " + "Bearer abc.def.ghi",
        "client_" + "secret=super-secret-value",
        "postgresql://" + "user:password@example.test/database",
    ],
)
def test_package_rejects_secret_patterns(tmp_path: Path, secret: str) -> None:
    package = tmp_path / "02-synthetic-data"
    write_package(package)
    (package / "verification.txt").write_text(secret, encoding="utf-8")

    with pytest.raises(EvidenceValidationError, match="secret"):
        validate_evidence_package(package)
