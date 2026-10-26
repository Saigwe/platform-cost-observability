"""Collector merge logic, close-window calendar, and checks on a finished run (PLATFORM_DB)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ingestion"))
from collect_github_actions import merge  # noqa: E402
from generate_fivetran_logs import close_windows  # noqa: E402

DB = os.environ.get("PLATFORM_DB", str(ROOT / "warehouse" / "platform.duckdb"))


def test_merge_keeps_one_row_per_id_and_the_latest_version_wins(tmp_path):
    path = tmp_path / "runs.jsonl"
    merge(path, [{"id": 1, "status": "in_progress"}, {"id": 2, "status": "completed"}])
    added = merge(path, [{"id": 1, "status": "completed"}, {"id": 3, "status": "queued"}])
    rows = {r["id"]: r for r in map(json.loads, path.read_text().splitlines())}
    assert added == 1 and len(rows) == 3 and rows[1]["status"] == "completed"


def test_close_window_is_last_two_business_days_to_third_business_day():
    w = close_windows().set_index("close_month").loc["2026-04"]
    assert w.window_start == pd.Timestamp("2026-04-29")   # Wed 29, Thu 30 April
    assert w.window_end == pd.Timestamp("2026-05-06")     # Fri 1, Mon 4, Tue 5 May, exclusive end


def test_every_planted_problem_is_detected_and_nothing_else():
    con = duckdb.connect(DB, read_only=True)
    pairs = {
        "cost_spikes": "select warehouse_name from gold.rpt_cost_spikes",
        "no_monitor": "select warehouse_name from gold.rpt_governance_gaps where issue = 'no_resource_monitor'",
        "idle_burn": "select warehouse_name from gold.rpt_governance_gaps where issue = 'idle_burn'",
        "unused": "select warehouse_name from gold.rpt_governance_gaps where issue = 'unused_90_days'",
        "incidents": "select connector_id from gold.rpt_connector_incidents",
    }
    for key, sql in pairs.items():
        col = "connector_id" if key == "incidents" else "warehouse_name"
        planted = {r[0] for r in con.execute(f"select {col} from answer_key.{key}").fetchall()}
        found = {r[0] for r in con.execute(sql).fetchall()}
        assert found == planted, key


def test_real_ci_history_is_loaded():
    con = duckdb.connect(DB, read_only=True)
    assert con.execute("select count(*) from gold.rpt_ci_reliability").fetchone()[0] > 0
