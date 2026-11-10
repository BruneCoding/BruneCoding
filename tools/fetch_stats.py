"""Fetch GitHub statistics into cache/: stats.json for the card, calendar.json
for the Pac-Man board.

Split from tools/build_card.py on purpose: this half is the slow, network-bound,
rate-limited part, so it caches aggressively and can fail without taking the
card down (build_card.py falls back to placeholders when the cache is absent).

Lines-of-code is the expensive figure -- it walks every commit you authored on
each repo's default branch. cache/loc.json memoises that per repo, keyed by the
branch head OID, so an unchanged repo costs one cheap field in the repo query
instead of a full history walk.

Every figure is fetched on its own, so one failing query no longer sinks the
rest: GraphQL first, then a REST fallback, then the last good value from
cache/stats.json. Without a personal access token (the STATS_TOKEN secret) the
Actions-provided token is often refused user-level GraphQL fields -- the log
says which figures fell back and why.

Usage:
    GITHUB_TOKEN=... python tools/fetch_stats.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache"
STATS_OUT = CACHE / "stats.json"
LOC_CACHE = CACHE / "loc.json"
CALENDAR_OUT = CACHE / "calendar.json"

LOGIN = os.environ.get("GH_LOGIN", "BruneCoding")
ENDPOINT = "https://api.github.com/graphql"
TOKEN = os.environ.get("GITHUB_TOKEN")

session = requests.Session()


def query(document: str, variables: dict, attempt: int = 0) -> dict:
    """POST a GraphQL document, retrying once on a secondary rate limit."""
    resp = session.post(
        ENDPOINT,
        json={"query": document, "variables": variables},
        headers={"Authorization": f"bearer {TOKEN}"},
        timeout=30,
    )
    if resp.status_code in (403, 429) and attempt < 3:
        wait = int(resp.headers.get("Retry-After", 60))
        print(f"  rate limited, sleeping {wait}s", file=sys.stderr)
        time.sleep(wait)
        return query(document, variables, attempt + 1)

    resp.raise_for_status()
    payload = resp.json()
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {json.dumps(payload['errors'], indent=2)}")
    return payload["data"]


REPOS_Q = """
query($login:String!, $after:String) {
  user(login:$login) {
    id
    createdAt
    followers { totalCount }
    repositories(ownerAffiliations:OWNER, isFork:false, first:100, after:$after) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        nameWithOwner
        stargazerCount
        defaultBranchRef { target { ... on Commit { oid } } }
      }
    }
  }
}
"""

# The same last-year calendar GitHub draws on the profile. Anything the
# profile hides from visitors -- private contributions, unless the owner opts
# in -- this token cannot see either, so the board always matches the graph
# rendered directly beneath it.
CALENDAR_Q = """
query($login:String!) {
  user(login:$login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { date weekday contributionCount contributionLevel }
        }
      }
    }
  }
}
"""

LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
          "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}

CONTRIB_Q = """
query($login:String!) {
  user(login:$login) {
    repositoriesContributedTo(
      first:1,
      contributionTypes:[COMMIT, PULL_REQUEST, REPOSITORY]
    ) { totalCount }
  }
}
"""

# contributionsCollection is capped at one year per call, so this gets asked
# once per year the account has existed.
COMMITS_Q = """
query($login:String!, $from:DateTime!, $to:DateTime!) {
  user(login:$login) {
    contributionsCollection(from:$from, to:$to) {
      totalCommitContributions
      restrictedContributionsCount
    }
  }
}
"""

HISTORY_Q = """
query($owner:String!, $name:String!, $authorId:ID!, $after:String) {
  repository(owner:$owner, name:$name) {
    defaultBranchRef {
      target { ... on Commit {
        history(first:100, after:$after, author:{id:$authorId}) {
          totalCount
          pageInfo { hasNextPage endCursor }
          nodes { additions deletions }
        }
      }}
    }
  }
}
"""


def fetch_repos() -> tuple[dict, list[dict]]:
    """Return (user_meta, repos). Paginates through every owned, non-fork repo."""
    repos: list[dict] = []
    meta: dict = {}
    after = None
    while True:
        data = query(REPOS_Q, {"login": LOGIN, "after": after})["user"]
        if not meta:
            meta = {
                "id": data["id"],
                "createdAt": data["createdAt"],
                "followers": data["followers"]["totalCount"],
                "repos": data["repositories"]["totalCount"],
            }
        repos.extend(data["repositories"]["nodes"])
        page = data["repositories"]["pageInfo"]
        if not page["hasNextPage"]:
            return meta, repos
        after = page["endCursor"]


def fetch_commit_total(created_at: str) -> int:
    """Sum contributions year by year from account creation to now."""
    start = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    total = 0
    cursor = start
    while cursor < now:
        try:
            next_year = cursor.replace(year=cursor.year + 1)
        except ValueError:
            next_year = cursor.replace(year=cursor.year + 1, day=28)  # Feb 29
        end = min(next_year, now)
        c = query(COMMITS_Q, {
            "login": LOGIN,
            "from": cursor.isoformat().replace("+00:00", "Z"),
            "to": end.isoformat().replace("+00:00", "Z"),
        })["user"]["contributionsCollection"]
        total += c["totalCommitContributions"] + c["restrictedContributionsCount"]
        cursor = end
    return total


def fetch_loc(repos: list[dict], author_id: str) -> tuple[int, int]:
    """Total additions/deletions authored across all repos, memoised by head OID."""
    cache = json.loads(LOC_CACHE.read_text(encoding="utf-8")) if LOC_CACHE.exists() else {}
    added = deleted = 0
    walked = reused = 0

    for repo in repos:
        name = repo["nameWithOwner"]
        target = (repo.get("defaultBranchRef") or {}).get("target") or {}
        head = target.get("oid")
        if not head:
            continue  # empty repo, nothing to walk

        hit = cache.get(name)
        if hit and hit.get("oid") == head:
            added += hit["added"]
            deleted += hit["deleted"]
            reused += 1
            continue

        owner, short = name.split("/", 1)
        r_add = r_del = 0
        after = None
        while True:
            target = query(HISTORY_Q, {
                "owner": owner, "name": short,
                "authorId": author_id, "after": after,
            })["repository"]["defaultBranchRef"]["target"]
            hist = target["history"]
            for node in hist["nodes"]:
                r_add += node["additions"]
                r_del += node["deletions"]
            if not hist["pageInfo"]["hasNextPage"]:
                break
            after = hist["pageInfo"]["endCursor"]

        cache[name] = {"oid": head, "added": r_add, "deleted": r_del}
        added += r_add
        deleted += r_del
        walked += 1
        print(f"  walked {name}: +{r_add:,} -{r_del:,}")

    CACHE.mkdir(exist_ok=True)
    LOC_CACHE.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")
    print(f"  loc cache: {walked} walked, {reused} reused")
    return added, deleted


def fetch_calendar() -> dict:
    """Weeks as seven weekday slots (0 = Sunday), None where a day doesn't exist yet."""
    cal = query(CALENDAR_Q, {"login": LOGIN})["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = []
    for week in cal["weeks"]:
        slots: list[dict | None] = [None] * 7
        for day in week["contributionDays"]:
            slots[day["weekday"]] = {
                "date": day["date"],
                "count": day["contributionCount"],
                "level": LEVELS[day["contributionLevel"]],
            }
        weeks.append(slots)
    return {"total": cal["totalContributions"], "weeks": weeks}


REST = "https://api.github.com"


def rest(path: str, params: dict | None = None, attempt: int = 0) -> requests.Response:
    resp = session.get(REST + path, params=params, timeout=30, headers={
        "Authorization": f"bearer {TOKEN}", "Accept": "application/vnd.github+json"})
    if resp.status_code == 202 and attempt < 5:          # stats still being computed
        time.sleep(3)
        return rest(path, params, attempt + 1)
    resp.raise_for_status()
    return resp


def rest_user_and_repos() -> tuple[dict, list[dict]]:
    u = rest(f"/users/{LOGIN}").json()
    repos, page = [], 1
    while True:
        batch = rest(f"/users/{LOGIN}/repos", {"type": "owner", "per_page": 100, "page": page}).json()
        repos += [r for r in batch if not r["fork"]]
        if len(batch) < 100:
            break
        page += 1
    meta = {"id": u["node_id"], "createdAt": u["created_at"], "followers": u["followers"], "repos": u["public_repos"]}
    return meta, [{"nameWithOwner": r["full_name"], "stargazerCount": r["stargazers_count"], "defaultBranchRef": None}
                  for r in repos]


def rest_commits() -> int:
    r = rest("/search/commits", {"q": f"author:{LOGIN}", "per_page": 1})
    return r.json()["total_count"]


def rest_contrib() -> int:
    """Repos you don't own that you've pushed to or opened PRs on lately (public events cover ~90 days)."""
    names = set()
    for page in (1, 2, 3):
        for ev in rest(f"/users/{LOGIN}/events/public", {"per_page": 100, "page": page}).json():
            if ev["type"] in ("PushEvent", "PullRequestEvent", "CreateEvent") and not ev["repo"]["name"].startswith(LOGIN + "/"):
                names.add(ev["repo"]["name"])
    return len(names)


def rest_loc(repos: list[dict]) -> tuple[int, int]:
    added = deleted = 0
    for repo in repos:
        try:
            data = rest(f"/repos/{repo['nameWithOwner']}/stats/contributors").json()
        except Exception as e:                           # empty repo (204) or stats unavailable
            print(f"  skipped {repo['nameWithOwner']}: {e}", file=sys.stderr)
            continue
        for c in data or []:
            if c["author"] and c["author"]["login"].lower() == LOGIN.lower():
                for w in c["weeks"]:
                    added += w["a"]
                    deleted += w["d"]
    return added, deleted


def attempt(label: str, *fns):
    """Run each strategy in turn; return the first that works, else None."""
    for fn in fns:
        try:
            value = fn()
            print(f"  {label}: ok via {fn.__name__}")
            return value
        except (Exception, SystemExit) as e:
            msg = str(e).replace("\n", " ")[:220]
            print(f"  {label}: {fn.__name__} failed -- {msg}", file=sys.stderr)
    print(f"  {label}: all strategies failed, keeping the last good value", file=sys.stderr)
    return None


def main() -> None:
    if not TOKEN:
        raise SystemExit("GITHUB_TOKEN is not set")

    CACHE.mkdir(exist_ok=True)
    stats = json.loads(STATS_OUT.read_text(encoding="utf-8")) if STATS_OUT.exists() else {}
    print(f"fetching stats for {LOGIN}")

    got = attempt("repos", fetch_repos, rest_user_and_repos)
    meta, repos = got if got else ({}, [])
    if meta:
        stats["repos"], stats["followers"] = meta["repos"], meta["followers"]
        stats["stars"] = sum(r["stargazerCount"] for r in repos)

    contrib = attempt("contributed", lambda: query(CONTRIB_Q, {"login": LOGIN})["user"]["repositoriesContributedTo"]["totalCount"], rest_contrib)
    if contrib is not None:
        stats["contrib"] = contrib

    if meta:
        commits = attempt("commits", lambda: fetch_commit_total(meta["createdAt"]), rest_commits)
    else:
        commits = attempt("commits", rest_commits)
    if commits is not None:
        stats["commits"] = commits

    def graphql_loc():
        if not meta or any(r.get("defaultBranchRef") is None for r in repos):
            raise RuntimeError("no GraphQL repo data (REST fallback was used)")
        return fetch_loc(repos, meta["id"])

    loc = attempt("lines of code", graphql_loc, lambda: rest_loc(repos))
    if loc is not None:
        stats["added"], stats["deleted"], stats["loc"] = loc[0], loc[1], loc[0] - loc[1]

    stats["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    STATS_OUT.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))

    cal = attempt("calendar", fetch_calendar)
    if cal:
        CALENDAR_OUT.write_text(json.dumps(cal, indent=1), encoding="utf-8")
        print(f"  calendar: {len(cal['weeks'])} weeks, {cal['total']} contributions")

    if not any(k in stats for k in ("repos", "commits", "loc")):
        raise SystemExit("could not fetch any statistic -- check the STATS_TOKEN secret")


if __name__ == "__main__":
    main()
