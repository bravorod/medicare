from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest

from partd_risk.config import FeatureSpec
from partd_risk.modeling.outlier_score import composite_score, score_prescribers, top_k_flags


def test_composite_score_keeps_risk_direction_and_caps():
    z = pd.DataFrame({"a": [-5.0, 1.0, 20.0], "b": [0.0, 3.0, 0.0]})
    score = composite_score(z, {"a": 1.0, "b": 1.0}, cap=8.0)
    assert score.tolist() == [0.0, 2.0, 4.0]


def test_composite_score_weights():
    z = pd.DataFrame({"a": [2.0], "b": [4.0]})
    assert composite_score(z, {"a": 3.0, "b": 1.0}, cap=10)[0] == pytest.approx(2.5)
    with pytest.raises(ValueError):
        composite_score(z, {"a": -1.0, "b": 1.0}, cap=10)
    with pytest.raises(ValueError):
        composite_score(z, {"a": 0.0, "b": 0.0}, cap=10)


def test_top_k_flags_exact_count_and_deterministic_ties():
    scores = pd.Series([1.0, 5.0, 5.0, 0.0, 2.0])
    ids = pd.Series(["e", "d", "c", "b", "a"])
    flags = top_k_flags(scores, 0.4, ids)
    assert flags.sum() == 2
    assert flags.tolist() == [False, True, True, False, False]
    flags = top_k_flags(scores, 0.2, ids)
    assert flags.tolist() == [False, False, True, False, False]  # tie broken by id "c" < "d"


def test_score_prescribers_end_to_end(feature_frame, ocfg):
    cfg = replace(
        ocfg,
        features=(
            FeatureSpec("cost_per_fill", "cost_per_fill", "log"),
            FeatureSpec("brand_fill_share", "brand_fill_share", "logit"),
            FeatureSpec("not_there", "missing_column", "log"),
        ),
        controls=("bene_avg_risk_score", "dual_eligible_share"),
    )
    result = score_prescribers(feature_frame, cfg)
    scores = result.scores
    assert len(scores) == len(feature_frame)
    assert result.adjustment.dropped_features == ["not_there"]
    assert scores["is_top_1pct"].sum() == 8  # ceil(1% of 720)
    assert scores["outlier_percentile"].between(0, 100).all()
    assert {"z__cost_per_fill", "z__brand_fill_share"} <= set(scores.columns)
    assert set(scores["top_feature"]) <= {"cost_per_fill", "brand_fill_share"}
