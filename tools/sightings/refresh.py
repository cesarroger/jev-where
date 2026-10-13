#!/usr/bin/env python3
"""Weekly upkeep for Jev Sightings. Runs in GitHub Actions with no API keys and no LLM.

--health  rechecks every record on GitHub: gone, archived, quiet (no push in 180 days)
--new     lists GitHub projects in the Sightings categories that we haven't read yet, in
          tools/sightings/waiting.json (names, links and categories only)

Writes a summary for the pull request body, and sets changed=true|false in
$GITHUB_OUTPUT when it runs inside GitHub Actions.

Usage:
    python3 -I tools/sightings/refresh.py --health --new [--summary PATH]
"""
import argparse
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build  # noqa: E402
import common  # noqa: E402
import harvest  # noqa: E402
import health as health_mod  # noqa: E402

WAITING_PATH = common.HERE / "waiting.json"


def recheck(records, fetch=common.gh_api, date=None):
    """Update records in place (and re-key renamed ones). Returns a list of (repo, change) lines.

    A verified project that 404s is marked missing first and only becomes
    gone if it is still missing a week later; gone projects are rechecked and
    come back if they reappear. Gone records keep their old facts."""
    date = date or common.today()
    changes = []
    for key, r in sorted(list(records.items())):
        if r["status"] not in ("verified", "no-jev-found", "gone"):
            continue
        h = health_mod.check(r["repo"], fetch, with_sha=False)
        if h.get("exists") is None:
            continue
        health = dict(r.get("health") or {})
        if h["exists"] is False:
            if r["status"] == "verified" and not health.get("missing"):
                health["missing"] = date
                r["health"] = health
                changes.append((r["repo"], "not found on GitHub; marked gone if still missing in a week"))
            elif r["status"] == "verified" and common.days_between(health["missing"], date) < 6:
                pass
            elif r["status"] != "gone":
                r["status"] = "gone"
                changes.append((r["repo"], "gone from GitHub"))
            continue
        came_back = r["status"] == "gone"
        if came_back:
            r["status"] = "verified" if r.get("calls") else "no-jev-found"
            changes.append((r["repo"], "back on GitHub"))
        if h.get("full_name") and h["full_name"].lower() != r["repo"].lower():
            changes.append((r["repo"], "renamed to %s (permalinks still redirect)" % h["full_name"]))
            r["repo"] = h["full_name"]
            records.pop(key, None)
            records[common.repo_key(r["repo"])] = r
        if r["status"] != "verified":
            continue
        new = build.health_of(h)
        old = {k: v for k, v in health.items() if k != "missing"}
        if health.get("missing") and not came_back:
            changes.append((r["repo"], "found on GitHub again"))
        if new != old:
            what = []
            if new["archived"] != old.get("archived"):
                what.append("archived" if new["archived"] else "no longer archived")
            if new["quiet"] != old.get("quiet"):
                what.append("quiet for %d+ days" % common.QUIET_DAYS if new["quiet"] else "active again")
            changes.append((r["repo"], ", ".join(what) or "health updated"))
        if new != health:
            r["health"] = new
    return changes


def waiting(records, live_queue, fetch=None):
    """Listed projects not read yet. With fetch, also drop ones that are gone or renamed to a known repo."""
    known = set(records)
    out = []
    for q in live_queue:
        if common.repo_key(q["repo"]) in known:
            continue
        if fetch:
            h = health_mod.check(q["repo"], fetch, with_sha=False)
            if h.get("exists") is False or common.repo_key(h.get("full_name") or "") in known:
                continue
        out.append(q)
    return out


def summary(changes, new, date, note=None):
    lines = ["Weekly Jev Sightings check, %s." % date, ""]
    if changes:
        lines += ["**Changed records**", ""] + ["- `%s`: %s" % c for c in changes] + [""]
    if note:
        lines += [note, ""]
    if new:
        lines += ["**%d listed projects not read yet**" % len(new), ""]
        lines += ["- %s: https://github.com/%s (%s)" % (q["name"], q["repo"], ", ".join(q["categories"])) for q in new[:50]]
        if len(new) > 50:
            lines.append("- …and %d more in `tools/sightings/waiting.json`" % (len(new) - 50))
        lines += ["", "Read them with the steps in DEVELOPMENT.md (locate, read, audit, build)."]
    if not changes and not new and not note:
        lines.append("Nothing changed.")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--health", action="store_true")
    ap.add_argument("--new", action="store_true")
    ap.add_argument("--categories", default="core+topup",
                    help="which awesome-jev categories to list unread projects from (see harvest.py)")
    ap.add_argument("--summary", default=str(common.WORK / "refresh-summary.md"))
    args = ap.parse_args(argv)
    date = common.today()
    rows = [r for r in common.read_jsonl(common.SIGHTINGS_PATH) if "meta" not in r]
    records = {common.repo_key(r["repo"]): r for r in rows}
    changes = recheck(records, date=date) if args.health else []
    new, waiting_changed, note = [], False, None
    if args.new:
        try:
            live, _ = harvest.merge(harvest.load(args.categories))
        except (SystemExit, OSError, ValueError) as e:
            note = "Couldn't list awesome-jev projects this week (%s); the unread list is unchanged." % (
                type(e).__name__ if not str(e) else str(e)[:120])
            new = common.read_json(WAITING_PATH, [])
        else:
            new = waiting(records, live, common.gh_api)
            waiting_changed = new != common.read_json(WAITING_PATH, [])
            if waiting_changed:
                common.write_json(WAITING_PATH, new)
    if changes:
        build.write_outputs(records, date)
    pathlib.Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(args.summary).write_text(summary(changes, new, date, note))
    changed = bool(changes) or waiting_changed
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as fh:
            fh.write("changed=%s\nnew=%d\n" % ("true" if changed else "false", len(new)))
    print("%d record changes, %d projects waiting -> %s" % (len(changes), len(new), args.summary))


if __name__ == "__main__":
    main()
