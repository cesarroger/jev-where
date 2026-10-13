#!/usr/bin/env python3
"""Turn audited reader answers into skills/jev-where/sightings/sightings.jsonl and SIGHTINGS.md.

Each answer is audited again here, exactly as it will be published (fixable
problems trimmed, anything else left out). Records already in the file stay
unless this build has newer facts for them, and a record keeps its first
"verified" date while its pinned commit is unchanged.

Usage:
    python3 -I tools/sightings/build.py work/reads/a.jsonl [more.jsonl ...]   # later files win
    python3 -I tools/sightings/build.py --check                               # validate the file only
"""
import argparse
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common  # noqa: E402
import audit as audit_mod  # noqa: E402
import health as health_mod  # noqa: E402
import locate  # noqa: E402

RE_PERMALINK = re.compile(r"^https://github\.com/[^/]+/[^/]+/blob/[0-9a-f]{40}/\S+#L\d+(-L\d+)?$")


def compact(rec):
    """Ordered record; non-verified records drop empty fields."""
    rec = common.ordered(rec, common.RECORD_KEYS)
    if rec["status"] != "verified":
        rec = {k: v for k, v in rec.items() if v not in (None, [], {})}
    return rec


def make_call(repo, sha, call):
    c = dict(call)
    c["permalink"] = common.permalink(repo, sha, call["path"], call["start"], call["end"])
    c["in"] = locate.place(call["path"])
    return common.ordered(c, common.CALL_KEYS)


def health_of(h):
    return {"archived": bool(h.get("archived")), "quiet": health_mod.quiet(h.get("pushed"))}


def usable(read, cand, summaries):
    """The answer as it can be published: as is, trimmed of fixable problems, or None.

    The build audits the exact answer it uses, so a stale audit file can't let
    an unchecked answer through."""
    if not read or read.get("status") not in ("verified", "no-jev-found"):
        return None
    if not audit_mod.audit_one(read, cand, summaries, final=True):
        return read
    fixed = audit_mod.repair(read, cand, summaries)
    return None if audit_mod.audit_one(fixed, cand, summaries, final=True) else fixed


def build_records(existing, queue, health, candidates, reads, summaries, date):
    """Merge this run's facts into the existing records. Returns {key: record}."""
    records = {common.repo_key(r["repo"]): r for r in existing}
    names = {common.repo_key(q["repo"]): q for q in queue}
    for key in sorted(set(names) | set(candidates)):
        q = names.get(key, {})
        h = health.get(key, {})
        cand = candidates.get(key, {})
        repo = h.get("full_name") or cand.get("full_name") or q.get("repo") or records.get(key, {}).get("repo")
        out = common.repo_key(repo)  # differs from key when the project was renamed
        old = records.get(key) or records.get(out) or {}

        def put(rec):
            if out != key:
                records.pop(key, None)
            records[out] = compact(rec)

        listed = sorted(set(q.get("categories", [])) | set(old.get("listed_in", [])))
        name = common.clean_name(q.get("name") or old.get("name")) or repo.split("/", 1)[1]
        base = {"repo": repo, "name": name, "listed_in": listed}
        if h.get("exists") is False:
            put(dict(old, **base, status="gone"))  # keeps the old facts, in case it comes back
            continue
        if h.get("private"):
            put(dict(base, status="private"))
            continue
        if not cand or cand.get("skipped"):
            continue
        read = reads.get(key)
        if read is None and cand.get("auto") == "no-jev-found":
            put(dict(base, status="no-jev-found", sha=cand["sha"]))
            continue
        read = usable(read, cand, summaries.get(key, []))
        if read is None:
            continue
        if read["status"] == "no-jev-found":
            put(dict(base, status="no-jev-found", sha=cand["sha"]))
            continue
        same = old.get("status") == "verified" and old.get("sha") == cand["sha"]
        put(dict(
            base,
            status="verified",
            verified=old["verified"] if same else date,
            sha=cand["sha"],
            kind=read["kind"],
            lang=read["lang"],
            stack=read["stack"],
            calls=[make_call(repo, cand["sha"], c) for c in read["calls"]],
            about=read.get("about"),
            evidence=read.get("evidence", []),
            health=health_of(h) if h else old.get("health"),
        ))
    return records


def meta(records, date):
    counts = {s: 0 for s in common.STATUSES}
    for r in records:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {"meta": {"schema": common.SCHEMA, "generated": date, "verified": counts["verified"],
                     "no_jev_found": counts["no-jev-found"], "gone": counts["gone"], "private": counts["private"],
                     "discovered_via": "https://github.com/yibie/awesome-jev"}}


def sorted_records(records):
    """Sorted by the record's own repo name, which can differ from its key after a rename."""
    return sorted(records.values(), key=lambda r: common.repo_key(r["repo"]))


def write_outputs(records, date, path=common.SIGHTINGS_PATH, index=common.INDEX_PATH):
    rows = sorted_records(records)
    common.write_jsonl(path, [meta(rows, date)] + rows)
    pathlib.Path(index).write_text(render_index(rows, date))


def short_path(permalink):
    tail = permalink.split("/blob/", 1)[1].split("/", 1)[1]
    path, _, lines = tail.partition("#L")
    return "%s:%s" % (path, lines.split("-")[0])


def render_index(rows, date):
    verified = [r for r in rows if r["status"] == "verified"]
    other = {s: sum(1 for r in rows if r["status"] == s) for s in ("no-jev-found", "gone", "private")}
    out = [
        "# Jev Sightings",
        "",
        "Projects where Jev was actually spotted in the code: each entry links to the",
        "exact lines that ask Jev a typed question, pinned to the commit we read. JEV",
        "WHERE? cites these as verified precedents. Descriptions are our own words.",
        "",
        "Projects were discovered through [awesome-jev](https://github.com/yibie/awesome-jev),",
        "then their code was read by Claude and checked by automatic audits. Every",
        "project belongs to its authors, and a sighting is not an endorsement. This file",
        "is generated by `tools/sightings/build.py`; don't edit it by hand.",
        "",
        "**%d verified** (updated %s). Also checked: %d with no Jev call found, %d gone, %d private." % (
            len(verified), date, other["no-jev-found"], other["gone"], other["private"]),
        "",
    ]
    by_pattern = {}
    for r in verified:
        for c in r["calls"]:
            by_pattern.setdefault(c["pattern"], []).append((r, c))
    for slug in common.PATTERNS:
        items = by_pattern.get(slug)
        if not items:
            continue
        out += ["## %s" % slug, "", "| Project | Shape | Language | What Jev decides | Code |", "| --- | --- | --- | --- | --- |"]
        seen = set()
        for r, c in sorted(items, key=lambda rc: rc[0]["repo"].lower()):
            if (r["repo"], c["permalink"]) in seen:
                continue
            seen.add((r["repo"], c["permalink"]))
            shapes = ", ".join(s.capitalize() for s in c["shapes"]) or "?"
            note = "" if c["in"] == "app" else " (%s)" % c["in"]
            via = "" if c["via"] in ("sdk", "http") else " via %s" % c["via"]
            name = (r.get("name") or r["repo"]).replace("|", "\\|")
            decides = re.sub(r"\s+", " ", c["decides"] or "").replace("|", "\\|")
            out.append("| [%s](https://github.com/%s) | %s%s | %s | %s%s | [%s](%s) |" % (
                name, r["repo"], shapes, via, ", ".join(r["lang"]), decides, note, short_path(c["permalink"]),
                c["permalink"]))
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def check(path=common.SIGHTINGS_PATH):
    """Validate a sightings file. Returns a list of problems."""
    rows = common.read_jsonl(path)
    if not rows or "meta" not in rows[0]:
        return ["first line must be the meta record"]
    problems = []
    m = rows[0]["meta"]
    if m.get("schema") != common.SCHEMA:
        problems.append("schema is %r, expected %r" % (m.get("schema"), common.SCHEMA))
    recs = rows[1:]
    keys = [common.repo_key(r.get("repo", "")) for r in recs]
    if keys != sorted(keys) or len(set(keys)) != len(keys):
        problems.append("records must be sorted by repo with no duplicates")
    if m.get("verified") != sum(1 for r in recs if r.get("status") == "verified"):
        problems.append("meta verified count is wrong")
    for r in recs:
        tag = r.get("repo", "?")
        if not common.RE_REPO.match(r.get("repo") or ""):
            problems.append("%s: bad repo name" % tag)
        if r.get("name") is not None and common.clean_name(r["name"]) != r["name"]:
            problems.append("%s: unsafe name" % tag)
        if r.get("status") not in common.STATUSES:
            problems.append("%s: bad status" % tag)
            continue
        if r["status"] != "verified":
            continue
        if list(r) != common.RECORD_KEYS:
            problems.append("%s: keys out of order or missing" % tag)
        if not re.fullmatch(r"[0-9a-f]{40}", r.get("sha") or ""):
            problems.append("%s: bad sha" % tag)
        if r.get("kind") not in common.KINDS:
            problems.append("%s: bad kind" % tag)
        for field in ("lang", "stack"):
            v = r.get(field)
            if not isinstance(v, list) or any(not isinstance(x, str) or common.clean_name(x, 40) != x for x in v):
                problems.append("%s: bad %s" % (tag, field))
        if not r.get("calls"):
            problems.append("%s: verified with no calls" % tag)
        for c in r.get("calls", []):
            if list(c) != common.CALL_KEYS:
                problems.append("%s: call keys out of order or missing" % tag)
            if not RE_PERMALINK.match(c.get("permalink") or "") or r["sha"] not in c["permalink"]:
                problems.append("%s: bad permalink" % tag)
            if c.get("pattern") not in common.PATTERNS or c.get("via") not in common.VIAS:
                problems.append("%s: bad pattern or via" % tag)
            if any(s not in common.SHAPES for s in c.get("shapes", [])) or c.get("in") not in common.PLACES:
                problems.append("%s: bad shapes or place" % tag)
            for field in ("decides", "confidence"):
                problems += ["%s: %s" % (tag, p) for p in audit_mod.check_text(field, c.get(field), [])]
        problems += ["%s: %s" % (tag, p) for p in audit_mod.check_text("about", r.get("about"), [])]
    return problems


def dead_links(path=common.SIGHTINGS_PATH, workers=6):
    """Permalinks that don't open on GitHub. Returns a list of (status, url)."""
    import concurrent.futures
    import urllib.error
    import urllib.request

    urls = [c["permalink"] for r in common.read_jsonl(path) if r.get("status") == "verified" for c in r["calls"]]

    def once(url):
        req = urllib.request.Request(url.split("#")[0], method="HEAD", headers={"User-Agent": "jev-sightings-check"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status
        except urllib.error.HTTPError as e:
            return e.code
        except OSError:
            return 0

    def status(url):
        code = once(url)
        if code == 0 or code >= 500:  # GitHub hiccups; try once more
            time.sleep(3)
            code = once(url)
        return code, url

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        return [(code, url) for code, url in pool.map(status, urls) if code != 200]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("reads", nargs="*")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--links", action="store_true", help="with --check: also open every permalink on GitHub")
    ap.add_argument("--queue", default=str(common.WORK / "queue.json"))
    ap.add_argument("--health", default=str(common.WORK / "health.json"))
    ap.add_argument("--candidates", default=str(common.WORK / "candidates"))
    args = ap.parse_args(argv)
    if args.check:
        problems = check()
        if args.links:
            problems += ["dead permalink (HTTP %s): %s" % d for d in dead_links()]
        for p in problems:
            print(p)
        print("sightings.jsonl: %s" % ("OK" if not problems else "%d problems" % len(problems)))
        sys.exit(1 if problems else 0)
    date = common.today()
    existing = [r for r in common.read_jsonl(common.SIGHTINGS_PATH) if "meta" not in r]
    records = build_records(existing, common.read_json(args.queue, []), common.read_json(args.health, {}),
                            audit_mod.load_candidates(args.candidates), audit_mod.load_reads(args.reads),
                            common.read_json(common.WORK / "summaries.json", {}), date)
    write_outputs(records, date)
    rows = sorted_records(records)
    print("wrote %d records (%d verified) -> %s" % (len(rows), sum(r["status"] == "verified" for r in rows),
                                                     common.SIGHTINGS_PATH))
    problems = check()
    if problems:
        print("\n".join(problems))
        sys.exit(1)


if __name__ == "__main__":
    main()
