-- One row per connector incident: a stretch with no successful sync for longer than
-- max(var('stale_intervals') x the sync frequency, var('stale_min_minutes')). Single failed syncs that recover on the
-- next run are noise and never open an incident. An incident still open at the end of the data is kept.
with successes as (
    select s.connector_id, s.synced_at, c.sync_frequency_min, c.is_close_critical
    from {{ ref('stg_fivetran__syncs') }} s
    join {{ ref('stg_fivetran__connectors') }} c using (connector_id)
    where s.is_success
),

gaps as (
    select
        connector_id,
        sync_frequency_min,
        is_close_critical,
        synced_at                                                                  as last_success_at,
        lead(synced_at) over (partition by connector_id order by synced_at)        as next_success_at
    from successes
),

data_end as (select max(synced_at) as ended_at from {{ ref('stg_fivetran__syncs') }})

select
    g.connector_id,
    c.connector_type,
    g.is_close_critical,
    g.sync_frequency_min,
    g.last_success_at,
    g.next_success_at,
    g.last_success_at + to_minutes(cast(g.sync_frequency_min as bigint))          as incident_start_at,
    cast(g.last_success_at + to_minutes(cast(g.sync_frequency_min as bigint)) as date) as incident_date,
    round(date_diff('minute', g.last_success_at, coalesce(g.next_success_at, d.ended_at)) / 60.0, 1) as hours_without_success,
    g.next_success_at is null                                                      as is_open,
    (select count(*) from {{ ref('stg_fivetran__syncs') }} f
      where f.connector_id = g.connector_id and not f.is_success
        and f.synced_at > g.last_success_at and f.synced_at < coalesce(g.next_success_at, d.ended_at)) as failed_syncs
from gaps g
join {{ ref('stg_fivetran__connectors') }} c using (connector_id)
cross join data_end d
where date_diff('minute', g.last_success_at, coalesce(g.next_success_at, d.ended_at))
      > greatest({{ var('stale_intervals') }} * g.sync_frequency_min, {{ var('stale_min_minutes') }})
