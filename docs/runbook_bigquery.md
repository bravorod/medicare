# Runbook: production run on BigQuery

Expect a few hours end to end, mostly downloading and uploading the source
files. These are estimates, so check the BigQuery job history after your first
run. Raw storage is on the order of 10 GB, and a full `dbt build` should scan
tens of GB, well inside the BigQuery free tier of 1 TB of queries per month.
The `maximum_bytes_billed` cap below guards against surprises.

## 0. Prerequisites

- A Google Cloud project with the BigQuery API enabled and billing attached.
- `gcloud` CLI, Python 3.10+, about 20 GB of free disk.
- Your account needs `BigQuery Data Editor` and `BigQuery Job User` on the project.

```bash
git clone https://github.com/bravorod/medicare && cd medicare
python -m venv .venv && source .venv/bin/activate
make setup                          # pip install -e ".[bigquery,dbt,dev]" + dbt deps
cp .env.example .env                # set GCP_PROJECT (and optionally BQ_DATASET)
gcloud auth application-default login
```

Sanity-check the code first. Nothing below touches BigQuery:

```bash
make check                          # lint + unit tests + dbt build on SYNTHETIC data
```

## 1. Download and stage the source files

```bash
partd-risk download                 # ~15 GB into data/raw/downloads (+ manifest.json)
partd-risk stage                    # -> data/raw/parquet/*.parquet (all-string, column-pruned)
```

Download URLs are resolved from the publishers' catalogs at run time
(`src/partd_risk/ingest/catalog.py`). If a publisher changes its catalog and
resolution fails, the error names the setting to fix. Paste the file's link
into `sources.<name>.url` in `config/pipeline.yml` and rerun.

If a publisher renames a column, `stage` fails and suggests the closest header
names. Update the column list in `config/pipeline.yml`.

## 2. Load raw tables

```bash
partd-risk load --target bigquery
```

This creates dataset `${GCP_PROJECT}.partd_raw` with five tables plus
`load_provenance` (URL, SHA-256, row count and load time for each file,
`is_synthetic = false`).

## 3. Build the warehouse

```bash
cd dbt
dbt build --exclude tag:post_ml     # seeds, staging, intermediate, marts, reporting + tests
cd ..
```

Datasets created: `partd_risk_reference`, `partd_risk_staging`,
`partd_risk_intermediate`, `partd_risk_marts`, `partd_risk_reporting`.

Before moving on, look at the warnings. These are the ones that matter:

| Warning | Meaning | Action |
|---|---|---|
| `relationships_stg_leie__exclusions_exclusion_type_code` | a new OIG exclusion code | add it to `seeds/leie_exclusion_types.csv` |
| `accepted_values_stg_open_payments__...program_year` | the file holds another program year | check the Open Payments download |
| `unique_stg_part_d__prescriber_drug_prescriber_drug_id` | duplicate NPI x drug rows | inspect; usually harmless name variants |
| `dbt_utils_expression_is_true_rpt_brand_comparison_...` | unpaid O/E is not about 1 | check the peer-group fallbacks |

## 4. Score, evaluate, finish the warehouse

```bash
partd-risk model --target bigquery          # writes partd_risk_ml.outlier_scores + reports/results/*
cd dbt && dbt build --select tag:post_ml && cd ..
```

## 5. Results, memo, README, Tableau

```bash
partd-risk results --target bigquery --update-readme
partd-risk export-tableau --target bigquery
```

`results` prints the four filled placeholders and the two bullets, and writes:

- `reports/results/headline_metrics.json`: every number, with CIs
- `reports/results/resume_bullets.md`
- `reports/memo/memo.md` and `reports/figures/*.png`
- the table between the `HEADLINE` markers in `README.md`

`export-tableau` writes de-identified CSVs to `tableau/extracts/`. See
`tableau/README.md` for the dashboard build.

## 6. Commit the results

```bash
git add reports/ tableau/extracts/ README.md
git commit -m "Results: 2021 Part D run on BigQuery"
```

## Re-running with different settings

Every rule is a dbt var or a YAML setting. After changing one, rerun steps 3-5.

```bash
cd dbt && dbt build --exclude tag:post_ml --vars '{industry_paid_definition: any, min_total_fills: 250}'
```

| Setting | Where | Default |
|---|---|---|
| Data year | `config/pipeline.yml` `data_year` and dbt var `data_year` | 2021 |
| Paid definition | dbt var `industry_paid_definition` | `drug_related` |
| Min volume | dbt var `min_total_fills` | 100 |
| Peer group size | dbt var `min_peer_group_size` | 25 |
| Outcome window end | dbt var `outcome_window_end` | 2026-07-31 |
| Score features / weights | `config/outlier_score.yml` | 9 features, weight 1 |

## Cost control

- `maximum_bytes_billed` in `dbt/profiles.yml` caps each query (default 200 GB,
  set with `BQ_MAX_BYTES_BILLED`).
- Staging models are views. Intermediate and mart models are tables, so
  downstream models do not re-scan the 25M-row Part D file.
- `fct_prescribers` is clustered by specialty and state.
