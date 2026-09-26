"""End-to-end run on a synthetic DuckDB warehouse: load -> dbt -> model -> results.

Slow (~1 min); run with `pytest -m integration`. Requires the dbt extra.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from partd_risk.config import REPO_ROOT, load_config, load_outlier_config

pytestmark = pytest.mark.integration


def _dbt(args: list[str], duckdb_path: Path, target_dir: Path) -> None:
    dbt = shutil.which("dbt")
    if dbt is None:
        pytest.skip("dbt not installed")
    env = {
        **os.environ,
        "DBT_TARGET": "duckdb",
        "DUCKDB_PATH": str(duckdb_path),
        "DBT_PROFILES_DIR": str(REPO_ROOT / "dbt"),
    }
    cmd = [dbt, *args, "--target-path", str(target_dir), "--no-partial-parse"]
    proc = subprocess.run(cmd, cwd=REPO_ROOT / "dbt", env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout[-4000:] + proc.stderr[-2000:]


def test_full_pipeline_on_synthetic_data(tmp_path):
    from partd_risk.ingest.load import load_duckdb
    from partd_risk.pipeline import output_dirs, run_model
    from partd_risk.reporting.headline import SyntheticDataError, build_headline
    from partd_risk.reporting.tableau import export_extracts
    from partd_risk.synthetic import write_synthetic_parquet
    from partd_risk.warehouse import get_warehouse

    cfg = load_config()
    db = tmp_path / "partd_risk_synthetic.duckdb"
    files = write_synthetic_parquet(cfg, tmp_path / "parquet", n_prescribers=4000, seed=21)
    load_duckdb(cfg, files, db, synthetic=True)

    if not (REPO_ROOT / "dbt" / "dbt_packages" / "dbt_utils").exists():
        _dbt(["deps"], db, tmp_path / "target")
    _dbt(["build", "--exclude", "tag:post_ml"], db, tmp_path / "target")

    wh = get_warehouse("duckdb", cfg, db)
    dirs = output_dirs(cfg, True, tmp_path / "out").create()
    summary = run_model(wh, cfg, load_outlier_config(), dirs)
    assert summary["is_synthetic"] is True
    assert summary["lift"]["events_total"] > 0
    # The generator plants a real signal, so the score must beat chance. The top
    # 1% of a small synthetic cohort is only a few dozen people, so check the
    # stabler AUROC and top-10% lift rather than the headline k.
    assert summary["lift"]["discrimination_unadjusted"]["auroc"] > 0.55
    design = summary["lift"]["design"]
    assert design["dev_events"] > 0 and design["test_events"] > 0
    assert summary["lift"]["selected_score"] in {"learned_weights", "equal_weights"}
    assert all(w >= 0 for w in summary["learned_weights"]["weights"].values())
    curve = pd.read_csv(dirs.results / "lift_curve.csv")
    top10 = curve[(curve["score"] == "equal_weights") & (curve["k"].round(4) == 0.1)]
    assert top10["lift"].iloc[0] > 1.5
    assert summary["brand_effect"]["rate_ratio"] > 1

    _dbt(["build", "--select", "tag:post_ml"], db, tmp_path / "target")

    with pytest.raises(SyntheticDataError):
        build_headline(wh, summary)
    headline, extras = build_headline(wh, summary, allow_synthetic=True)
    assert all("SYNTHETIC" in b for b in headline.bullets)

    from partd_risk.reporting import figures
    from partd_risk.reporting.memo import render_memo

    tiers = wh.read("reporting", "rpt_brand_by_payment_tier")
    by_drug = wh.read("reporting", "rpt_savings_by_drug")
    figs = {
        "dose_response": figures.brand_dose_response(tiers, dirs.figures / "a.png", "SYNTHETIC"),
        "savings": figures.savings_by_drug(by_drug, dirs.figures / "b.png", watermark="SYNTHETIC"),
        "gains": figures.cumulative_gains(
            pd.read_csv(dirs.results / "lift_curve.csv"),
            0.01,
            dirs.figures / "c.png",
            "SYNTHETIC",
            selected=summary["lift"]["selected_score"],
        ),
    }
    assert all(p.stat().st_size > 10_000 for p in figs.values())
    memo = render_memo(
        headline, tiers, by_drug, extras["sensitivity"], {k: p.name for k, p in figs.items()},
        dirs.memo / "memo.md",
    )  # fmt: skip
    text = memo.read_text()
    assert text.startswith("> **SYNTHETIC")
    assert "Bottom line" in text and "{{" not in text

    written = export_extracts(wh, dirs.tableau, dirs.results)
    names = {p.name for p in written}
    assert {"brand_comparison.csv", "outlier_by_segment.csv", "model_lift_curve.csv"} <= names
    for path in written:
        header = path.read_text().splitlines()[0]
        assert "npi" not in header.split(","), f"{path.name} leaks NPIs"
        extract = pd.read_csv(path)
        if "n_prescribers" in extract and path.stem != "cohort_flow":
            assert (extract["n_prescribers"] >= 11).all(), f"{path.name} has small cells"
    json.loads((dirs.results / "model_summary.json").read_text())
