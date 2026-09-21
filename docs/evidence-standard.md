# Execution Evidence Standard

Every build task that changes or exercises a Databricks capability must commit one text-readable package under `evidence/<task-number>-<task-name>/`.

## Required Files

| File | Purpose |
|---|---|
| `README.md` | Human-readable outcome, interpretation, limitations, and links between results |
| `manifest.json` | Machine-readable package identity, capture context, resource IDs, commands, and artifact index |
| `run-output.json` | Sanitized raw job, pipeline, deployment, model, application, or agent execution output |
| `queries.sql` | Exact SQL used to validate the task; use comments to associate queries with result blocks |
| `query-results.json` | Sanitized raw result columns, rows, statement IDs, and states |
| `verification.txt` | Local tests, compilation/linting, bundle validation, remote checks, and exit results |

If a task legitimately performs no SQL, `queries.sql` must contain a comment explaining why, and `query-results.json` must contain an empty `results` array with the same explanation.

## Manifest Contract

`manifest.json` uses schema version `1.0` and contains:

```json
{
  "schema_version": "1.0",
  "task": "02-synthetic-data",
  "captured_at": "2026-09-21T18:19:32Z",
  "profile": "fe-bar",
  "workspace": "fevm-serverless-stable-febar-scottj.cloud.databricks.com",
  "resources": {},
  "commands": [],
  "artifacts": [
    "README.md",
    "manifest.json",
    "run-output.json",
    "queries.sql",
    "query-results.json",
    "verification.txt"
  ]
}
```

The profile is documentary; commands still pass `--profile` explicitly. `resources` contains stable, non-secret identifiers such as job IDs, run IDs, pipeline IDs, model versions, table names, and application names.

## Sanitization Rules

Evidence must never contain:

- Databricks personal access tokens or OAuth access/refresh tokens;
- `Authorization` headers;
- client secrets, passwords, database credentials, or connection strings containing passwords;
- browser cookies, temporary signed URLs, or environment dumps;
- real student/customer records or customer-identifying content; or
- raw application logs that have not been reviewed for the preceding values.

Workspace hostnames, resource IDs, statement IDs, synthetic identifiers, and the selected CLI profile are allowed because they make execution traceable. User email addresses should be removed unless identity behavior is the capability under test.

## Capture Procedure

1. Run the capability and wait for a terminal state.
2. Save only relevant raw response fields in `run-output.json`.
3. Put exact validation SQL in `queries.sql` and its returned columns/rows/state in `query-results.json`.
4. Write `README.md` from the captured results; do not invent or round values inconsistently.
5. Record verification commands and exit outcomes in `verification.txt`.
6. Run the package validator:

```bash
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 -c \
  "from pathlib import Path; from src.evidence.package import validate_evidence_package; validate_evidence_package(Path('evidence/02-synthetic-data'))"
```

7. Run repository secret scanning through the normal pre-commit hook before committing.

## Evaluation Mapping

Each package README must explain which build-domain claim the raw evidence proves. The final `evidence/README.md` will index packages against submission requirements so the evaluator can navigate the proof without relying on screenshots.
