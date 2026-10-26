PY ?= python
DB ?= warehouse/platform.duckdb
DATA ?= data
DBT_BIN ?= dbt
DBT = cd dbt && DUCKDB_PATH=../$(DB) $(DBT_BIN)
JOBS ?=

.PHONY: all collect generate load dbt digest test clean

all: collect generate load dbt digest test   ## real CI history + synthetic Snowflake/Fivetran -> dbt -> digest -> tests

collect:    ## REAL GitHub Actions runs and jobs, incremental (set GITHUB_TOKEN; JOBS=--no-jobs without one)
	$(PY) ingestion/collect_github_actions.py --owner Saigwe --out $(DATA)/github $(JOBS)

generate:   ## SYNTHETIC Snowflake account usage and Fivetran logs with planted problems (fixed seeds)
	$(PY) ingestion/generate_snowflake_usage.py --out $(DATA)/snowflake
	$(PY) ingestion/generate_fivetran_logs.py --out $(DATA)/fivetran

load:
	$(PY) ingestion/load.py --data $(DATA) --db $(DB)

dbt:
	$(DBT) deps --profiles-dir .
	$(DBT) build --profiles-dir .

digest:
	$(PY) ops/daily_digest.py --db $(DB) --out $(DATA)/digests

test:
	PLATFORM_DB=$(DB) $(PY) -m pytest -q tests

clean:
	rm -rf warehouse dbt/target dbt/logs dbt/dbt_packages
