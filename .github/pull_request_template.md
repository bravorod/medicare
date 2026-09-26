## What changed

<!-- One or two sentences. Link the issue if there is one. -->

## Why

## How it was checked

- [ ] `make lint` and `make test` pass
- [ ] `make synthetic-build` passes (dbt build + model on synthetic DuckDB)
- [ ] BigQuery compile check passes (CI job `bigquery-sql`)
- [ ] If a metric definition changed: `docs/methodology.md` and `docs/results_placeholders.md` updated
- [ ] If a model or column changed: dbt YAML descriptions/tests updated and `make docs` re-run

## Effect on headline numbers

<!-- Does this change any number in the README / memo? Before -> after, from a real BigQuery run. -->
