"""SYNTHETIC Snowflake account usage for one year, shaped like the real SNOWFLAKE.ACCOUNT_USAGE views, with planted
cost problems as ground truth (fixed seed).

Writes parquet files named after the views they imitate (same column names, upper case as in Snowflake):
  warehouses.parquet                    SHOW WAREHOUSES: name, size, auto_suspend, resource_monitor, owner, created_on
  tag_references.parquet                TAG_REFERENCES: the COST_CENTER tag on each warehouse
  resource_monitors.parquet             RESOURCE_MONITORS: name, credit_quota, frequency
  warehouse_metering_history.parquet    WAREHOUSE_METERING_HISTORY: hourly credits per warehouse
  query_history.parquet                 QUERY_HISTORY: one row per query (a subset of columns)
  planted_*.csv                         the answer keys (never read by the detection models)

Scale: 165 warehouses, about 400,000 credits a year (1 Oct 2025 - 30 Sep 2026). Planted:
  - 8 cost spikes: one warehouse-day at 4-6x its normal credits (a runaway query or backfill)
  - 14 warehouses with no resource monitor (no spend cap)
  - 5 warehouses with auto-suspend at 3,600 s: they keep burning credits for an hour after the last query
  - 3 warehouses with no queries in the last 90 days that still exist (decommission candidates)

Usage: python ingestion/generate_snowflake_usage.py --out data/snowflake [--warehouses 165 --days 365]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 400
START = pd.Timestamp("2025-10-01")
SIZE_CREDITS = {"X-Small": 1, "Small": 2, "Medium": 4, "Large": 8, "X-Large": 16}
TEAMS = {"FINANCE": 0.16, "ACCOUNTING": 0.12, "RISK": 0.10, "MARKETING": 0.12, "PRODUCT": 0.12,
         "DATA_ENG": 0.18, "ML": 0.10, "SALES_OPS": 0.10}
WORKLOADS = ["REPORTING", "ELT", "ADHOC", "DBT", "BI", "ML_TRAIN", "SANDBOX", "APP"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path("data/snowflake"))
    ap.add_argument("--warehouses", type=int, default=165)
    ap.add_argument("--days", type=int, default=365)
    args = ap.parse_args()
    rng = np.random.default_rng(SEED)
    n, days = args.warehouses, args.days
    args.out.mkdir(parents=True, exist_ok=True)

    # warehouses
    teams = rng.choice(list(TEAMS), n, p=list(TEAMS.values()))
    names = [f"{t}_{rng.choice(WORKLOADS)}_WH_{i + 1:03d}" for i, t in enumerate(teams)]
    sizes = rng.choice(list(SIZE_CREDITS), n, p=[0.30, 0.30, 0.22, 0.13, 0.05])
    created = START - pd.to_timedelta(rng.integers(30, 900, n), unit="D")
    late = rng.random(n) < 0.08  # some warehouses are created during the year
    created = np.where(late, START + pd.to_timedelta(rng.integers(30, days - 60, n), unit="D"), created)
    created = pd.to_datetime(created)
    ids = np.arange(1, n + 1)
    idx = rng.permutation(n)
    no_monitor, idle_burn, unused = idx[:14], idx[14:19], idx[19:22]
    auto_suspend = rng.choice([60, 120, 300], n, p=[0.5, 0.3, 0.2])
    auto_suspend[idle_burn] = 3600
    monitors = [f"RM_{t}" for t in teams]
    for i in no_monitor:
        monitors[i] = None
    wh = pd.DataFrame({"WAREHOUSE_ID": ids, "NAME": names, "SIZE": sizes, "AUTO_SUSPEND": auto_suspend,
                       "AUTO_RESUME": True, "RESOURCE_MONITOR": monitors, "OWNER": [f"{t}_ADMIN" for t in teams],
                       "CREATED_ON": created})
    tags = pd.DataFrame({"OBJECT_NAME": names, "DOMAIN": "WAREHOUSE", "TAG_NAME": "COST_CENTER", "TAG_VALUE": teams})
    rm = pd.DataFrame({"NAME": sorted({m for m in monitors if m}), "FREQUENCY": "MONTHLY"})
    rm["CREDIT_QUOTA"] = rng.integers(3, 12, len(rm)) * 1000

    # daily active hours per warehouse: weekday level x day noise, weekends at 20%
    dates = pd.date_range(START, periods=days, freq="D")
    base = 1.9 * rng.lognormal(0.0, 0.7, n) * np.array([{1: 2.6, 2: 1.6, 4: 1.0, 8: 0.6, 16: 0.35}[SIZE_CREDITS[s]] for s in sizes])
    weekday = np.where(dates.day_of_week < 5, 1.0, 0.2)
    hours = base[:, None] * weekday[None, :] * rng.lognormal(0, 0.22, (n, days))
    active = (dates.values[None, :] >= created.values[:, None]).astype(float)
    active[unused, :] *= (dates.values[None, :] < dates.values[-90]).astype(float)  # unused: nothing in the last 90 days
    hours *= active
    # spikes go where they are possible and worth an alert: a 6x day must still fit in 20 metered hours, and a 4x day
    # must cost more than the 10-credit floor the detector uses
    size_cr = np.array([SIZE_CREDITS[s] for s in sizes])
    spiky = [w for w in idx[22:] if base[w] < 2.5 and base[w] * size_cr[w] >= 4 and not late[w]][:8]
    planted_spikes = []
    for w in spiky:
        candidates = np.where((active[w] > 0) & (dates.day_of_week < 5) & (np.arange(days) > 40) & (np.arange(days) < days - 1))[0]
        d = int(rng.choice(candidates))
        factor = float(rng.uniform(4, 6))
        hours[w, d] *= factor
        planted_spikes.append({"warehouse_name": names[w], "spike_date": dates[d].date(), "w": w, "d": d})
    hours = np.minimum(hours, 20.0)
    for p in planted_spikes:  # record the multiple actually planted, after the cap
        w, d = p.pop("w"), p.pop("d")
        prior = hours[w, max(0, d - 28):d]
        p["planted_multiple"] = round(float(hours[w, d] / np.median(prior)), 2)

    # hourly metering + queries. Activity sits in business hours (07:00-19:00) in contiguous blocks.
    meter = {"w": [], "t0": [], "used": [], "has_queries": []}
    for w in range(n):
        for d in np.nonzero(hours[w])[0]:
            h_total = hours[w, d]
            full = int(h_total)
            frac = h_total - full
            start_hour = int(rng.integers(7, max(8, 19 - full)))
            busy = [(start_hour + k, 1.0) for k in range(full)] + ([(start_hour + full, frac)] if frac > 0.05 else [])
            if not busy:
                continue
            if w in idle_burn:  # one extra metered hour after the last query, every active day
                busy.append((busy[-1][0] + 1, -1.0))
            for hour, f in busy:
                meter["w"].append(w)
                meter["t0"].append(dates[d] + pd.Timedelta(hours=hour % 24))
                meter["used"].append(abs(f))
                meter["has_queries"].append(f > 0)
    w_arr, used = np.array(meter["w"]), np.array(meter["used"])
    t0 = pd.DatetimeIndex(meter["t0"])
    size_arr = np.array([SIZE_CREDITS[s] for s in sizes])[w_arr]
    compute = np.round(size_arr * used, 6)
    cloud = np.round(compute * rng.uniform(0.03, 0.09, len(compute)), 6)
    metering = pd.DataFrame({"START_TIME": t0, "END_TIME": t0 + pd.Timedelta(hours=1), "WAREHOUSE_ID": ids[w_arr],
                             "WAREHOUSE_NAME": np.array(names)[w_arr], "CREDITS_USED": compute + cloud,
                             "CREDITS_USED_COMPUTE": compute, "CREDITS_USED_CLOUD_SERVICES": cloud})

    qmask = np.array(meter["has_queries"])
    q_per_hour = np.where(qmask, np.maximum(1, rng.poisson(14 * used)), 0)
    hour_of_q = np.repeat(np.arange(len(used)), q_per_hour)
    nq = len(hour_of_q)
    qw = w_arr[hour_of_q]
    starts = t0[hour_of_q] + pd.to_timedelta(rng.uniform(0, 3600, nq) * used[hour_of_q], unit="s")
    elapsed = rng.lognormal(9, 1.2, nq).astype(np.int64)
    queries = pd.DataFrame({
        "QUERY_ID": [f"01b{k:012x}" for k in range(nq)], "WAREHOUSE_ID": ids[qw],
        "WAREHOUSE_NAME": np.array(names)[qw], "WAREHOUSE_SIZE": sizes[qw], "START_TIME": starts,
        "END_TIME": starts + pd.to_timedelta(elapsed, unit="ms"), "TOTAL_ELAPSED_TIME": elapsed,
        "BYTES_SCANNED": rng.lognormal(18, 2, nq).astype(np.int64),
        "EXECUTION_STATUS": np.where(rng.random(nq) < 0.015, "FAIL", "SUCCESS"),
        "USER_NAME": [f"{t}_USER_{u}" for t, u in zip(teams[qw], rng.integers(1, 12, nq))],
        "ROLE_NAME": [f"{t}_ROLE" for t in teams[qw]]})

    for name, df in [("warehouses", wh), ("tag_references", tags), ("resource_monitors", rm),
                     ("warehouse_metering_history", metering), ("query_history", queries)]:
        df.to_parquet(args.out / f"{name}.parquet", index=False)
    pd.DataFrame(planted_spikes).to_csv(args.out / "planted_cost_spikes.csv", index=False)
    pd.DataFrame({"warehouse_name": [names[i] for i in no_monitor]}).to_csv(args.out / "planted_no_monitor.csv", index=False)
    pd.DataFrame({"warehouse_name": [names[i] for i in idle_burn]}).to_csv(args.out / "planted_idle_burn.csv", index=False)
    pd.DataFrame({"warehouse_name": [names[i] for i in unused]}).to_csv(args.out / "planted_unused.csv", index=False)
    print(f"{n} warehouses, {metering.CREDITS_USED.sum():,.0f} credits, {len(metering):,} metering hours, "
          f"{len(queries):,} queries (synthetic)")


if __name__ == "__main__":
    main()
