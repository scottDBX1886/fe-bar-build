import pytest

from src.common.config import RuntimeConfig


REQUIRED_ENV = {
    "RETENTION_CATALOG": "serverless_stable_febar_scottj_catalog",
    "RETENTION_SCHEMA_PREFIX": "student_retention",
    "RETENTION_WAREHOUSE_ID": "1dd756b73d046482",
    "RETENTION_SEED": "20260921",
}


def set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in REQUIRED_ENV.items():
        monkeypatch.setenv(name, value)


@pytest.mark.parametrize("missing_name", REQUIRED_ENV)
def test_from_env_requires_every_setting(
    monkeypatch: pytest.MonkeyPatch, missing_name: str
) -> None:
    set_required_env(monkeypatch)
    monkeypatch.delenv(missing_name)

    with pytest.raises(ValueError, match=missing_name):
        RuntimeConfig.from_env()


@pytest.mark.parametrize(
    "variable,value",
    [
        ("RETENTION_CATALOG", "invalid-catalog"),
        ("RETENTION_SCHEMA_PREFIX", "9invalid"),
        ("RETENTION_SCHEMA_PREFIX", "invalid prefix"),
    ],
)
def test_from_env_rejects_invalid_unity_catalog_identifiers(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    set_required_env(monkeypatch)
    monkeypatch.setenv(variable, value)

    with pytest.raises(ValueError, match=variable):
        RuntimeConfig.from_env()


def test_from_env_rejects_non_integer_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required_env(monkeypatch)
    monkeypatch.setenv("RETENTION_SEED", "repeatable")

    with pytest.raises(ValueError, match="RETENTION_SEED"):
        RuntimeConfig.from_env()


def test_schema_names_and_table_name_are_derived(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_required_env(monkeypatch)

    config = RuntimeConfig.from_env()

    assert config.bronze_schema == "student_retention_bronze"
    assert config.silver_schema == "student_retention_silver"
    assert config.gold_schema == "student_retention_gold"
    assert config.ml_schema == "student_retention_ml"
    assert config.cdc_schema == "student_retention_cdc"
    assert (
        config.table_name("gold", "advisor_caseload")
        == "serverless_stable_febar_scottj_catalog."
        "student_retention_gold.advisor_caseload"
    )


def test_table_name_rejects_unknown_layer(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required_env(monkeypatch)
    config = RuntimeConfig.from_env()

    with pytest.raises(ValueError, match="Unknown layer"):
        config.table_name("raw", "students")


def test_table_name_rejects_invalid_table_identifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_required_env(monkeypatch)
    config = RuntimeConfig.from_env()

    with pytest.raises(ValueError, match="table"):
        config.table_name("gold", "student-risk")
