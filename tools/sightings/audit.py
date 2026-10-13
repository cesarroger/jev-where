#!/usr/bin/env python3
"""Check reader answers against the candidate snippets before they become Sightings.

Every flagged answer goes to a second read by a stronger model. Checks:
- allowed values for status, kind, shapes, pattern, via, place and evidence
- each call's line range sits inside a snippet the reader was shown, near a
  strong or medium Jev signal (or on an HTTP send in a file that clearly
  talks to Jev), in a code file (not Markdown), with its shapes filled in
- our text is short, has no links or secret-looking values, and shares no run
  of 6+ words with the awesome-jev summary, the README excerpt or the code

Usage:
    python3 -I tools/sightings/audit.py work/reads/a.jsonl [work/reads/b.jsonl ...] [--strict]
Later files win when they answer the same repo.
"""
import argparse
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common  # noqa: E402

RE_LINK = re.compile(r"(?i)https?://|www\.|\]\(")
RE_SNIPPET_LINE = re.compile(r"^(\d+): ?(.*)$")
MAX_RANGE = 15
NEAR = 15
TEXT_FIELDS = ("about", "notes")
CALL_TEXT_FIELDS = ("decides", "confidence")


def load_reads(paths):
    reads = {}
    for p in paths:
        for row in common.read_jsonl(p):
            if isinstance(row, dict) and row.get("repo"):
                reads[common.repo_key(row["repo"])] = row
    return reads


def load_candidates(cand_dir):
    out = {}
    for p in sorted(pathlib.Path(cand_dir).glob("*.json")):
        c = common.read_json(p)
        out[common.repo_key(c["repo"])] = c
    return out


def snippet_lines(site):
    lines = {}
    for raw in site.get("snippet", "").split("\n"):
        m = RE_SNIPPET_LINE.match(raw)
        if m:
            lines[int(m.group(1))] = m.group(2)
    return lines


def check_text(label, text, sources):
    problems = []
    if text is None:
        return problems
    if not isinstance(text, str):
        return ["%s is not text" % label]
    if common.word_count(text) > common.MAX_WORDS:
        problems.append("%s longer than %d words" % (label, common.MAX_WORDS))
    if RE_LINK.search(text):
        problems.append("%s contains a link" % label)
    if "\n" in text or "\r" in text:
        problems.append("%s contains a line break" % label)
    if common.radar.mask(text) != text:
        problems.append("%s looks like it contains a secret" % label)
    for name, src in sources:
        if common.shared_run(text, src):
            problems.append("%s copies 6+ words from the %s" % (label, name))
            break
    return problems


def audit_one(read, cand, summaries, final=False):
    p = []
    status = read.get("status")
    if status not in common.READER_STATUSES:
        return ["bad status %r" % status]
    if status == "unsure":
        p.append("reader unsure: %s" % (read.get("notes") or "no reason given"))
    if read.get("kind") not in common.KINDS:
        p.append("bad kind %r" % read.get("kind"))
    for field, limit in (("lang", 2), ("stack", 3)):
        v = read.get(field)
        if not isinstance(v, list) or len(v) > limit or not all(isinstance(x, str) for x in v):
            p.append("%s must be a list of at most %d strings" % (field, limit))
    ev = read.get("evidence")
    if not isinstance(ev, list) or any(e not in common.EVIDENCE for e in ev):
        p.append("bad evidence %r" % ev)
    calls = read.get("calls")
    if not isinstance(calls, list):
        return p + ["calls must be a list"]
    if status == "verified" and not calls:
        p.append("verified with no calls")
    if status == "no-jev-found" and calls:
        p.append("no-jev-found but lists calls")
    if len(calls) > 3:
        p.append("more than 3 calls")

    sites = cand.get("sites", [])
    code_text = "\n".join(l for s in sites for l in snippet_lines(s).values())
    sources = [("awesome-jev summary", s) for s in summaries] + [("README", cand.get("readme", "")),
                                                                ("code", code_text)]
    for field in TEXT_FIELDS:
        p += check_text(field, read.get(field), sources)

    for n, call in enumerate(calls, 1):
        tag = "call %d" % n
        if not isinstance(call, dict):
            p.append("%s is not an object" % tag)
            continue
        if call.get("via") not in common.VIAS:
            p.append("%s: bad via %r" % (tag, call.get("via")))
        shapes = call.get("shapes")
        if not isinstance(shapes, list) or any(s not in common.SHAPES for s in shapes):
            p.append("%s: bad shapes %r" % (tag, shapes))
        if call.get("pattern") not in common.PATTERNS:
            p.append("%s: bad pattern %r" % (tag, call.get("pattern")))
        if call.get("batched") not in (True, False, None):
            p.append("%s: batched must be true, false or null" % tag)
        if not call.get("decides"):
            p.append("%s: missing decides" % tag)
        for field in CALL_TEXT_FIELDS:
            p += check_text("%s %s" % (tag, field), call.get(field), sources)
        start, end = call.get("start"), call.get("end")
        if not isinstance(start, int) or not isinstance(end, int) or start > end:
            p.append("%s: bad line range" % tag)
            continue
        if end - start + 1 > MAX_RANGE:
            p.append("%s: range longer than %d lines" % (tag, MAX_RANGE))
        site = next((s for s in sites if s["path"] == call.get("path") and s["start"] <= start and end <= s["end"]), None)
        if not site:
            p.append("%s: %s:%s-%s is not inside a snippet the reader saw" % (tag, call.get("path"), start, end))
            continue
        if call.get("in") != site.get("in"):
            p.append("%s: in %r does not match the site (%r)" % (tag, call.get("in"), site.get("in")))
        if os.path.splitext(site["path"])[1].lower() in (".md", ".mdx"):
            p.append("%s: points at Markdown, not code" % tag)
        lines = snippet_lines(site)
        near = [common.line_signals(t) for ln, t in lines.items() if start - NEAR <= ln <= end + NEAR]
        best = max((common.LEVEL_RANK[s[0]["level"]] for s in near if s), default=0)
        send_ok = "send" in site.get("ids", []) and bool(cand.get("jev_files", {}).get(site["path"]))
        if best < common.LEVEL_RANK["medium"] and not send_ok:
            p.append("%s: no strong or medium Jev signal within %d lines" % (tag, NEAR))
        if not final and status == "verified" and isinstance(shapes, list) and not shapes:
            p.append("%s: shapes left blank" % tag)
    return p


def repair(read, cand, summaries):
    """A copy of a second-read answer with its fixable problems removed.

    Text that fails a check is dropped (about, notes, a call's confidence),
    and a call with any other problem is dropped. Record-level problems stay."""
    r = json.loads(json.dumps(read))
    probs = audit_one(r, cand, summaries, final=True)
    for field in TEXT_FIELDS:
        if any(x.startswith(field + " ") for x in probs):
            r[field] = None
    keep = []
    for n, call in enumerate(r.get("calls") or [], 1):
        tag = "call %d" % n
        mine = [x for x in probs if x.startswith(tag + ":") or x.startswith(tag + " ")]
        conf = [x for x in mine if x.startswith(tag + " confidence")]
        if conf:
            call["confidence"] = None
        if not [x for x in mine if x not in conf]:
            keep.append(call)
    if isinstance(r.get("calls"), list):
        r["calls"] = keep
    return r


def audit(reads, candidates, summaries, final=False):
    result = {"checked": 0, "pass": [], "flagged": {}, "unread": [], "auto_no_jev": [], "repaired": []}
    for key, cand in sorted(candidates.items()):
        if cand.get("skipped"):
            continue
        if key not in reads:
            if cand.get("auto") == "no-jev-found":
                result["auto_no_jev"].append(cand["repo"])
            else:
                result["unread"].append(cand["repo"])
            continue
        result["checked"] += 1
        problems = audit_one(reads[key], cand, summaries.get(key, []))
        if problems and final:
            fixed = repair(reads[key], cand, summaries.get(key, []))
            if not audit_one(fixed, cand, summaries.get(key, []), final=True):
                reads[key] = fixed
                result["repaired"].append(cand["repo"])
                problems = []
        if problems:
            result["flagged"][cand["repo"]] = problems
        else:
            result["pass"].append(cand["repo"])
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("reads", nargs="+")
    ap.add_argument("--candidates", default=str(common.WORK / "candidates"))
    ap.add_argument("--out", default=str(common.WORK / "audit.json"))
    ap.add_argument("--strict", action="store_true", help="exit 1 when anything is flagged or unread")
    ap.add_argument("--final", action="store_true",
                    help="after the second read: report what build.py will trim, and accept blank shapes")
    args = ap.parse_args(argv)
    summaries = common.read_json(common.WORK / "summaries.json", {})
    reads = load_reads(args.reads)
    result = audit(reads, load_candidates(args.candidates), summaries, final=args.final)
    common.write_json(args.out, result)
    print("checked %d: %d pass (%d trimmed), %d flagged, %d unread, %d with no Jev signal at all -> %s" % (
        result["checked"], len(result["pass"]), len(result["repaired"]), len(result["flagged"]), len(result["unread"]),
        len(result["auto_no_jev"]), args.out))
    for repo, problems in sorted(result["flagged"].items()):
        print("  %s: %s" % (repo, "; ".join(problems)))
    if args.strict and (result["flagged"] or result["unread"]):
        sys.exit(1)


if __name__ == "__main__":
    main()
