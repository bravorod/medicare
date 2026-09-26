"""Load staged Parquet files into the raw schema of BigQuery or DuckDB.

Both targets get the same raw tables plus a ``load_provenance`` table that
records where every table came from. The provenance table is what the results
step checks before it will print any headline number (see
``partd_risk.reporting.headline``).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

from partd_risk.config import PipelineConfig
from partd_risk.ingest.download import read_manifest

log = logging.getLogger(__name__)

PROVENANCE_TABLE = "load_provenance"


def provenance_frame(
    cfg: PipelineConfig, row_counts: dict[str, int], synthetic: bool
) -> pd.DataFrame:
    manifest = {} if synthetic else read_manifest(cfg.downloads_dir)
    loaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = []
    for name, count in row_counts.items():
        rec = manifest.get(name)
        rows.append(
            {
                "source_name": name,
                "raw_table": cfg.source(name).raw_table,
                "row_count": int(count),
                "source_url": rec.url if rec else None,
                "sha256": rec.sha256 if rec else None,
                "downloaded_at": rec.downloaded_at if rec else None,
                "loaded_at": loaded_at,
                "data_year": cfg.data_year,
                "is_synthetic": synthetic,
            }
        )
    return pd.DataFrame(rows)


def load_duckdb(
    cfg: PipelineConfig,
    parquet_files: dict[str, Path],
    db_path: Path | None = None,
    synthetic: bool = False,
) -> dict[str, int]:
    db_path = Path(db_path or cfg.duckdb_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    with duckdb.connect(str(db_path)) as con:
        con.execute(f"create schema if not exists {cfg.raw_schema}")
        for name, path in parquet_files.items():
            table = f"{cfg.raw_schema}.{cfg.source(name).raw_table}"
            con.execute(
                f"create or replace table {table} as select * from read_parquet(?)", [str(path)]
            )
            counts[name] = con.execute(f"select count(*) from {table}").fetchone()[0]
            log.info("Loaded %s rows into %s:%s", f"{counts[name]:,}", db_path.name, table)
        con.register("provenance", provenance_frame(cfg, counts, synthetic))
        con.execute(
            f"create or replace table {cfg.raw_schema}.{PROVENANCE_TABLE} "
            "as select * from provenance"
        )
    return counts


def load_bigquery(
    cfg: PipelineConfig, parquet_files: dict[str, Path], synthetic: bool = False
) -> dict[str, int]:
    try:
        from google.cloud import bigquery
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Install the BigQuery extra: pip install -e '.[bigquery]'") from exc

    if not cfg.bigquery_project:
        raise RuntimeError("Set GCP_PROJECT (see .env.example) before loading to BigQuery")

    client = bigquery.Client(project=cfg.bigquery_project, location=cfg.bigquery_location)
    dataset_id = f"{cfg.bigquery_project}.{cfg.raw_schema}"
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = cfg.bigquery_location
    dataset.description = (
        "Raw CMS / OIG / NPPES extracts (all STRING columns). Loaded by partd-risk."
    )
    client.create_dataset(dataset, exists_ok=True)

    counts: dict[str, int] = {}
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    for name, path in parquet_files.items():
        table_id = f"{dataset_id}.{cfg.source(name).raw_table}"
        log.info("Uploading %s (%.1f MB) -> %s", path.name, path.stat().st_size / 1e6, table_id)
        with path.open("rb") as fh:
            job = client.load_table_from_file(fh, table_id, job_config=job_config)
        job.result()
        counts[name] = client.get_table(table_id).num_rows
        log.info("Loaded %s rows into %s", f"{counts[name]:,}", table_id)

    prov = provenance_frame(cfg, counts, synthetic)
    client.load_table_from_dataframe(
        prov,
        f"{dataset_id}.{PROVENANCE_TABLE}",
        job_config=bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
        ),
    ).result()
    return counts


def staged_files(cfg: PipelineConfig, names: list[str] | None = None) -> dict[str, Path]:
    files = {}
    for name in names or list(cfg.sources):
        path = cfg.parquet_dir / f"{cfg.source(name).raw_table}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"{path} not found; run `partd-risk stage` first")
        files[name] = path
    return files
