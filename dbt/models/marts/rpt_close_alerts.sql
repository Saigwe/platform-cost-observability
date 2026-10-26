-- Month-end close alerts: an incident on a connector finance needs for close that overlaps a close window. These are
-- the ones to page someone for: the books can't close on stale ledger, bank or payments data.
select
    i.connector_id,
    i.connector_type,
    w.close_month,
    i.incident_start_at,
    coalesce(i.next_success_at, w.window_end) as incident_end_at,
    i.hours_without_success,
    i.failed_syncs,
    case when i.failed_syncs = 0 then 'no syncs at all (paused or not scheduled)' else 'syncs failing' end as symptom
from {{ ref('rpt_connector_incidents') }} i
join {{ source('config', 'close_windows') }} w
  on i.incident_start_at < w.window_end
 and coalesce(i.next_success_at, w.window_end) > w.window_start
where i.is_close_critical
