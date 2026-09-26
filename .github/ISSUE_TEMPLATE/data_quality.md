---
name: Data quality issue
about: A source file changed layout, a dbt test warns, or a value looks implausible
labels: data-quality
---

**Source / model** (e.g. `open_payments_general`, `stg_leie__exclusions`)

**What looks wrong** (column, example values, row counts)

**How it was found** (dbt test name, analysis query, notebook)

**Suspected cause** (publisher renamed a column, new suppression marker, ...)

- [ ] `config/pipeline.yml` column lists still match the file header
- [ ] Checked the publisher's data dictionary for the release
