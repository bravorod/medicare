"""Download raw source files and record what was fetched in a manifest."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

from partd_risk.config import PipelineConfig, SourceConfig
from partd_risk.ingest.catalog import resolve_url

log = logging.getLogger(__name__)

MANIFEST_NAME = "manifest.json"
_CHUNK = 8 * 1024 * 1024


@dataclass
class DownloadRecord:
    source: str
    url: str
    path: str
    bytes: int
    sha256: str
    downloaded_at: str


def _filename_for(source: SourceConfig, url: str) -> str:
    name = Path(urlparse(url).path).name or f"{source.name}.csv"
    return f"{source.name}__{name}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def _stream(url: str, dest: Path, retries: int = 4) -> None:
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("Content-Length", 0))
                written = 0
                next_report = 0.0
                with tmp.open("wb") as fh:
                    for block in resp.iter_content(chunk_size=_CHUNK):
                        fh.write(block)
                        written += len(block)
                        if total and written / total >= next_report:
                            log.info("  %s: %.0f%%", dest.name, 100 * written / total)
                            next_report += 0.1
            tmp.replace(dest)
            return
        except requests.RequestException as exc:
            if attempt == retries:
                raise
            wait = 2**attempt
            log.warning("Download failed (%s); retrying in %ss", exc, wait)
            time.sleep(wait)


def read_manifest(downloads_dir: Path) -> dict[str, DownloadRecord]:
    path = downloads_dir / MANIFEST_NAME
    if not path.exists():
        return {}
    return {k: DownloadRecord(**v) for k, v in json.loads(path.read_text()).items()}


def write_manifest(downloads_dir: Path, records: dict[str, DownloadRecord]) -> None:
    payload = {k: asdict(v) for k, v in sorted(records.items())}
    (downloads_dir / MANIFEST_NAME).write_text(json.dumps(payload, indent=2) + "\n")


def download_source(cfg: PipelineConfig, name: str, force: bool = False) -> DownloadRecord:
    source = cfg.source(name)
    cfg.downloads_dir.mkdir(parents=True, exist_ok=True)
    manifest = read_manifest(cfg.downloads_dir)
    url = resolve_url(source, cfg.data_year)
    dest = cfg.downloads_dir / _filename_for(source, url)

    existing = manifest.get(name)
    if existing and existing.url == url and dest.exists() and not force:
        log.info("%s already downloaded (%s); skipping", name, dest.name)
        return existing

    log.info("Downloading %s from %s", name, url)
    _stream(url, dest)
    record = DownloadRecord(
        source=name,
        url=url,
        path=str(dest.relative_to(cfg.downloads_dir)),
        bytes=dest.stat().st_size,
        sha256=_sha256(dest),
        downloaded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    manifest[name] = record
    write_manifest(cfg.downloads_dir, manifest)
    log.info("Saved %s (%.1f MB)", dest.name, record.bytes / 1e6)
    return record
