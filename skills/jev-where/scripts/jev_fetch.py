#!/usr/bin/env python3
"""JEV WHERE? fetcher: downloads only the pages the skill needs, from a fixed allowlist.

The skill pre-approves this script instead of curl, so a command built from
untrusted text can't fetch other URLs, upload files, or write outside a
temporary folder. Every URL is built here from a known target; redirects to
other hosts are refused; pages are saved to files and never printed.

Targets:
    categories             awesome-jev's category list (from the README's "Current coverage"
                           section, or the folder listing if that fails) -> categories.txt
    category:<slug>        one awesome-jev category file -> category-<slug>.md
    sightings              the newest Jev Sightings file from this plugin's repo, else the copy
                           bundled with the skill -> sightings.jsonl
    repo:<owner>/<name>    GitHub's public facts about one repo (still there? archived? renamed?)
                           -> repo-<owner>__<name>.json; at most 10 per call

Usage:
    python3 jev_fetch.py [--dir DIR] [--offline] TARGET [TARGET ...]

The first call creates a temporary folder and prints it; pass it back with
--dir on later calls. Standard library only (Python 3.8+).
"""
import argparse
import json
import os
import pathlib
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

ALLOWED_HOSTS = {"raw.githubusercontent.com", "api.github.com"}
LIST_RAW = "https://raw.githubusercontent.com/yibie/awesome-jev/main/"
LIST_API = "https://api.github.com/repos/yibie/awesome-jev/contents/categories"
SIGHTINGS_URL = "https://raw.githubusercontent.com/cesarroger/jev-where/main/skills/jev-where/sightings/sightings.jsonl"
SIGHTINGS_SCHEMA = "jev-where/sightings@1"
BUNDLED = pathlib.Path(__file__).resolve().parent.parent / "sightings" / "sightings.jsonl"
MARKER = ".jev-where-fetch"
MAX_BYTES = 3_000_000
MAX_REPOS = 10
TIMEOUT = 20

RE_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RE_PART = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}$")
RE_COVERAGE_LINK = re.compile(r"\[([^\]]+)\]\((?:\./)?categories/([a-z0-9-]+)\.md\)")
RE_ENTRY = re.compile(r"^- \[[^\]]+\]\([^)\s]+\)")


class FetchError(Exception):
    pass


def allowed_url(url):
    parts = urllib.parse.urlsplit(url)
    return parts.scheme == "https" and parts.hostname in ALLOWED_HOSTS and not parts.username


class SameHostsRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl):
            raise urllib.error.HTTPError(newurl, code, "redirect to a host outside the allowlist", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


OPENER = urllib.request.build_opener(SameHostsRedirects)


def get(url):
    """Body of an allowlisted URL, as bytes. Raises FetchError with a short reason."""
    if not allowed_url(url):
        raise FetchError("not on the allowlist")
    req = urllib.request.Request(url, headers={"User-Agent": "jev-where-fetch", "Accept": "*/*"})
    try:
        with OPENER.open(req, timeout=TIMEOUT) as resp:
            body = resp.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        raise FetchError("HTTP %s" % e.code)
    except (urllib.error.URLError, OSError) as e:
        raise FetchError("network error (%s)" % type(e).__name__)
    if len(body) > MAX_BYTES:
        raise FetchError("page too large")
    return body


def work_dir(given):
    """The folder to write into: one this script created, inside the system temp folder."""
    if given:
        path = pathlib.Path(given).resolve()
        tmp = pathlib.Path(tempfile.gettempdir()).resolve()
        if not (path.is_dir() and (path / MARKER).is_file() and tmp in path.parents):
            raise SystemExit("--dir must be a folder this script created earlier; run without --dir to make one")
        return path
    path = pathlib.Path(tempfile.mkdtemp(prefix="jev-where-")).resolve()
    (path / MARKER).write_text("created by jev_fetch.py\n")
    return path


def parse_coverage(readme):
    """(slug, title) pairs linked from the README's "Current coverage" section."""
    out, inside = [], False
    for line in readme.splitlines():
        if line.startswith("#"):
            if inside:
                break
            inside = "current coverage" in line.lower()
            continue
        if inside:
            for title, slug in RE_COVERAGE_LINK.findall(line):
                if (slug, title) not in out:
                    out.append((slug, title))
    return out


def do_categories(folder, offline):
    if offline:
        return "categories: skipped (no network)"
    pairs, source = [], "README"
    try:
        pairs = parse_coverage(get(LIST_RAW + "README.md").decode("utf-8", "replace"))
    except FetchError as e:
        source = "folder listing (README: %s)" % e
    if not pairs:
        if source == "README":
            source = "folder listing (README had no coverage section)"
        try:
            listing = json.loads(get(LIST_API).decode("utf-8", "replace"))
            pairs = [(d["name"][:-3], d["name"][:-3]) for d in listing
                     if isinstance(d, dict) and str(d.get("name", "")).endswith(".md") and RE_SLUG.match(d["name"][:-3])]
        except (FetchError, ValueError, KeyError, TypeError) as e:
            return "categories: failed (%s)" % e
    target = folder / "categories.txt"
    target.write_text("".join("%s\t%s\n" % (slug, title) for slug, title in pairs))
    return "categories: %d, from the %s -> %s" % (len(pairs), source, target)


def do_category(folder, slug, offline):
    if offline:
        return "category %s: skipped (no network)" % slug
    try:
        text = get(LIST_RAW + "categories/%s.md" % slug).decode("utf-8", "replace")
    except FetchError as e:
        return "category %s: failed (%s)" % (slug, e)
    target = folder / ("category-%s.md" % slug)
    target.write_text(text)
    entries = sum(1 for l in text.splitlines() if RE_ENTRY.match(l) and not l.startswith("- [Name](URL)"))
    return "category %s: %d entries -> %s" % (slug, entries, target)


def sightings_meta(text):
    try:
        meta = json.loads(text.split("\n", 1)[0])["meta"]
    except (ValueError, KeyError, TypeError, IndexError):
        return None
    return meta if isinstance(meta, dict) and meta.get("schema") == SIGHTINGS_SCHEMA else None


def do_sightings(folder, offline):
    target = folder / "sightings.jsonl"
    why = "no network"
    if not offline:
        try:
            text = get(SIGHTINGS_URL).decode("utf-8", "replace")
            meta = sightings_meta(text)
            if meta:
                target.write_text(text)
                return "sightings: live copy, generated %s, %s verified -> %s" % (
                    meta.get("generated"), meta.get("verified"), target)
            why = "live copy has an unexpected format"
        except FetchError as e:
            why = "live copy unavailable: %s" % e
    try:
        text = BUNDLED.read_text()
    except OSError:
        return "sightings: none (%s, and no bundled copy)" % why
    meta = sightings_meta(text)
    if not meta:
        return "sightings: none (%s, and the bundled copy has an unexpected format)" % why
    target.write_text(text)
    return "sightings: bundled copy (%s), generated %s, %s verified -> %s" % (
        why, meta.get("generated"), meta.get("verified"), target)


def do_repo(folder, owner, name, offline):
    repo = "%s/%s" % (owner, name)
    if offline:
        return "repo %s: not rechecked (no network)" % repo
    try:
        data = json.loads(get("https://api.github.com/repos/%s" % repo).decode("utf-8", "replace"))
    except FetchError as e:
        if str(e) == "HTTP 404":
            facts = {"repo": repo, "exists": False}
            (folder / ("repo-%s__%s.json" % (owner, name))).write_text(json.dumps(facts) + "\n")
            return "repo %s: gone (HTTP 404)" % repo
        return "repo %s: not rechecked (%s)" % (repo, e)
    except ValueError:
        return "repo %s: not rechecked (unexpected reply)" % repo
    full = data.get("full_name") if isinstance(data, dict) else None
    facts = {"repo": repo, "exists": True, "archived": bool(data.get("archived")), "full_name": full}
    (folder / ("repo-%s__%s.json" % (owner, name))).write_text(json.dumps(facts) + "\n")
    notes = ["live"]
    if facts["archived"]:
        notes.append("archived")
    if full and full.lower() != repo.lower():
        notes.append("renamed to %s" % full)
    return "repo %s: %s" % (repo, ", ".join(notes))


def parse_target(raw):
    """A validated (kind, args) tuple, or None. Never echoes rejected input."""
    if raw in ("categories", "sightings"):
        return (raw,)
    if raw.startswith("category:"):
        slug = raw[len("category:"):]
        return ("category", slug) if len(slug) <= 60 and RE_SLUG.match(slug) else None
    if raw.startswith("repo:"):
        parts = raw[len("repo:"):].split("/")
        if len(parts) == 2 and all(RE_PART.match(p) and ".." not in p for p in parts):
            return ("repo", parts[0], parts[1])
    return None


def run(argv=None):
    ap = argparse.ArgumentParser(description="Fetch the pages JEV WHERE? needs, from a fixed allowlist.")
    ap.add_argument("--dir", help="a folder this script created earlier")
    ap.add_argument("--offline", action="store_true", help="no network: skip fetches and use the bundled Sightings")
    ap.add_argument("targets", nargs="+")
    args = ap.parse_args(argv)
    folder = work_dir(args.dir)
    lines = ["folder: %s" % folder]
    repos = 0
    for n, raw in enumerate(args.targets, 1):
        t = parse_target(raw)
        if t is None:
            lines.append("target %d: rejected (not a known target)" % n)
        elif t[0] == "categories":
            lines.append(do_categories(folder, args.offline))
        elif t[0] == "category":
            lines.append(do_category(folder, t[1], args.offline))
        elif t[0] == "sightings":
            lines.append(do_sightings(folder, args.offline))
        else:
            repos += 1
            if repos > MAX_REPOS:
                lines.append("repo %s/%s: not rechecked (more than %d repos in one call)" % (t[1], t[2], MAX_REPOS))
            else:
                lines.append(do_repo(folder, t[1], t[2], args.offline))
    print("\n".join(lines))


if __name__ == "__main__":
    run()
