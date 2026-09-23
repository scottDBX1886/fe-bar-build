from pathlib import Path

import yaml


JOB_FILE = Path(__file__).parents[2] / "resources" / "student_jobs.job.yml"
SILVER_FILE = Path(__file__).parents[2] / "src" / "pipelines" / "silver.py"


def _job():
    return yaml.safe_load(JOB_FILE.read_text())["resources"]["jobs"]["student_retention_daily"]


def _tasks():
    return {task["task_key"]: task for task in _job()["tasks"]}


def _deps(task):
    return {item["task_key"]: item.get("outcome") for item in task.get("depends_on", [])}


def test_daily_job_has_explicit_operational_parameters():
    parameters = {item["name"]: item["default"] for item in _job()["parameters"]}
    assert parameters == {
        "run_date": "2026-09-21",
        "bootstrap": "false",
        "retrain": "false",
        "model_alias": "prod",
    }


def test_retraining_is_an_explicit_branch_and_routine_runs_score_existing_model():
    tasks = _tasks()
    gate = tasks["retrain_requested"]
    assert gate["condition_task"] == {
        "left": "{{job.parameters.retrain}}",
        "op": "EQUAL_TO",
        "right": "true",
    }
    assert _deps(tasks["train_model"]) == {"retrain_requested": "true"}
    assert _deps(tasks["score_after_train"]) == {"train_model": None}
    assert _deps(tasks["score_existing_model"]) == {"retrain_requested": "false"}


def test_hard_gates_and_degradable_genai_form_the_required_dag():
    tasks = _tasks()
    assert _deps(tasks["run_student_pipeline"]) == {"generate_synthetic_data": None}
    assert set(_deps(tasks["bootstrap_gold_governance"])) == {
        "score_after_train", "score_existing_model"
    }
    assert tasks["bootstrap_gold_governance"]["run_if"] == "AT_LEAST_ONE_SUCCESS"
    assert _deps(tasks["run_gold_pipeline"]) == {"bootstrap_gold_governance": None}
    assert _deps(tasks["generate_advisor_briefings"]) == {"apply_gold_core_policies": None}
    assert tasks["check_serving_sync"]["run_if"] == "ALL_DONE"
    assert set(_deps(tasks["check_serving_sync"])) == {
        "generate_advisor_briefings", "evaluate_advisor_briefings"
    }
    assert _deps(tasks["refresh_intervention_gold"]) == {"check_serving_sync": None}
    assert _deps(tasks["capture_daily_evidence"]) == {"refresh_intervention_gold": None}


def test_scoring_receives_explicit_model_alias():
    tasks = _tasks()
    for key in ("score_after_train", "score_existing_model"):
        params = tasks[key]["spark_python_task"]["parameters"]
        assert params[params.index("--model-alias") + 1] == "{{job.parameters.model_alias}}"


def test_daily_snapshot_dates_advance_from_incremental_event_partitions():
    source = SILVER_FILE.read_text()
    function = source.split("def student_daily_snapshots()", 1)[1].split("def model_feature_snapshots()", 1)[0]
    assert 'table(_silver("attendance_events"))' in function
    assert 'table(_silver("engagement_events"))' in function
    assert 'table(_silver("financial_events"))' in function
    assert ".crossJoin(event_dates)" in function
