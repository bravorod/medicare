from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from partd_risk.config import load_config, load_outlier_config


@pytest.fixture(scope="session")
def cfg():
    return load_config()


@pytest.fixture(scope="session")
def ocfg():
    return load_outlier_config()


@pytest.fixture
def rng():
    return np.random.default_rng(1234)


@pytest.fixture
def feature_frame(rng) -> pd.DataFrame:
    """Small cohort with a peer-group effect, a case-mix effect and planted outliers."""
    n_groups, per_group = 12, 60
    n = n_groups * per_group
    group = np.repeat([f"Spec{g % 4} | S{g}" for g in range(n_groups)], per_group)
    group_effect = np.repeat(rng.normal(0, 1.0, n_groups), per_group)
    risk_score = rng.normal(1.2, 0.3, n)
    base = group_effect + 0.8 * (risk_score - 1.2)
    frame = pd.DataFrame(
        {
            "npi": [f"{1000000000 + i}" for i in range(n)],
            "peer_group_id": group,
            "bene_avg_risk_score": risk_score,
            "bene_avg_age": rng.normal(72, 3, n),
            "dual_eligible_share": rng.beta(2, 6, n),
            "lis_claim_share": rng.beta(2, 5, n),
            "female_share": rng.beta(10, 9, n),
            "is_rural": rng.integers(0, 2, n),
            "cost_per_fill": np.exp(4 + base + rng.normal(0, 0.2, n)),
            "brand_fill_share": 1 / (1 + np.exp(-(-1 + base + rng.normal(0, 0.2, n)))),
        }
    )
    frame["is_outlier"] = False
    outliers = rng.choice(n, 8, replace=False)
    frame.loc[outliers, "cost_per_fill"] *= np.exp(1.5)
    frame.loc[outliers, "is_outlier"] = True
    return frame
