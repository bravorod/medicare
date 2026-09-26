"""Orchestrates the Python half of the pipeline (after `dbt build`).

``run_model`` scores prescribers, learns feature weights on development-window
exclusions, evaluates on held-out later exclusions, fits the brand-prescribing
regression and writes every artifact the results step needs.

Outcome discipline: the peer adjustment never sees an outcome; the weights and
the choice between candidate scores see only development-window (2022-2023)
exclusions; the headline lift is measured on test-window (2024+) exclusions
that played no part in either.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from partd_risk.config import REPO_ROOT, OutlierConfig, PipelineConfig
from partd_risk.evaluation.lift import bootstrap_lift, discrimination, lift_at_k, lift_curve
from partd_risk.modeling.brand_effect import fit_brand_effect, fit_tier_effects
from partd_risk.modeling.outlier_score import score_prescribers, top_k_flags
from partd_risk.modeling.weights import fit_nonnegative_logistic, weighted_score

log = logging.getLogger(__name__)

SYNTHETIC_OUTPUT_ROOT = REPO_ROOT / "data" / "synthetic" / "outputs"


@dataclass(frozen=True)
class OutputDirs:
    results: Path
    figures: Path
    tableau: Path
    memo: Path

    def create(self) -> OutputDirs:
        for path in (self.results, self.figures, self.tableau, self.memo):
            path.mkdir(parents=True, exist_ok=True)
        return self


def output_dirs(cfg: PipelineConfig, is_synthetic: bool, root: Path | None = None) -> OutputDirs:
    """Real runs write into the repo's reports/ and tableau/ folders.

    Synthetic runs are routed to data/synthetic/outputs (git-ignored) so a
    simulated number can never end up committed next to the real ones.
    """
    if root is not None:
        base = Path(root)
        return OutputDirs(base / "results", base / "figures", base / "tableau", base / "memo")
    if is_synthetic:
        base = SYNTHETIC_OUTPUT_ROOT
        return OutputDirs(base / "results", base / "figures", base / "tableau", base / "memo")
    return OutputDirs(
        cfg.results_dir, cfg.figures_dir, cfg.tableau_dir, REPO_ROOT / "reports" / "memo"
    )


def is_synthetic_warehouse(wh) -> bool:
    prov = wh.read("reporting", "rpt_data_provenance", ["is_synthetic"])
    if prov.empty:
        raise RuntimeError("rpt_data_provenance is empty; was the raw data loaded with partd-risk?")
    return bool(prov["is_synthetic"].astype(bool).any())


def _json_default(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    raise TypeError(f"Not JSON serializable: {type(value)}")


def write_json(payload: dict, path: Path) -> None:
    path.write_text(json.dumps(payload, indent=2, default=_json_default) + "\n")


@dataclass(frozen=True)
class TemporalSplit:
    """Development / test outcomes for the score (ADR 0007)."""

    split_date: pd.Timestamp
    dev_y: np.ndarray  # first exclusion in [window start, split_date)
    test_mask: np.ndarray  # everyone not already excluded in the dev window
    test_y: np.ndarray  # first exclusion on/after split_date (full length; use with mask)
    window_end: pd.Timestamp | None

    def describe(self) -> dict:
        return {
            "split_date": self.split_date.date().isoformat(),
            "dev_events": int(self.dev_y.sum()),
            "test_events": int(self.test_y[self.test_mask].sum()),
            "test_population": int(self.test_mask.sum()),
            "test_window_end": self.window_end.date().isoformat() if self.window_end else None,
        }


def temporal_split(features: pd.DataFrame, split_date: str) -> TemporalSplit:
    excluded = features["excluded_in_window"].fillna(False).astype(bool).to_numpy()
    when = pd.to_datetime(features["window_exclusion_date"])
    split = pd.Timestamp(split_date)
    dev_y = excluded & (when < split).fillna(False).to_numpy()
    test_y = excluded & (when >= split).fillna(False).to_numpy()
    # Prefer the configured window end (dbt var outcome_window_end) over the
    # last observed exclusion date.
    if "outcome_window_end" in features and features["outcome_window_end"].notna().any():
        end = pd.to_datetime(features["outcome_window_end"]).max()
    else:
        end = when.max()
    return TemporalSplit(split, dev_y, ~dev_y, test_y, None if pd.isna(end) else end)


def _metrics(scores: np.ndarray, y: np.ndarray, k: float, tiebreak: np.ndarray) -> dict:
    out = discrimination(scores, y)
    out["lift_at_k"] = lift_at_k(scores, y, k, tiebreak).lift
    return out


def evaluate_score(
    features: pd.DataFrame,
    candidates: dict[str, pd.Series],
    selected: str,
    split: TemporalSplit,
    z: pd.DataFrame,
    ocfg: OutlierConfig,
    tiebreak: np.ndarray,
) -> tuple[dict, dict[str, pd.DataFrame]]:
    """Test-window lift, bootstrap CI and baselines for every candidate score."""
    k = ocfg.headline_k
    mask, y = split.test_mask, split.test_y[split.test_mask]
    tables: dict[str, pd.DataFrame] = {}
    if y.sum() == 0:
        log.warning("No test-window exclusions; skipping lift evaluation")
        return {"events_total": 0, "design": split.describe()}, tables

    tb = tiebreak[mask]
    curves = []
    for name, score in candidates.items():
        curve = lift_curve(score.to_numpy()[mask], y, ocfg.top_k, tb)
        curve.insert(0, "score", name)
        curves.append(curve)
    tables["lift_curve"] = pd.concat(curves, ignore_index=True)

    test_by_score = {
        name: lift_at_k(score.to_numpy()[mask], y, k, tb).as_dict()
        for name, score in candidates.items()
    }
    chosen = candidates[selected].to_numpy()[mask]
    headline = lift_at_k(chosen, y, k, tb)
    lo, hi, _ = bootstrap_lift(chosen, y, k, reps=ocfg.bootstrap_reps, seed=ocfg.seed)

    single = []
    for col in z.columns:
        dev = lift_at_k(z[col].to_numpy(), split.dev_y, k, tiebreak) if split.dev_y.any() else None
        test = lift_at_k(z[col].to_numpy()[mask], y, k, tb)
        single.append(
            {
                "feature": col,
                "dev_lift": dev.lift if dev else None,
                "test_lift": test.lift,
                "test_events_captured": test.events_captured,
            }
        )
    tables["single_feature_lift"] = pd.DataFrame(single).sort_values("dev_lift", ascending=False)

    flagged = np.zeros(int(mask.sum()), dtype=bool)
    flagged[np.lexsort((tb, -chosen))[: headline.n_flagged]] = True
    captured = features.loc[mask].loc[flagged & y]
    tables["captured_exclusion_themes"] = (
        captured.groupby("window_exclusion_theme", dropna=False)
        .size()
        .rename("n_captured")
        .reset_index()
        .sort_values("n_captured", ascending=False)
    )

    summary = {
        "design": split.describe(),
        "headline_k": k,
        "selected_score": selected,
        "headline": headline.as_dict(),
        "headline_ci95": [lo, hi],
        "bootstrap_reps": ocfg.bootstrap_reps,
        "test_by_score": test_by_score,
        "unadjusted_headline": test_by_score.get("unadjusted", {}),
        "discrimination": discrimination(chosen, y),
        "discrimination_unadjusted": discrimination(candidates["unadjusted"].to_numpy()[mask], y),
        "events_total": int(y.sum()),
        "median_days_to_exclusion_captured": float(captured["days_to_window_exclusion"].median())
        if len(captured)
        else None,
    }
    return summary, tables


def run_model(wh, cfg: PipelineConfig, ocfg: OutlierConfig, dirs: OutputDirs) -> dict:
    is_synthetic = is_synthetic_warehouse(wh)
    features = wh.read("marts", "mart_outlier_features")
    log.info("Loaded %s cohort prescribers from mart_outlier_features", f"{len(features):,}")
    tiebreak = features["npi"].astype(str).to_numpy()

    # 1. Peer adjustment and the equal-weight score. No outcome columns go in.
    outcome_cols = [c for c in features.columns if "exclu" in c]
    result = score_prescribers(features.drop(columns=outcome_cols), ocfg)
    z = result.adjustment.z.clip(lower=0.0, upper=ocfg.z_cap)

    # 2. Learn weights on development-window exclusions only.
    split = temporal_split(features, ocfg.split_date)
    log.info("Temporal split: %s", split.describe())
    learned = fit_nonnegative_logistic(z, split.dev_y, ocfg.l2_penalty)
    candidates = {
        "learned_weights": weighted_score(z, learned.weights),
        "equal_weights": result.scores["outlier_score"],
        "unadjusted": result.scores["unadjusted_score"],
    }

    # 3. Choose between the two peer-adjusted candidates on the dev window.
    dev_metrics = {
        name: _metrics(score.to_numpy(), split.dev_y, ocfg.headline_k, tiebreak)
        for name, score in candidates.items()
    }
    selected = max(
        ("learned_weights", "equal_weights"),
        key=lambda name: dev_metrics[name][ocfg.selection_metric],
    )
    log.info("Selected %s on development %s", selected, ocfg.selection_metric)

    # 4. Final scores written back for the post-ML dbt models.
    final = candidates[selected]
    weights = learned.weights if selected == "learned_weights" else {c: 1.0 for c in z.columns}
    contributions = z.mul(pd.Series(weights), axis=1)
    scores = result.scores.copy()
    scores["equal_weight_score"] = candidates["equal_weights"]
    scores["learned_weight_score"] = candidates["learned_weights"]
    scores["outlier_score"] = final
    scores["outlier_percentile"] = 100 * final.rank(pct=True, method="max")
    scores["is_top_1pct"] = top_k_flags(final, 0.01, scores["npi"])
    scores["top_feature"] = contributions.idxmax(axis=1)
    raw_z = result.adjustment.z
    scores["top_feature_z"] = [
        raw_z.at[i, f] for i, f in zip(scores.index, scores["top_feature"], strict=True)
    ]
    scores["selected_score"] = selected
    scores["is_synthetic"] = is_synthetic
    scores["scored_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    wh.write(scores, "ml", "outlier_scores")

    # 5. Evaluate on the held-out test window.
    lift_summary, tables = evaluate_score(
        features, candidates, selected, split, result.adjustment.z, ocfg, tiebreak
    )
    lift_summary["selection_metric"] = ocfg.selection_metric
    lift_summary["dev_by_score"] = dev_metrics
    tables["learned_weights"] = learned.table()
    tables["score_selection"] = pd.DataFrame(
        [
            {"score": name, **{f"dev_{k}": v for k, v in m.items()}}
            for name, m in dev_metrics.items()
        ]
    )

    # 6. Brand-prescribing regression (robustness check on the SQL headline).
    brand = wh.read("marts", "mart_brand_peer_comparison")
    controls = list(ocfg.controls)
    brand = brand.merge(features[["npi", *controls]], on="npi", how="left")
    brand_effect, brand_summary_text = fit_brand_effect(brand, controls)
    tables["brand_tier_effects"] = fit_tier_effects(brand, controls)
    tables["peer_adjustment_diagnostics"] = result.adjustment.diagnostics()

    dirs.create()
    for stale in ("feature_ablation.csv",):
        (dirs.results / stale).unlink(missing_ok=True)
    for name, frame in tables.items():
        frame.to_csv(dirs.results / f"{name}.csv", index=False)
    (dirs.results / "brand_effect_glm_summary.txt").write_text(brand_summary_text)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target": wh.target,
        "is_synthetic": is_synthetic,
        "data_year": cfg.data_year,
        "n_cohort": len(features),
        "features_used": result.feature_names,
        "features_dropped": result.adjustment.dropped_features,
        "learned_weights": learned.as_dict(),
        "lift": lift_summary,
        "brand_effect": brand_effect.as_dict(),
    }
    write_json(summary, dirs.results / "model_summary.json")
    log.info("Model artifacts written to %s", dirs.results)
    return summary
