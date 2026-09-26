# Architecture

## Pipeline

```mermaid
flowchart LR
    subgraph sources[Public sources]
        A1[CMS Part D<br/>by Provider & Drug]
        A2[CMS Part D<br/>by Provider]
        A3[Open Payments<br/>General Payments]
        A4[OIG LEIE]
        A5[NPPES]
    end

    subgraph ingest[Python ingest]
        B1[download<br/>catalog URL resolution<br/>+ SHA-256 manifest]
        B2[stage<br/>column check, all-string Parquet]
        B3[load<br/>raw tables + provenance]
    end

    subgraph dbt[dbt on BigQuery]
        C1[staging<br/>typed, cleaned views]
        C2[intermediate<br/>drug reference, fills,<br/>payments, exclusions, cohort]
        C3[marts<br/>fct_prescribers, brand O/E,<br/>savings, outlier features]
        C4[reporting<br/>rpt_* tables]
    end

    subgraph py[Python modelling]
        D1[peer adjustment<br/>FE regression + robust z]
        D2[outlier score]
        D3[lift vs later exclusions<br/>bootstrap CI]
        D4[brand-effect GLM]
    end

    subgraph out[Outputs]
        E1[headline_metrics.json<br/>resume bullets]
        E2[memo.md + figures]
        E3[Tableau extracts]
        E4[README table]
    end

    A1 & A2 & A3 & A4 & A5 --> B1 --> B2 --> B3 --> C1 --> C2 --> C3 --> C4
    C3 --> D1 --> D2 --> D3
    C3 --> D4
    D2 -->|ml.outlier_scores| C5[post_ml dbt models]
    C4 & D3 & D4 --> E1 --> E2 & E4
    C4 & C5 --> E3
```

## dbt lineage (simplified)

```mermaid
flowchart TB
    s1[stg_part_d__prescriber_drug] --> i1[int_part_d__drug_reference]
    s1 --> i2[int_prescribers__fill_summary]
    i1 --> i2
    s2[stg_part_d__prescriber] --> i5[int_prescribers__cohort]
    s3[stg_open_payments__general_payments] --> i3[int_payments__prescriber_summary]
    s3 --> i6[int_payments__drug_matched]
    s4[stg_leie__exclusions] --> i4[int_exclusions__by_npi]
    s5[stg_nppes__providers] --> i5
    i2 & i3 & i4 --> i5
    i5 --> f[fct_prescribers]
    f --> m1[mart_brand_peer_comparison] --> r1[rpt_brand_comparison]
    m1 --> r2[rpt_brand_by_payment_tier]
    f --> m2[mart_generic_substitution_savings] --> r3[rpt_savings_summary]
    i1 --> m2
    f --> m3[mart_outlier_features]
    f --> m4[mart_drug_matched_prescribing]
    i6 --> m4
```

Run `make dbt-docs` for the full, clickable lineage graph.

## Two engines, one codebase

Production runs on **BigQuery**. CI and local development run the same dbt
models on **DuckDB** against synthetic data. Dialect differences (safe casts,
date parsing, regex, division) go through `adapter.dispatch` macros in
`dbt/macros/cross_db.sql`. CI also compiles the project for BigQuery and
parses every model with sqlglot's BigQuery dialect, so a DuckDB-only function
cannot slip into the production build. See
[ADR 0001](decisions/0001-bigquery-dbt-with-duckdb-for-ci.md).

## Layers and materializations

| Layer | Materialization | Dataset | Purpose |
|---|---|---|---|
| raw | table (loader) | `partd_raw` | All-string copies of the source files + provenance |
| reference | seed | `partd_risk_reference` | Payment categories, LEIE exclusion types, state regions |
| staging | view | `partd_risk_staging` | Typing, cleaning, renaming, one model per source |
| intermediate | table | `partd_risk_intermediate` | Reusable per-drug / per-NPI aggregates and the cohort |
| marts | table | `partd_risk_marts` | Analysis-ready facts and the ML feature table |
| reporting | table | `partd_risk_reporting` | Small aggregated tables for Tableau and the memo |
| ml | table (Python) | `partd_risk_ml` | Outlier scores written back by `partd-risk model` |
