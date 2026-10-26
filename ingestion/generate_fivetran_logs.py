"""SYNTHETIC Fivetran connector activity for six months, shaped like the Fivetran Platform Connector tables, with
planted incidents as ground truth (fixed seed).

Writes parquet files named after the tables they imitate (column names as in the Platform Connector):
  connector.parquet   CONNECTOR_ID, CONNECTOR_NAME, CONNECTOR_TYPE_ID, DESTINATION_ID, SYNC_FREQUENCY (minutes), PAUSED
  log.parquet         ID, TIME_STAMP, CONNECTOR_ID, EVENT, MESSAGE_EVENT (sync_start / sync_end), MESSAGE_DATA (JSON)
  close_critical_connectors.csv   which connectors feed month-end close (the business's own list, used by dbt)
  planted_*.csv                   the answer keys (never read by the detection models)

Scale: 470 connectors, 1 Apr - 30 Sep 2026. Organic noise: 0.4% of syncs fail at random, singly. Planted:
  - 16 incidents: a connector fails every sync for 20-36 hours (6 close-critical connectors inside a month-end close
    window, 4 other connectors inside a window, 4 close-critical connectors outside any window) plus 2 close-critical
    connectors paused for a whole close window
  - so 8 close alerts are expected: (connector, close month) pairs

Usage: python ingestion/generate_fivetran_logs.py --out data/fivetran
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 470
START, END = pd.Timestamp("2026-04-01"), pd.Timestamp("2026-10-01")
TYPES = {"netsuite_suiteanalytics": 1, "stripe": 1, "adyen": 1, "plaid": 1, "workday": 1, "coupa": 1,
         "salesforce": 0, "hubspot": 0, "zendesk": 0, "postgres": 0, "mysql": 0, "google_sheets": 0, "s3": 0,
         "google_ads": 0, "facebook_ads": 0, "jira": 0, "greenhouse": 0, "snowflake": 0}
FREQ = [15, 60, 360, 1440]


def close_windows() -> pd.DataFrame:
    """Month-end close: the last 2 business days of a month through the 3rd business day of the next."""
    rows = []
    for month_end in pd.date_range("2026-03-31", "2026-09-30", freq="ME"):
        bdays_before = pd.bdate_range(month_end - pd.Timedelta(days=10), month_end)[-2:]
        bdays_after = pd.bdate_range(month_end + pd.Timedelta(days=1), month_end + pd.Timedelta(days=10))[:3]
        rows.append({"close_month": month_end.strftime("%Y-%m"), "window_start": bdays_before[0],
                     "window_end": bdays_after[-1] + pd.Timedelta(days=1)})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path("data/fivetran"))
    ap.add_argument("--connectors", type=int, default=470)
    args = ap.parse_args()
    rng = np.random.default_rng(SEED)
    n = args.connectors
    args.out.mkdir(parents=True, exist_ok=True)

    types = list(TYPES)
    finance = [t for t in types if TYPES[t]]
    ctype = rng.choice(types, n, p=np.where([TYPES[t] for t in types], 0.12 / len(finance), 0.88 / (len(types) - len(finance))))
    ids = [f"conn_{i:04d}" for i in range(n)]
    freq = rng.choice(FREQ, n, p=[0.08, 0.32, 0.30, 0.30])
    critical = np.array([TYPES[t] == 1 for t in ctype]) & (rng.random(n) < 0.9)
    connectors = pd.DataFrame({"CONNECTOR_ID": ids, "CONNECTOR_NAME": [f"{t}_{i:03d}" for i, t in enumerate(ctype)],
                               "CONNECTOR_TYPE_ID": ctype, "DESTINATION_ID": "snowflake_prod",
                               "SYNC_FREQUENCY": freq, "PAUSED": False})
    windows = close_windows()
    windows_in = windows[(windows.window_start >= START) & (windows.window_end <= END)].reset_index(drop=True)

    # planted incidents: (connector index, start, hours, kind)
    eligible = np.where(freq <= 360)[0]
    crit, other = [i for i in eligible if critical[i]], [i for i in eligible if not critical[i]]
    rng.shuffle(crit)
    rng.shuffle(other)
    incidents, close_alerts = [], []

    def inside_window(w):
        span = (w.window_end - w.window_start).total_seconds() / 3600
        return w.window_start + pd.Timedelta(hours=float(rng.uniform(2, span - 40)))

    for i in crit[:6]:
        w = windows_in.iloc[int(rng.integers(len(windows_in)))]
        incidents.append((i, inside_window(w), float(rng.uniform(20, 36)), "failing"))
        close_alerts.append({"connector_id": ids[i], "close_month": w.close_month})
    for i in other[:4]:
        w = windows_in.iloc[int(rng.integers(len(windows_in)))]
        incidents.append((i, inside_window(w), float(rng.uniform(20, 36)), "failing"))
    for i in crit[6:10]:
        start = pd.Timestamp("2026-04-14") + pd.Timedelta(days=int(rng.integers(0, 10)), hours=int(rng.integers(0, 24)))
        start += pd.Timedelta(days=30 * int(rng.integers(0, 5)))
        incidents.append((i, start, float(rng.uniform(20, 36)), "failing"))
    for i in crit[10:12]:
        w = windows_in.iloc[int(rng.integers(len(windows_in)))]
        hours = (w.window_end - w.window_start).total_seconds() / 3600
        incidents.append((i, w.window_start, hours, "paused"))
        close_alerts.append({"connector_id": ids[i], "close_month": w.close_month})

    frames = []
    for c in range(n):
        step = pd.Timedelta(minutes=int(freq[c]))
        times = pd.date_range(START + pd.Timedelta(minutes=float(rng.uniform(0, freq[c]))), END, freq=step)
        times = times + pd.to_timedelta(rng.uniform(0, 0.1 * freq[c], len(times)), unit="m")
        status = np.where(rng.random(len(times)) < 0.004, "FAILURE_WITH_TASK", "SUCCESSFUL")
        keep = np.ones(len(times), dtype=bool)
        for i, start, hours, kind in incidents:
            if i != c:
                continue
            in_inc = (times >= start) & (times < start + pd.Timedelta(hours=hours))
            if kind == "failing":
                status[in_inc] = "FAILURE_WITH_TASK"
            else:
                keep &= ~in_inc
        times, status = times[keep], status[keep]
        dur = pd.to_timedelta(rng.lognormal(1.6, 0.8, len(times)), unit="m")
        frames.append(pd.DataFrame({"CONNECTOR_ID": ids[c], "start": times, "end": times + dur, "status": status}))
    syncs = pd.concat(frames, ignore_index=True)
    starts = pd.DataFrame({"TIME_STAMP": syncs.start, "CONNECTOR_ID": syncs.CONNECTOR_ID, "EVENT": "INFO",
                           "MESSAGE_EVENT": "sync_start", "MESSAGE_DATA": None})
    ends = pd.DataFrame({"TIME_STAMP": syncs.end, "CONNECTOR_ID": syncs.CONNECTOR_ID,
                         "EVENT": np.where(syncs.status == "SUCCESSFUL", "INFO", "SEVERE"), "MESSAGE_EVENT": "sync_end",
                         "MESSAGE_DATA": [json.dumps({"status": s}) for s in syncs.status]})
    log = pd.concat([starts, ends], ignore_index=True).sort_values(["TIME_STAMP", "CONNECTOR_ID"]).reset_index(drop=True)
    log.insert(0, "ID", [f"log_{k:09d}" for k in range(len(log))])

    connectors.to_parquet(args.out / "connector.parquet", index=False)
    log.to_parquet(args.out / "log.parquet", index=False)
    pd.DataFrame({"connector_id": [ids[i] for i in np.where(critical)[0]]}).to_csv(
        args.out / "close_critical_connectors.csv", index=False)
    pd.DataFrame([{"connector_id": ids[i], "incident_date": s.date(), "kind": k, "hours": round(h, 1)}
                  for i, s, h, k in incidents]).to_csv(args.out / "planted_incidents.csv", index=False)
    pd.DataFrame(close_alerts).to_csv(args.out / "planted_close_alerts.csv", index=False)
    windows.to_csv(args.out / "close_windows.csv", index=False)
    print(f"{n} connectors ({int(critical.sum())} close-critical), {len(syncs):,} syncs, {len(log):,} log rows, "
          f"{len(incidents)} planted incidents, {len(close_alerts)} planted close alerts (synthetic)")


if __name__ == "__main__":
    main()
