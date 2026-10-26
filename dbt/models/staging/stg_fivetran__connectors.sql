-- SYNTHETIC: one row per connector, with whether finance needs it for month-end close.
select
    c.CONNECTOR_ID        as connector_id,
    c.CONNECTOR_NAME      as connector_name,
    c.CONNECTOR_TYPE_ID   as connector_type,
    c.SYNC_FREQUENCY      as sync_frequency_min,
    c.PAUSED              as is_paused,
    k.connector_id is not null as is_close_critical
from {{ source('bronze', 'ft_connector') }} c
left join {{ source('config', 'close_critical_connectors') }} k on k.connector_id = c.CONNECTOR_ID
