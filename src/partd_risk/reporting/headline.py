"""Assemble the headline metrics that fill the project's placeholders.

Every number in the README, the memo and the resume bullets comes from here,
and every one of them is traceable to a dbt model or a model artifact (see
docs/results_placeholders.md). If the warehouse was loaded with synthetic data
the numbers are refused unless ``allow_synthetic`` is set, and are then
labelled SYNTHETIC everywhere they appear.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

SYNTHETIC_LABEL = "SYNTHETIC - NOT A FINDING"

BULLET_TEMPLATE = [
    "Estimated {savings} in Medicare savings by building a BigQuery and dbt pipeline over "
    "{records} Part D, Open Payments, and provider records, finding industry-paid prescribers "
    "wrote {pct_more} more brand-name fills than peers.",
    "Built a peer-adjusted outlier score with regression in Python whose top 1% captured "
    "{lift} the expected share of later Medicare exclusions, presenting findings in a Tableau "
    "dashboard and memo for non-technical readers.",
]

SAVINGS_SCENARIOS = [
    # (label, brand rebate haircut, share of excess fills actually switched)
    ("Headline: gross cost, full substitution", 0.00, 1.00),
    ("Gross cost, half of excess fills switched", 0.00, 0.50),
    ("Brand cost net of 15% rebates, full substitution", 0.15, 1.00),
    ("Brand cost net of 30% rebates, full substitution", 0.30, 1.00),
    ("Brand cost net of 30% rebates, half switched", 0.30, 0.50),
]


class SyntheticDataError(RuntimeError):
    """Raised when headline numbers are requested from a synthetic warehouse."""


def fmt_savings(usd_millions: float) -> str:
    return f"${usd_millions:,.0f}M" if usd_millions >= 10 else f"${usd_millions:,.1f}M"


def fmt_records(records: int) -> str:
    return f"{math.floor(records / 1e6):,}M+"


def fmt_pct(pct: float) -> str:
    return f"{pct:.0f}%"


def fmt_lift(lift: float) -> str:
    return f"{lift:.1f}x"


def savings_sensitivity(cells: pd.DataFrame) -> pd.DataFrame:
    """Re-price the net excess brand fills under rebate / realization scenarios.

    Scenarios run on the headline set (single brand product per generic name).
    A final row prices every multi-source drug, which pools dosage forms under
    one generic name and so over-states the brand premium (upper bound).
    """
    everything = cells
    if "is_single_brand_equivalent" in cells:
        cells = cells[cells["is_single_brand_equivalent"].astype(bool)]
    rows = []
    for label, rebate, realization in SAVINGS_SCENARIOS:
        premium = (
            cells["brand_cost_per_fill"] * (1 - rebate) - cells["generic_cost_per_fill"]
        ).clip(lower=0)
        usd = float((cells["net_excess_brand_fills"] * realization * premium).sum())
        rows.append(
            {
                "scenario": label,
                "brand_rebate_haircut": rebate,
                "substitution_realization": realization,
                "estimated_savings_usd": usd,
                "estimated_savings_usd_millions": usd / 1e6,
            }
        )
    premium = (everything["brand_cost_per_fill"] - everything["generic_cost_per_fill"]).clip(
        lower=0
    )
    usd = float((everything["net_excess_brand_fills"] * premium).sum())
    rows.append(
        {
            "scenario": "Upper bound: all multi-source drugs (dosage forms pooled)",
            "brand_rebate_haircut": 0.0,
            "substitution_realization": 1.0,
            "estimated_savings_usd": usd,
            "estimated_savings_usd_millions": usd / 1e6,
        }
    )
    return pd.DataFrame(rows)


@dataclass
class Headline:
    metrics: dict
    placeholders: dict[str, str]
    bullets: list[str]
    is_synthetic: bool


def build_headline(wh, model_summary: dict, allow_synthetic: bool = False) -> tuple[Headline, dict]:
    prov = wh.read("reporting", "rpt_data_provenance")
    is_synthetic = bool(prov["is_synthetic"].astype(bool).any())
    if is_synthetic and not allow_synthetic:
        raise SyntheticDataError(
            "The warehouse was loaded with SYNTHETIC data. Headline numbers are only produced "
            "from real CMS/OIG/NPPES loads. Pass --allow-synthetic to smoke-test the reporting "
            "code (output is watermarked and written outside reports/)."
        )

    row_counts = wh.read("reporting", "rpt_source_row_counts")
    brand = wh.read("reporting", "rpt_brand_comparison").set_index("payment_group")
    savings = wh.read("reporting", "rpt_savings_summary").iloc[0]
    flow = wh.read("reporting", "rpt_cohort_flow").sort_values("step")
    cells = wh.read("marts", "mart_generic_substitution_savings")
    sensitivity = savings_sensitivity(cells)

    records = int(row_counts["row_count"].sum())
    paid = brand.loc["industry_paid"]
    unpaid = brand.loc["not_industry_paid"]
    lift = model_summary.get("lift", {})
    headline_lift = lift.get("headline", {})
    effect = model_summary.get("brand_effect", {})

    metrics = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "is_synthetic": is_synthetic,
        "target": wh.target,
        "data_year": model_summary.get("data_year"),
        "records": {
            "total_raw_records": records,
            "total_raw_records_millions": records / 1e6,
            "by_source": dict(
                zip(row_counts["raw_table"], row_counts["row_count"].astype(int), strict=True)
            ),
        },
        "cohort": {
            "n_prescribers": int(paid["n_prescribers"] + unpaid["n_prescribers"]),
            "n_industry_paid": int(paid["n_prescribers"]),
            "share_industry_paid": float(paid["pct_of_cohort"]) / 100,
            "flow": flow[["step", "n_prescribers"]].to_dict(orient="records"),
        },
        "brand_prescribing": {
            "pct_more_brand_fills_peer_adjusted": float(paid["pct_more_brand_fills_peer_adjusted"]),
            "pct_more_brand_fills_crude": float(paid["pct_more_brand_fills_crude"]),
            "pct_more_multisource_brand_fills_peer_adjusted": float(
                paid["pct_more_multisource_brand_fills_peer_adjusted"]
            ),
            "brand_share_paid": float(paid["crude_brand_share"]),
            "brand_share_unpaid": float(unpaid["crude_brand_share"]),
            "regression_pct_more": effect.get("pct_more"),
            "regression_pct_ci95": [effect.get("pct_ci_low"), effect.get("pct_ci_high")],
            "regression_p_value": effect.get("p_value"),
        },
        "savings": {
            "estimated_savings_usd": float(savings["estimated_savings_usd"]),
            "estimated_savings_usd_millions": float(savings["estimated_savings_usd_millions"]),
            "net_excess_brand_fills": float(savings["net_excess_brand_fills"]),
            "n_drugs": int(savings["n_drugs"]),
            "estimated_savings_usd_millions_all_multisource": float(
                savings["estimated_savings_usd_millions_all_multisource"]
            ),
            "share_of_multisource_fills": float(savings["share_of_multisource_fills"]),
            "sensitivity": sensitivity.to_dict(orient="records"),
        },
        "outlier_score": {
            "headline_k": lift.get("headline_k"),
            "lift": headline_lift.get("lift"),
            "lift_ci95": lift.get("headline_ci95"),
            "events_captured": headline_lift.get("events_captured"),
            "events_total": lift.get("events_total"),
            "capture_share": headline_lift.get("capture_share"),
            "precision": headline_lift.get("precision"),
            "base_rate": headline_lift.get("base_rate"),
            "unadjusted_lift": lift.get("unadjusted_headline", {}).get("lift"),
            "equal_weights_lift": lift.get("test_by_score", {})
            .get("equal_weights", {})
            .get("lift"),
            "learned_weights_lift": lift.get("test_by_score", {})
            .get("learned_weights", {})
            .get("lift"),
            "selected_score": lift.get("selected_score"),
            "selection_metric": lift.get("selection_metric"),
            "design": lift.get("design", {}),
            "learned_weights": model_summary.get("learned_weights", {}).get("weights", {}),
            "auroc": lift.get("discrimination", {}).get("auroc"),
            "average_precision": lift.get("discrimination", {}).get("average_precision"),
            "features_used": model_summary.get("features_used", []),
        },
    }

    placeholders = {
        "$[X]M (Medicare savings)": fmt_savings(
            metrics["savings"]["estimated_savings_usd_millions"]
        ),
        "[X]M+ (records)": fmt_records(records),
        "[X]% (more brand-name fills)": fmt_pct(
            metrics["brand_prescribing"]["pct_more_brand_fills_peer_adjusted"]
        ),
        "[X]x (top-1% exclusion capture)": fmt_lift(headline_lift["lift"])
        if headline_lift.get("lift") is not None
        else "n/a (no later exclusions)",
    }
    values = list(placeholders.values())
    bullets = [
        BULLET_TEMPLATE[0].format(savings=values[0], records=values[1], pct_more=values[2]),
        BULLET_TEMPLATE[1].format(lift=values[3]),
    ]
    if is_synthetic:
        placeholders = {k: f"{v} [{SYNTHETIC_LABEL}]" for k, v in placeholders.items()}
        bullets = [f"[{SYNTHETIC_LABEL}] {b}" for b in bullets]
    return Headline(metrics, placeholders, bullets, is_synthetic), {"sensitivity": sensitivity}


def bullets_markdown(headline: Headline) -> str:
    lines = ["# Resume bullets (filled from measured results)", ""]
    if headline.is_synthetic:
        lines += [f"> **{SYNTHETIC_LABEL}.** Generated from simulated data for testing.", ""]
    lines += [f"- {b}" for b in headline.bullets]
    lines += ["", "## Placeholder values", "", "| Placeholder | Value |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in headline.placeholders.items()]
    lines += ["", "Definitions and source models: docs/results_placeholders.md", ""]
    return "\n".join(lines)


README_START = "<!-- HEADLINE:START -->"
README_END = "<!-- HEADLINE:END -->"


def _test_window(lift: dict) -> str:
    design = lift.get("design") or {}
    start = (design.get("split_date") or "")[:4]
    end = (design.get("test_window_end") or "")[:4]
    return f"{start}-{end}" if start and end else "test-window"


def readme_table(headline: Headline) -> str:
    m = headline.metrics
    lift = m["outlier_score"]
    ci = lift.get("lift_ci95") or [None, None]
    brand = m["brand_prescribing"]
    reg_ci = brand.get("regression_pct_ci95") or [None, None]

    def ci_text(lo, hi, fmt):
        return f" (95% CI {fmt(lo)}-{fmt(hi)})" if lo is not None and hi is not None else ""

    rows = [
        (
            "Potential Part D savings (generic substitution)",
            fmt_savings(m["savings"]["estimated_savings_usd_millions"]),
            "gross drug cost; sensitivity table in the memo",
        ),
        (
            "Raw records processed",
            fmt_records(m["records"]["total_raw_records"]),
            "5 public sources",
        ),
        (
            "Brand-name fills, industry-paid vs. unpaid peers",
            f"{brand['pct_more_brand_fills_peer_adjusted']:+.0f}%",
            f"peer-adjusted; regression {brand['regression_pct_more']:+.0f}%"
            + ci_text(reg_ci[0], reg_ci[1], lambda v: f"{v:.0f}%")
            if brand.get("regression_pct_more") is not None
            else "peer-adjusted",
        ),
        (
            "Later OIG exclusions captured by top 1% of outlier scores",
            fmt_lift(lift["lift"]) if lift.get("lift") is not None else "n/a",
            f"held-out {_test_window(lift)} exclusions: "
            f"{lift.get('events_captured')} of {lift.get('events_total')}"
            + ci_text(ci[0], ci[1], lambda v: f"{v:.1f}x"),
        ),
    ]
    out = ["| Metric | Result | Notes |", "|---|---|---|"]
    out += [f"| {a} | **{b}** | {c} |" for a, b, c in rows]
    out += [
        "",
        f"_Data year {m.get('data_year')}; generated {m['generated_at'][:10]} "
        f"from `{m['target']}`. Full detail: "
        "[`reports/results/headline_metrics.json`](reports/results/headline_metrics.json), "
        "[memo](reports/memo/memo.md)._",
        "",
        '<p align="center">',
        '  <img src="reports/figures/brand_fills_by_payment_tier.png" width="49%" '
        'alt="Brand-name fills vs. unpaid peers by payment tier">',
        '  <img src="reports/figures/exclusion_capture.png" width="49%" '
        'alt="Later exclusions captured by the outlier score">',
        "</p>",
    ]
    if headline.is_synthetic:
        out.insert(0, f"> **{SYNTHETIC_LABEL}**\n")
    return "\n".join(out)


def update_readme(readme: Path, headline: Headline) -> bool:
    """Replace the block between the HEADLINE markers with the results table."""
    if headline.is_synthetic:
        log.warning("Refusing to write synthetic numbers into %s", readme)
        return False
    text = readme.read_text()
    pattern = re.compile(re.escape(README_START) + r".*?" + re.escape(README_END), re.DOTALL)
    if not pattern.search(text):
        log.warning("No %s ... %s block in %s", README_START, README_END, readme)
        return False
    block = f"{README_START}\n{readme_table(headline)}\n{README_END}"
    readme.write_text(pattern.sub(lambda _: block, text))
    log.info("Updated headline table in %s", readme)
    return True
