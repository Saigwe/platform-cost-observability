-- REAL: CI reliability per repo, from every GitHub Actions run on the default branch (main).
-- Time to green: for each failed run, the hours until the next successful run of the same workflow on main.
with runs as (
    select * from {{ ref('stg_github__runs') }}
    where status = 'completed' and branch = 'main' and conclusion in ('success', 'failure')
),

ordered as (
    select
        *,
        min(case when conclusion = 'success' then created_at end) over (
            partition by repo, workflow order by created_at
            rows between 1 following and unbounded following) as next_success_at
    from runs
),

minutes as (
    select repo, sum(billable_minutes) as billable_minutes, avg(queue_s) as avg_queue_s
    from {{ ref('stg_github__jobs') }}
    group by repo
)

select
    o.repo,
    count(*)                                                               as runs,
    count(*) filter (where conclusion = 'failure')                         as failed_runs,
    round(avg(case when conclusion = 'success' then 1.0 else 0 end), 3)    as success_rate,
    round(median(duration_s) / 60.0, 2)                                    as median_duration_min,
    round(quantile_cont(duration_s, 0.9) / 60.0, 2)                        as p90_duration_min,
    round(avg(case when conclusion = 'failure' and next_success_at is not null
                   then date_diff('second', created_at, next_success_at) / 3600.0 end), 2) as avg_hours_to_green,
    count(*) filter (where conclusion = 'failure' and next_success_at is null) as failures_still_red,
    min(created_at)                                                        as first_run_at,
    max(created_at)                                                        as last_run_at,
    max(m.billable_minutes)                                                as billable_minutes,
    round(max(m.avg_queue_s), 1)                                           as avg_queue_s
from ordered o
left join minutes m on m.repo = o.repo
group by o.repo
