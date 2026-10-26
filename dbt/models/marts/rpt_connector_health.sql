-- One row per connector: sync success rate, incidents and the longest stretch without a successful sync.
with syncs as (
    select connector_id, count(*) as syncs, count(*) filter (where is_success) as successful_syncs,
           max(case when is_success then synced_at end) as last_success_at
    from {{ ref('stg_fivetran__syncs') }}
    group by connector_id
),

incidents as (
    select connector_id, count(*) as incidents, max(hours_without_success) as worst_hours_without_success
    from {{ ref('rpt_connector_incidents') }}
    group by connector_id
)

select
    c.connector_id,
    c.connector_name,
    c.connector_type,
    c.sync_frequency_min,
    c.is_close_critical,
    coalesce(s.syncs, 0)                                                    as syncs,
    round(s.successful_syncs * 1.0 / nullif(s.syncs, 0), 4)                 as success_rate,
    s.last_success_at,
    coalesce(i.incidents, 0)                                                as incidents,
    coalesce(i.worst_hours_without_success, 0)                              as worst_hours_without_success
from {{ ref('stg_fivetran__connectors') }} c
left join syncs s using (connector_id)
left join incidents i using (connector_id)
