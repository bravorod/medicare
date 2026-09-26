"""Write the de-identified CSV extracts the Tableau workbook is built on.

Only aggregated reporting tables leave the warehouse. The optional
prescriber-level extract drops NPIs and names and replaces the NPI with a
salted hash so the dashboard can show distributions (scatter plots,
histograms) without identifying anyone.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

AGGREGATE_EXTRACTS = {
    # extract file name: (warehouse layer, model)
    "brand_comparison": ("reporting", "rpt_brand_comparison"),
    "brand_by_payment_tier": ("reporting", "rpt_brand_by_payment_tier"),
    "savings_summary": ("reporting", "rpt_savings_summary"),
    "savings_by_drug": ("reporting", "rpt_savings_by_drug"),
    "specialty_summary": ("reporting", "rpt_specialty_summary"),
    "state_summary": ("reporting", "rpt_state_summary"),
    "cohort_flow": ("reporting", "rpt_cohort_flow"),
    "exclusion_outcomes": ("reporting", "rpt_exclusion_outcomes"),
    "outlier_by_segment": ("reporting", "rpt_outlier_by_segment"),
    "top_feature_mix": ("reporting", "rpt_top_feature_mix"),
    "drug_matched_prescribing": ("marts", "mart_drug_matched_prescribing"),
}

# Same convention CMS uses in the Part D files: no published cell describes
# fewer than 11 prescribers. The cohort flow is exempt (it counts records
# removed by a rule, not people in a segment).
SMALL_CELL_THRESHOLD = 11
SMALL_CELL_EXEMPT = {"cohort_flow"}

PRESCRIBER_COLUMNS = [
    "prescriber_specialty",
    "prescriber_state",
    "census_region",
    "is_industry_paid",
    "payment_tier",
    "total_payment_usd",
    "drug_detail_fills",
    "brand_fill_share",
    "multisource_brand_share",
    "cost_per_fill",
    "opioid_claim_share",
    "outlier_score",
    "outlier_percentile",
    "is_top_1pct",
    "top_feature",
    "excluded_in_window",
]


def pseudonym(npi: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{npi}".encode()).hexdigest()[:12]


def suppress_small_cells(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    """Drop aggregate rows that describe fewer than 11 prescribers."""
    if name in SMALL_CELL_EXEMPT or "n_prescribers" not in frame:
        return frame
    keep = frame["n_prescribers"].fillna(0) >= SMALL_CELL_THRESHOLD
    if (~keep).any():
        log.info(
            "%s: suppressed %d rows with < %d prescribers",
            name,
            (~keep).sum(),
            SMALL_CELL_THRESHOLD,
        )
    return frame.loc[keep]


def export_extracts(
    wh,
    dest: Path,
    model_results_dir: Path | None = None,
    include_prescriber_level: bool = False,
) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    written = []
    for name, (layer, model) in AGGREGATE_EXTRACTS.items():
        try:
            frame = wh.read(layer, model)
        except Exception as exc:
            log.warning("Skipping %s (%s): %s", name, model, exc)
            continue
        frame = suppress_small_cells(frame, name)
        path = dest / f"{name}.csv"
        frame.to_csv(path, index=False)
        written.append(path)

    if model_results_dir is not None:
        for name in (
            "lift_curve",
            "brand_tier_effects",
            "single_feature_lift",
            "learned_weights",
            "score_selection",
        ):
            src = model_results_dir / f"{name}.csv"
            if src.exists():
                path = dest / f"model_{name}.csv"
                pd.read_csv(src).to_csv(path, index=False)
                written.append(path)

    if include_prescriber_level:
        salt = os.environ.get("TABLEAU_PSEUDONYM_SALT")
        if not salt:
            raise RuntimeError("Set TABLEAU_PSEUDONYM_SALT to export prescriber-level rows")
        frame = wh.read("marts", "fct_prescriber_risk", ["npi", *PRESCRIBER_COLUMNS])
        frame.insert(0, "prescriber_key", [pseudonym(str(n), salt) for n in frame.pop("npi")])
        path = dest / "prescribers_deidentified.csv"
        frame.to_csv(path, index=False)
        written.append(path)

    log.info("Wrote %d Tableau extracts to %s", len(written), dest)
    return written
