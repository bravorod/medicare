from __future__ import annotations

import zipfile

import pyarrow.parquet as pq
import pytest

from partd_risk.config import SourceConfig
from partd_risk.ingest.stage import (
    SchemaError,
    iter_chunks,
    normalize_column,
    plan_columns,
    write_parquet,
)

SOURCE = SourceConfig(
    name="toy",
    description="toy",
    raw_table="toy",
    resolver="static",
    required_columns=("prscrbr_npi", "tot_clms"),
    optional_columns=("tot_benes",),
    zip_member_pattern=r"(?i)^data_\d+\.csv$",
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Prscrbr_NPI", "prscrbr_npi"),
        ("Provider Last Name (Legal Name)", "provider_last_name_legal_name"),
        ("Healthcare Provider Taxonomy Code_1", "healthcare_provider_taxonomy_code_1"),
        ("  Total_Amount_of_Payment_USDollars ", "total_amount_of_payment_usdollars"),
    ],
)
def test_normalize_column(raw, expected):
    assert normalize_column(raw) == expected


def test_plan_columns_fills_optional_and_suggests_required():
    plan = plan_columns(["Prscrbr_NPI", "Tot_Clms", "Extra"], SOURCE)
    assert plan.missing_optional == ["tot_benes"]
    assert plan.usecols == ["Prscrbr_NPI", "Tot_Clms"]
    with pytest.raises(SchemaError, match=r"tot_clms \(close: tot_clm"):
        plan_columns(["Prscrbr_NPI", "Tot_Clm"], SOURCE)


def _csv(path):
    path.write_text('Prscrbr_NPI,Tot_Clms,Other\n1234567890,12,x\n0987654321,,"quoted, value"\n')
    return path


def test_iter_chunks_csv_keeps_strings_and_nulls(tmp_path):
    chunks = list(iter_chunks(_csv(tmp_path / "data_1.csv"), SOURCE, chunk_rows=1))
    assert len(chunks) == 2
    first, second = chunks
    assert list(first.columns) == ["prscrbr_npi", "tot_clms", "tot_benes"]
    assert first.loc[0, "prscrbr_npi"] == "1234567890"
    assert second["tot_clms"].isna().all()
    assert second["tot_benes"].isna().all()


def test_iter_chunks_reads_matching_zip_member(tmp_path):
    csv = _csv(tmp_path / "data_1.csv")
    archive = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.write(csv, "data_1.csv")
        zf.writestr("README.txt", "ignore me")
        zf.writestr("other_2.csv", "a,b\n1,2\n")
    rows = sum(len(c) for c in iter_chunks(archive, SOURCE))
    assert rows == 2


def test_write_parquet_is_all_string(tmp_path):
    dest = tmp_path / "out.parquet"
    rows = write_parquet(iter_chunks(_csv(tmp_path / "data_1.csv"), SOURCE), SOURCE, dest)
    table = pq.read_table(dest)
    assert rows == 2 == table.num_rows
    assert all(str(t) == "string" for t in table.schema.types)
    assert table.column("prscrbr_npi").to_pylist() == ["1234567890", "0987654321"]
