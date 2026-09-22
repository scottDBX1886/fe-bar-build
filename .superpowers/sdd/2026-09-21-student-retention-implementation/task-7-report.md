# Task 7 Report: Grounded Advisor Briefings

## Outcome

Implemented bounded, governed advisor-summary generation and MLflow GenAI
evaluation. Generation reads only
`<catalog>.<schema_prefix>_gold.student_detail`, creates no risk score, and
persists versioned/idempotent records to
`<catalog>.<schema_prefix>_gold.advisor_summaries`. Failed endpoint or
validation attempts become visible `generation_status = failed` records, so
the risk-score history remains usable and untouched.

The configured endpoint is `databricks-glm-5-3`, not Sonnet. Live
compatibility evidence supplied by the controller showed it accepts
`temperature=0.1` and may wrap strict JSON in one `json` code fence; native
`response_format` is intentionally not used. Generation sends 1200 maximum
tokens and has a hard cohort limit of 50.

## Files Changed

- `src/genai/generate.py` — explicit input allowlist, strict JSON/schema and
  grounding validation, optional single-fence parsing, retrying endpoint call,
  safe failure record, and idempotent summary persistence.
- `src/genai/evaluate.py` — fixed nested synthetic MLflow 3.9 evaluation
  dataset, unpacked `predict_fn`, built-in `Safety`, named `Guidelines`,
  decorated deterministic citation/unsupported/prohibited scorers, exact
  publication gates, and evaluation-status update.
- `src/genai/__init__.py` — package marker.
- `tests/unit/test_genai_contract.py` and `tests/fixtures/genai_cases.json` —
  contract tests and synthetic fixture.
- `pytest.ini` — makes the documented bare `pytest` command import `src`
  correctly in this repository.
- `resources/student_jobs.job.yml` — bounded generation then evaluation tasks;
  MLflow pinned to `>=3.9,<3.10`.
- `databricks.yml`, `docs/build-decisions.md`, and `docs/data-contracts.md` —
  endpoint, contract, governance, and publication decisions.
- `evidence/06-genai/*` — standardized local-only evidence package.

## Red/Green TDD Evidence

1. Initial red command:

   ```text
   pytest tests/unit/test_genai_contract.py -v
   ERROR: ModuleNotFoundError: No module named 'src.genai'
   ```

   This was the expected absence of the GenAI contract. The repository also
   lacked pytest source-root configuration, so `pytest.ini` was added before
   rerunning the same command, which then specifically reported the missing
   `src.genai` package.

2. Regression red command for factual content moved into the suggested action:

   ```text
   pytest tests/unit/test_genai_contract.py -v
   FAILED: did not raise GenerationFailure
   ```

   The validator was then changed to reject uncited factual action sentences.

3. Regression red command for protected-trait leakage:

   ```text
   pytest tests/unit/test_genai_contract.py -v
   FAILED: did not raise GenerationFailure
   ```

   The prohibited-content validator was then extended to reject protected-trait
   references.

4. Regression red command for missing evaluation gate API:

   ```text
   pytest tests/unit/test_genai_contract.py -v
   ERROR: cannot import name 'EvaluationGateFailure'
   ```

   The exact publication gate was then implemented.

5. Final green commands and fresh results:

   ```text
   pytest tests/unit/test_genai_contract.py -v  # 12 passed
   pytest -v                                    # 92 passed
   python -m py_compile $(find src -name '*.py' -type f | sort)  # exit 0
   DATABRICKS_AUTH_STORAGE=plaintext databricks bundle validate --strict -t dev --profile fe-bar
   # Validation OK
   ```

   `validate_evidence_package(Path('evidence/06-genai'))` also passed, and
   `git diff --check` emitted no errors.

## Design Choices

- The payload is constructed from an explicit factual-signal allowlist rather
  than filtering a broad student record. Protected audit fields, raw notes,
  outcomes, labels, and arbitrary fields cannot enter the prompt.
- Responses require exactly six fields. Every factual briefing sentence, and
  a fact-bearing action sentence, needs an inline allowed fact ID; its
  `citations` array must match the inline set exactly. Unsupported claims are
  never accepted.
- `databricks-glm-5-3` receives a low-temperature (0.1) strict-JSON prompt.
  The parser accepts one complete `json` fence only, then uses `json.loads` and
  schema/grounding validation. It does not trust `response_format`.
- Summary identity hashes student, feature timestamp, model version, and
  prompt version. Reruns update that identity; a prompt version change creates
  a new summary identity. No risk field is written to the summary table.
- Successes start as `evaluation_status = pending`. The evaluation task uses a
  fixed nested synthetic dataset and only marks generated summaries `passed`
  after citation coverage, unsupported-fact, prohibited-content, `Safety`, and
  named-guideline aggregate scores are all 1.0. Any evaluation error/failure is
  visibly marked `failed`.

## Remaining Remote Execution

1. Deploy this revision and run `generate_advisor_briefings` followed by
   `evaluate_advisor_briefings` in the authenticated workspace.
2. Confirm the 50-row maximum and query `advisor_summaries` for succeeded,
   failed, pending, and passed status counts. Verify it contains no risk-score
   column and no writes were made to `student_risk_score_history`.
3. Inspect the MLflow baseline run `advisor-briefing-baseline-v1` and retain
   sanitized scorer output proving perfect citation, unsupported/prohibited,
   Safety, and guideline aggregates.
4. Replace local-only placeholders in `evidence/06-genai/run-output.json` and
   `query-results.json` with sanitized remote job, MLflow, and SQL evidence.

## Concerns

- No remote generation or MLflow evaluation has been run by this implementer;
  the evidence package says so explicitly and must not be interpreted as a
  remote capability claim.
- The endpoint is intentionally different from the original Task 7 brief. The
  controller supplied the corrected live compatibility ruling for
  `databricks-glm-5-3`; the bundle, contract, and implementation all use that
  ruling.
- Runtime confirmation should verify the workspace's model-judge configuration
  can execute MLflow `Safety` and `Guidelines`. A scorer failure leaves summaries
  visibly failed rather than published.

## Fix Round 1: Grounding, Gating, and Persistence Hardening

### Red/Green Commands

New regressions were written before the repair. The initial red run was:

```text
pytest tests/unit/test_genai_contract.py -v
ERROR: cannot import name 'render_briefing' from src.genai.generate
```

After implementing the structured fact/value contract, a first green run found
one test-expectation wording mismatch (`4 assignments` versus `Four
assignments`); the deterministic renderer's numeric output was retained and
the test was corrected. Fresh verification then produced:

```text
pytest tests/unit/test_genai_contract.py -v  # 18 passed
pytest -v                                    # 98 passed
python -m py_compile $(find src -name '*.py' -type f | sort)  # exit 0
DATABRICKS_AUTH_STORAGE=plaintext databricks bundle validate --strict -t dev --profile fe-bar
# Validation OK
```

### Design Notes

- The six-field response shape remains, but `briefing` is now an array of
  `{fact_id, fact_value}` records. Both fields must exactly match the supplied
  governed fact, and advisor-visible factual prose is deterministically rendered
  from those validated records. `risk_score` and `risk_tier` are now governed
  facts too. This removes reliance on semantic/heuristic claim matching.
- `suggested_action` is an allowlisted action code, rendered from a fixed
  template. The model has no free-text path to store an unsupported student
  claim. The same validation protects every generation before persistence;
  deterministic evaluators validate action code, citations, IDs, and exact
  values as well.
- Prohibited matching now covers the reviewed bypasses: causal improvement of
  persistence, female/male/nonbinary references, ADHD and other diagnosis
  terms, and punish/discipline terms.
- Summary persistence now declares a complete nullable `StructType`, including
  `ArrayType(StringType)`, so an all-failure first cohort can create its Delta
  target. The target carries a stable hash of the generated cohort; task values
  pass that identifier into evaluation and its update merges only that cohort.
- Exact gates reject all non-finite values and anything other than `1.0`.
  Generation and evaluation reject any endpoint other than the approved
  `databricks-glm-5-3`.

### Remaining Concern

The same remote execution caveat remains: the new task-value handoff,
all-failure Delta creation, and MLflow scorer metrics need authenticated
workspace execution before remote evidence can be finalized.

## Fix Round 2: Runtime Handoff, Persisted Citations, and Schema Evolution

### Red/Green Commands

The initial test-first run added the explicit runtime publication and
old-schema tests and failed as intended:

```text
pytest tests/unit/test_genai_contract.py -v
ERROR: cannot import name 'publish_generation_run_id' from src.genai.generate
```

After adding the helper, bumping the genuinely breaking output schema to
`advisor-briefing-v2` made the v1 fixture fail closed on `prompt_version`, so
the fixed synthetic fixture was deliberately updated to v2. A further
test-first handoff-finalization regression failed with the expected missing
`persist_and_publish_generation` import before that production path was added.

Fresh green verification:

```text
pytest tests/unit/test_genai_contract.py -v  # 21 passed
pytest -v                                    # 101 passed
python -m py_compile $(find src -name '*.py' -type f | sort)  # exit 0
DATABRICKS_AUTH_STORAGE=plaintext databricks bundle validate --strict -t dev --profile fe-bar
# Validation OK
```

### Design Notes

- `publish_generation_run_id` imports `dbutils` only from
  `databricks.sdk.runtime` when no injected task-values object is supplied. It
  invokes `dbutils.jobs.taskValues.set` and raises a clear runtime error if the
  handoff is unavailable or fails. `generate_validated_summary` remains a pure
  local-testable function; the runtime-only handoff occurs after persistence in
  the actual job path. A regression verifies persistence and task-value
  publication receive the same cohort ID.
- Every deterministic rendered factual sentence now carries `[fact_id]`. The
  evaluator additionally renders verified facts and confirms that those inline
  citations remain present, so the persisted/app-facing form as well as the
  internal exact-value structure is gated.
- `persist_summaries` now detects the actual existing table fields and issues
  a single additive `ALTER TABLE ... ADD COLUMNS` only for missing current
  contract columns before merging. Existing data is never replaced. This covers
  migration from v1 tables missing `generation_run_id` and any other current
  contract field.

### Remaining Concern

The Databricks runtime task-value import and additive Delta evolution are
unit-tested with injected fakes but still require authenticated workspace
execution for final remote evidence.

## Fix Round 3: Empty-Cohort Schema Initialization

### Red/Green Commands

The new narrow regressions for an empty record set produced the expected red
state:

```text
pytest tests/unit/test_genai_contract.py -v
FAILED test_empty_records_migrate_an_existing_v1_summary_table_before_returning
FAILED test_empty_first_cohort_creates_a_current_schema_summary_table
```

`persist_summaries` had returned before it could evolve an existing table or
create a first empty-cohort table. The order was changed so schema creation or
additive evolution occurs before the empty-record return.

Fresh verification:

```text
pytest tests/unit/test_genai_contract.py -v  # 23 passed
pytest -v                                    # 103 passed
python -m py_compile $(find src -name '*.py' -type f | sort)  # exit 0
DATABRICKS_AUTH_STORAGE=plaintext databricks bundle validate --strict -t dev --profile fe-bar
# Validation OK
```

### Design Note

An absent `advisor_summaries` table is now created from the complete current
schema using an empty DataFrame. An existing table is evolved with its additive
contract migration before any record-dependent work. Only after either action
does an empty cohort return; nonempty cohorts still merge as before.

## Fix Round 4: Serverless Imports and SDK Message Types

### Proven Remote Root Causes

- Databricks attempts `325260807637781` and `436087485840055` failed while
  executing `src/genai/evaluate.py`: serverless executes the Python file through
  `exec` without the repository root on `sys.path`, so the top-level
  `from src.genai.generate ...` raised `ModuleNotFoundError: No module named
  'src'`.
- SQL statement `01f1b69e-304e-12a0-b40a-e9868c7c0f57` showed all 50 bounded
  generation rows in failed status. SQL statement
  `01f1b69e-45d4-1ace-a8f7-49a6423279a6` grouped the shared error as
  `'dict' object has no attribute 'as_dict'`. The installed Databricks SDK
  serializes serving endpoint messages by calling `as_dict()` on each
  `ChatMessage`; the application had passed its internal plain dictionaries
  directly to that boundary.

These are failed-attempt diagnostics only. They do not demonstrate a successful
post-fix remote generation or evaluation run.

### Red/Green Commands

The serverless-style entry-point regression executes the real evaluation file
through `exec`, without `__file__` or repository `PYTHONPATH`. Its red result was:

```text
pytest tests/unit/test_genai_evaluation_runtime.py -v
FAILED: ModuleNotFoundError: No module named 'src'
```

The separate SDK-boundary regression retained internal dictionary messages and
exercised the SDK serializer contract. Its red result was:

```text
pytest tests/unit/test_genai_contract.py::test_databricks_completer_converts_internal_messages_at_sdk_boundary -v
FAILED: AttributeError: 'dict' object has no attribute 'as_dict'
```

After the two narrow fixes, local verification produced:

```text
pytest tests/unit/test_genai_contract.py tests/unit/test_genai_evaluation_runtime.py -v
# 25 passed
pytest -v
# 105 passed
python3 -m compileall -q src tests
# exit 0
DATABRICKS_AUTH_STORAGE=plaintext databricks bundle validate --strict -t dev --profile fe-bar
# Validation OK
```

### Design Notes and Remaining Concern

- `evaluate.py` now applies the same explicit `--bundle-root`/`sys.path`
  bootstrap already used by the working ML training entry point, before any
  `src.*` import. The evaluation task passes `${workspace.root_path}/files`.
- `databricks_completer` converts each internal `{role, content}` dictionary to
  a typed SDK `ChatMessage` only at `ServingEndpointsAPI.query`; prompt creation
  and retry/validation contracts remain dependency-light dictionaries.
- A deployed post-fix run is still required. Until it succeeds, the diagnostic
  run and statement IDs above remain evidence of the two former failure modes,
  not proof of remote success.
