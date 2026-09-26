from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from partd_risk.ingest import download


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.headers = {"Content-Length": str(len(payload))}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        for i in range(0, len(self.payload), 4):
            yield self.payload[i : i + 4]


@pytest.fixture
def tmp_cfg(cfg, tmp_path):
    leie = replace(cfg.source("leie_exclusions"), url="https://example.org/UPDATED.csv")
    return replace(cfg, downloads_dir=tmp_path, sources={**cfg.sources, "leie_exclusions": leie})


def test_download_writes_file_and_manifest(tmp_cfg, monkeypatch):
    payload = b"LASTNAME,NPI\nDOE,1234567890\n"
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return FakeResponse(payload)

    monkeypatch.setattr(download.requests, "get", fake_get)
    record = download.download_source(tmp_cfg, "leie_exclusions")
    path = tmp_cfg.downloads_dir / record.path
    assert path.read_bytes() == payload
    assert record.sha256 == hashlib.sha256(payload).hexdigest()
    assert record.bytes == len(payload)
    assert download.read_manifest(tmp_cfg.downloads_dir)["leie_exclusions"] == record

    # second call is a no-op because the manifest matches and the file exists
    download.download_source(tmp_cfg, "leie_exclusions")
    assert len(calls) == 1
    download.download_source(tmp_cfg, "leie_exclusions", force=True)
    assert len(calls) == 2


def test_download_retries_then_raises(tmp_cfg, monkeypatch):
    monkeypatch.setattr(download.time, "sleep", lambda _: None)

    def boom(url, **kwargs):
        raise download.requests.ConnectionError("proxy reset")

    monkeypatch.setattr(download.requests, "get", boom)
    with pytest.raises(download.requests.ConnectionError):
        download.download_source(tmp_cfg, "leie_exclusions")
    assert not any(tmp_cfg.downloads_dir.glob("*.part"))
