-- REAL: one row per job. Queue time is creation to start; billable minutes round each job up to a whole minute,
-- as GitHub bills hosted runners.
select
    id                                                                       as job_id,
    run_id,
    repo,
    name                                                                     as job_name,
    conclusion,
    cast(created_at as timestamp)                                            as created_at,
    cast(started_at as timestamp)                                            as started_at,
    cast(completed_at as timestamp)                                          as completed_at,
    date_diff('second', cast(created_at as timestamp), cast(started_at as timestamp))   as queue_s,
    date_diff('second', cast(started_at as timestamp), cast(completed_at as timestamp)) as run_s,
    ceil(date_diff('second', cast(started_at as timestamp), cast(completed_at as timestamp)) / 60.0) as billable_minutes
from {{ source('bronze', 'github_jobs') }}
where status = 'completed'
