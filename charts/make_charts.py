"""README charts from the gold marts. Usage: python charts/make_charts.py [--db warehouse/platform.duckdb] [--out docs/charts]"""
import argparse
from pathlib import Path

import duckdb
import matplotlib.dates as mdates

import style as st

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--db", default=str(ROOT / "warehouse" / "platform.duckdb"))
ap.add_argument("--out", default=str(ROOT / "docs" / "charts"))
a = ap.parse_args()
OUT = Path(a.out)
con = duckdb.connect(a.db, read_only=True)

# 1. Warehouse spend by cost center and month
rows = con.execute("select cost_center, month, cost_usd::double from gold.rpt_cost_by_cost_center order by month").fetchall()
tot = {}
for cc, _, v in rows:
    tot[cc] = tot.get(cc, 0) + v
top = sorted(tot, key=tot.get, reverse=True)[:4]
months = sorted({r[1] for r in rows})
f, ax = st.fig(8, 3.4)
bottom = [0.0] * len(months)
for i, cc in enumerate(top + ["All other cost centers"]):
    v = [sum(x for c, m, x in rows if m == mo and (c == cc or (cc == "All other cost centers" and c not in top))) / 1e3
         for mo in months]
    ax.bar(months, v, width=22, bottom=bottom, color=(st.S + [st.MUTED])[i], label=cc.replace("_", " ").title() if cc.isupper() else cc, edgecolor=st.SURFACE, linewidth=1)
    bottom = [b + y for b, y in zip(bottom, v)]
ax.yaxis.set_major_formatter(st.FuncFormatter(lambda v, _: f"${v:,.0f}k"))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
grand = sum(tot.values())
st.head(ax, f"\\${grand / 1e6:,.2f}M of warehouse spend a year, {tot[top[0]] / grand:.0%} of it in {top[0].replace('_', ' ').title()}",
        "Snowflake credits by tagged cost center and month, priced per credit (synthetic ACCOUNT_USAGE)", legend=True, ncol=5)
st.save(f, OUT / "cost_by_cost_center.png")

# 2. The largest detected cost spike in context
s = con.execute("""select warehouse_name, spike_date, credits::double, baseline_credits::double, multiple::double
                   from gold.rpt_cost_spikes order by excess_cost_usd desc limit 1""").fetchone()
n = con.execute("select count(*) from gold.rpt_cost_spikes").fetchone()[0]
d = con.execute("""select usage_date, credits::double from gold.fct_warehouse_daily_credits
                   where warehouse_name = ? and usage_date between ?::date - 45 and ?::date + 20 order by usage_date""",
                [s[0], s[1], s[1]]).fetchall()
f, ax = st.fig(8, 3.2)
ax.plot([r[0] for r in d], [r[1] for r in d], color=st.S[0], lw=2, label="Daily credits")
ax.axhline(s[3] * 3, color=st.MUTED, lw=1, ls="--", label="Alert line on that day: 3x its 28-day median")
ax.scatter([s[1]], [s[2]], s=60, color=st.S[1], zorder=3, label=f"Flagged: {s[4]:.1f}x its median")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
ax.set_ylim(0, max(r[1] for r in d) * 1.15)
ax.set_ylabel("Credits per day")
st.head(ax, f"Each warehouse is judged against its own baseline: {n} spikes found, all planted, none false",
        f"Warehouse {s[0]}, the largest spike by excess cost", legend=True, ncol=3)
st.save(f, OUT / "cost_spike.png")
print(f"wrote charts to {OUT}")
