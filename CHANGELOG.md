# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.3.0] - 2026-09-24

### Changed

- Outlier score validated out-of-time (ADR 0007): non-negative logistic
  weights and the equal-vs-learned choice use only 2022-2023 exclusions; the
  headline lift is measured on held-out exclusions from 2024 onward.
- Feature ablation replaced by learned-weight and score-selection tables;
  single-feature lift reported for both windows.
- Notebook 04 follows the development / test split.
- Outcome window end pinned to 2026-07-31 for reproducibility. Headline with
  the pinned window: 4.1x (16 of 389; 95% CI 2.4-6.2x); through the Sept 2026
  snapshot it was 4.1x (17 of 411). Both recorded in ADR 0007.

## [0.2.0] - 2026-09-24

First run on the real 2021 data (DuckDB target, same dbt project as BigQuery).

### Changed

- Brand/generic rule: a brand name that is the generic name plus a
  formulation suffix ("Metformin Hcl Er") is now generic. Mean brand share
  moved from 22.0% to 18.2% against CMS's 17.7% (ADR 0002).
- Savings: net excess brand fills are signed and never floored (cell flooring
  turned noise into about $661M); the headline uses single-brand-product drugs,
  and all multi-source drugs are reported as an upper bound (ADR 0005).
- Tableau extracts drop rows describing fewer than 11 prescribers.

### Fixed

- NPPES monthly file resolution (single-quoted links on the index page).

### Results

- `reports/results/`, `reports/memo/memo.md`, `reports/figures/`,
  `tableau/extracts/` and the README table populated from the real run.

## [0.1.0] - 2026-09-24

### Added

- Ingest: catalog-based URL resolution, download manifest with SHA-256,
  column-checked all-string Parquet staging, BigQuery and DuckDB loaders with a
  provenance table.
- dbt project (BigQuery + DuckDB): 5 staging, 6 intermediate, 6 mart,
  10 reporting and 3 post-ML models; 3 seeds; 123 data tests; exposures for the
  Tableau dashboard and memo; cross-database dispatch macros.
- Analyses: peer-adjusted brand-name prescribing gap (indirect
  standardization), dose-response by payment tier and type, drug-matched
  payments, generic-substitution savings with rebate sensitivity.
- Modelling: regression-based peer adjustment (fixed-effects within
  estimator + case-mix controls), robust-z composite outlier score, Poisson
  GLM brand effect with peer-clustered SEs.
- Evaluation: lift / capture at 0.1%-20% against later OIG exclusions,
  bootstrap CIs, unadjusted and single-feature baselines, ablation.
- Reporting: headline metrics with placeholder filling, synthetic-data guard,
  README table updater, memo template, figures, de-identified Tableau
  extracts, generated data dictionary.
- Synthetic data generator, unit + integration tests, CI (lint, tests on
  3.10-3.12, synthetic dbt build, BigQuery compile + parse).
- Docs: methodology, runbook, data sources, architecture, limitations and
  ethics, ADRs 0001-0006, Tableau build spec, notebooks 01-04.
