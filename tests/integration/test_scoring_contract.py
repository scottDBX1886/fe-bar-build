from pathlib import Path


def test_scoring_implementation_preserves_immutable_history_contract():
    source = Path("src/ml/score.py").read_text(encoding="utf-8")
    assert "models:/" in source
    assert "@prod" in source
    assert "mlflow.pyfunc.spark_udf" in source
    assert "MERGE INTO" in source
    assert "student_id" in source
    assert "feature_as_of" in source
    assert "model_version" in source
    assert "WHEN NOT MATCHED" in source
    assert "WHEN MATCHED" not in source


def test_scoring_contract_includes_explanations_and_tiers():
    source = Path("src/ml/score.py").read_text(encoding="utf-8")
    assert "leading_factors" in source
    assert "risk_tier" in source
    assert "risk_score" in source
