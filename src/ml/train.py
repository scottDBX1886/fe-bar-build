"""Train, compare, register, and score the student stop-out classifier."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import mlflow.pyfunc

# Serverless Spark Python tasks execute through ``exec`` without ``__file__``.
if "--bundle-root" in sys.argv:
    _BUNDLE_ROOT = sys.argv[sys.argv.index("--bundle-root") + 1]
    if _BUNDLE_ROOT not in sys.path:
        sys.path.insert(0, _BUNDLE_ROOT)

from src.ml.policy import calibration_error, cohort_error_rates, pr_auc, top_k_metrics
from src.ml.score import score_registered_model


SEED = 20260921
TOP_K_FRACTION = 0.10
MIN_PR_AUC = 0.20
MIN_TOP_K_RECALL = 0.20
MAX_CALIBRATION_ERROR = 0.10


class RiskModel(mlflow.pyfunc.PythonModel):
    """MLflow pyfunc wrapper returning probabilities and SHAP-style leading factors."""

    def __init__(self, estimator: Any, transformed_feature_names: list[str], background: list[float]):
        self.estimator = estimator
        self.transformed_feature_names = transformed_feature_names
        self.background = np.asarray(background)

    def predict(self, context: Any, model_input: pd.DataFrame, params: Any = None) -> pd.DataFrame:
        transformed = self.estimator.named_steps["preprocess"].transform(model_input)
        classifier = self.estimator.named_steps["classifier"]
        probabilities = classifier.predict_proba(transformed)[:, 1]
        dense = transformed.toarray() if hasattr(transformed, "toarray") else np.asarray(transformed)
        if hasattr(classifier, "coef_"):
            shap_values = (dense - self.background) * classifier.coef_[0]
        else:
            import shap

            shap_values = shap.TreeExplainer(classifier).shap_values(dense)
        factors = []
        for row in np.asarray(shap_values):
            indices = np.argsort(np.abs(row))[-3:][::-1]
            factors.append([self.transformed_feature_names[index] for index in indices])
        return pd.DataFrame({"risk_score": probabilities, "leading_factors": factors})


def _business_rule(frame: pd.DataFrame) -> np.ndarray:
    """Transparent comparator based on four institutionally actionable signals."""
    score = (
        0.35 * (1.0 - frame["attendance_rate_28d"].clip(0, 1))
        + 0.20 * (frame["missed_assignments_28d"].clip(0, 4) / 4)
        + 0.20 * frame["financial_hold_flag"].astype(float)
        + 0.15 * (frame["days_since_lms_activity"].clip(0, 60) / 60)
        + 0.10 * (frame["withdrawal_count_prior"].clip(0, 2) / 2)
    )
    return score.clip(0, 1).to_numpy()


def _metrics(labels: np.ndarray, probabilities: np.ndarray) -> dict[str, float]:
    capacity = max(1, round(len(labels) * TOP_K_FRACTION))
    top_k = top_k_metrics(labels.tolist(), probabilities.tolist(), k=capacity)
    return {
        "pr_auc": pr_auc(labels.tolist(), probabilities.tolist()),
        "top_k_recall": float(top_k["recall"]),
        "top_k_precision": float(top_k["precision"]),
        "calibration_error": calibration_error(labels.tolist(), probabilities.tolist()),
    }


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema-prefix", required=True)
    parser.add_argument("--experiment-path", required=True)
    parser.add_argument("--bundle-root", required=True)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--model-alias", default="prod")
    parser.add_argument("--no-score", action="store_true")
    return parser.parse_args()


def main(args: argparse.Namespace) -> dict[str, Any]:
    import mlflow
    import mlflow.pyfunc
    from mlflow import MlflowClient
    from mlflow.models import infer_signature
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler
    from xgboost import XGBClassifier

    spark = globals().get("spark")
    if spark is None:
        from pyspark.sql import SparkSession

        spark = SparkSession.builder.getOrCreate()

    mlflow.set_registry_uri("databricks-uc")
    mlflow.set_experiment(args.experiment_path)
    ml_schema = f"{args.schema_prefix}_ml"
    model_name = f"{args.catalog}.{ml_schema}.student_stopout_risk"
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {args.catalog}.{ml_schema}")

    feature_table = f"{args.catalog}.{args.schema_prefix}_silver.model_feature_snapshots"
    label_table = f"{args.catalog}.{args.schema_prefix}_silver.training_labels"
    protected_table = f"{args.catalog}.{args.schema_prefix}_silver.student_protected_audit"
    joined = spark.sql(
        f"""SELECT f.*, l.stopout_label, l.label_term_code
            FROM {feature_table} f JOIN {label_table} l
            USING (student_id, feature_as_of)"""
    )
    periods = [row[0] for row in joined.select("feature_as_of").distinct().orderBy("feature_as_of").collect()]
    if len(periods) < 2:
        raise ValueError("training requires at least two chronological feature snapshots")
    train_pdf = joined.filter(joined.feature_as_of < periods[-1]).toPandas()
    validation_pdf = joined.filter(joined.feature_as_of == periods[-1]).toPandas()
    excluded = {
        "student_id", "advisor_id", "feature_as_of", "max_feature_event_at",
        "synthetic_net_tuition_next_term", "stopout_label", "label_term_code",
    }
    features = [column for column in joined.columns if column not in excluded]
    categorical = [column for column in features if train_pdf[column].dtype == "object"]
    numeric = [column for column in features if column not in categorical]
    preprocess = ColumnTransformer(
        [
            ("numeric", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), numeric),
            ("categorical", Pipeline([("impute", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), categorical),
        ]
    )
    candidates = {
        "logistic_regression": LogisticRegression(max_iter=1000, class_weight="balanced", random_state=args.seed),
        "xgboost": XGBClassifier(
            n_estimators=250, max_depth=4, learning_rate=0.05, subsample=0.9,
            colsample_bytree=0.9, eval_metric="logloss", random_state=args.seed,
        ),
    }
    labels_train = train_pdf["stopout_label"].astype(int).to_numpy()
    labels_validation = validation_pdf["stopout_label"].astype(int).to_numpy()
    fitted: dict[str, Any] = {}
    comparisons = {"business_rule": _metrics(labels_validation, _business_rule(validation_pdf))}
    for family, classifier in candidates.items():
        pipeline = Pipeline([("preprocess", preprocess), ("classifier", classifier)])
        pipeline.fit(train_pdf[features], labels_train)
        probabilities = pipeline.predict_proba(validation_pdf[features])[:, 1]
        fitted[family] = pipeline
        comparisons[family] = _metrics(labels_validation, probabilities)

    eligible = [
        family for family in ("logistic_regression", "xgboost")
        if comparisons[family]["pr_auc"] >= MIN_PR_AUC
        and comparisons[family]["top_k_recall"] >= MIN_TOP_K_RECALL
        and comparisons[family]["calibration_error"] <= MAX_CALIBRATION_ERROR
    ]
    selected_family = eligible[0] if eligible else max(
        fitted, key=lambda family: comparisons[family]["pr_auc"]
    )
    selected = fitted[selected_family]
    selected_probabilities = selected.predict_proba(validation_pdf[features])[:, 1]
    predictions = (selected_probabilities >= 0.5).astype(int)

    protected = spark.read.table(protected_table).toPandas()
    audit = validation_pdf[["student_id"]].merge(protected, on="student_id", how="left")
    fairness: dict[str, Any] = {}
    for cohort_column in [
        "synthetic_gender", "synthetic_first_generation", "synthetic_race_ethnicity"
    ]:
        if cohort_column in audit:
            fairness[cohort_column] = cohort_error_rates(
                labels_validation.tolist(), predictions.tolist(), audit[cohort_column].fillna("UNKNOWN").astype(str).tolist()
            )

    transformed_names = selected.named_steps["preprocess"].get_feature_names_out().tolist()
    transformed_train = selected.named_steps["preprocess"].transform(train_pdf[features])
    dense_train = transformed_train.toarray() if hasattr(transformed_train, "toarray") else np.asarray(transformed_train)
    wrapper = RiskModel(selected, transformed_names, dense_train.mean(axis=0).tolist())
    example = validation_pdf[features].head(5)
    example_output = wrapper.predict(None, example)

    with mlflow.start_run(run_name=f"student-stopout-{selected_family}") as run:
        mlflow.log_params(
            {
                "selected_family": selected_family,
                "seed": args.seed,
                "train_period_end": str(periods[-2]),
                "validation_period": str(periods[-1]),
                "top_k_fraction": TOP_K_FRACTION,
                "min_pr_auc": MIN_PR_AUC,
                "min_top_k_recall": MIN_TOP_K_RECALL,
                "max_calibration_error": MAX_CALIBRATION_ERROR,
            }
        )
        mlflow.log_metrics({f"validation_{key}": value for key, value in comparisons[selected_family].items()})
        mlflow.log_input(mlflow.data.from_spark(joined, table_name=feature_table), context="training_and_validation")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "feature-list.json").write_text(json.dumps(features, indent=2), encoding="utf-8")
            (root / "model-comparison.json").write_text(json.dumps(comparisons, indent=2), encoding="utf-8")
            (root / "fairness-audit.json").write_text(json.dumps(fairness, indent=2), encoding="utf-8")
            mlflow.log_artifacts(directory, artifact_path="evaluation")
        model_info = mlflow.pyfunc.log_model(
            artifact_path="model",
            python_model=wrapper,
            signature=infer_signature(example, example_output),
            input_example=example,
            pip_requirements=["mlflow", "pandas", "numpy", "scikit-learn", "xgboost", "shap"],
        )
        run_id = run.info.run_id

    registered = mlflow.register_model(model_info.model_uri, model_name)
    client = MlflowClient(registry_uri="databricks-uc")
    client.set_registered_model_alias(model_name, args.model_alias, registered.version)
    rows_scored = 0 if args.no_score else score_registered_model(
        catalog=args.catalog, schema_prefix=args.schema_prefix,
        model_version=str(registered.version), model_alias=args.model_alias,
    )
    output = {
        "run_id": run_id,
        "model_name": model_name,
        "model_version": str(registered.version),
        "selected_family": selected_family,
        **comparisons[selected_family],
        "fairness_summary": fairness,
        "rows_scored": rows_scored,
        "comparison": comparisons,
    }
    dbutils = globals().get("dbutils")
    if dbutils is not None:
        dbutils.notebook.exit(json.dumps(output))
    return output


if __name__ == "__main__":
    print(json.dumps(main(_arguments())))
