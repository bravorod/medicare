from __future__ import annotations

import pytest

from partd_risk.config import expand_env, load_config, load_outlier_config


def test_expand_env_uses_value_then_default(monkeypatch):
    monkeypatch.setenv("PARTD_TEST_VAR", "abc")
    monkeypatch.delenv("PARTD_MISSING", raising=False)
    assert expand_env("x-${PARTD_TEST_VAR}-y") == "x-abc-y"
    assert expand_env("${PARTD_MISSING:-fallback}") == "fallback"
    assert expand_env({"a": ["${PARTD_TEST_VAR}", 1]}) == {"a": ["abc", 1]}


def test_pipeline_config_has_all_sources(cfg):
    assert cfg.data_year == 2021
    assert set(cfg.sources) == {
        "part_d_prescriber_drug",
        "part_d_prescriber",
        "open_payments_general",
        "leie_exclusions",
        "nppes_providers",
    }
    for source in cfg.sources.values():
        assert source.required_columns, source.name
        assert len(set(source.columns)) == len(source.columns), (
            f"duplicate columns in {source.name}"
        )


def test_unknown_source_lists_known(cfg):
    with pytest.raises(KeyError, match="Known sources"):
        cfg.source("nope")


def test_bigquery_project_from_env(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT", "my-project")
    assert load_config().bigquery_project == "my-project"
    monkeypatch.delenv("GCP_PROJECT")
    assert load_config().bigquery_project is None


def test_outlier_config_features_are_valid(ocfg):
    names = [f.name for f in ocfg.features]
    assert len(names) == len(set(names))
    assert all(f.weight >= 0 for f in ocfg.features)
    assert 0 < ocfg.headline_k < 1
    assert ocfg.headline_k in ocfg.top_k


def test_outlier_config_rejects_unknown_transform(tmp_path):
    bad = tmp_path / "bad.yml"
    bad.write_text("features:\n  - {name: x, column: x, transform: sqrt}\n")
    with pytest.raises(ValueError, match="Unknown transform"):
        load_outlier_config(bad)


def test_outlier_features_exist_in_dbt_mart(ocfg):
    """Every scored column must be selected by mart_outlier_features.sql."""
    from partd_risk.config import REPO_ROOT

    sql = (REPO_ROOT / "dbt/models/marts/analysis/mart_outlier_features.sql").read_text()
    for column in [f.column for f in ocfg.features] + list(ocfg.controls):
        assert column in sql, column
