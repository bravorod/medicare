"""Render the plain-language stakeholder memo from the headline metrics."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from partd_risk.config import REPO_ROOT
from partd_risk.reporting.headline import (
    SYNTHETIC_LABEL,
    Headline,
    fmt_lift,
    fmt_records,
    fmt_savings,
)

log = logging.getLogger(__name__)

TEMPLATE_DIR = REPO_ROOT / "reports" / "memo"
TEMPLATE_NAME = "memo_template.md.j2"


def _money(value: float) -> str:
    if value is None:
        return "n/a"
    return fmt_savings(value / 1e6)


def _headline_drugs(by_drug: pd.DataFrame) -> pd.DataFrame:
    if "is_single_brand_equivalent" not in by_drug:
        return by_drug
    return by_drug[by_drug["is_single_brand_equivalent"].astype(bool)]


def render_memo(
    headline: Headline,
    tiers: pd.DataFrame,
    top_drugs: pd.DataFrame,
    sensitivity: pd.DataFrame,
    figures: dict[str, str],
    dest: Path,
) -> Path:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["money"] = _money
    env.filters["pct"] = lambda v, d=0: "n/a" if v is None else f"{v:.{d}f}%"
    env.filters["signed"] = lambda v: "n/a" if v is None else f"{v:+.0f}%"
    env.filters["abs_pct"] = lambda v: "n/a" if v is None else f"{abs(v):.0f}%"
    env.filters["share"] = lambda v, d=0: "n/a" if v is None else f"{100 * v:.{d}f}%"
    env.filters["lift"] = lambda v: "n/a" if v is None else fmt_lift(v)
    env.filters["records"] = fmt_records
    env.filters["thousands"] = lambda v: "n/a" if v is None else f"{v:,.0f}"
    text = env.get_template(TEMPLATE_NAME).render(
        m=headline.metrics,
        bullets=headline.bullets,
        is_synthetic=headline.is_synthetic,
        synthetic_label=SYNTHETIC_LABEL,
        tiers=tiers[tiers["dimension"] == "payment_tier"]
        .sort_values("dimension_value")
        .to_dict(orient="records"),
        profiles=tiers[tiers["dimension"] == "payment_profile"]
        .sort_values("dimension_value")
        .to_dict(orient="records"),
        top_drugs=_headline_drugs(top_drugs)
        .sort_values("estimated_savings_usd", ascending=False)
        .head(10)
        .to_dict(orient="records"),
        sensitivity=sensitivity.to_dict(orient="records"),
        conservative=sensitivity[~sensitivity["scenario"].str.startswith("Upper bound")].to_dict(
            orient="records"
        ),
        figures=figures,
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text)
    log.info("Wrote memo to %s", dest)
    return dest
