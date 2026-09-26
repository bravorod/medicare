from __future__ import annotations

import pandas as pd

from partd_risk.synthetic import generate


def test_synthetic_layout_matches_loader_config(cfg):
    data = generate(n_prescribers=300, seed=3)
    for name, frame in data.tables.items():
        assert set(frame.columns) == set(cfg.source(name).columns), name


def test_synthetic_is_deterministic():
    a = generate(n_prescribers=200, seed=11)["part_d_prescriber_drug"]
    b = generate(n_prescribers=200, seed=11)["part_d_prescriber_drug"]
    pd.testing.assert_frame_equal(a, b)


def test_synthetic_respects_cms_suppression_rule():
    drug = generate(n_prescribers=300, seed=5)["part_d_prescriber_drug"]
    assert drug["tot_clms"].astype(int).min() >= 11


def test_synthetic_values_are_strings_or_null():
    for name, frame in generate(n_prescribers=100, seed=2).tables.items():
        for column in frame.columns:
            values = frame[column].dropna()
            assert values.map(lambda v: isinstance(v, str)).all(), f"{name}.{column}"
