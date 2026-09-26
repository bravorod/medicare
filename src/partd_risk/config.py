"""Load pipeline and model configuration from ``config/*.yml``."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
PIPELINE_CONFIG = CONFIG_DIR / "pipeline.yml"
OUTLIER_CONFIG = CONFIG_DIR / "outlier_score.yml"

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")


def expand_env(value: Any) -> Any:
    """Recursively expand ``${VAR}`` / ``${VAR:-default}`` in strings."""
    if isinstance(value, str):
        return _ENV_PATTERN.sub(lambda m: os.environ.get(m.group(1), m.group(2) or ""), value)
    if isinstance(value, dict):
        return {k: expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [expand_env(v) for v in value]
    return value


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


@dataclass(frozen=True)
class SourceConfig:
    """One upstream dataset and the columns we keep from it."""

    name: str
    description: str
    raw_table: str
    resolver: str
    required_columns: tuple[str, ...]
    optional_columns: tuple[str, ...] = ()
    publisher: str = ""
    url: str | None = None
    catalog_title: str | None = None
    index_url: str | None = None
    zip_member_pattern: str | None = None

    @property
    def columns(self) -> tuple[str, ...]:
        return self.required_columns + self.optional_columns


@dataclass(frozen=True)
class PipelineConfig:
    data_year: int
    downloads_dir: Path
    parquet_dir: Path
    duckdb_path: Path
    results_dir: Path
    figures_dir: Path
    tableau_dir: Path
    raw_schema: str
    dataset_prefix: str
    bigquery_project: str | None
    bigquery_location: str
    sources: dict[str, SourceConfig] = field(default_factory=dict)

    def source(self, name: str) -> SourceConfig:
        try:
            return self.sources[name]
        except KeyError as exc:
            known = ", ".join(sorted(self.sources))
            raise KeyError(f"Unknown source '{name}'. Known sources: {known}") from exc


def load_config(path: Path | str | None = None) -> PipelineConfig:
    raw = expand_env(yaml.safe_load(Path(path or PIPELINE_CONFIG).read_text()))
    paths = raw["paths"]
    wh = raw["warehouse"]
    sources = {
        name: SourceConfig(
            name=name,
            description=" ".join(spec.get("description", "").split()),
            publisher=spec.get("publisher", ""),
            raw_table=spec["raw_table"],
            resolver=spec["resolver"],
            required_columns=tuple(spec["required_columns"]),
            optional_columns=tuple(spec.get("optional_columns", ())),
            url=spec.get("url"),
            catalog_title=spec.get("catalog_title"),
            index_url=spec.get("index_url"),
            zip_member_pattern=spec.get("zip_member_pattern"),
        )
        for name, spec in raw["sources"].items()
    }
    return PipelineConfig(
        data_year=int(raw["data_year"]),
        downloads_dir=_resolve_path(paths["downloads"]),
        parquet_dir=_resolve_path(paths["parquet"]),
        duckdb_path=_resolve_path(paths["duckdb"]),
        results_dir=_resolve_path(paths["results"]),
        figures_dir=_resolve_path(paths["figures"]),
        tableau_dir=_resolve_path(paths["tableau_extracts"]),
        raw_schema=wh["raw_schema"],
        dataset_prefix=wh["dataset_prefix"],
        bigquery_project=wh["bigquery"].get("project") or None,
        bigquery_location=wh["bigquery"].get("location") or "US",
        sources=sources,
    )


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    column: str
    transform: str
    weight: float = 1.0
    rationale: str = ""


@dataclass(frozen=True)
class OutlierConfig:
    peer_group_column: str
    features: tuple[FeatureSpec, ...]
    controls: tuple[str, ...]
    logit_eps: float
    z_cap: float
    min_feature_coverage: float
    top_k: tuple[float, ...]
    headline_k: float
    bootstrap_reps: int
    seed: int
    split_date: str = "2024-01-01"
    l2_penalty: float = 1.0
    selection_metric: str = "average_precision"


def load_outlier_config(path: Path | str | None = None) -> OutlierConfig:
    raw = yaml.safe_load(Path(path or OUTLIER_CONFIG).read_text())
    settings = raw.get("settings", {})
    evaluation = raw.get("evaluation", {})
    weighting = raw.get("weighting", {})
    if weighting.get("selection_metric", "average_precision") not in {"average_precision", "auroc"}:
        raise ValueError("weighting.selection_metric must be average_precision or auroc")
    features = tuple(FeatureSpec(**spec) for spec in raw["features"])
    valid = {"logit", "log", "log1p", "identity"}
    bad = [f.name for f in features if f.transform not in valid]
    if bad:
        raise ValueError(f"Unknown transform for features {bad}; expected one of {sorted(valid)}")
    return OutlierConfig(
        peer_group_column=raw.get("peer_group_column", "peer_group_id"),
        features=features,
        controls=tuple(raw.get("controls", ())),
        logit_eps=float(settings.get("logit_eps", 0.005)),
        z_cap=float(settings.get("z_cap", 8.0)),
        min_feature_coverage=float(settings.get("min_feature_coverage", 0.5)),
        top_k=tuple(float(k) for k in evaluation.get("top_k", (0.01,))),
        headline_k=float(evaluation.get("headline_k", 0.01)),
        bootstrap_reps=int(evaluation.get("bootstrap_reps", 1000)),
        seed=int(evaluation.get("seed", 0)),
        split_date=str(weighting.get("split_date", "2024-01-01")),
        l2_penalty=float(weighting.get("l2_penalty", 1.0)),
        selection_metric=str(weighting.get("selection_metric", "average_precision")),
    )
