"""Regression estimate of the industry-payment brand-prescribing gap.

The SQL headline (``rpt_brand_comparison``) is an indirect standardization:
observed brand fills vs. those expected from unpaid peers in the same
specialty and state. This module checks it with a regression that also
controls for beneficiary case-mix and prescribing volume:

    log E[brand_fills_i] = log(expected_brand_fills_i)          (offset)
                           + beta * industry_paid_i
                           + gamma' * controls_i

fit as a Poisson GLM (quasi-likelihood, so non-integer 30-day fills are fine)
with standard errors clustered by peer group. ``exp(beta) - 1`` is the
percentage difference in brand-name fills for paid vs. comparable unpaid
prescribers.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm

from partd_risk.modeling.peer_adjust import prepare_controls

log = logging.getLogger(__name__)


@dataclass
class BrandEffect:
    term: str
    rate_ratio: float
    ci_low: float
    ci_high: float
    p_value: float
    n: int
    n_exposed: int
    n_clusters: int

    @property
    def pct_more(self) -> float:
        return 100 * (self.rate_ratio - 1)

    def as_dict(self) -> dict:
        out = asdict(self)
        out.update(
            pct_more=self.pct_more,
            pct_ci_low=100 * (self.ci_low - 1),
            pct_ci_high=100 * (self.ci_high - 1),
        )
        return out


def _design(
    df: pd.DataFrame, exposure: pd.DataFrame, controls: Sequence[str]
) -> tuple[pd.DataFrame, pd.Series, pd.Series, pd.Series]:
    keep = (df["expected_brand_fills"] > 0) & (df["drug_detail_fills"] > 0)
    d = df.loc[keep]
    x = pd.concat(
        [
            exposure.loc[keep].astype(float),
            prepare_controls(d, controls),
            np.log(d["drug_detail_fills"]).rename("log_total_fills")
            - np.log(d["drug_detail_fills"]).mean(),
        ],
        axis=1,
    )
    x = sm.add_constant(x, has_constant="add")
    return x, d["brand_fills"].astype(float), np.log(d["expected_brand_fills"]), d["peer_group_id"]


def _fit(x, y, offset, clusters):
    codes = pd.factorize(clusters)[0]
    model = sm.GLM(y, x, family=sm.families.Poisson(), offset=offset)
    return model.fit(cov_type="cluster", cov_kwds={"groups": codes}), len(np.unique(codes))


def fit_brand_effect(df: pd.DataFrame, controls: Sequence[str]) -> tuple[BrandEffect, str]:
    """Adjusted rate ratio of brand-name fills for industry-paid prescribers."""
    exposure = (
        df[["is_industry_paid"]].astype(bool).rename(columns={"is_industry_paid": "industry_paid"})
    )
    x, y, offset, clusters = _design(df, exposure, controls)
    result, n_clusters = _fit(x, y, offset, clusters)
    beta = result.params["industry_paid"]
    lo, hi = result.conf_int().loc["industry_paid"]
    effect = BrandEffect(
        term="industry_paid",
        rate_ratio=float(np.exp(beta)),
        ci_low=float(np.exp(lo)),
        ci_high=float(np.exp(hi)),
        p_value=float(result.pvalues["industry_paid"]),
        n=len(y),
        n_exposed=int(x["industry_paid"].sum()),
        n_clusters=n_clusters,
    )
    log.info(
        "Brand effect: RR=%.3f (95%% CI %.3f-%.3f), n=%s",
        effect.rate_ratio,
        effect.ci_low,
        effect.ci_high,
        f"{effect.n:,}",
    )
    return effect, result.summary().as_text()


def fit_tier_effects(df: pd.DataFrame, controls: Sequence[str]) -> pd.DataFrame:
    """Dose-response: one rate ratio per payment tier vs. no payments."""
    tiers = df["payment_tier"].astype(str)
    reference = sorted(tiers.unique())[0]  # '0: none'
    dummies = pd.get_dummies(tiers, prefix="tier").drop(columns=f"tier_{reference}")
    x, y, offset, clusters = _design(df, dummies, controls)
    result, n_clusters = _fit(x, y, offset, clusters)
    ci = result.conf_int()
    rows = []
    for col in dummies.columns:
        rows.append(
            {
                "payment_tier": col.removeprefix("tier_"),
                "rate_ratio": float(np.exp(result.params[col])),
                "ci_low": float(np.exp(ci.loc[col, 0])),
                "ci_high": float(np.exp(ci.loc[col, 1])),
                "p_value": float(result.pvalues[col]),
                "n_prescribers": int(x[col].sum()),
                "n_clusters": n_clusters,
            }
        )
    out = pd.DataFrame(rows).sort_values("payment_tier").reset_index(drop=True)
    out["pct_more"] = 100 * (out["rate_ratio"] - 1)
    return out
