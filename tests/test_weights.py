from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from partd_risk.modeling.weights import fit_nonnegative_logistic, weighted_score
from partd_risk.pipeline import temporal_split


@pytest.fixture
def clipped_z(rng):
    n = 40_000
    x = pd.DataFrame(
        {
            "signal": rng.exponential(1.0, n),
            "noise": rng.exponential(1.0, n),
            "protective": rng.exponential(1.0, n),
        }
    )
    eta = -7.0 + 1.2 * x["signal"] - 0.8 * x["protective"]
    y = rng.random(n) < 1 / (1 + np.exp(-eta))
    return x, y.to_numpy()


def test_learns_signal_and_respects_non_negativity(clipped_z):
    x, y = clipped_z
    fit = fit_nonnegative_logistic(x, y, l2_penalty=1.0)
    assert fit.converged
    assert fit.weights["signal"] == pytest.approx(1.2, abs=0.35)
    assert fit.weights["noise"] < 0.2
    # a truly protective feature is pinned at zero, never negative
    assert fit.weights["protective"] == 0.0
    assert all(w >= 0 for w in fit.weights.values())
    assert fit.n_events == int(y.sum())
    assert fit.table()["feature"].iloc[0] == "signal"


def test_weighted_score_ranks_by_signal(clipped_z):
    x, y = clipped_z
    fit = fit_nonnegative_logistic(x, y)
    score = weighted_score(x, fit.weights)
    top = score.nlargest(400).index
    assert y[top].mean() > 3 * y.mean()


def test_no_events_is_an_error():
    x = pd.DataFrame({"a": [0.0, 1.0, 2.0]})
    with pytest.raises(ValueError, match="No development-window events"):
        fit_nonnegative_logistic(x, np.zeros(3))


def test_temporal_split_keeps_roles_apart():
    features = pd.DataFrame(
        {
            "excluded_in_window": [True, True, False, True, None],
            "window_exclusion_date": ["2022-06-01", "2024-03-01", None, "2023-12-31", None],
        }
    )
    split = temporal_split(features, "2024-01-01")
    assert split.dev_y.tolist() == [True, False, False, True, False]
    assert split.test_y.tolist() == [False, True, False, False, False]
    # already-excluded (dev) prescribers are not in the test population
    assert split.test_mask.tolist() == [False, True, True, False, True]
    assert split.describe() == {
        "split_date": "2024-01-01",
        "dev_events": 2,
        "test_events": 1,
        "test_population": 3,
        "test_window_end": "2024-03-01",
    }
