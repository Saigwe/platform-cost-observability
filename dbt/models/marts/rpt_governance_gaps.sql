-- One row per warehouse and governance problem: no spend cap, a long auto-suspend that burns idle credits, or no
-- queries in the last 90 days (a decommission candidate). Each row carries the credits at stake over the year.
with usage as (
    select
        warehouse_name,
        sum(credits)                     as credits,
        sum(idle_credits)                as idle_credits,
        sum(idle_hours) * 1.0 / nullif(sum(metered_hours), 0) as idle_share,
        max(case when queries > 0 then usage_date end) as last_query_date
    from {{ ref('fct_warehouse_daily_credits') }}
    group by warehouse_name
),

today as (select max(usage_date) as as_of from {{ ref('fct_warehouse_daily_credits') }})

select w.warehouse_name, w.cost_center, 'no_resource_monitor' as issue,
       'No spend cap: assign a resource monitor' as action, round(coalesce(u.credits, 0), 1) as credits_at_stake
from {{ ref('stg_snowflake__warehouses') }} w
left join usage u using (warehouse_name)
where w.resource_monitor is null
union all
select w.warehouse_name, w.cost_center, 'idle_burn',
       'Idle ' || cast(round(100 * u.idle_share) as integer) || '% of metered hours: lower AUTO_SUSPEND from '
       || w.auto_suspend_s || ' s', round(u.idle_credits, 1)
from {{ ref('stg_snowflake__warehouses') }} w
join usage u using (warehouse_name)
where u.idle_share >= 0.10 and u.idle_credits >= 100
union all
select w.warehouse_name, w.cost_center, 'unused_90_days',
       'No queries since ' || coalesce(cast(u.last_query_date as varchar), 'creation') || ': decommission',
       round(coalesce(u.credits, 0), 1)
from {{ ref('stg_snowflake__warehouses') }} w
left join usage u using (warehouse_name)
cross join today
where w.created_on < today.as_of - 90
  and (u.last_query_date is null or u.last_query_date <= today.as_of - 90)
