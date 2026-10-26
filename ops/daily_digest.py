"""The morning digest a platform lead reads: what broke, what costs too much, and what threatens month-end close.

Reads the gold tables and writes a short markdown report (and posts it to Slack when SLACK_WEBHOOK_URL is set).
Sections stay empty-but-present on a quiet day, so "nothing to do" is visible rather than a missing report.

Usage: python ops/daily_digest.py --db warehouse/platform.duckdb --out ops-log/digests [--as-of 2026-09-30]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import urllib.request
from pathlib import Path

import duckdb


def table(rows: list[tuple], headers: list[str]) -> str:
    if not rows:
        return "_None._\n"
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join("" if v is None else str(v) for v in r) + " |" for r in rows]
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="warehouse/platform.duckdb")
    ap.add_argument("--out", type=Path, default=Path("ops-log/digests"))
    ap.add_argument("--as-of", type=dt.date.fromisoformat, default=None,
                    help="the day the digest is for (default: the last day of synthetic usage data)")
    ap.add_argument("--lookback-days", type=int, default=7)
    args = ap.parse_args()
    con = duckdb.connect(args.db, read_only=True)
    as_of = args.as_of or con.execute("select max(usage_date) from gold.fct_warehouse_daily_credits").fetchone()[0]
    since = as_of - dt.timedelta(days=args.lookback_days)

    ci_red = con.execute("""select repo, failed_runs, failures_still_red, round(success_rate * 100, 1)
                            from gold.rpt_ci_reliability where failures_still_red > 0 order by repo""").fetchall()
    ci = con.execute("""select count(*), sum(runs), sum(failed_runs) from gold.rpt_ci_reliability""").fetchone()
    spikes = con.execute("""select spike_date, warehouse_name, cost_center, credits, multiple, excess_cost_usd
                            from gold.rpt_cost_spikes where spike_date > ? and spike_date <= ?
                            order by excess_cost_usd desc""", [since, as_of]).fetchall()
    gaps = con.execute("""select issue, count(*), round(sum(credits_at_stake)) from gold.rpt_governance_gaps
                          group by issue order by issue""").fetchall()
    close = con.execute("""select close_month, connector_id, connector_type, symptom, hours_without_success
                           from gold.rpt_close_alerts order by incident_start_at desc limit 10""").fetchall()
    month = con.execute("""select round(sum(cost_usd)), round(sum(idle_credits) / sum(credits) * 100, 1)
                           from gold.fct_warehouse_daily_credits
                           where date_trunc('month', usage_date) = date_trunc('month', cast(? as date))""", [as_of]).fetchone()

    md = [f"# Platform digest, {dt.date.today()}", "",
          f"CI figures are live. Snowflake and Fivetran figures are synthetic, up to {as_of}.", "",
          f"**CI (real, all repos):** {ci[0]} repos, {ci[1]} runs on main, {ci[2]} failed. "
          f"{len(ci_red)} repo(s) still red after their last failure.", "",
          "## CI still red", table(ci_red, ["Repo", "Failed runs", "Failures not yet fixed", "Success rate %"]),
          f"## Cost spikes in the last {args.lookback_days} days (synthetic Snowflake data)",
          table(spikes, ["Date", "Warehouse", "Cost center", "Credits", "x median", "Excess $"]),
          f"Month to date: ${month[0]:,.0f}, {month[1]}% of credits burned idle.", "",
          "## Governance gaps (open)", table(gaps, ["Issue", "Warehouses", "Credits at stake (year)"]),
          "## Month-end close alerts (synthetic Fivetran data, latest 10)",
          table(close, ["Close month", "Connector", "Type", "Symptom", "Hours without success"])]
    text = "\n".join(md)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"digest_{as_of}.md").write_text(text, encoding="utf-8")
    (args.out / "latest.md").write_text(text, encoding="utf-8")
    print(text)

    hook = os.environ.get("SLACK_WEBHOOK_URL")
    if hook:
        body = json.dumps({"text": f"Platform digest {as_of}: {len(ci_red)} repos red, {len(spikes)} cost spikes, "
                                   f"{len(close)} close alerts. Full report in ops-log."}).encode()
        urllib.request.urlopen(urllib.request.Request(hook, data=body, headers={"Content-Type": "application/json"}),
                               timeout=30)


if __name__ == "__main__":
    main()
