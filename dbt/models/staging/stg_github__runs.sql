-- REAL: one row per workflow run attempt's latest state. Duration counts only completed runs.
select
    id                                                       as run_id,
    repo,
    name                                                     as workflow,
    event,
    status,
    conclusion,
    head_branch                                              as branch,
    head_sha,
    run_attempt,
    cast(created_at as timestamp)                            as created_at,
    cast(run_started_at as timestamp)                        as started_at,
    cast(updated_at as timestamp)                            as updated_at,
    case when status = 'completed'
         then date_diff('second', cast(run_started_at as timestamp), cast(updated_at as timestamp)) end as duration_s,
    html_url
from {{ source('bronze', 'github_runs') }}
