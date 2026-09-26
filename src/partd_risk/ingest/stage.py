"""Convert downloaded CSV/ZIP files into column-pruned, all-string Parquet.

Raw tables are deliberately loaded as STRING columns: CMS files use blanks and
suppression markers inside numeric columns, and typing is handled explicitly
(with ``SAFE_CAST``) in the dbt staging layer where it can be tested.
"""

from __future__ import annotations

import difflib
import io
import logging
import re
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import IO

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from partd_risk.config import PipelineConfig, SourceConfig
from partd_risk.ingest.download import read_manifest

log = logging.getLogger(__name__)

CHUNK_ROWS = 500_000
_NON_ALNUM = re.compile(r"[^0-9a-z]+")


def normalize_column(name: str) -> str:
    """``"Provider Last Name (Legal Name)"`` -> ``"provider_last_name_legal_name"``."""
    return _NON_ALNUM.sub("_", name.strip().lower()).strip("_")


class SchemaError(ValueError):
    """Raised when a required column is missing from a source file."""


@dataclass
class ColumnPlan:
    """Mapping from normalized names to the file's original header names."""

    present: dict[str, str]
    missing_optional: list[str]

    @property
    def usecols(self) -> list[str]:
        return list(self.present.values())


def plan_columns(header: list[str], source: SourceConfig) -> ColumnPlan:
    normalized = {normalize_column(h): h for h in header}
    missing_required = [c for c in source.required_columns if c not in normalized]
    if missing_required:
        hints = {
            c: difflib.get_close_matches(c, normalized.keys(), n=3, cutoff=0.6)
            for c in missing_required
        }
        detail = "; ".join(f"{c} (close: {', '.join(h) or 'none'})" for c, h in hints.items())
        raise SchemaError(
            f"{source.name}: required columns missing from file header: {detail}. "
            "Update config/pipeline.yml if the publisher renamed a column."
        )
    missing_optional = [c for c in source.optional_columns if c not in normalized]
    for col in missing_optional:
        log.warning("%s: optional column %s not in file; filling with NULL", source.name, col)
    present = {c: normalized[c] for c in source.columns if c in normalized}
    return ColumnPlan(present=present, missing_optional=missing_optional)


@contextmanager
def open_source_file(path: Path, member_pattern: str | None) -> Iterator[IO[bytes]]:
    """Open a CSV directly, or the matching CSV member inside a ZIP archive."""
    if path.suffix.lower() != ".zip":
        with path.open("rb") as fh:
            yield fh
        return
    with zipfile.ZipFile(path) as zf:
        members = [m for m in zf.namelist() if m.lower().endswith(".csv")]
        if member_pattern:
            pattern = re.compile(member_pattern)
            members = [m for m in members if pattern.search(m)]
        members = [m for m in members if "fileheader" not in m.lower()]
        if len(members) != 1:
            raise SchemaError(
                f"Expected exactly one CSV in {path.name} matching {member_pattern!r}, "
                f"found {members}"
            )
        log.info("Reading %s from %s", members[0], path.name)
        with zf.open(members[0]) as fh:
            yield fh


def _read_header(fh: IO[bytes]) -> list[str]:
    text = io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace", newline="")
    header = pd.read_csv(text, nrows=0).columns.tolist()
    text.detach()
    return header


def iter_chunks(
    path: Path, source: SourceConfig, chunk_rows: int = CHUNK_ROWS
) -> Iterator[pd.DataFrame]:
    with open_source_file(path, source.zip_member_pattern) as fh:
        header = _read_header(fh)
    plan = plan_columns(header, source)
    rename = {orig: norm for norm, orig in plan.present.items()}
    with open_source_file(path, source.zip_member_pattern) as fh:
        text = io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace", newline="")
        reader = pd.read_csv(
            text,
            usecols=plan.usecols,
            dtype=str,
            keep_default_na=False,
            na_values=[""],
            chunksize=chunk_rows,
        )
        for chunk in reader:
            chunk = chunk.rename(columns=rename)
            for col in plan.missing_optional:
                chunk[col] = None
            yield chunk[list(source.columns)]


def arrow_schema(source: SourceConfig) -> pa.Schema:
    return pa.schema([pa.field(c, pa.string()) for c in source.columns])


def write_parquet(chunks: Iterator[pd.DataFrame], source: SourceConfig, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    schema = arrow_schema(source)
    rows = 0
    tmp = dest.with_suffix(".parquet.part")
    with pq.ParquetWriter(tmp, schema, compression="zstd") as writer:
        for chunk in chunks:
            table = pa.Table.from_pandas(chunk.astype(object), schema=schema, preserve_index=False)
            writer.write_table(table)
            rows += len(chunk)
            log.info("  %s: %s rows", source.name, f"{rows:,}")
    tmp.replace(dest)
    return rows


def stage_source(cfg: PipelineConfig, name: str) -> tuple[Path, int]:
    source = cfg.source(name)
    manifest = read_manifest(cfg.downloads_dir)
    if name not in manifest:
        raise FileNotFoundError(f"{name} has not been downloaded; run `partd-risk download` first")
    path = cfg.downloads_dir / manifest[name].path
    dest = cfg.parquet_dir / f"{source.raw_table}.parquet"
    rows = write_parquet(iter_chunks(path, source), source, dest)
    log.info("Staged %s -> %s (%s rows)", name, dest, f"{rows:,}")
    return dest, rows
