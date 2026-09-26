# Notebooks

Exploratory and diagnostic notebooks behind the pipeline. The pipeline itself
(`partd-risk` + dbt) does not depend on them. Outputs are cleared in git;
run them against your own warehouse to populate.

| Notebook | What it covers |
|---|---|
| `01_data_profiling.ipynb` | Provenance, row counts, cohort flow, suppression/null rates, volume and payment distributions, multi-source drugs |
| `02_brand_prescribing_and_payments.ipynb` | Crude vs. peer-adjusted brand gap, validation of the brand rule against CMS, GLM check, dose-response, specialty heterogeneity, drug-matched payments |
| `03_outlier_score_development.ipynb` | Feature transforms, peer-adjustment diagnostics, z-score correlations, score distribution, who moves in or out of the top 1% with adjustment |
| `04_exclusion_validation.ipynb` | Development-window weights and model choice, held-out test-window lift, bootstrap uncertainty, single features in both windows, captured exclusion types, regional stability |

```bash
# BigQuery (after the production run)
PARTD_TARGET=bigquery jupyter lab

# or the synthetic warehouse (numbers are simulated)
make synthetic-build
PARTD_TARGET=duckdb DUCKDB_PATH=$PWD/data/synthetic/partd_risk_synthetic.duckdb jupyter lab
```

Notebook 04 needs `partd-risk model` and the `post_ml` dbt models to have run.
