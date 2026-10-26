# 3-minute walkthrough: Data Platform Cost & Reliability Monitor

A timed script for a Loom recording of about 3 minutes (screen plus camera bubble, 1080p). Say it in your own words; the lines are a guide, not a teleprompter.

**Open these tabs before you press record:** README, the architecture diagram, `dbt/models/marts/rpt_cost_spikes.sql`, the marts YAML with `matches_answer_key`, the `ops-log` branch (latest digest), GitHub Actions (CI and Daily), `docs/design_doc.md`.

| Time | On screen | What to say |
|---|---|---|
| 0:00–0:20 | Portfolio card, then the README title | Three things a data platform lead checks every morning: did the pipelines run, what is the warehouse costing and where is it wasted, and will month-end close have its data. Each usually lives in a different console. This puts them in one dbt project with a daily digest. |
| 0:20–0:45 | README intro and the Data table | As an independent consultant for a US food-delivery company I built Snowflake cost intelligence over about 400k credits and 165 warehouses, and health checks on about 470 Fivetran connectors. Here, CI history is real: every Actions run across my repos. Snowflake and Fivetran are synthetic, shaped exactly like their system tables. |
| 0:45–1:10 | Architecture diagram | The collector pulls runs and jobs incrementally and keeps the history on a data branch. The generators plant known problems: cost spikes, uncapped warehouses, idle burn, connector outages. Those answers sit in a separate schema that only the tests read. |
| 1:10–1:35 | `rpt_cost_spikes.sql`, then the `matches_answer_key` YAML | A spike is a day at three times the warehouse's own 28-day median and over 10 credits. Every detector must find exactly the planted problems, and a lineage test fails the build if any model reads the answers. |
| 1:35–2:05 | Numbers: cost and connectors | 386,721 credits, $1.16M a year. 8 of 8 spikes, 14 warehouses with no spend cap ($106k uncapped), 5 burning credits with no query running, 3 unused. On connectors: 16 of 16 incidents and 8 month-end close alerts, all with zero false alarms. |
| 2:05–2:25 | Numbers: real CI reliability | On my own repos: 132 runs, 79.5% green, failures fixed in about 20 minutes on average. And it found three of my older repos still red on main. |
| 2:25–2:45 | "What the tests caught while I built it" | My first connector rule raised 7 false alarms: two random failures in a row on hourly connectors. Requiring three in a row removed them. Each tuning change follows a stated rule, recorded in the README, not a number picked to pass. |
| 2:45–3:00 | The latest digest on `ops-log`, then the README top | It runs every morning at 06:30 and can post to Slack. For a platform team, that's one report: what's red, what costs too much and why, and which close-critical feed is down. Links are under the video. |

## Recording checklist
- Close email, chat and notifications. Zoom the browser to 125% so code is readable.
- Open the newest digest on the `ops-log` branch before recording; its numbers move daily, so say "today's digest" rather than quoting it.
- Keep to one take per section; Loom lets you trim. Aim for 2:45 to 3:10.
- Show real numbers on screen as you say them; never estimate on camera.
- Say "synthetic" out loud for the Snowflake and Fivetran parts, as the README does.

## After recording
1. Copy the Loom share link.
2. In `README.md`, replace the roadmap line with `- [x] [3-minute Loom walkthrough](<your Loom link>)` and add the link under the title.
3. Add the link to this project's card on saigwe.github.io.
