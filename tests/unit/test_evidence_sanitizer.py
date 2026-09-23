from pathlib import Path

import pytest

from scripts.capture_evidence import (
    EvidenceCriterion,
    UnsafeEvidenceError,
    build_evidence_index,
    capture,
    sanitize_text,
    scan_evidence_files,
)


def test_sanitizer_redacts_credentials_connections_and_realistic_identity():
    bearer = "dapi" + "0123456789abcdef"
    oauth_secret = "oauth-" + "secret-value"
    databricks_token = "dapi" + "abcdef0123456789"
    postgres_url = "postgres" + "ql://app_user:super-secret@db.example.com:5432/student_retention"
    user_identity = "scott.johnson" + "@databricks.com"
    raw = (
        f"Authorization: Bearer {bearer}\n"
        f"client_secret={oauth_secret}\n"
        f"DATABRICKS_TOKEN={databricks_token}\n"
        f"{postgres_url}\n"
        f"created_by={user_identity}\n"
    )

    sanitized = sanitize_text(raw)

    assert "dapi0123456789abcdef" not in sanitized
    assert "oauth-secret-value" not in sanitized
    assert "dapiabcdef0123456789" not in sanitized
    assert "super-secret" not in sanitized
    assert "scott.johnson@databricks.com" not in sanitized
    assert sanitized.count("[REDACTED]") >= 5


def test_sanitizer_preserves_results_metrics_synthetic_ids_and_resource_ids():
    safe = """risk_history_rows=60000
roc_auc=0.8124
student_id=STU-002564
job_id=666694306037627
pipeline_id=b22af6b5-ff4b-47b3-a2b4-0d3945986ce7
run_id=1039509727786572
"""

    assert sanitize_text(safe) == safe


def test_scan_refuses_capture_when_a_secret_pattern_is_detected(tmp_path: Path):
    safe = tmp_path / "safe.txt"
    unsafe = tmp_path / "unsafe.txt"
    safe.write_text("model_accuracy=0.91\n", encoding="utf-8")
    unsafe.write_text("Authorization: Bearer dapi0123456789abcdef\n", encoding="utf-8")

    with pytest.raises(UnsafeEvidenceError, match="unsafe.txt"):
        scan_evidence_files([safe, unsafe])


def test_index_is_deterministic_and_maps_every_required_field(tmp_path: Path):
    evidence_file = tmp_path / "verification.txt"
    evidence_file.write_text("127 passed\n", encoding="utf-8")
    criteria = (
        EvidenceCriterion(
            criterion="AC-9",
            requirement="Text-readable evidence exists for every build domain.",
            evidence_path="verification.txt",
            reproduction_command="pytest -q",
            workspace_resource="repository test suite",
            expected_interpretation="All required automated checks pass.",
        ),
    )

    first = build_evidence_index(criteria, captured_at="2026-09-23T22:00:00Z")
    second = build_evidence_index(criteria, captured_at="2026-09-23T22:00:00Z")

    assert first == second
    assert "AC-9" in first
    assert "verification.txt" in first
    assert "pytest -q" in first
    assert "2026-09-23T22:00:00Z" in first
    assert "repository test suite" in first
    assert "All required automated checks pass." in first


def test_capture_allows_index_to_reference_its_own_output(tmp_path: Path, monkeypatch):
    output = tmp_path / "README.md"
    criterion = EvidenceCriterion(
        criterion="AC-9",
        requirement="Evidence index exists.",
        evidence_path="README.md",
        reproduction_command="python scripts/capture_evidence.py",
        workspace_resource="repository",
        expected_interpretation="The index is generated only after scanning succeeds.",
    )
    monkeypatch.setattr("scripts.capture_evidence.DEFAULT_CRITERIA", (criterion,))

    capture(tmp_path, output, captured_at="2026-09-23T22:00:00Z")

    assert output.exists()
    assert "AC-9" in output.read_text(encoding="utf-8")
