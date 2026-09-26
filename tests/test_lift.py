from __future__ import annotations

import numpy as np
import pytest

from partd_risk.evaluation.lift import bootstrap_lift, discrimination, lift_at_k, lift_curve


def test_lift_at_k_exact():
    # 100 prescribers, 5 events; top 10% contains 3 of them.
    scores = np.arange(100, 0, -1, dtype=float)
    outcome = np.zeros(100, dtype=bool)
    outcome[[0, 4, 9, 50, 80]] = True
    res = lift_at_k(scores, outcome, 0.10)
    assert res.n_flagged == 10
    assert res.events_captured == 3
    assert res.capture_share == pytest.approx(0.6)
    assert res.lift == pytest.approx(6.0)
    assert res.precision == pytest.approx(0.3)
    assert res.base_rate == pytest.approx(0.05)


def test_random_scores_have_lift_near_one(rng):
    scores = rng.random(200_000)
    outcome = rng.random(200_000) < 0.01
    assert lift_at_k(scores, outcome, 0.10).lift == pytest.approx(1.0, abs=0.15)


def test_lift_curve_is_monotone_in_capture(rng):
    scores = rng.random(5000)
    outcome = rng.random(5000) < (0.005 + 0.05 * scores)
    curve = lift_curve(scores, outcome, [0.01, 0.05, 0.1, 0.5, 1.0])
    assert curve["capture_share"].is_monotonic_increasing
    assert curve["capture_share"].iloc[-1] == pytest.approx(1.0)


def test_bootstrap_ci_brackets_point_estimate(rng):
    scores = rng.random(20_000)
    outcome = rng.random(20_000) < (0.002 + 0.02 * scores**4)
    point = lift_at_k(scores, outcome, 0.05).lift
    lo, hi, samples = bootstrap_lift(scores, outcome, 0.05, reps=300, seed=1)
    assert lo < point < hi
    assert len(samples) == 300


def test_errors():
    with pytest.raises(ValueError, match="no positive"):
        lift_at_k([1.0, 2.0], [False, False], 0.5)
    with pytest.raises(ValueError, match="k must"):
        lift_at_k([1.0, 2.0], [True, False], 0.0)
    with pytest.raises(ValueError, match="same length"):
        lift_at_k([1.0, 2.0], [True], 0.5)


def test_discrimination_perfect_ranking():
    out = discrimination([0.9, 0.8, 0.1, 0.0], [True, True, False, False])
    assert out["auroc"] == pytest.approx(1.0)
    assert out["average_precision"] == pytest.approx(1.0)
