-- Warehouse-days that cost at least var('spike_multiple') times the warehouse's median over the previous 28 days,
-- and more than var('spike_min_credits'). Days with no usage count as zero, and a warehouse needs 14 days of history.
with calendar as (
    select w.warehouse_name, w.cost_center, cast(d as date) as usage_date
    from {{ ref('stg_snowflake__warehouses') }} w
    cross join range(
        (select min(usage_date) from {{ ref('fct_warehouse_daily_credits') }}),
        (select max(usage_date) + 1 from {{ ref('fct_warehouse_daily_credits') }}),
        interval 1 day) t(d)
    where cast(d as date) >= w.created_on
),

daily as (
    select c.warehouse_name, c.cost_center, c.usage_date, coalesce(f.credits, 0) as credits
    from calendar c
    left join {{ ref('fct_warehouse_daily_credits') }} f using (warehouse_name, usage_date)
),

scored as (
    select
        *,
        median(credits) over (partition by warehouse_name order by usage_date
                              rows between 28 preceding and 1 preceding) as baseline_credits,
        count(*) over (partition by warehouse_name order by usage_date
                       rows between 28 preceding and 1 preceding) as history_days
    from daily
)

select
    warehouse_name,
    cost_center,
    usage_date                                               as spike_date,
    round(credits, 2)                                        as credits,
    round(baseline_credits, 2)                               as baseline_credits,
    round(credits / nullif(baseline_credits, 0), 1)          as multiple,
    round((credits - baseline_credits) * {{ var('credit_price_usd') }}, 2) as excess_cost_usd
from scored
where history_days >= 14
  and credits > {{ var('spike_min_credits') }}
  and credits >= {{ var('spike_multiple') }} * baseline_credits
