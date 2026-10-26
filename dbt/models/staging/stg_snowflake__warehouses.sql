-- SYNTHETIC: one row per warehouse, with its COST_CENTER tag.
select
    w.WAREHOUSE_ID     as warehouse_id,
    w.NAME             as warehouse_name,
    w.SIZE             as warehouse_size,
    w.AUTO_SUSPEND     as auto_suspend_s,
    w.RESOURCE_MONITOR as resource_monitor,
    w.OWNER            as owner_role,
    cast(w.CREATED_ON as date) as created_on,
    t.TAG_VALUE        as cost_center
from {{ source('bronze', 'sf_warehouses') }} w
left join {{ source('bronze', 'sf_tag_references') }} t
  on t.OBJECT_NAME = w.NAME and t.DOMAIN = 'WAREHOUSE' and t.TAG_NAME = 'COST_CENTER'
