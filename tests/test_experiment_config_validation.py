import pytest

from config.schema import ExperimentConfig


def test_experiment_config_rejects_sqlite_search_backend():
    with pytest.raises(ValueError, match="SEARCH_BACKEND must be one of"):
        ExperimentConfig(search_backend="sqlite")


def test_experiment_config_accepts_postgres_search_backend():
    cfg = ExperimentConfig(search_backend="postgres")
    assert cfg.search_backend == "postgres"

    cfg_pg = ExperimentConfig(search_backend="postgresql")
    assert cfg_pg.search_backend == "postgresql"
