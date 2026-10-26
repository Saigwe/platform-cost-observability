-- SYNTHETIC: one row per finished sync (the sync_end event), with its status from MESSAGE_DATA.
select
    ID                                                 as log_id,
    CONNECTOR_ID                                       as connector_id,
    TIME_STAMP                                         as synced_at,
    json_extract_string(MESSAGE_DATA, '$.status')      as sync_status,
    json_extract_string(MESSAGE_DATA, '$.status') = 'SUCCESSFUL' as is_success
from {{ source('bronze', 'ft_log') }}
where MESSAGE_EVENT = 'sync_end'
