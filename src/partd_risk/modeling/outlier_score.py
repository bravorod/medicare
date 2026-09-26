"""Composite peer-adjusted outlier score.

The score is the weighted mean of each prescriber's peer-adjusted robust
z-scores, keeping only the risk direction (negative z clipped to 0) and
capping each feature so one extreme metric cannot dominate:

    score_i = sum_f w_f * min(max(z_if, 0), cap) / sum_f w_f

The score is unsupervised: it is built only from prescribing, cost and payment
behaviour. OIG exclusions are used afterwards to *evaluate* it.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

from partd_risk.config import OutlierConfig
from partd_risk.modeling.peer_adjust import PeerAdjustment, peer_adjust, unadjusted_z

log = logging.getLogger(__name__)


def composite_score(z: pd.DataFrame, weights: Mapping[str, float], cap: float) -> pd.Series:
    if z.empty:
        raise ValueError("No features available to score")
    w = pd.Series({col: float(weights.get(col, 1.0)) for col in z.columns})
    if (w < 0).any():
        raise ValueError("Feature weights must be non-negative")
    if w.sum() == 0:
        raise ValueError("At least one feature needs a positive weight")
    clipped = z.clip(lower=0.0, upper=cap)
    return clipped.mul(w, axis=1).sum(axis=1) / w.sum()


def rank_order(scores: pd.Series, tiebreak: pd.Series | None = None) -> np.ndarray:
    """Positions sorted from highest to lowest score, deterministic on ties."""
    values = scores.to_numpy(dtype=float)
    if tiebreak is None:
        return np.argsort(-values, kind="stable")
    # lexsort sorts by the last key first; negate the score for descending order.
    return np.lexsort((tiebreak.astype(str).to_numpy(), -values))


def top_k_flags(scores: pd.Series, k: float, tiebreak: pd.Series | None = None) -> pd.Series:
    n_flag = int(np.ceil(k * len(scores)))
    flags = np.zeros(len(scores), dtype=bool)
    flags[rank_order(scores, tiebreak)[:n_flag]] = True
    return pd.Series(flags, index=scores.index)


@dataclass
class ScoreResult:
    scores: pd.DataFrame
    adjustment: PeerAdjustment
    raw_z: pd.DataFrame

    @property
    def feature_names(self) -> list[str]:
        return list(self.adjustment.z.columns)


def score_prescribers(features: pd.DataFrame, cfg: OutlierConfig) -> ScoreResult:
    """Peer-adjust, score and rank every cohort prescriber."""
    adjustment = peer_adjust(
        features,
        cfg.features,
        cfg.controls,
        cfg.peer_group_column,
        eps=cfg.logit_eps,
        min_coverage=cfg.min_feature_coverage,
    )
    weights = {f.name: f.weight for f in cfg.features}
    score = composite_score(adjustment.z, weights, cfg.z_cap)
    raw_z = unadjusted_z(
        features, [f for f in cfg.features if f.name in adjustment.z], cfg.logit_eps
    )
    raw_score = composite_score(raw_z, weights, cfg.z_cap)

    npi = features["npi"].astype(str)
    out = pd.DataFrame(
        {
            "npi": npi,
            "outlier_score": score,
            "outlier_percentile": 100 * score.rank(pct=True, method="max"),
            "is_top_1pct": top_k_flags(score, 0.01, npi),
            "unadjusted_score": raw_score,
            "top_feature": adjustment.z.idxmax(axis=1),
            "top_feature_z": adjustment.z.max(axis=1),
        },
        index=features.index,
    )
    for col in adjustment.z.columns:
        out[f"z__{col}"] = adjustment.z[col]
    log.info(
        "Scored %s prescribers on %d features (dropped: %s)",
        f"{len(out):,}",
        adjustment.z.shape[1],
        ", ".join(adjustment.dropped_features) or "none",
    )
    return ScoreResult(scores=out, adjustment=adjustment, raw_z=raw_z)
