-- SYNTHETIC: one row per query.
select
    QUERY_ID              as query_id,
    WAREHOUSE_ID          as warehouse_id,
    WAREHOUSE_NAME        as warehouse_name,
    START_TIME            as started_at,
    END_TIME              as ended_at,
    date_trunc('hour', START_TIME) as start_hour,
    TOTAL_ELAPSED_TIME    as elapsed_ms,
    BYTES_SCANNED         as bytes_scanned,
    EXECUTION_STATUS      as execution_status,
    USER_NAME             as user_name,
    ROLE_NAME             as role_name
from {{ source('bronze', 'sf_query_history') }}
