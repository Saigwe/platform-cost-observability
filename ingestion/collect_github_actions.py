"""REAL data: every GitHub Actions workflow run and job across one owner's public repos, loaded incrementally.

Writes newline-delimited JSON, one file per entity, de-duplicated on id (a run is re-read while it is still in
progress or was re-run, so the latest version wins):
  <out>/repos.jsonl  <out>/runs.jsonl  <out>/jobs.jsonl  <out>/_state.json (watermark per repo)

The watermark is the newest run's `updated_at` per repo, minus a 2-day overlap, so runs that finish or are re-run late
are picked up again. Uses GITHUB_TOKEN when set (1,000+ requests an hour in Actions); without it, 60 an hour, so pass
--no-jobs for a quick local run.

Usage: python ingestion/collect_github_actions.py --owner Saigwe --out data/github [--no-jobs]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com"
OVERLAP = dt.timedelta(days=2)


def get(url: str) -> tuple[dict | list, dict]:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": "platform-cost-observability"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
                return json.loads(r.read()), dict(r.headers)
        except urllib.error.HTTPError as e:
            if e.code == 403 and e.headers.get("X-RateLimit-Remaining") == "0":
                raise SystemExit(f"GitHub rate limit reached; resets at {e.headers.get('X-RateLimit-Reset')} (epoch)")
            if e.code >= 500 and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError("unreachable")


def paged(url: str, key: str | None = None, max_pages: int = 50):
    for page in range(1, max_pages + 1):
        sep = "&" if "?" in url else "?"
        body, _ = get(f"{url}{sep}per_page=100&page={page}")
        items = body[key] if key else body
        yield from items
        if len(items) < 100:
            return


def merge(path: Path, rows: list[dict], key: str = "id") -> int:
    existing = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            existing[r[key]] = r
    before = len(existing)
    for r in rows:
        existing[r[key]] = r
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for _, r in sorted(existing.items())), encoding="utf-8")
    return len(existing) - before


KEEP_RUN = ("id", "name", "path", "event", "status", "conclusion", "head_branch", "head_sha", "run_number",
            "run_attempt", "created_at", "updated_at", "run_started_at", "workflow_id", "html_url")
KEEP_JOB = ("id", "run_id", "run_attempt", "name", "status", "conclusion", "created_at", "started_at", "completed_at",
            "labels", "runner_name", "html_url")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--owner", default="Saigwe")
    ap.add_argument("--out", type=Path, default=Path("data/github"))
    ap.add_argument("--no-jobs", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    state_path = args.out / "_state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}

    repos = [r for r in paged(f"{API}/users/{args.owner}/repos?type=owner&sort=full_name") if not r["fork"]]
    merge(args.out / "repos.jsonl", [{k: r[k] for k in ("id", "name", "full_name", "private", "created_at",
                                                        "pushed_at", "language", "topics")} for r in repos])
    new_runs = new_jobs = 0
    for repo in repos:
        name = repo["name"]
        since = state.get(name)
        query = f"?created=>={since}" if since else ""
        runs = []
        for r in paged(f"{API}/repos/{args.owner}/{name}/actions/runs{query}", key="workflow_runs"):
            runs.append({**{k: r.get(k) for k in KEEP_RUN}, "repo": name})
        if not runs:
            continue
        new_runs += merge(args.out / "runs.jsonl", runs)
        if not args.no_jobs:
            jobs = []
            for r in runs:
                for j in paged(f"{API}/repos/{args.owner}/{name}/actions/runs/{r['id']}/jobs?filter=all", key="jobs"):
                    jobs.append({**{k: j.get(k) for k in KEEP_JOB}, "repo": name})
            new_jobs += merge(args.out / "jobs.jsonl", jobs)
        newest = max(dt.datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) for r in runs)
        state[name] = (newest - OVERLAP).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"{name:<36} {len(runs):>4} runs read")
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True))
    print(f"{len(repos)} repos; {new_runs} new runs, {new_jobs} new jobs")


if __name__ == "__main__":
    main()
