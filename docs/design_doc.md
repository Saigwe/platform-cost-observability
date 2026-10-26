# Design doc: Data Platform Cost & Reliability Monitor

| | |
|---|---|
| **Author** | Stanley Igwe |
| **Status** | Built; daily job running |
| **Last updated** | 26 Oct 2026 |

## 1. Problem and users
- **Users:** the data platform lead, the finance systems owner, and engineers on call.
- **Questions:** Is anything red? Which warehouse costs too much this week, and why? Which spend has no cap? Is any feed finance needs for close down?
- **Current pain:** three consoles (CI, warehouse, ingestion), no shared definitions, and month-end surprises.

## 2. Requirements
| Type | Requirement |
|---|---|
| Functional | CI reliability per repo; daily cost per warehouse and cost center; spike, idle, uncapped and unused detection; connector incidents; close alerts; a daily digest |
| Correctness | Each detector finds exactly the planted problems; no detector may read the answers; daily credits tie to hourly metering |
| Freshness | Daily by 07:00 UTC; the collector re-reads the last 2 days so late and re-run results are caught |
| Scale | 5.6M synthetic rows build in about 20 s on DuckDB. Real Snowflake `ACCOUNT_USAGE` would be read incrementally on `START_TIME` |
| Cost | £0: public-repo Actions minutes are free; DuckDB |

## 3. Design
- **Real where I can get it, faithful synthetic where I can't.** My CI history is real and public. A real Snowflake bill or Fivetran account isn't, so the generators use the vendors' table and column names, which means the dbt models would point at real views with only source changes.
- **Answer keys plus a lineage guard.** Planted problems live in a separate `answer_key` schema. `trust_tests.matches_answer_key` fails on any miss or false alarm, and a graph test fails if a model reads that schema.
- **Detectors are explainable rules, each stated in business terms:** three failed syncs in a row; three times the warehouse's own median and worth more than 10 credits; 10% idle and 100 credits a year; nothing run in 90 days.
- **Idle hours from overlap, not start times.** A metered hour is idle only if no query was running in it, by expanding each query to the hours it spans. Counting query starts would call a long-running hour idle.
- **Incremental collection with overlap.** Per-repo watermark minus 2 days, merged on id with the latest version winning, so a run that finishes or is re-run later replaces its earlier state.
- **State on branches.** The daily job keeps collected history on `data` and digests on `ops-log`, the same pattern as my load-forecasting project, so no external storage is needed.

## 4. Options considered
| Decision | Options | Chosen | Why |
|---|---|---|---|
| Spike baseline | Fixed budget / 7-day mean / 28-day median | 28-day median, zeros included | Robust to the spike itself and to quiet weekends |
| Connector staleness | Any failure / k failures / time without success | Time without success > max(3.5 intervals, 3 h) | Works for 15-minute and daily connectors alike, and catches paused connectors with no failures |
| Close calendar | Calendar days / business days | Business days | Close follows the working calendar |
| CI cost | Estimate $ / minutes only | Minutes only | Public-repo minutes are free; a dollar figure would be invented |

## 5. Results
All detectors match their answer keys exactly (see README). Four detector changes were needed while building, each recorded in the README with its reason, plus one generator fix so planted spikes are physically possible and material.

## 6. Risks and next steps
- **Overfitting to planted data:** mitigated by stating each rule in business terms before checking it, and by keeping organic noise in the generators. A real account is the real test.
- **Next:** point the sources at a real Snowflake account and Fivetran Platform Connector; add job-minute cost by repo once jobs accumulate; alert routing by owner role.
