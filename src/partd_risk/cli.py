"""Command-line entry point: ``partd-risk <command>``.

Typical production run (see docs/runbook_bigquery.md):

    partd-risk download
    partd-risk stage
    partd-risk load --target bigquery
    (cd dbt && dbt build --exclude tag:post_ml)
    partd-risk model --target bigquery
    (cd dbt && dbt build --select tag:post_ml)
    partd-risk results --target bigquery --update-readme
    partd-risk export-tableau --target bigquery
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated

import typer

from partd_risk.config import REPO_ROOT, load_config, load_outlier_config

app = typer.Typer(
    help="Medicare Part D prescribing risk analysis pipeline.",
    no_args_is_help=True,
    add_completion=False,
)

TargetOpt = Annotated[str, typer.Option("--target", "-t", help="bigquery or duckdb")]
DuckOpt = Annotated[
    Path | None, typer.Option("--duckdb-path", help="DuckDB file (duckdb target only)")
]
SourcesOpt = Annotated[
    list[str] | None, typer.Option("--source", "-s", help="Limit to these sources (repeatable)")
]
OutOpt = Annotated[
    Path | None,
    typer.Option("--output-dir", help="Override where results/figures/memo/tableau are written"),
]


@app.callback()
def _main(verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


@app.command()
def download(sources: SourcesOpt = None, force: bool = False) -> None:
    """Download raw files from CMS, Open Payments, OIG and NPPES."""
    from partd_risk.ingest.download import download_source

    cfg = load_config()
    for name in sources or list(cfg.sources):
        download_source(cfg, name, force=force)


@app.command()
def stage(sources: SourcesOpt = None) -> None:
    """Convert downloads into column-pruned, all-string Parquet files."""
    from partd_risk.ingest.stage import stage_source

    cfg = load_config()
    for name in sources or list(cfg.sources):
        stage_source(cfg, name)


@app.command()
def load(target: TargetOpt = "bigquery", duckdb_path: DuckOpt = None, sources: SourcesOpt = None):
    """Load staged Parquet into the raw schema of BigQuery or DuckDB."""
    from partd_risk.ingest.load import load_bigquery, load_duckdb, staged_files

    cfg = load_config()
    files = staged_files(cfg, sources)
    if target == "bigquery":
        counts = load_bigquery(cfg, files)
    elif target == "duckdb":
        counts = load_duckdb(cfg, files, duckdb_path)
    else:
        raise typer.BadParameter("target must be bigquery or duckdb")
    typer.echo(json.dumps(counts, indent=2))


@app.command()
def synthetic(
    duckdb_path: DuckOpt = None,
    n_prescribers: Annotated[int, typer.Option(help="Synthetic prescribers")] = 4000,
    seed: int = 7,
) -> None:
    """Build a SYNTHETIC DuckDB warehouse for tests and CI (never used for results)."""
    from partd_risk.ingest.load import load_duckdb
    from partd_risk.synthetic import write_synthetic_parquet

    cfg = load_config()
    root = REPO_ROOT / "data" / "synthetic"
    path = duckdb_path or root / "partd_risk_synthetic.duckdb"
    files = write_synthetic_parquet(cfg, root / "parquet", n_prescribers=n_prescribers, seed=seed)
    counts = load_duckdb(cfg, files, path, synthetic=True)
    typer.echo(f"Synthetic warehouse: {path}")
    typer.echo(json.dumps(counts, indent=2))


def _warehouse(target: str, duckdb_path: Path | None):
    from partd_risk.warehouse import get_warehouse

    return get_warehouse(target, load_config(), duckdb_path)


@app.command()
def model(target: TargetOpt = "bigquery", duckdb_path: DuckOpt = None, output_dir: OutOpt = None):
    """Score prescribers, evaluate against later exclusions, fit the brand regression."""
    from partd_risk.pipeline import is_synthetic_warehouse, output_dirs, run_model

    cfg = load_config()
    wh = _warehouse(target, duckdb_path)
    dirs = output_dirs(cfg, is_synthetic_warehouse(wh), output_dir)
    summary = run_model(wh, cfg, load_outlier_config(), dirs)
    lift = summary["lift"].get("headline", {}).get("lift", float("nan"))
    flag = "  [SYNTHETIC]" if summary["is_synthetic"] else ""
    typer.echo(f"Scored {summary['n_cohort']:,} prescribers; top-1% lift = {lift:.2f}x{flag}")


@app.command()
def results(
    target: TargetOpt = "bigquery",
    duckdb_path: DuckOpt = None,
    output_dir: OutOpt = None,
    update_readme: Annotated[
        bool, typer.Option("--update-readme", help="Write the results table into README.md")
    ] = False,
    allow_synthetic: Annotated[
        bool, typer.Option("--allow-synthetic", help="Smoke-test on synthetic data (watermarked)")
    ] = False,
) -> None:
    """Compute headline metrics, fill the placeholders, render figures and the memo."""
    import pandas as pd

    from partd_risk.pipeline import is_synthetic_warehouse, output_dirs, write_json
    from partd_risk.reporting import figures
    from partd_risk.reporting.headline import (
        SYNTHETIC_LABEL,
        SyntheticDataError,
        build_headline,
        bullets_markdown,
    )
    from partd_risk.reporting.headline import update_readme as write_readme
    from partd_risk.reporting.memo import render_memo

    cfg = load_config()
    wh = _warehouse(target, duckdb_path)
    synthetic_wh = is_synthetic_warehouse(wh)
    dirs = output_dirs(cfg, synthetic_wh, output_dir).create()
    summary_path = dirs.results / "model_summary.json"
    if not summary_path.exists():
        raise typer.BadParameter(f"{summary_path} not found; run `partd-risk model` first")
    model_summary = json.loads(summary_path.read_text())

    try:
        headline, extras = build_headline(wh, model_summary, allow_synthetic=allow_synthetic)
    except SyntheticDataError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc

    write_json(headline.metrics, dirs.results / "headline_metrics.json")
    extras["sensitivity"].to_csv(dirs.results / "savings_sensitivity.csv", index=False)
    (dirs.results / "resume_bullets.md").write_text(bullets_markdown(headline))

    watermark = SYNTHETIC_LABEL if headline.is_synthetic else None
    tiers = wh.read("reporting", "rpt_brand_by_payment_tier")
    by_drug = wh.read("reporting", "rpt_savings_by_drug")
    figs = {
        "dose_response": figures.brand_dose_response(
            tiers, dirs.figures / "brand_fills_by_payment_tier.png", watermark
        ),
        "savings": figures.savings_by_drug(
            by_drug, dirs.figures / "savings_by_drug.png", watermark=watermark
        ),
    }
    lift_path = dirs.results / "lift_curve.csv"
    if lift_path.exists():
        design = model_summary["lift"].get("design", {})
        figs["gains"] = figures.cumulative_gains(
            pd.read_csv(lift_path),
            model_summary["lift"]["headline_k"],
            dirs.figures / "exclusion_capture.png",
            watermark,
            selected=model_summary["lift"].get("selected_score", "learned_weights"),
            test_label=f"exclusions {design.get('split_date', '')[:7]} to "
            f"{(design.get('test_window_end') or '')[:7]}",
        )
    memo_path = dirs.memo / "memo.md"
    # memo/ and figures/ are siblings in every output layout.
    rel = {k: Path("..", "figures", v.name).as_posix() for k, v in figs.items()}
    render_memo(headline, tiers, by_drug, extras["sensitivity"], rel, memo_path)

    if update_readme:
        write_readme(REPO_ROOT / "README.md", headline)

    typer.echo("")
    for key, value in headline.placeholders.items():
        typer.echo(f"  {key:<34} {value}")
    typer.echo("")
    for bullet in headline.bullets:
        typer.echo(f"  - {bullet}")
    typer.echo(f"\nWritten to {dirs.results}")


@app.command("export-tableau")
def export_tableau(
    target: TargetOpt = "bigquery",
    duckdb_path: DuckOpt = None,
    output_dir: OutOpt = None,
    prescriber_level: Annotated[
        bool, typer.Option(help="Also export de-identified prescriber rows (needs a salt)")
    ] = False,
) -> None:
    """Write de-identified CSV extracts for the Tableau dashboard."""
    from partd_risk.pipeline import is_synthetic_warehouse, output_dirs
    from partd_risk.reporting.tableau import export_extracts

    cfg = load_config()
    wh = _warehouse(target, duckdb_path)
    dirs = output_dirs(cfg, is_synthetic_warehouse(wh), output_dir).create()
    export_extracts(wh, dirs.tableau, dirs.results, include_prescriber_level=prescriber_level)


@app.command("data-dictionary")
def data_dictionary(
    dest: Annotated[Path, typer.Option(help="Markdown file to write")] = REPO_ROOT
    / "docs"
    / "data_dictionary.md",
) -> None:
    """Regenerate docs/data_dictionary.md from the dbt model YAML."""
    from partd_risk.reporting.dictionary import write_data_dictionary

    write_data_dictionary(REPO_ROOT / "dbt" / "models", dest)
    typer.echo(f"Wrote {dest}")


if __name__ == "__main__":  # pragma: no cover
    app()
