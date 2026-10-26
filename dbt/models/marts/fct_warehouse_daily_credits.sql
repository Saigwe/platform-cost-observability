-- One row per warehouse and day it was metered: credits, dollars at the configured price, queries and idle hours.
-- An idle hour is a metered hour in which no query was running.
with busy_hours as (
    -- every hour in which at least one query was running on the warehouse
    select distinct warehouse_id, h as hour_start
    from {{ ref('stg_snowflake__queries') }},
         unnest(generate_series(date_trunc('hour', started_at), date_trunc('hour', ended_at), interval 1 hour)) t(h)
),

hours as (
    select m.warehouse_name, m.usage_date, m.hour_start, m.credits, b.hour_start is not null as had_query
    from {{ ref('stg_snowflake__metering') }} m
    left join busy_hours b on b.warehouse_id = m.warehouse_id and b.hour_start = m.hour_start
),

queries as (
    select warehouse_name, cast(started_at as date) as usage_date, count(*) as queries,
           count(*) filter (where execution_status = 'FAIL') as failed_queries
    from {{ ref('stg_snowflake__queries') }}
    group by all
)

select
    h.warehouse_name,
    w.cost_center,
    w.warehouse_size,
    h.usage_date,
    sum(h.credits)                                                   as credits,
    round(sum(h.credits) * {{ var('credit_price_usd') }}, 2)         as cost_usd,
    count(*)                                                         as metered_hours,
    count(*) filter (where not h.had_query)                          as idle_hours,
    coalesce(sum(case when not h.had_query then h.credits end), 0)   as idle_credits,
    coalesce(max(q.queries), 0)                                      as queries,
    coalesce(max(q.failed_queries), 0)                               as failed_queries
from hours h
join {{ ref('stg_snowflake__warehouses') }} w using (warehouse_name)
left join queries q using (warehouse_name, usage_date)
group by all
