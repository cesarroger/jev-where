#!/usr/bin/env python3
"""Collect the GitHub projects listed on awesome-jev into a reading queue.

Fetches the category files live and keeps only project names, links and
categories in work/queue.json. The one-line summaries go to
work/summaries.json, which is gitignored and used only by audit.py to check
that our own descriptions don't copy them.

Usage:
    python3 -I tools/sightings/harvest.py [--categories core|topup|core+topup|all|a,b] [--from-dir DIR]
"""
import argparse
import pathlib
import re
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common  # noqa: E402

RE_ENTRY = re.compile(r"^- \[(?P<name>[^\]]+)\]\((?P<url>[^)\s]+)\)(?P<rest>.*)$")


def parse_category(text):
    """Entries in one category file, skipping the submission template line."""
    out = []
    for line in text.splitlines():
        m = RE_ENTRY.match(line.strip())
        if not m:
            continue
        if m.group("name") == "Name" and m.group("url") == "URL":
            continue
        rest = m.group("rest").strip()
        rest = re.sub(r"^`\{[^}]*\}`\s*", "", rest)
        rest = re.sub(r"^[-–—]\s*", "", rest)
        out.append({"name": m.group("name"), "url": m.group("url"), "summary": rest})
    return out


def merge(categories):
    """categories: {slug: text}. Returns (queue, summaries) with repos de-duplicated."""
    queue, summaries = {}, {}
    for slug in sorted(categories):
        for e in parse_category(categories[slug]):
            repo = common.github_repo(e["url"])
            if not repo:
                continue
            key = common.repo_key(repo)
            name = common.clean_name(e["name"]) or repo.split("/", 1)[1]
            item = queue.setdefault(key, {"repo": repo, "name": name, "url": "https://github.com/" + repo,
                                          "categories": []})
            if slug not in item["categories"]:
                item["categories"].append(slug)
            if e["summary"]:
                summaries.setdefault(key, []).append(e["summary"])
    return [queue[k] for k in sorted(queue)], summaries


def list_categories(fetch=common.gh_api):
    status, data = fetch("repos/%s/contents/categories" % common.LIST_REPO)
    if status != 200 or not isinstance(data, list):
        raise SystemExit("could not list awesome-jev categories (HTTP %s)" % status)
    return sorted(d["name"][:-3] for d in data if d.get("name", "").endswith(".md"))


def fetch_category(slug):
    url = common.LIST_RAW + slug + ".md"
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read().decode("utf-8", "replace")


def pick(spec, available):
    if spec == "core":
        wanted = common.CORE_CATEGORIES
    elif spec == "topup":
        wanted = common.TOPUP_CATEGORIES
    elif spec == "core+topup":
        wanted = common.CORE_CATEGORIES + common.TOPUP_CATEGORIES
    elif spec == "all":
        wanted = available
    else:
        wanted = [s.strip() for s in spec.split(",") if s.strip()]
    missing = [s for s in wanted if s not in available]
    if missing:
        print("note: not on the live list: %s" % ", ".join(missing), file=sys.stderr)
    return [s for s in wanted if s in available]


def load(spec, from_dir=None):
    if from_dir:
        files = {p.stem: p.read_text() for p in sorted(pathlib.Path(from_dir).glob("*.md"))}
        return {s: files[s] for s in pick(spec, sorted(files))}
    return {s: fetch_category(s) for s in pick(spec, list_categories())}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--categories", default="core")
    ap.add_argument("--from-dir", help="read category .md files from a folder instead of the network")
    ap.add_argument("--out", default=str(common.WORK / "queue.json"))
    args = ap.parse_args(argv)
    categories = load(args.categories, args.from_dir)
    queue, summaries = merge(categories)
    common.write_json(args.out, queue)
    common.write_json(common.WORK / "summaries.json", summaries)
    print("queued %d GitHub projects from %d categories -> %s" % (len(queue), len(categories), args.out))


if __name__ == "__main__":
    main()
