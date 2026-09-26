"""Static figures for the README and the stakeholder memo.

Styling follows one small system so every chart reads the same way: thin
marks, hairline grid, text in ink colors (never the series color), one color
per series in a fixed order, direct labels only where they carry the story.
Palette slots 1-2 were checked for color-vision-deficiency separation
(protan/deutan/tritan) against the light surface.
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter, PercentFormatter

log = logging.getLogger(__name__)

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834"]  # categorical slots 1-2 (validated)
REFERENCE = "#898781"


def _style(ax, title: str, subtitle: str | None = None) -> None:
    fig = ax.figure
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.tick_params(colors=INK_MUTED, labelcolor=INK_SECONDARY, length=0, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title(title, loc="left", color=INK, fontsize=12, fontweight="bold", pad=22)
    if subtitle:
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, color=INK_SECONDARY, fontsize=9)


def _save(fig, path: Path, watermark: str | None) -> Path:
    if watermark:
        fig.text(
            0.99, -0.02, watermark, ha="right", va="top", color="#d03b3b", fontsize=9,
            fontweight="bold",
        )  # fmt: skip
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    log.info("Wrote %s", path)
    return path


def brand_dose_response(tiers: pd.DataFrame, path: Path, watermark: str | None = None) -> Path:
    """Peer-adjusted brand O/E by payment tier (ordered categories, one series)."""
    d = tiers[tiers["dimension"] == "payment_tier"].sort_values("dimension_value")
    labels = [v.split(": ", 1)[-1] for v in d["dimension_value"]]
    pct = 100 * (d["brand_oe_ratio"] - 1)
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    bars = ax.bar(labels, pct, color=SERIES[0], width=0.55)
    ax.axhline(0, color=BASELINE, linewidth=1)
    for bar, value, n in zip(bars, pct, d["n_prescribers"], strict=True):
        ax.annotate(
            f"{value:+.0f}%\n",
            (bar.get_x() + bar.get_width() / 2, max(value, 0)),
            ha="center", va="bottom", color=INK, fontsize=9,
        )  # fmt: skip
        ax.annotate(
            f"n={n:,}", (bar.get_x() + bar.get_width() / 2, max(value, 0)),
            ha="center", va="bottom", color=INK_MUTED, fontsize=8,
        )  # fmt: skip
    ax.set_ylim(min(0, pct.min() * 1.25), max(pct.max(), 1) * 1.3)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:+.0f}%"))
    ax.set_xlabel("Industry general payments received in the program year", color=INK_SECONDARY)
    _style(
        ax,
        "Brand-name fills vs. unpaid peers, by payment amount",
        "Observed / expected brand fills - 1; "
        "expected from unpaid prescribers, same specialty & state",
    )
    return _save(fig, path, watermark)


SCORE_LABELS = {
    "learned_weights": "Peer-adjusted, learned weights",
    "equal_weights": "Peer-adjusted, equal weights",
    "unadjusted": "Unadjusted baseline",
}


def cumulative_gains(
    gains: pd.DataFrame,
    headline_k: float,
    path: Path,
    watermark: str | None = None,
    selected: str = "learned_weights",
    test_label: str = "held-out exclusions",
) -> Path:
    """Test-window share of exclusions captured vs share of prescribers flagged.

    Two series: the selected score and the unadjusted baseline.
    """
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    names = {
        selected: SCORE_LABELS.get(selected, selected),
        "unadjusted": SCORE_LABELS["unadjusted"],
    }
    ends = {}
    for color, (key, label) in zip(SERIES, names.items(), strict=True):
        d = gains[gains["score"] == key].sort_values("k")
        if d.empty:
            continue
        ax.plot(d["k"], d["capture_share"], color=color, linewidth=2, marker="o", markersize=4)
        ends[label] = (d.iloc[-1]["k"], d.iloc[-1]["capture_share"])
    # Direct end labels, pushed apart when the two lines finish close together.
    offsets = dict.fromkeys(ends, 0)
    if len(ends) == 2:
        (la, (_, ya)), (lb, (_, yb)) = ends.items()
        span = max(gains["capture_share"].max(), 1e-9)
        if abs(ya - yb) < 0.06 * span:
            offsets[la], offsets[lb] = (7, -7) if ya >= yb else (-7, 7)
    for label, (x, y) in ends.items():
        ax.annotate(
            label, (x, y), xytext=(6, offsets[label]),
            textcoords="offset points", va="center", color=INK_SECONDARY, fontsize=9,
        )  # fmt: skip
    top = gains["k"].max()
    diagonal = np.geomspace(gains["k"].min(), top, 50)
    ax.plot(diagonal, diagonal, color=REFERENCE, linewidth=1)
    ax.annotate(
        "Random", (top, top), xytext=(6, 0), textcoords="offset points",
        va="center", color=INK_MUTED, fontsize=9,
    )  # fmt: skip
    head = gains[(gains["score"] == selected) & (gains["k"].round(6) == round(headline_k, 6))]
    if not head.empty:
        row = head.iloc[0]
        ax.annotate(
            f"Top {headline_k:.0%}: {row['capture_share']:.1%} of held-out exclusions "
            f"({row['lift']:.1f}x)",
            (row["k"], row["capture_share"]), xytext=(-40, 70), textcoords="offset points",
            ha="left", color=INK, fontsize=9,
            arrowprops={"arrowstyle": "-", "color": INK_MUTED, "lw": 0.8},
        )  # fmt: skip
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=1))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("Share of prescribers flagged (highest scores first, log scale)")
    ax.xaxis.label.set_color(INK_SECONDARY)
    ax.set_xlim(right=top * 2.2)
    _style(
        ax,
        "Later OIG exclusions captured by the outlier score",
        f"Test set: {test_label}; weights and model choice used only earlier exclusions",
    )
    return _save(fig, path, watermark)


def savings_by_drug(
    by_drug: pd.DataFrame, path: Path, top_n: int = 12, watermark: str | None = None
) -> Path:
    """Top drugs by estimated generic-substitution savings (one series)."""
    if "is_single_brand_equivalent" in by_drug:
        by_drug = by_drug[by_drug["is_single_brand_equivalent"].astype(bool)]
    d = by_drug.sort_values("estimated_savings_usd", ascending=False).head(top_n).iloc[::-1]
    labels = [
        f"{g.title()} ({b})" if isinstance(b, str) else g.title()
        for g, b in zip(d["generic_name"], d["example_brand_name"], strict=True)
    ]
    values = d["estimated_savings_usd"] / 1e6
    fig, ax = plt.subplots(figsize=(7.2, 0.34 * len(d) + 1.4))
    bars = ax.barh(labels, values, color=SERIES[0], height=0.6)
    for bar, v in zip(bars, values, strict=True):
        ax.annotate(
            f"${v:,.1f}M", (v, bar.get_y() + bar.get_height() / 2), xytext=(4, 0),
            textcoords="offset points", va="center", color=INK, fontsize=8,
        )  # fmt: skip
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:,.0f}M"))
    _style(
        ax,
        "Where the generic-substitution savings are",
        "Net excess brand fills by industry-paid prescribers x brand premium per fill (gross cost)",
    )
    ax.grid(axis="y", visible=False)
    return _save(fig, path, watermark)
