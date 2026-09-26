from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from partd_risk.config import FeatureSpec
from partd_risk.modeling.peer_adjust import (
    peer_adjust,
    prepare_controls,
    robust_z,
    transform_metric,
    unadjusted_z,
    within_transform,
)

COST = FeatureSpec(name="cost_per_fill", column="cost_per_fill", transform="log")
BRAND = FeatureSpec(name="brand_fill_share", column="brand_fill_share", transform="logit")
CONTROLS = ["bene_avg_risk_score", "bene_avg_age", "dual_eligible_share", "is_rural"]


def test_transforms():
    s = pd.Series([0.0, 0.5, 1.0, None])
    logit = transform_metric(s, "logit", eps=0.01)
    assert logit[1] == pytest.approx(0.0)
    assert logit[0] == pytest.approx(np.log(0.01 / 0.99))
    assert np.isnan(logit[3])
    assert np.isnan(transform_metric(pd.Series([0.0]), "log")[0])
    assert transform_metric(pd.Series([0.0]), "log1p")[0] == 0.0
    with pytest.raises(ValueError):
        transform_metric(s, "sqrt")


def test_within_transform_zeroes_group_means():
    frame = pd.DataFrame({"x": [1.0, 3.0, 10.0, 14.0]})
    groups = pd.Series(["a", "a", "b", "b"])
    out = within_transform(frame, groups)
    assert out["x"].tolist() == [-1.0, 1.0, -2.0, 2.0]


def test_robust_z_is_resistant_to_outliers():
    values = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 1000.0])
    z = robust_z(values)
    assert z.iloc[2] == pytest.approx(0.0, abs=0.5)
    assert z.iloc[-1] > 100
    assert (robust_z(pd.Series([2.0, 2.0, 2.0])) == 0).all()


def test_prepare_controls_imputes_and_flags_missing():
    df = pd.DataFrame({"a": [1.0, None, 3.0], "b": [5.0, 5.0, 5.0]})
    out = prepare_controls(df, ["a", "b", "absent"])
    assert out["a"].tolist() == [1.0, 2.0, 3.0]
    assert out["a__missing"].tolist() == [0.0, 1.0, 0.0]
    assert "b" not in out  # zero variance dropped


def test_peer_adjustment_removes_group_and_casemix_effects(feature_frame):
    adj = peer_adjust(feature_frame, [COST, BRAND], CONTROLS, "peer_group_id")
    fit = {f.feature: f for f in adj.fits}["cost_per_fill"]
    # the planted case-mix slope (0.8 on the log scale) is recovered
    assert fit.coefficients["bene_avg_risk_score"] == pytest.approx(0.8, abs=0.15)
    # residuals are centred within every peer group
    resid = adj.residuals["cost_per_fill"]
    group_means = resid.groupby(feature_frame["peer_group_id"]).mean()
    assert group_means.abs().max() < 0.2


def test_planted_outliers_rank_highest(feature_frame):
    adj = peer_adjust(feature_frame, [COST], CONTROLS, "peer_group_id")
    top = adj.z["cost_per_fill"].nlargest(8).index
    assert feature_frame.loc[top, "is_outlier"].mean() >= 0.875


def test_peer_adjustment_beats_unadjusted(feature_frame):
    adjusted = peer_adjust(feature_frame, [COST], CONTROLS, "peer_group_id").z["cost_per_fill"]
    raw = unadjusted_z(feature_frame, [COST])["cost_per_fill"]
    hits_adj = feature_frame.loc[adjusted.nlargest(8).index, "is_outlier"].sum()
    hits_raw = feature_frame.loc[raw.nlargest(8).index, "is_outlier"].sum()
    assert hits_adj > hits_raw


def test_low_coverage_feature_is_dropped(feature_frame):
    frame = feature_frame.copy()
    frame.loc[frame.index[: int(0.8 * len(frame))], "brand_fill_share"] = np.nan
    adj = peer_adjust(frame, [COST, BRAND], CONTROLS, "peer_group_id", min_coverage=0.5)
    assert adj.dropped_features == ["brand_fill_share"]
    assert list(adj.z.columns) == ["cost_per_fill"]


def test_missing_metric_scores_neutral(feature_frame):
    frame = feature_frame.copy()
    frame.loc[0, "cost_per_fill"] = np.nan
    adj = peer_adjust(frame, [COST], CONTROLS, "peer_group_id")
    assert adj.z.loc[0, "cost_per_fill"] == 0.0


def test_missing_group_column_raises(feature_frame):
    with pytest.raises(KeyError):
        peer_adjust(feature_frame.drop(columns="peer_group_id"), [COST], CONTROLS, "peer_group_id")
