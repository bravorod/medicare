from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from partd_risk.modeling.brand_effect import fit_brand_effect, fit_tier_effects


@pytest.fixture
def brand_frame(rng):
    n = 6000
    groups = rng.integers(0, 30, n)
    paid = rng.random(n) < 0.45
    tier = np.where(paid, rng.choice(["1: $1-99", "2: $100-999", "3: $1,000+"], n), "0: none")
    fills = rng.integers(150, 3000, n).astype(float)
    peer_share = 0.15 + 0.01 * groups
    risk = rng.normal(1.2, 0.3, n)
    tier_rr = pd.Series(tier).map(
        {"0: none": 1.0, "1: $1-99": 1.1, "2: $100-999": 1.25, "3: $1,000+": 1.4}
    )
    mean = fills * peer_share * tier_rr.to_numpy() * np.exp(0.1 * (risk - 1.2))
    return pd.DataFrame(
        {
            "npi": [str(i) for i in range(n)],
            "peer_group_id": groups.astype(str),
            "is_industry_paid": paid,
            "payment_tier": tier,
            "drug_detail_fills": fills,
            "expected_brand_fills": fills * peer_share,
            "brand_fills": rng.poisson(mean).astype(float),
            "bene_avg_risk_score": risk,
        }
    )


def test_recovers_planted_rate_ratio(brand_frame):
    effect, summary = fit_brand_effect(brand_frame, ["bene_avg_risk_score"])
    # paid prescribers are an even mix of RR 1.10 / 1.25 / 1.40 -> ~1.25 overall
    assert effect.rate_ratio == pytest.approx(1.25, abs=0.04)
    assert effect.ci_low < effect.rate_ratio < effect.ci_high
    assert effect.pct_more == pytest.approx(100 * (effect.rate_ratio - 1))
    assert effect.n_clusters == 30
    assert "Generalized Linear Model" in summary


def test_tier_effects_are_ordered(brand_frame):
    tiers = fit_tier_effects(brand_frame, ["bene_avg_risk_score"])
    assert tiers["payment_tier"].tolist() == ["1: $1-99", "2: $100-999", "3: $1,000+"]
    assert tiers["rate_ratio"].is_monotonic_increasing
    assert tiers.loc[2, "rate_ratio"] == pytest.approx(1.4, abs=0.06)
