# Contributing

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
make setup          # package + BigQuery/dbt/dev extras, dbt deps, pre-commit hooks
make check          # lint, unit tests, dbt build + model on synthetic DuckDB
```

`make check` needs no cloud access. It runs the whole pipeline on a synthetic
DuckDB warehouse.

## Workflow

1. Branch from `main`.
2. Change code, dbt models or config. Keep dbt YAML descriptions and tests in
   step with the SQL (`tests/test_reporting_misc.py` fails on an undocumented
   model).
3. `make check`. If you touched SQL, CI also compiles the project for BigQuery
   and parses it (`scripts/check_bigquery_sql.py`).
4. If a metric definition changed, update `docs/methodology.md` and
   `docs/results_placeholders.md`, and add an ADR under `docs/decisions/` if
   the reason isn't obvious.
5. Open a PR using the template and state the effect on headline numbers.

## Conventions

- **SQL:** lower-case keywords, one CTE per logical step, `ref`/`source`
  only, and no engine-specific functions in models (add a dispatch macro to
  `dbt/macros/cross_db.sql` instead).
- **Python:** ruff (line length 100), type hints, no notebook-only logic.
  Anything the pipeline depends on lives in `src/partd_risk`.
- **Data:** nothing under `data/` is committed. Synthetic outputs go to
  `data/synthetic/outputs` automatically.
- **Identifiers:** never commit NPIs, names or prescriber-level scores. See
  `docs/limitations_and_ethics.md`.
