"""Shared notebook setup: pick the warehouse from environment variables.

    PARTD_TARGET=bigquery                (default; needs GCP_PROJECT)
    PARTD_TARGET=duckdb DUCKDB_PATH=...  (local DuckDB, e.g. the synthetic warehouse)
"""

from __future__ import annotations

import os

import matplotlib.pyplot as plt
import pandas as pd

from partd_risk.config import load_config, load_outlier_config
from partd_risk.warehouse import get_warehouse

pd.set_option("display.max_columns", 50)
pd.set_option("display.float_format", lambda v: f"{v:,.4f}")
plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False})

CFG = load_config()
OCFG = load_outlier_config()
TARGET = os.environ.get("PARTD_TARGET", "bigquery")
WH = get_warehouse(TARGET, CFG, os.environ.get("DUCKDB_PATH"))


def table(layer: str, name: str) -> str:
    return WH.table(layer, name)


def q(sql: str) -> pd.DataFrame:
    return WH.query(sql)


def banner() -> None:
    prov = WH.read("reporting", "rpt_data_provenance")
    synthetic = bool(prov["is_synthetic"].astype(bool).any())
    print(f"target={TARGET}  data_year={CFG.data_year}  synthetic={synthetic}")
    if synthetic:
        print("WARNING: SYNTHETIC warehouse - outputs are for testing only, not findings.")
