# Task 7 local verification evidence

This package records local, sanitized verification of the grounded advisor
briefing implementation. The contract suite proves protected/raw-note exclusion,
citation coverage enforcement, prohibited-claim rejection, optional JSON-fence
parsing, retry behavior, and visible failure status. Bundle validation confirms
that the Databricks job definition is syntactically valid.

No remote generation or MLflow evaluation run is represented here. The
authenticated controller must run the bounded job and replace the placeholder
run/query artifacts with sanitized remote output before treating generation or
evaluation thresholds as demonstrated.
