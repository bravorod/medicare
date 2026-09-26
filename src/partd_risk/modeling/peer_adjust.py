"""Regression-based peer adjustment.

For each prescribing metric we fit a fixed-effects regression

    f(metric_i) = alpha_{peer group(i)} + beta' * casemix_i + e_i

where ``f`` is a variance-stabilising transform (logit for shares, log for
costs and volumes), ``alpha`` is a peer-group fixed effect (specialty x state,
with fallbacks assigned in dbt) and ``casemix`` holds beneficiary controls
(average HCC risk score, age, dual-eligible share, low-income-subsidy share,
female share, rurality). The model is estimated with the within
transformation, so ``alpha`` never has to be materialised as dummies and the
fit scales to the ~1M prescribers in a Part D year.

The residual ``e_i`` is what is left after accounting for *who the prescriber
is compared with* and *who their patients are*. It is converted to a robust
z-score (median / MAD) so that a handful of extreme prescribers cannot mask
each other.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from partd_risk.config import FeatureSpec

log = logging.getLogger(__name__)

MAD_TO_SD = 1.4826


def transform_metric(values: pd.Series, kind: str, eps: float = 0.005) -> pd.Series:
    """Apply the configured transform; invalid inputs become NaN."""
    x = pd.to_numeric(values, errors="coerce").astype(float)
    if kind == "logit":
        p = x.clip(eps, 1 - eps)
        return np.log(p / (1 - p))
    if kind == "log":
        return np.log(x.where(x > 0))
    if kind == "log1p":
        return np.log1p(x.clip(lower=0))
    if kind == "identity":
        return x
    raise ValueError(f"Unknown transform {kind!r}")


def prepare_controls(df: pd.DataFrame, controls: Sequence[str]) -> pd.DataFrame:
    """Median-impute controls and add a missingness indicator where needed.

    CMS suppresses small beneficiary counts, so some case-mix fields are NULL;
    the indicator lets the regression absorb any systematic difference in
    prescribers with suppressed values instead of dropping them.
    """
    out = pd.DataFrame(index=df.index)
    for name in controls:
        if name not in df:
            log.warning("Control %s not in feature table; skipping", name)
            continue
        col = pd.to_numeric(df[name], errors="coerce").astype(float)
        missing = col.isna()
        fill = col.median() if col.notna().any() else 0.0
        out[name] = col.fillna(fill)
        if 0 < missing.mean() < 1:
            out[f"{name}__missing"] = missing.astype(float)
    return out.loc[:, out.std(ddof=0) > 0]


def within_transform(frame: pd.DataFrame | pd.Series, groups: pd.Series):
    """Subtract group means (the fixed-effects 'within' transformation)."""
    return frame - frame.groupby(groups).transform("mean")


def robust_z(values: pd.Series) -> pd.Series:
    """(x - median) / (1.4826 * MAD), falling back to the SD if MAD is 0."""
    med = values.median()
    scale = MAD_TO_SD * (values - med).abs().median()
    if not np.isfinite(scale) or scale == 0:
        scale = values.std(ddof=0)
    if not np.isfinite(scale) or scale == 0:
        return pd.Series(0.0, index=values.index)
    return (values - med) / scale


@dataclass
class MetricFit:
    feature: str
    transform: str
    n: int
    coverage: float
    r2_within: float
    residual_scale: float
    coefficients: dict[str, float] = field(default_factory=dict)


@dataclass
class PeerAdjustment:
    z: pd.DataFrame
    residuals: pd.DataFrame
    fits: list[MetricFit]
    dropped_features: list[str]

    def diagnostics(self) -> pd.DataFrame:
        rows = []
        for fit in self.fits:
            row = {
                "feature": fit.feature,
                "transform": fit.transform,
                "n": fit.n,
                "coverage": fit.coverage,
                "r2_within": fit.r2_within,
                "residual_scale": fit.residual_scale,
            }
            row.update({f"beta__{k}": v for k, v in fit.coefficients.items()})
            rows.append(row)
        return pd.DataFrame(rows)


def peer_adjust(
    df: pd.DataFrame,
    features: Sequence[FeatureSpec],
    controls: Sequence[str],
    group_col: str,
    eps: float = 0.005,
    min_coverage: float = 0.5,
) -> PeerAdjustment:
    """Peer-adjust every feature and return robust z-scores of the residuals.

    Prescribers with a missing metric get z = 0 for that metric (neutral), so
    missing data can never push someone up the ranking.
    """
    if group_col not in df:
        raise KeyError(f"Peer group column {group_col!r} missing from feature table")
    groups = df[group_col].astype(str)
    controls_frame = prepare_controls(df, controls)
    z_cols, resid_cols, fits, dropped = {}, {}, [], []

    for feature in features:
        if feature.column not in df:
            log.warning("Feature column %s missing; dropping %s", feature.column, feature.name)
            dropped.append(feature.name)
            continue
        y = transform_metric(df[feature.column], feature.transform, eps)
        mask = y.notna() & np.isfinite(y)
        coverage = float(mask.mean())
        if coverage < min_coverage:
            log.warning("%s covers %.0f%% of cohort; dropping", feature.name, 100 * coverage)
            dropped.append(feature.name)
            continue

        g = groups[mask]
        y_within = within_transform(y[mask], g)
        x_within = within_transform(controls_frame[mask], g)
        if x_within.shape[1]:
            beta, *_ = np.linalg.lstsq(x_within.to_numpy(), y_within.to_numpy(), rcond=None)
            resid = y_within - x_within.to_numpy() @ beta
            coefs = dict(zip(x_within.columns, map(float, beta), strict=True))
        else:
            resid, coefs = y_within, {}
        total_var = float(y_within.var(ddof=0))
        r2 = 1 - float(resid.var(ddof=0)) / total_var if total_var > 0 else 0.0
        z = robust_z(resid)

        z_cols[feature.name] = z.reindex(df.index).fillna(0.0)
        resid_cols[feature.name] = resid.reindex(df.index)
        fits.append(
            MetricFit(
                feature=feature.name,
                transform=feature.transform,
                n=int(mask.sum()),
                coverage=coverage,
                r2_within=r2,
                residual_scale=float(MAD_TO_SD * (resid - resid.median()).abs().median()),
                coefficients=coefs,
            )
        )
        log.info(
            "Peer-adjusted %-26s n=%s coverage=%.2f within-R2=%.3f",
            feature.name,
            f"{int(mask.sum()):,}",
            coverage,
            r2,
        )

    return PeerAdjustment(
        z=pd.DataFrame(z_cols, index=df.index),
        residuals=pd.DataFrame(resid_cols, index=df.index),
        fits=fits,
        dropped_features=dropped,
    )


def unadjusted_z(
    df: pd.DataFrame, features: Sequence[FeatureSpec], eps: float = 0.005
) -> pd.DataFrame:
    """Baseline without peer adjustment: global robust z of each transformed metric."""
    cols = {}
    for feature in features:
        if feature.column not in df:
            continue
        y = transform_metric(df[feature.column], feature.transform, eps)
        mask = y.notna() & np.isfinite(y)
        cols[feature.name] = robust_z(y[mask]).reindex(df.index).fillna(0.0)
    return pd.DataFrame(cols, index=df.index)
