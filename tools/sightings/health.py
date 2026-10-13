#!/usr/bin/env python3
"""Check each queued project on GitHub: does it exist, is it archived, what is its latest commit.

Usage:
    python3 -I tools/sightings/health.py [--queue work/queue.json] [--out work/health.json] [--only owner/a,owner/b]
"""
import argparse
import concurrent.futures
import datetime
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common  # noqa: E402


def quiet(pushed, now=None):
    """True when the last push is more than QUIET_DAYS ago."""
    if not pushed:
        return False
    now = now or datetime.date.today()
    last = datetime.date.fromisoformat(pushed[:10])
    return (now - last).days > common.QUIET_DAYS


def check(repo, fetch=common.gh_api, with_sha=True):
    """Health facts for one repo. Never raises on HTTP errors."""
    status, data = fetch("repos/%s" % repo)
    if status == 404:
        return {"repo": repo, "exists": False}
    if status != 200 or not isinstance(data, dict):
        return {"repo": repo, "exists": None, "error": "HTTP %s" % status}
    info = {
        "repo": repo,
        "exists": True,
        "full_name": data.get("full_name"),
        "private": bool(data.get("private")),
        "archived": bool(data.get("archived")),
        "fork": bool(data.get("fork")),
        "default_branch": data.get("default_branch"),
        "size_kb": data.get("size"),
        "language": data.get("language"),
        "pushed": (data.get("pushed_at") or "")[:10] or None,
        "stars": data.get("stargazers_count"),
    }
    branch = info["default_branch"]
    if branch and with_sha:
        s2, commit = fetch("repos/%s/commits/%s" % (info["full_name"] or repo, branch))
        if s2 == 200 and isinstance(commit, dict):
            info["sha"] = commit.get("sha")
    return info


def check_all(repos, fetch=common.gh_api, workers=8):
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda r: check(r, fetch), repos))
    return {common.repo_key(r["repo"]): r for r in results}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--queue", default=str(common.WORK / "queue.json"))
    ap.add_argument("--out", default=str(common.WORK / "health.json"))
    ap.add_argument("--only", help="comma-separated owner/name list to check instead of the whole queue")
    args = ap.parse_args(argv)
    if args.only:
        repos = [r.strip() for r in args.only.split(",") if r.strip()]
    else:
        repos = [q["repo"] for q in common.read_json(args.queue, [])]
    old = common.read_json(args.out, {})
    old.update(check_all(repos))
    common.write_json(args.out, old)
    gone = sum(1 for r in repos if old[common.repo_key(r)].get("exists") is False)
    err = sum(1 for r in repos if old[common.repo_key(r)].get("exists") is None)
    print("checked %d repos: %d gone, %d errors -> %s" % (len(repos), gone, err, args.out))


if __name__ == "__main__":
    main()
