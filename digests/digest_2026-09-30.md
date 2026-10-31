# Platform digest, 2026-10-31

CI figures are live. Snowflake and Fivetran figures are synthetic, up to 2026-09-30.

**CI (real, all repos):** 45 repos, 209 runs on main, 30 failed. 3 repo(s) still red after their last failure.

## CI still red
| Repo | Failed runs | Failures not yet fixed | Success rate % |
|---|---|---|---|
| ae_clone_dbt | 4 | 4 | 0.0 |
| ae_stanley_igwe_monzo | 9 | 9 | 0.0 |
| ae_stanley_tasks | 3 | 2 | 50.0 |

## Cost spikes in the last 7 days (synthetic Snowflake data)
| Date | Warehouse | Cost center | Credits | x median | Excess $ |
|---|---|---|---|---|---|
| 2026-09-29 | DATA_ENG_DBT_WH_029 | DATA_ENG | 29.76 | 6.6 | 75.8 |

Month to date: $102,303, 1.5% of credits burned idle.

## Governance gaps (open)
| Issue | Warehouses | Credits at stake (year) |
|---|---|---|
| idle_burn | 5 | 6188.0 |
| no_resource_monitor | 14 | 35386.0 |
| unused_90_days | 3 | 5044.0 |

## Month-end close alerts (synthetic Fivetran data, latest 10)
| Close month | Connector | Type | Symptom | Hours without success |
|---|---|---|---|---|
| 2026-07 | conn_0280 | adyen | no syncs at all (paused or not scheduled) | 168.9 |
| 2026-06 | conn_0004 | coupa | syncs failing | 30.0 |
| 2026-06 | conn_0451 | coupa | syncs failing | 36.4 |
| 2026-06 | conn_0257 | adyen | syncs failing | 22.3 |
| 2026-05 | conn_0302 | netsuite_suiteanalytics | syncs failing | 30.4 |
| 2026-05 | conn_0207 | adyen | no syncs at all (paused or not scheduled) | 168.9 |
| 2026-04 | conn_0295 | adyen | syncs failing | 29.1 |
| 2026-04 | conn_0159 | coupa | syncs failing | 36.0 |
