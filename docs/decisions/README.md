# Architecture decision records

Short records of the choices that shape the results, why they were made and
what was rejected. Format: context, decision, consequences.

| # | Decision | Status |
|---|---|---|
| [0001](0001-bigquery-dbt-with-duckdb-for-ci.md) | BigQuery + dbt in production, DuckDB for CI | Accepted |
| [0002](0002-brand-generic-classification.md) | Name-based brand/generic classification | Accepted |
| [0003](0003-indirect-standardization-for-brand-gap.md) | Indirect standardization for the brand gap, regression as a check | Accepted |
| [0004](0004-unsupervised-score-validated-on-leie.md) | Unsupervised peer-adjusted score, validated on later LEIE exclusions | Accepted |
| [0005](0005-savings-netting-and-gross-cost.md) | Savings: signed net excess, single-brand equivalents, gross cost | Accepted |
| [0006](0006-deidentified-reporting.md) | Aggregate / pseudonymized reporting only | Accepted |
| [0007](0007-temporal-holdout-for-the-score.md) | Learn score weights on 2022-23 exclusions, test on 2024 onward | Accepted |
