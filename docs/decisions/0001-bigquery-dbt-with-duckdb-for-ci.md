# 0001: BigQuery + dbt in production, DuckDB for CI

**Status:** Accepted

## Context

The full inputs are about 45M rows across five sources. Stakeholders should be
able to re-run the analysis, and every transformation should be reviewable and
tested. CI has no access to a GCP project, and synthetic data is the only thing
it can run on.

## Decision

- Use **BigQuery** as the production warehouse, with **dbt** for every SQL
  transformation (staging, intermediate, marts, reporting), tests and docs.
- Run the **same dbt project on DuckDB** in CI and locally. Put every dialect
  difference behind `adapter.dispatch` macros (`dbt/macros/cross_db.sql`).
- Load raw tables as **all-string Parquet** and type them in staging with safe
  casts, so malformed values become testable NULLs instead of load failures.
- In CI, compile for BigQuery with a throwaway key (nothing is executed) and
  parse every model with sqlglot's BigQuery dialect.

## Consequences

- Model SQL cannot use engine-specific functions directly. That is a small
  constraint, and a lint check enforces it.
- A dialect bug that parses but behaves differently (e.g. regex semantics)
  could still slip through. The dbt tests run on BigQuery in production are the
  backstop.
- Python modelling reads marts through a thin `Warehouse` interface that works
  on both engines.
