"""Load every source into DuckDB, unchanged.

  bronze.github_repos / github_runs / github_jobs   REAL, from collect_github_actions.py (jsonl)
  bronze.sf_*                                       SYNTHETIC Snowflake ACCOUNT_USAGE-shaped tables (parquet)
  bronze.ft_connector / ft_log                      SYNTHETIC Fivetran Platform Connector-shaped tables (parquet)
  config.close_critical_connectors / close_windows  the business's own lists (CSV)
  answer_key.*                                      planted ground truth, read only by tests

Full refresh: the files are the system of record, so a rerun is idempotent.

Usage: python ingestion/load.py --data data --db warehouse/platform.duckdb
"""
from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

GITHUB_EMPTY = {
    "github_runs": "id bigint, repo varchar, name varchar, path varchar, event varchar, status varchar, conclusion varchar, "
                   "head_branch varchar, head_sha varchar, run_number bigint, run_attempt bigint, created_at varchar, "
                   "updated_at varchar, run_started_at varchar, workflow_id bigint, html_url varchar",
    "github_jobs": "id bigint, repo varchar, run_id bigint, run_attempt bigint, name varchar, status varchar, "
                   "conclusion varchar, created_at varchar, started_at varchar, completed_at varchar, labels varchar[], "
                   "runner_name varchar, html_url varchar",
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument("--db", default="warehouse/platform.duckdb")
    args = ap.parse_args()
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(args.db)
    for schema in ("bronze", "config", "answer_key"):
        con.execute(f"create schema if not exists {schema}")

    gh = args.data / "github"
    for name, file in (("github_repos", "repos.jsonl"), ("github_runs", "runs.jsonl"), ("github_jobs", "jobs.jsonl")):
        path = gh / file
        if path.exists() and path.stat().st_size:
            con.execute(f"create or replace table bronze.{name} as select * from read_json_auto('{path.as_posix()}', "
                        "format = 'newline_delimited', union_by_name = true)")
        else:
            con.execute(f"create or replace table bronze.{name} ({GITHUB_EMPTY.get(name, 'id bigint, name varchar')})")

    sf, ft = args.data / "snowflake", args.data / "fivetran"
    for f in sorted(sf.glob("*.parquet")):
        con.execute(f"create or replace table bronze.sf_{f.stem} as select * from read_parquet('{f.as_posix()}')")
    for f in sorted(ft.glob("*.parquet")):
        con.execute(f"create or replace table bronze.ft_{f.stem} as select * from read_parquet('{f.as_posix()}')")
    for name in ("close_critical_connectors", "close_windows"):
        con.execute(f"create or replace table config.{name} as select * from read_csv_auto('{(ft / (name + '.csv')).as_posix()}')")
    for f in sorted([*sf.glob("planted_*.csv"), *ft.glob("planted_*.csv")]):
        con.execute(f"create or replace table answer_key.{f.stem.removeprefix('planted_')} as "
                    f"select * from read_csv_auto('{f.as_posix()}')")

    for schema in ("bronze", "config", "answer_key"):
        for (t,) in con.execute(f"select table_name from information_schema.tables where table_schema = '{schema}' "
                                "order by 1").fetchall():
            print(f"{schema}.{t:<34} {con.execute(f'select count(*) from {schema}.{t}').fetchone()[0]:>10,} rows")


if __name__ == "__main__":
    main()
