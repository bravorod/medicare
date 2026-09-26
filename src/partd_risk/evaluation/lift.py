"""Lift / capture metrics for a risk score against a binary outcome.

The headline question is: *what share of later OIG exclusions fall in the top
k% of scores, relative to the k% you would expect by chance?*

    capture_share(k) = excluded prescribers in top k% / all excluded prescribers
    lift(k)          = capture_share(k) / k

A lift of 1 means the score is no better than random; a lift of 10 at k = 1%
means the top 1% of scores contains 10% of all later exclusions.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score


@dataclass(frozen=True)
class LiftResult:
    k: float
    n: int
    n_flagged: int
    events_total: int
    events_captured: int
    capture_share: float
    expected_share: float
    lift: float
    precision: float
    base_rate: float

    def as_dict(self) -> dict:
        return asdict(self)


def _order(scores: np.ndarray, tiebreak: np.ndarray | None) -> np.ndarray:
    if tiebreak is None:
        return np.argsort(-scores, kind="stable")
    return np.lexsort((tiebreak, -scores))


def lift_at_k(
    scores: Sequence[float] | np.ndarray,
    outcome: Sequence[bool] | np.ndarray,
    k: float,
    tiebreak: np.ndarray | None = None,
) -> LiftResult:
    s = np.asarray(scores, dtype=float)
    y = np.asarray(outcome, dtype=bool)
    if s.shape != y.shape:
        raise ValueError("scores and outcome must have the same length")
    if not 0 < k <= 1:
        raise ValueError("k must be in (0, 1]")
    n = len(s)
    events = int(y.sum())
    if events == 0:
        raise ValueError("Outcome has no positive cases; lift is undefined")
    n_flag = int(np.ceil(k * n))
    captured = int(y[_order(s, tiebreak)[:n_flag]].sum())
    expected_share = n_flag / n
    capture_share = captured / events
    return LiftResult(
        k=k,
        n=n,
        n_flagged=n_flag,
        events_total=events,
        events_captured=captured,
        capture_share=capture_share,
        expected_share=expected_share,
        lift=capture_share / expected_share,
        precision=captured / n_flag,
        base_rate=events / n,
    )


def lift_curve(
    scores: Sequence[float] | np.ndarray,
    outcome: Sequence[bool] | np.ndarray,
    ks: Sequence[float],
    tiebreak: np.ndarray | None = None,
) -> pd.DataFrame:
    return pd.DataFrame([lift_at_k(scores, outcome, k, tiebreak).as_dict() for k in ks])


def bootstrap_lift(
    scores: Sequence[float] | np.ndarray,
    outcome: Sequence[bool] | np.ndarray,
    k: float,
    reps: int = 1000,
    seed: int = 0,
    alpha: float = 0.05,
) -> tuple[float, float, np.ndarray]:
    """Percentile bootstrap CI for lift at k, resampling prescribers.

    Each replicate draws n prescribers with replacement. Instead of re-sorting
    every replicate, prescribers are sorted once and the replicate's top-k set
    is read off the cumulative multiplicity counts, which is exact and O(n)
    per replicate.
    """
    s = np.asarray(scores, dtype=float)
    y = np.asarray(outcome, dtype=bool)
    order = _order(s, None)
    y_sorted = y[order].astype(np.int64)
    n = len(s)
    n_flag = int(np.ceil(k * n))
    rng = np.random.default_rng(seed)
    lifts = np.empty(reps)
    for r in range(reps):
        counts = np.bincount(rng.integers(0, n, n), minlength=n)[order]
        cum = np.cumsum(counts)
        cut = int(np.searchsorted(cum, n_flag))  # first position where cum >= n_flag
        full = counts[:cut]
        taken = np.append(full, n_flag - (cum[cut - 1] if cut > 0 else 0))
        captured = float((taken * y_sorted[: cut + 1]).sum())
        events = float((counts * y_sorted).sum())
        lifts[r] = (captured / events) / (n_flag / n) if events > 0 else np.nan
    lifts = lifts[np.isfinite(lifts)]
    lo, hi = np.quantile(lifts, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi), lifts


def discrimination(
    scores: Sequence[float] | np.ndarray, outcome: Sequence[bool] | np.ndarray
) -> dict[str, float]:
    y = np.asarray(outcome, dtype=bool)
    s = np.asarray(scores, dtype=float)
    return {
        "auroc": float(roc_auc_score(y, s)),
        "average_precision": float(average_precision_score(y, s)),
        "base_rate": float(y.mean()),
    }
