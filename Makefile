# Medicare Part D prescribing risk analysis
#
#   make setup          install Python + dbt dependencies
#   make check          lint, unit tests, dbt build on synthetic data
#   make bigquery       full production run on BigQuery (needs .env)
#   make help           list every target

SHELL := /bin/bash
-include .env
export

PY        ?= python
DBT       ?= dbt
DBT_DIR   := dbt
SYN_DB    := $(CURDIR)/data/synthetic/partd_risk_synthetic.duckdb

.DEFAULT_GOAL := help

.PHONY: help
help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------- setup ----
.PHONY: setup
setup:  ## Install the package with BigQuery, dbt and dev extras
	$(PY) -m pip install -e ".[bigquery,dbt,dev]"
	cd $(DBT_DIR) && $(DBT) deps
	pre-commit install || true

# ------------------------------------------------------------ quality -----
.PHONY: lint format test test-integration check
lint:  ## Ruff lint + format check
	ruff check src tests scripts
	ruff format --check src tests scripts

format:  ## Auto-format Python
	ruff format src tests scripts
	ruff check --fix src tests scripts

test:  ## Unit tests
	$(PY) -m pytest -m "not integration" --cov --cov-report=term-missing:skip-covered

test-integration:  ## End-to-end test on a synthetic DuckDB warehouse
	$(PY) -m pytest -m integration -v

check: lint test synthetic-build  ## Everything CI runs

# ------------------------------------------------ synthetic (CI / demo) ---
.PHONY: synthetic synthetic-build synthetic-results
synthetic:  ## Build the SYNTHETIC DuckDB warehouse (test data, never results)
	partd-risk synthetic --duckdb-path $(SYN_DB)

synthetic-build: synthetic  ## dbt build + model on synthetic data
	cd $(DBT_DIR) && DBT_TARGET=duckdb DUCKDB_PATH=$(SYN_DB) $(DBT) build --exclude tag:post_ml
	partd-risk model --target duckdb --duckdb-path $(SYN_DB)
	cd $(DBT_DIR) && DBT_TARGET=duckdb DUCKDB_PATH=$(SYN_DB) $(DBT) build --select tag:post_ml

synthetic-results: synthetic-build  ## Smoke-test reporting (watermarked, written to data/synthetic/outputs)
	partd-risk results --target duckdb --duckdb-path $(SYN_DB) --allow-synthetic
	partd-risk export-tableau --target duckdb --duckdb-path $(SYN_DB)

# ------------------------------------------------------ real data ---------
.PHONY: download stage load-bigquery dbt-bigquery model-bigquery results-bigquery tableau-bigquery bigquery
download:  ## Download the public source files (~15 GB)
	partd-risk download

stage: download  ## Convert downloads to all-string Parquet
	partd-risk stage

load-bigquery:  ## Load staged Parquet into BigQuery ($(GCP_PROJECT).partd_raw)
	partd-risk load --target bigquery

dbt-bigquery:  ## dbt build (staging -> marts -> reporting) on BigQuery
	cd $(DBT_DIR) && DBT_TARGET=bigquery $(DBT) build --exclude tag:post_ml

model-bigquery:  ## Outlier score, lift evaluation, brand regression
	partd-risk model --target bigquery
	cd $(DBT_DIR) && DBT_TARGET=bigquery $(DBT) build --select tag:post_ml

results-bigquery:  ## Headline metrics, figures, memo, README table
	partd-risk results --target bigquery --update-readme

tableau-bigquery:  ## De-identified CSV extracts for Tableau
	partd-risk export-tableau --target bigquery

bigquery: stage load-bigquery dbt-bigquery model-bigquery results-bigquery tableau-bigquery  ## Full production run

# ---------------------------------------------------------- docs ----------
.PHONY: docs dbt-docs
docs:  ## Regenerate docs/data_dictionary.md from the dbt YAML
	partd-risk data-dictionary

dbt-docs:  ## Build and serve the dbt docs site (lineage graph)
	cd $(DBT_DIR) && $(DBT) docs generate && $(DBT) docs serve

.PHONY: clean
clean:  ## Remove build artefacts (keeps downloads)
	rm -rf $(DBT_DIR)/target $(DBT_DIR)/target_bq $(DBT_DIR)/logs .pytest_cache .ruff_cache
	rm -rf data/synthetic
