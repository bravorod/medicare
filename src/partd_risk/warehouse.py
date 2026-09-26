"""Thin read/write layer over the two supported warehouses.

dbt writes models to ``<prefix>_<layer>`` schemas (BigQuery datasets or DuckDB
schemas); the Python steps read marts from there and write model outputs to
``<prefix>_ml`` so a second dbt pass can pick them up.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import duckdb
import pandas as pd

from partd_risk.config import PipelineConfig

log = logging.getLogger(__name__)

TARGETS = ("bigquery", "duckdb")


class Warehouse(Protocol):
    target: str

    def table(self, layer: str, name: str) -> str: ...

    def query(self, sql: str) -> pd.DataFrame: ...

    def read(self, layer: str, name: str, columns: list[str] | None = None) -> pd.DataFrame: ...

    def write(self, frame: pd.DataFrame, layer: str, name: str) -> None: ...


def _select(columns: list[str] | None) -> str:
    return ", ".join(columns) if columns else "*"


@dataclass
class DuckDBWarehouse:
    path: Path
    prefix: str
    raw_schema: str
    target: str = "duckdb"

    def table(self, layer: str, name: str) -> str:
        schema = self.raw_schema if layer == "raw" else f"{self.prefix}_{layer}"
        return f"{schema}.{name}"

    def query(self, sql: str) -> pd.DataFrame:
        with duckdb.connect(str(self.path), read_only=True) as con:
            return con.execute(sql).df()

    def read(self, layer: str, name: str, columns: list[str] | None = None) -> pd.DataFrame:
        return self.query(f"select {_select(columns)} from {self.table(layer, name)}")

    def write(self, frame: pd.DataFrame, layer: str, name: str) -> None:
        schema = f"{self.prefix}_{layer}"
        with duckdb.connect(str(self.path)) as con:
            con.execute(f"create schema if not exists {schema}")
            con.register("frame_to_write", frame)
            con.execute(f"create or replace table {schema}.{name} as select * from frame_to_write")
        log.info("Wrote %s rows to %s.%s", f"{len(frame):,}", schema, name)


@dataclass
class BigQueryWarehouse:
    project: str
    prefix: str
    raw_schema: str
    location: str = "US"
    target: str = "bigquery"

    def _client(self):
        try:
            from google.cloud import bigquery
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("Install the BigQuery extra: pip install -e '.[bigquery]'") from exc
        return bigquery.Client(project=self.project, location=self.location)

    def table(self, layer: str, name: str) -> str:
        dataset = self.raw_schema if layer == "raw" else f"{self.prefix}_{layer}"
        return f"`{self.project}.{dataset}.{name}`"

    def query(self, sql: str) -> pd.DataFrame:
        return self._client().query(sql).to_dataframe(create_bqstorage_client=True)

    def read(self, layer: str, name: str, columns: list[str] | None = None) -> pd.DataFrame:
        return self.query(f"select {_select(columns)} from {self.table(layer, name)}")

    def write(self, frame: pd.DataFrame, layer: str, name: str) -> None:
        from google.cloud import bigquery

        client = self._client()
        dataset_id = f"{self.project}.{self.prefix}_{layer}"
        dataset = bigquery.Dataset(dataset_id)
        dataset.location = self.location
        client.create_dataset(dataset, exists_ok=True)
        job = client.load_table_from_dataframe(
            frame,
            f"{dataset_id}.{name}",
            job_config=bigquery.LoadJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
            ),
        )
        job.result()
        log.info("Wrote %s rows to %s.%s", f"{len(frame):,}", dataset_id, name)


def get_warehouse(
    target: str, cfg: PipelineConfig, duckdb_path: Path | None = None
) -> DuckDBWarehouse | BigQueryWarehouse:
    if target == "duckdb":
        path = Path(duckdb_path or cfg.duckdb_path)
        if not path.exists():
            raise FileNotFoundError(f"DuckDB warehouse {path} does not exist")
        return DuckDBWarehouse(path=path, prefix=cfg.dataset_prefix, raw_schema=cfg.raw_schema)
    if target == "bigquery":
        if not cfg.bigquery_project:
            raise RuntimeError("Set GCP_PROJECT (see .env.example) to use the BigQuery target")
        return BigQueryWarehouse(
            project=cfg.bigquery_project,
            prefix=cfg.dataset_prefix,
            raw_schema=cfg.raw_schema,
            location=cfg.bigquery_location,
        )
    raise ValueError(f"Unknown target {target!r}; expected one of {TARGETS}")
