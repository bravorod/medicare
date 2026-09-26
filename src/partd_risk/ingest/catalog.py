"""Resolve download URLs for each upstream dataset.

CMS re-publishes files under new names with every refresh, so URLs are looked
up from the publishers' machine-readable catalogs at run time instead of being
hard-coded. Any source can be pinned by setting ``url`` in config/pipeline.yml.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any
from urllib.parse import urljoin

import requests

from partd_risk.config import SourceConfig

log = logging.getLogger(__name__)

CMS_DATA_CATALOG_URL = "https://data.cms.gov/data.json"
OPEN_PAYMENTS_CATALOG_URL = (
    "https://openpaymentsdata.cms.gov/api/1/metastore/schemas/dataset/items"
    "?show-reference-ids=false"
)
DEFAULT_NPPES_INDEX_URL = "https://download.cms.gov/nppes/NPI_Files.html"

_TIMEOUT = 60


class ResolutionError(RuntimeError):
    """Raised when a download URL cannot be determined from a catalog."""


def _get_json(url: str) -> Any:
    resp = requests.get(url, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _get_text(url: str) -> str:
    resp = requests.get(url, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.text


def _is_csv(dist: dict[str, Any]) -> bool:
    media = (dist.get("mediaType") or dist.get("format") or "").lower()
    url = (dist.get("downloadURL") or "").lower().split("?")[0]
    return "csv" in media or url.endswith(".csv")


def resolve_cms_data_catalog(
    source: SourceConfig, year: int, fetch: Callable[[str], Any] = _get_json
) -> str:
    """Find the CSV for ``year`` of a data.cms.gov dataset via its DCAT catalog."""
    catalog = fetch(CMS_DATA_CATALOG_URL)
    title = (source.catalog_title or "").strip().lower()
    datasets = [
        d for d in catalog.get("dataset", []) if d.get("title", "").strip().lower() == title
    ]
    if not datasets:
        raise ResolutionError(
            f"No dataset titled {source.catalog_title!r} in {CMS_DATA_CATALOG_URL}. "
            f"Set sources.{source.name}.url in config/pipeline.yml to the CSV link."
        )
    candidates = []
    for dist in datasets[0].get("distribution", []):
        if not dist.get("downloadURL") or not _is_csv(dist):
            continue
        temporal = str(dist.get("temporal", ""))
        label = str(dist.get("title", ""))
        if temporal.startswith(f"{year}-") or re.search(rf"\b{year}\b", label):
            candidates.append(dist)
    if not candidates:
        raise ResolutionError(
            f"Dataset {source.catalog_title!r} has no CSV distribution for {year}. "
            f"Set sources.{source.name}.url in config/pipeline.yml."
        )
    # Prefer the most recently modified release of that year.
    candidates.sort(key=lambda d: str(d.get("modified", "")), reverse=True)
    return candidates[0]["downloadURL"]


def resolve_open_payments_catalog(
    source: SourceConfig, year: int, fetch: Callable[[str], Any] = _get_json
) -> str:
    """Find the General Payments file for a program year on openpaymentsdata.cms.gov."""
    items = fetch(OPEN_PAYMENTS_CATALOG_URL)
    title = (source.catalog_title or "{year} General Payment Data").format(year=year).lower()
    for item in items:
        if str(item.get("title", "")).strip().lower() != title:
            continue
        for dist in item.get("distribution", []):
            dist = dist.get("data", dist)  # DKAN nests under "data" with reference ids on
            if dist.get("downloadURL"):
                return dist["downloadURL"]
    raise ResolutionError(
        f"No Open Payments dataset titled {title!r}. "
        f"Set sources.{source.name}.url in config/pipeline.yml to the CSV or ZIP link."
    )


_NPPES_MONTHLY = re.compile(
    r"""href=['"]([^'"]*NPPES_Data_Dissemination_[A-Za-z]+_\d{4}(?:_V2)?\.zip)['"]""",
    re.IGNORECASE,
)


def resolve_nppes_monthly(
    source: SourceConfig, year: int, fetch: Callable[[str], str] = _get_text
) -> str:
    """Pick the current monthly full-replacement NPPES file from the index page.

    The NPPES snapshot is used for provider attributes (entity type, taxonomy,
    practice location), which change slowly, so the latest file is used
    regardless of ``year``.
    """
    index_url = source.index_url or DEFAULT_NPPES_INDEX_URL
    links = _NPPES_MONTHLY.findall(fetch(index_url))
    if not links:
        raise ResolutionError(
            f"No monthly NPPES file linked from {index_url}. "
            f"Set sources.{source.name}.url in config/pipeline.yml."
        )
    # Prefer V2 files (current layout) and keep page order otherwise.
    links.sort(key=lambda href: not href.upper().endswith("_V2.ZIP"))
    return urljoin(index_url, links[0])


RESOLVERS: dict[str, Callable[[SourceConfig, int], str]] = {
    "cms_data_catalog": resolve_cms_data_catalog,
    "open_payments_catalog": resolve_open_payments_catalog,
    "nppes_monthly": resolve_nppes_monthly,
}


def resolve_url(source: SourceConfig, year: int) -> str:
    """Return the download URL for ``source``, honouring a pinned ``url``."""
    if source.url:
        return source.url
    if source.resolver == "static":
        raise ResolutionError(f"Source {source.name} uses the static resolver but has no url.")
    try:
        resolver = RESOLVERS[source.resolver]
    except KeyError as exc:
        raise ResolutionError(f"Unknown resolver {source.resolver!r} for {source.name}") from exc
    url = resolver(source, year)
    log.info("Resolved %s -> %s", source.name, url)
    return url
