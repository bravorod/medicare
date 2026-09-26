from __future__ import annotations

import pandas as pd
import pytest

from partd_risk.reporting.headline import (
    README_END,
    README_START,
    SyntheticDataError,
    build_headline,
    bullets_markdown,
    fmt_lift,
    fmt_pct,
    fmt_records,
    fmt_savings,
    savings_sensitivity,
    update_readme,
)


class FakeWarehouse:
    target = "fake"

    def __init__(self, synthetic: bool):
        self.tables = {
            "rpt_data_provenance": pd.DataFrame({"is_synthetic": [synthetic, synthetic]}),
            "rpt_source_row_counts": pd.DataFrame(
                {"raw_table": ["a", "b"], "row_count": [45_000_000, 2_700_000]}
            ),
            "rpt_brand_comparison": pd.DataFrame(
                {
                    "payment_group": ["industry_paid", "not_industry_paid"],
                    "n_prescribers": [400, 600],
                    "pct_of_cohort": [40.0, 60.0],
                    "pct_more_brand_fills_peer_adjusted": [17.6, 0.0],
                    "pct_more_brand_fills_crude": [25.0, 0.0],
                    "pct_more_multisource_brand_fills_peer_adjusted": [30.0, 0.0],
                    "crude_brand_share": [0.3, 0.24],
                }
            ),
            "rpt_savings_summary": pd.DataFrame(
                {
                    "estimated_savings_usd": [123_400_000.0],
                    "estimated_savings_usd_millions": [123.4],
                    "estimated_savings_usd_millions_all_multisource": [400.0],
                    "share_of_multisource_fills": [0.5],
                    "net_excess_brand_fills": [1e6],
                    "n_drugs": [150],
                }
            ),
            "rpt_cohort_flow": pd.DataFrame(
                {"step": ["5_analysis_cohort"], "n_prescribers": [1000]}
            ),
            "mart_generic_substitution_savings": pd.DataFrame(
                {
                    "net_excess_brand_fills": [100.0, -50.0],
                    "brand_cost_per_fill": [300.0, 100.0],
                    "generic_cost_per_fill": [10.0, 90.0],
                    "is_single_brand_equivalent": [True, True],
                }
            ),
        }

    def read(self, layer, name, columns=None):
        frame = self.tables[name]
        return frame[columns] if columns else frame


MODEL_SUMMARY = {
    "data_year": 2021,
    "features_used": ["a", "b"],
    "lift": {
        "headline_k": 0.01,
        "headline": {"lift": 7.26, "events_captured": 30, "capture_share": 0.07, "precision": 0.03},
        "headline_ci95": [5.1, 9.4],
        "events_total": 410,
        "unadjusted_headline": {"lift": 4.0},
        "discrimination": {"auroc": 0.71, "average_precision": 0.02},
    },
    "brand_effect": {"pct_more": 15.2, "pct_ci_low": 12.0, "pct_ci_high": 18.5, "p_value": 1e-9},
}


def test_formatters():
    assert fmt_savings(123.4) == "$123M"
    assert fmt_savings(4.26) == "$4.3M"
    assert fmt_records(47_700_000) == "47M+"
    assert fmt_pct(17.6) == "18%"
    assert fmt_lift(7.26) == "7.3x"


def test_savings_sensitivity_reprices_premium():
    cells = FakeWarehouse(False).tables["mart_generic_substitution_savings"]
    out = savings_sensitivity(cells).set_index("scenario")["estimated_savings_usd"]
    # net excess is signed: the second drug's shortfall offsets the first
    assert out.iloc[0] == pytest.approx(100 * 290 - 50 * 10)
    # 30% rebate: premiums 200 and 0 (premium floored at 0), half realization
    assert out.iloc[-2] == pytest.approx(0.5 * (100 * 200 - 50 * 0))
    assert out.index[-1].startswith("Upper bound")


def test_savings_sensitivity_headline_excludes_pooled_drugs():
    cells = pd.DataFrame(
        {
            "net_excess_brand_fills": [10.0, 1000.0],
            "brand_cost_per_fill": [110.0, 500.0],
            "generic_cost_per_fill": [10.0, 5.0],
            "is_single_brand_equivalent": [True, False],
        }
    )
    out = savings_sensitivity(cells).set_index("scenario")["estimated_savings_usd"]
    assert out.iloc[0] == pytest.approx(10 * 100)
    assert out.iloc[-1] == pytest.approx(10 * 100 + 1000 * 495)


def test_build_headline_fills_every_placeholder():
    headline, _ = build_headline(FakeWarehouse(False), MODEL_SUMMARY)
    assert list(headline.placeholders.values()) == ["$123M", "47M+", "18%", "7.3x"]
    assert "Estimated $123M in Medicare savings" in headline.bullets[0]
    assert "over 47M+ Part D" in headline.bullets[0]
    assert "wrote 18% more brand-name fills" in headline.bullets[0]
    assert "captured 7.3x the expected share" in headline.bullets[1]
    assert "[X]" not in " ".join(headline.bullets)
    assert "SYNTHETIC" not in bullets_markdown(headline)


def test_synthetic_warehouse_is_refused_then_watermarked():
    with pytest.raises(SyntheticDataError):
        build_headline(FakeWarehouse(True), MODEL_SUMMARY)
    headline, _ = build_headline(FakeWarehouse(True), MODEL_SUMMARY, allow_synthetic=True)
    assert headline.is_synthetic
    assert all("SYNTHETIC" in b for b in headline.bullets)
    assert all("SYNTHETIC" in v for v in headline.placeholders.values())


def test_update_readme_replaces_marked_block_only(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(f"intro\n{README_START}\nold\n{README_END}\noutro\n")
    headline, _ = build_headline(FakeWarehouse(False), MODEL_SUMMARY)
    assert update_readme(readme, headline)
    text = readme.read_text()
    assert text.startswith("intro\n") and text.endswith("outro\n")
    assert "old" not in text and "**$123M**" in text and "**7.3x**" in text


def test_update_readme_refuses_synthetic(tmp_path):
    readme = tmp_path / "README.md"
    original = f"{README_START}\nold\n{README_END}\n"
    readme.write_text(original)
    headline, _ = build_headline(FakeWarehouse(True), MODEL_SUMMARY, allow_synthetic=True)
    assert not update_readme(readme, headline)
    assert readme.read_text() == original
