from __future__ import annotations

from dataclasses import replace

import pytest

from partd_risk.ingest import catalog


@pytest.fixture
def part_d(cfg):
    return cfg.source("part_d_prescriber_drug")


def test_cms_catalog_picks_csv_for_year(part_d):
    csv, year21 = "text/csv", "2021-01-01/2021-12-31"
    fake = {
        "dataset": [
            {"title": "Something else", "distribution": []},
            {
                "title": "Medicare Part D Prescribers - by Provider and Drug",
                "distribution": [
                    {"format": "API", "downloadURL": "https://x/api", "temporal": year21},
                    {
                        "mediaType": csv,
                        "downloadURL": "https://x/2020.csv",
                        "temporal": "2020-01-01/2020-12-31",
                    },
                    {
                        "mediaType": csv,
                        "downloadURL": "https://x/2021_old.csv",
                        "temporal": year21,
                        "modified": "2023-01-01",
                    },
                    {
                        "mediaType": csv,
                        "downloadURL": "https://x/2021.csv",
                        "temporal": year21,
                        "modified": "2024-05-01",
                    },
                ],
            },
        ]
    }
    url = catalog.resolve_cms_data_catalog(part_d, 2021, fetch=lambda _: fake)
    assert url == "https://x/2021.csv"


def test_cms_catalog_errors_helpfully(part_d):
    with pytest.raises(catalog.ResolutionError, match=r"pipeline\.yml"):
        catalog.resolve_cms_data_catalog(part_d, 2021, fetch=lambda _: {"dataset": []})


def test_open_payments_catalog_handles_nested_distribution(cfg):
    source = cfg.source("open_payments_general")
    items = [
        {"title": "2020 General Payment Data", "distribution": [{"downloadURL": "https://x/2020"}]},
        {
            "title": "2021 General Payment Data",
            "distribution": [{"data": {"downloadURL": "https://x/OP_DTL_GNRL_PGYR2021.csv"}}],
        },
    ]
    url = catalog.resolve_open_payments_catalog(source, 2021, fetch=lambda _: items)
    assert url.endswith("PGYR2021.csv")


def test_nppes_prefers_v2_monthly_file(cfg):
    html = """
      <a href="NPPES_Data_Dissemination_091526_092126_Weekly_V2.zip">weekly</a>
      <a href="NPPES_Data_Dissemination_September_2026.zip">monthly v1</a>
      <a href="NPPES_Data_Dissemination_September_2026_V2.zip">monthly v2</a>
      <a href="NPPES_Deactivated_NPI_Report_091526.zip">deactivated</a>
    """
    url = catalog.resolve_nppes_monthly(cfg.source("nppes_providers"), 2021, fetch=lambda _: html)
    assert url == "https://download.cms.gov/nppes/NPPES_Data_Dissemination_September_2026_V2.zip"


def test_nppes_accepts_single_quoted_links(cfg):
    html = "<a id='DDSMTH.ZIP.D' href='./NPPES_Data_Dissemination_September_2026_V2.zip'>x</a>"
    url = catalog.resolve_nppes_monthly(cfg.source("nppes_providers"), 2021, fetch=lambda _: html)
    assert url == "https://download.cms.gov/nppes/NPPES_Data_Dissemination_September_2026_V2.zip"


def test_pinned_url_wins(part_d):
    pinned = replace(part_d, url="https://example.org/file.csv")
    assert catalog.resolve_url(pinned, 2021) == "https://example.org/file.csv"


def test_static_without_url_is_an_error(cfg):
    leie = replace(cfg.source("leie_exclusions"), url=None)
    with pytest.raises(catalog.ResolutionError):
        catalog.resolve_url(leie, 2021)
