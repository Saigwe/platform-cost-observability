# Data Platform Cost & Reliability Monitor

[![CI](https://github.com/Saigwe/platform-cost-observability/actions/workflows/ci.yml/badge.svg)](https://github.com/Saigwe/platform-cost-observability/actions/workflows/ci.yml)
[![Daily](https://github.com/Saigwe/platform-cost-observability/actions/workflows/daily.yml/badge.svg)](https://github.com/Saigwe/platform-cost-observability/actions/workflows/daily.yml)

> The three things a data platform lead checks every morning, in one dbt project: did the pipelines run (real GitHub Actions history across all my repos), what is the warehouse costing and where is it wasted (Snowflake account usage), and will month-end close have the data it needs (Fivetran connector health). A daily job collects, rebuilds and publishes a digest.

**Author:** Stanley Igwe, Lead Data (Analytics) Engineer · [Portfolio](https://saigwe.github.io)
**Stack:** Python · DuckDB · dbt Core · [dbt-trust-tests](https://github.com/Saigwe/dbt-trust-tests) · GitHub REST API · GitHub Actions (CI + daily schedule) · Slack webhook
**Status:** ✅ Built. `dbt build` 48/48, pytest 4/4. The daily job keeps collecting real CI history.

Based on work I did as an independent consultant for a US food-delivery company: Snowflake cost intelligence across about 400k credits and 165 warehouses (flagging 300% cost spikes and missing spend caps), and health monitoring for about 470 Fivetran connectors with month-end close alerts. This repo rebuilds it: the CI part on my own **real** GitHub Actions history, the Snowflake and Fivetran parts on **synthetic** data shaped exactly like their system tables, with planted problems as ground truth. No employer data, code or logic is used.

---

## 90-second summary
| | |
|---|---|
| **Problem** | Warehouse bills grow quietly, nobody notices a connector that stopped syncing until finance can't close the month, and CI failures sit red for days. Each lives in a different console. |
| **What I built** | Incremental collection of every GitHub Actions run and job across my repos; generators for Snowflake `ACCOUNT_USAGE` and Fivetran Platform Connector tables with planted cost spikes, uncapped warehouses, idle burn, unused warehouses, connector outages and close-window failures; dbt models that detect each one; a daily digest. |
| **Why it matters** | One morning report: what's red, what costs too much and why, and which close-critical feed is down, ranked by money or by risk to the books. |
| **Proof** | Every detector finds **exactly** the planted problems (an answer-key test per detector, from my own test package), and a lineage test proves no model reads the answers. On real CI: 132 runs across 22 repos, 79.5% green, failures fixed in 0.34 hours on average, and 3 older repos still red. See [Numbers](#numbers). |

## Architecture
```mermaid
flowchart LR
  GH[GitHub REST API<br/>REAL runs + jobs, all repos] -->|collect_github_actions.py<br/>incremental, 2-day overlap| J[(data/github<br/>jsonl, kept on the data branch)]
  SG[generate_snowflake_usage.py<br/>SYNTHETIC ACCOUNT_USAGE + planted problems] --> P[(parquet)]
  FG[generate_fivetran_logs.py<br/>SYNTHETIC CONNECTOR + LOG + planted incidents] --> P
  J --> B[(DuckDB bronze)]
  P --> B
  P -.answer keys.-> AK[(answer_key schema<br/>tests only)]
  B -->|dbt staging| S[(silver)]
  S -->|dbt marts| G[(gold: CI reliability, daily credits,<br/>spikes, governance gaps, incidents, close alerts)]
  AK -.trust_tests.matches_answer_key.-> G
  G --> D[daily_digest.py<br/>markdown + Slack]
  D --> OL[(ops-log branch)]
```

## Data
| Source | Shaped like | Rows | Real or synthetic |
|---|---|---:|---|
| GitHub Actions runs, all public repos of Saigwe | GitHub REST API `actions/runs` | 141 runs (and growing daily) | **Real** |
| GitHub Actions jobs | `actions/runs/{id}/jobs` | 261 jobs (collected in Actions, with the workflow token) | **Real** |
| Snowflake warehouses, tags, resource monitors | `SHOW WAREHOUSES`, `TAG_REFERENCES`, `RESOURCE_MONITORS` | 165 warehouses, 8 monitors | Synthetic |
| Snowflake metering | `ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY` | 200,633 hours, 386,721 credits | Synthetic |
| Snowflake queries | `ACCOUNT_USAGE.QUERY_HISTORY` | 2,413,268 queries | Synthetic |
| Fivetran connectors and logs | Platform Connector `CONNECTOR`, `LOG` | 470 connectors, 2,972,712 log rows | Synthetic |

Planted ground truth, in the `answer_key` schema: 8 cost spikes (4.6–7.3x), 14 warehouses with no resource monitor, 5 with a one-hour auto-suspend, 3 unused for 90 days, 16 connector incidents (including 2 paused connectors), and 8 resulting close alerts. Organic noise is there too: day-to-day cost variation, 0.4% of syncs failing at random, quiet weekends, warehouses created mid-year.

## Data model (gold)
| Model | Grain | What it answers |
|---|---|---|
| `rpt_ci_reliability` | repo | Runs on main, success rate, median and p90 duration, average hours from a failure to the next green run, failures still red |
| `fct_warehouse_daily_credits` | warehouse × day | Credits, dollars, queries, and idle hours (metered with no query running) |
| `rpt_cost_spikes` | warehouse × day | Days at ≥3x the warehouse's own 28-day median and over 10 credits, with the excess in dollars |
| `rpt_governance_gaps` | warehouse × issue | No spend cap; idle burn (≥10% of hours idle and ≥100 credits a year); no queries in 90 days |
| `rpt_cost_by_cost_center` | cost center × month | Spend, idle share, cost per query |
| `rpt_connector_incidents` | connector × incident | No successful sync for longer than max(3.5 sync intervals, 3 hours) |
| `rpt_close_alerts` | connector × close month | Incidents on close-critical connectors overlapping a close window (last 2 business days to the 3rd business day) |
| `rpt_connector_health` | connector | Success rate, incidents, worst stretch without a successful sync |

## Tests
- **Answer keys** (`trust_tests.matches_answer_key`): spikes (warehouse and date), uncapped, idle-burning and unused warehouses, connector incidents and close alerts. Each must match exactly: no misses, no false alarms.
- **Lineage guard:** `assert_detection_never_reads_answer_key` walks the dbt graph and fails if any model depends on the answer keys.
- **Reconciliation** (`trust_tests.reconciles_to`): daily credits and metered hours tie back to the hourly metering, warehouse by warehouse.
- **Grain** (`trust_tests.unique_combination`) on every report; keys, relationships and accepted values in staging.
- **pytest:** the collector's merge keeps one row per id with the latest version winning; the close-window calendar; every planted problem detected and nothing else; real CI history loaded.

## Numbers
From `make all` on 26 Oct 2026.

**CI reliability (real, all my public repos, runs on main)**

| Metric | Value |
|---|---|
| Repos with Actions history / runs | 22 / 132 |
| Success rate | 79.5% (27 failed runs) |
| Median run duration (median across repos) | 0.9 min |
| Average time from a failure to the next green run | 0.34 hours |
| Billable minutes / average queue time | 348 minutes across 261 jobs; 3.9 s queue. The portfolio site uses the most (97) |
| Repos still red on main | 3 older repos: `ae_clone_dbt` and `ae_stanley_igwe_monzo` have never passed; `ae_stanley_tasks` has been red since its last 2 failures |

**Warehouse cost (synthetic, at an assumed $3.00 per credit)**

| Metric | Value |
|---|---|
| Spend over the year | 386,721 credits, $1.16M, 165 warehouses |
| Largest cost centers | Finance 19.2%, Data Engineering 16.5%, Product 13.4% |
| Cost spikes found | 8 of 8 planted, 0 false alarms; $782 of excess on those days |
| No spend cap | 14 warehouses, 35,386 credits a year uncapped ($106k) |
| Idle burn | 5 warehouses, 6,188 credits ($18.6k) spent with no query running |
| Unused 90 days | 3 warehouses to decommission |

**Connectors (synthetic)**

| Metric | Value |
|---|---|
| Connectors / syncs | 470 / 1,486,356, 99.6% successful |
| Incidents found | 16 of 16 planted, 0 false alarms |
| Month-end close alerts | 8 of 8 planted: 6 failing feeds and 2 paused ones, on ledger, payments and procurement connectors |

| Pipeline | Value |
|---|---|
| dbt | 15 models, 33 data tests: 48/48 pass in 20 s |
| Generators + load | about 40 s for 5.6M synthetic rows |

## What the tests caught while I built it
- The first connector rule (3 sync intervals without success) found all 16 incidents but also raised 7 false alarms: hourly connectors with two random failures in a row. At a 0.4% failure rate that's expected about 10 times a year. Requiring 3.5 intervals (three failures in a row) removed them.
- The first idle rule (25% of metered hours idle) found 1 of 5 idle burners. Busy warehouses dilute the share even when they waste 380+ credits a year, so the rule now needs 10% idle and 100 credits.
- An off-by-one on the 90-day boundary missed all 3 unused warehouses.
- My own reconciliation test config counted daily rows instead of summing hours; the test failed on 159 warehouses until I fixed it.
- One planted spike couldn't physically happen (a 5.7x day on a warehouse already near 20 hours), and another was a $28 blip below the alert floor. The generator now plants only spikes that are possible and worth an alert, and records the multiple actually planted.

Tuning detectors on planted data risks fitting the answer key. Each change above follows a stated rule (three failures in a row, a money floor, an inclusive boundary) rather than a number chosen to make the test pass, and the reasons are recorded here.

## Daily job
`.github/workflows/daily.yml` runs at 06:30 UTC: it restores the collected history from the `data` branch, collects new runs and jobs with the workflow's token, rebuilds everything, writes the digest, and pushes the history back to `data` and the digest to [`ops-log`](https://github.com/Saigwe/platform-cost-observability/tree/ops-log/digests). With a `SLACK_WEBHOOK_URL` secret it also posts a one-line summary.

## How to run
Requires **Python 3.12** (what CI uses) and `make`, or run the commands in the `Makefile` by hand.
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export GITHUB_TOKEN=...      # optional; without it run `make all JOBS=--no-jobs` (60 API calls an hour)
make all
```

## Roadmap
- [x] Real CI history: incremental collector, reliability mart, daily schedule with history kept on a branch
- [x] Snowflake cost: daily credits, spikes, governance gaps, cost centers, idle burn, with answer keys
- [x] Fivetran health: incidents, month-end close alerts, with answer keys
- [x] Daily digest to a branch, optional Slack
- [ ] Point it at a real Snowflake account (`ACCOUNT_USAGE` views) and a real Fivetran Platform Connector
- [x] Job-level minutes and queue time by repo
- [ ] 3-minute Loom walkthrough ([script ready](docs/walkthrough.md))

## Data and licence
- **GitHub Actions history:** my own public repositories, via the GitHub REST API.
- **Snowflake and Fivetran data:** synthetic, generated with fixed seeds; column names follow the vendors' documented system tables. No real account is described.
- **Code:** MIT (see `LICENSE`).
