-- SYNTHETIC: one row per warehouse and metered hour.
select
    WAREHOUSE_ID                    as warehouse_id,
    WAREHOUSE_NAME                  as warehouse_name,
    START_TIME                      as hour_start,
    cast(START_TIME as date)        as usage_date,
    CREDITS_USED                    as credits,
    CREDITS_USED_COMPUTE            as credits_compute,
    CREDITS_USED_CLOUD_SERVICES     as credits_cloud_services
from {{ source('bronze', 'sf_warehouse_metering_history') }}
