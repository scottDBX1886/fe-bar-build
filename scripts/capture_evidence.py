#!/usr/bin/env python3
"""Build the evaluator-facing evidence index after rejecting unsafe evidence."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


REDACTION = "[REDACTED]"
TEXT_SUFFIXES = {".json", ".md", ".sql", ".txt", ".yaml", ".yml"}
_PATTERNS = (
    re.compile(r"(?i)(Authorization\s*:\s*Bearer\s+)[A-Za-z0-9._-]{12,}"),
    re.compile(r"(?i)\b(dapi)[A-Za-z0-9]{12,}\b"),
    re.compile(
        r"(?i)\b(client_secret|oauth_token|access_token|refresh_token|databricks_token)"
        r"(\s*[=:]\s*)(?!\[REDACTED\])[^\s,;\"']+"
    ),
    re.compile(r"(?i)\b(postgres(?:ql)?://[^\s:/]+:)[^\s@]+(@[^\s]+)"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
)


class UnsafeEvidenceError(RuntimeError):
    """Raised when evidence contains content that would require redaction."""


@dataclass(frozen=True)
class EvidenceCriterion:
    criterion: str
    requirement: str
    evidence_path: str
    reproduction_command: str
    workspace_resource: str
    expected_interpretation: str


def sanitize_text(text: str) -> str:
    """Redact credentials, connection passwords, and email-like identities."""
    result = text
    result = _PATTERNS[0].sub(r"\1" + REDACTION, result)
    result = _PATTERNS[1].sub(REDACTION, result)
    result = _PATTERNS[2].sub(lambda match: f"{match.group(1)}{match.group(2)}{REDACTION}", result)
    result = _PATTERNS[3].sub(r"\1" + REDACTION + r"\2", result)
    result = _PATTERNS[4].sub(REDACTION, result)
    return result


def scan_evidence_files(paths: Iterable[Path]) -> None:
    """Fail closed if any supplied text evidence contains unsafe content."""
    unsafe: list[str] = []
    for path in sorted(paths, key=lambda item: item.as_posix()):
        text = path.read_text(encoding="utf-8")
        if sanitize_text(text) != text:
            unsafe.append(path.as_posix())
    if unsafe:
        raise UnsafeEvidenceError("Unsafe evidence detected in: " + ", ".join(unsafe))


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def build_evidence_index(
    criteria: Sequence[EvidenceCriterion], *, captured_at: str
) -> str:
    """Render a stable, text-readable acceptance-criteria evidence index."""
    rows = []
    def criterion_order(item: EvidenceCriterion) -> tuple[str, int]:
        prefix, _, number = item.criterion.partition("-")
        return prefix, int(number) if number.isdigit() else 0

    for item in sorted(criteria, key=criterion_order):
        rows.append(
            "| " + " | ".join(
                _cell(value)
                for value in (
                    item.criterion,
                    item.requirement,
                    item.evidence_path,
                    item.reproduction_command,
                    captured_at,
                    item.workspace_resource,
                    item.expected_interpretation,
                )
            ) + " |"
        )
    return "\n".join(
        (
            "# Student Retention Evidence Index",
            "",
            "All records and business values in this demonstration are synthetic. Evidence is text-readable, sanitized, and reproducible against the explicitly selected `fe-bar` profile.",
            "",
            "| Criterion | Requirement | Evidence | Reproduction command | Captured at | Resource | Expected interpretation |",
            "|---|---|---|---|---|---|---|",
            *rows,
            "",
            "## Domain index",
            "",
            "1. Synthetic generation — `01-synthetic-data/`",
            "2. Bronze ingestion and quality — `02-bronze/`",
            "3. Silver conformance and features — `03-silver/`",
            "4. ML training, evaluation, registry, and scoring — `04-ml/`",
            "5. Gold products and governance — `05-gold-governance/`",
            "6. Grounded GenAI and evaluation — `06-genai/`",
            "7. Lakebase serving and transactional write-back — `07-lakebase/`",
            "8. Intervention CDC and analytical Gold — `08-intervention-gold/`",
            "9. Curated Genie Agent — `09-genie/`",
            "10. Databricks App shell and workflows — `10-app-shell/`, `10-app-workflows/`",
            "11. Trusted embedded Genie — `11-app-genie/`",
            "12. Triggered daily workflow — `12-daily-workflow/`",
            "",
        )
    )


DEFAULT_CRITERIA = (
    EvidenceCriterion("AC-1", "A triggered run incrementally publishes Bronze, Silver, and Gold with quality evidence.", "12-daily-workflow/README.md", "databricks jobs get-run 1039509727786572 --profile fe-bar -o json", "Lakeflow Job 666694306037627", "The incident-day run and identical rerun succeed without duplicate logical records."),
    EvidenceCriterion("AC-2", "A versioned model beats documented baselines and produces reproducible scores.", "04-ml/README.md", "pytest -q tests/unit/test_ml_model.py tests/integration/test_scoring_contract.py", "UC model student_retention_ml.student_stopout_risk", "Evaluation, registry alias, immutable scoring, and explanations meet the demo contract."),
    EvidenceCriterion("AC-3", "Grounded advisor briefings cite governed facts and pass the fixed evaluation set.", "06-genai/README.md", "pytest -q tests/unit/test_genai_contract.py", "MLflow advisor briefing evaluation", "Briefings are factual, bounded, traceable, and evaluated."),
    EvidenceCriterion("AC-4", "The app enforces executive aggregate and advisor assignment boundaries.", "10-app-workflows/verification.txt", "cd app && npx playwright test tests/smoke.spec.ts", "Databricks App dev-student-retention", "Authorization is enforced by governed data policies and backend identity, not UI hiding."),
    EvidenceCriterion("AC-5", "An advisor can write interventions without modifying synchronized serving tables.", "07-lakebase/README.md", "RUN_LAKEBASE_INTEGRATION=1 pytest -q tests/integration/test_lakebase_transactions.py", "Lakebase student_retention_app", "Transactional writes stay in app-owned tables; synchronized serving tables remain read-only."),
    EvidenceCriterion("AC-6", "Intervention CDC reaches Unity Catalog and produces current-state and history Gold outputs.", "08-intervention-gold/README.md", "pytest -q tests/unit/test_intervention_cdc.py tests/integration/test_intervention_cdc.py", "UC student_retention_cdc and student_retention_gold", "Ordered, deduplicated CDC supports correct analytical state and event history."),
    EvidenceCriterion("AC-7", "Embedded Genie answers governed questions and exposes SQL and execution identity.", "11-app-genie/README.md", "cd app && npx playwright test tests/smoke.spec.ts", "Genie Agent 01f1b75b8eea15a8af20b1f773bb1b38", "Answers use approved Gold sources with visible trust indicators."),
    EvidenceCriterion("AC-8", "Major app paths represent loading, empty, error, partial, and stale states.", "10-app-shell/verification.txt", "cd app && npx playwright test tests/smoke.spec.ts", "Databricks App dev-student-retention", "The app communicates operational state instead of silently failing."),
    EvidenceCriterion("AC-9", "Every required build domain has text-readable execution evidence.", "README.md", "python scripts/capture_evidence.py --captured-at 2026-09-23T22:00:00Z", "Repository evidence/ tree", "The secret-safe index links every acceptance criterion to reproducible text evidence."),
    EvidenceCriterion("AC-10", "The demo tells one complete scenario and the deck leads with synthetic business outcomes.", "../docs/runbooks/demo.md; ../docs/presentation/student-retention.md", "pytest -q && cd app && npx playwright test tests/smoke.spec.ts", "Deployed retention solution", "The evaluator can repeat the business workflow and distinguish synthetic estimates from claims."),
)


def _text_evidence(root: Path, output: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES and path != output
    ]


def capture(root: Path, output: Path, *, captured_at: str) -> None:
    paths = _text_evidence(root, output)
    scan_evidence_files(paths)
    for criterion in DEFAULT_CRITERIA:
        for relative in criterion.evidence_path.split("; "):
            target = root / relative
            if target != output and not target.exists():
                raise FileNotFoundError(f"Evidence target does not exist: {target}")
    output.write_text(build_evidence_index(DEFAULT_CRITERIA, captured_at=captured_at), encoding="utf-8")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", type=Path, default=Path("evidence"))
    parser.add_argument("--output", type=Path, default=Path("evidence/README.md"))
    parser.add_argument("--captured-at", default=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    return parser.parse_args()


if __name__ == "__main__":
    args = _arguments()
    capture(args.evidence_root, args.output, captured_at=args.captured_at)
