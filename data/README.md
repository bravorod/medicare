# data/

Git-ignored working area. Nothing in here is committed.

| Path | Written by | Contents |
|---|---|---|
| `raw/downloads/` | `partd-risk download` | Original CMS / Open Payments / OIG / NPPES files plus `manifest.json` (URL, SHA-256, size, timestamp) |
| `raw/parquet/` | `partd-risk stage` | Column-pruned, all-string Parquet, one file per source |
| `warehouse/` | `partd-risk load --target duckdb` | Optional local DuckDB warehouse built from the real files |
| `synthetic/` | `partd-risk synthetic` | **Simulated** test data and its outputs (CI / smoke tests only) |

Expect roughly 15 GB for the downloads (NPPES and Open Payments are the large
ones) and 2-3 GB of Parquet.
