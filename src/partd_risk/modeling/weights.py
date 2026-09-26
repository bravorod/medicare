"""Learn feature weights for the outlier score from *earlier* exclusions.

The peer-adjusted z-scores say how unusual a prescriber is on each metric.
Averaging them with equal weights treats every metric as equally telling. This
module instead fits a logistic regression of the development-window outcome
(first OIG exclusion in 2022-2023) on the clipped z-scores:

    logit P(excluded in dev window) = b0 + sum_f w_f * min(max(z_f, 0), cap)

with every w_f constrained to be >= 0, so a metric can only add risk, never
subtract it, and the score stays readable as "sum of risk-direction
deviations". An L2 penalty keeps the handful of development events from
producing extreme weights.

The fitted weights are then applied unchanged to every prescriber and
evaluated on exclusions that happened *after* the development window
(pipeline.run_model), so the test outcomes never influence the weights.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize


@dataclass
class LearnedWeights:
    weights: dict[str, float]
    standardized_weights: dict[str, float]
    intercept: float
    n: int
    n_events: int
    l2_penalty: float
    converged: bool

    def as_dict(self) -> dict:
        return asdict(self)

    def table(self) -> pd.DataFrame:
        return (
            pd.DataFrame(
                {
                    "feature": list(self.weights),
                    "weight": list(self.weights.values()),
                    "standardized_weight": list(self.standardized_weights.values()),
                }
            )
            .sort_values("standardized_weight", ascending=False)
            .reset_index(drop=True)
        )


def fit_nonnegative_logistic(
    x: pd.DataFrame, y: np.ndarray | pd.Series, l2_penalty: float = 1.0
) -> LearnedWeights:
    """L2-penalised logistic regression with non-negative slopes (L-BFGS-B).

    Columns are divided by their standard deviation before fitting (no
    centring, which would break the sign constraint's meaning), so the penalty
    treats every feature alike; weights are reported back on the original
    scale.
    """
    y = np.asarray(y, dtype=float)
    if y.sum() == 0:
        raise ValueError("No development-window events to learn weights from")
    names = list(x.columns)
    values = x.to_numpy(dtype=float)
    sd = values.std(axis=0)
    sd[sd == 0] = 1.0
    xs = values / sd
    n, p = xs.shape

    def objective(params: np.ndarray) -> tuple[float, np.ndarray]:
        b0, beta = params[0], params[1:]
        eta = b0 + xs @ beta
        loss = np.logaddexp(0.0, eta).sum() - y @ eta + 0.5 * l2_penalty * beta @ beta
        resid = 1.0 / (1.0 + np.exp(-eta)) - y
        grad = np.concatenate(([resid.sum()], xs.T @ resid + l2_penalty * beta))
        return loss, grad

    start = np.zeros(p + 1)
    start[0] = np.log(y.mean() / (1 - y.mean()))
    bounds = [(None, None)] + [(0.0, None)] * p
    result = minimize(objective, start, jac=True, method="L-BFGS-B", bounds=bounds)
    beta = result.x[1:]
    return LearnedWeights(
        weights={name: float(b / s) for name, b, s in zip(names, beta, sd, strict=True)},
        standardized_weights={name: float(b) for name, b in zip(names, beta, strict=True)},
        intercept=float(result.x[0]),
        n=int(n),
        n_events=int(y.sum()),
        l2_penalty=float(l2_penalty),
        converged=bool(result.success),
    )


def weighted_score(x: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """Linear risk score: sum of weight x clipped z (the logit without intercept)."""
    w = pd.Series({col: weights.get(col, 0.0) for col in x.columns})
    return x.mul(w, axis=1).sum(axis=1)
