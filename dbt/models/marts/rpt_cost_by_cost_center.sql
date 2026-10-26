-- Credits and dollars by cost center and month, with the share of credits burned while idle.
select
    cost_center,
    date_trunc('month', usage_date)                         as month,
    count(distinct warehouse_name)                          as warehouses,
    round(sum(credits), 1)                                  as credits,
    round(sum(cost_usd), 2)                                 as cost_usd,
    round(sum(idle_credits) / nullif(sum(credits), 0), 4)   as idle_share,
    sum(queries)                                            as queries,
    round(sum(cost_usd) / nullif(sum(queries), 0), 4)       as cost_per_query_usd
from {{ ref('fct_warehouse_daily_credits') }}
group by all
