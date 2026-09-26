from __future__ import annotations

import pandas as pd

from partd_risk.config import REPO_ROOT
from partd_risk.reporting.dictionary import collect_models, render
from partd_risk.reporting.tableau import pseudonym, suppress_small_cells


def test_pseudonym_is_stable_and_salted():
    assert pseudonym("1234567890", "s1") == pseudonym("1234567890", "s1")
    assert pseudonym("1234567890", "s1") != pseudonym("1234567890", "s2")
    assert "1234567890" not in pseudonym("1234567890", "s1")
    assert len(pseudonym("1234567890", "s1")) == 12


def test_data_dictionary_covers_every_documented_model():
    models = collect_models(REPO_ROOT / "dbt" / "models")
    names = {m["name"] for m in models}
    for expected in ("fct_prescribers", "mart_outlier_features", "rpt_brand_comparison"):
        assert expected in names
    text = render(models)
    assert text.index("## Staging") < text.index("## Intermediate") < text.index("## Marts")


def test_every_sql_model_is_documented():
    sql = {p.stem for p in (REPO_ROOT / "dbt" / "models").rglob("*.sql")}
    documented = {m["name"] for m in collect_models(REPO_ROOT / "dbt" / "models")}
    assert sql - documented == set()


def test_small_cells_are_suppressed_except_cohort_flow():
    frame = pd.DataFrame({"segment": ["a", "b", "c"], "n_prescribers": [10, 11, 500]})
    assert suppress_small_cells(frame, "specialty_summary")["segment"].tolist() == ["b", "c"]
    assert len(suppress_small_cells(frame, "cohort_flow")) == 3
    assert len(suppress_small_cells(frame.drop(columns="n_prescribers"), "x")) == 3
