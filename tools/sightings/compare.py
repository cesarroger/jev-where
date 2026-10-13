#!/usr/bin/env python3
"""Compare two sets of reader answers for the same projects (for example Haiku vs Opus).

Prints an agreement table: status, shapes, pattern and call site, plus every
disagreement, so we can decide which model reads the main pass.

Usage:
    python3 -I tools/sightings/compare.py work/reads/pilot-haiku.jsonl work/reads/pilot-opus.jsonl
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import audit  # noqa: E402


def shapes(read):
    return sorted({s for c in read.get("calls", []) for s in c.get("shapes", [])})


def patterns(read):
    return sorted({c.get("pattern") for c in read.get("calls", [])})


def overlaps(a, b):
    return any(x.get("path") == y.get("path") and x.get("start", 0) <= y.get("end", 0) and y.get("start", 0) <= x.get("end", 0)
               for x in a.get("calls", []) for y in b.get("calls", []))


def compare(a, b):
    keys = sorted(set(a) & set(b))
    rows = {"status": 0, "shapes": 0, "pattern": 0, "call site": 0}
    both_verified = 0
    diffs = []
    for k in keys:
        x, y = a[k], b[k]
        if x.get("status") == y.get("status"):
            rows["status"] += 1
        else:
            diffs.append((k, "status", x.get("status"), y.get("status")))
        if x.get("status") == y.get("status") == "verified":
            both_verified += 1
            for name, fn in (("shapes", shapes), ("pattern", patterns)):
                if fn(x) == fn(y):
                    rows[name] += 1
                else:
                    diffs.append((k, name, fn(x), fn(y)))
            if overlaps(x, y):
                rows["call site"] += 1
            else:
                diffs.append((k, "call site", [c.get("path") for c in x["calls"]], [c.get("path") for c in y["calls"]]))
    return keys, both_verified, rows, diffs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("first")
    ap.add_argument("second")
    args = ap.parse_args(argv)
    a, b = audit.load_reads([args.first]), audit.load_reads([args.second])
    keys, both, rows, diffs = compare(a, b)
    print("| Check | Agree | Out of |\n| --- | --- | --- |")
    print("| status | %d | %d |" % (rows["status"], len(keys)))
    for name in ("shapes", "pattern", "call site"):
        print("| %s | %d | %d |" % (name, rows[name], both))
    verified = sum(1 for k in keys if b[k].get("status") == "verified")
    print("\nYield (second reader): %d of %d verified" % (verified, len(keys)))
    if diffs:
        print("\nDisagreements (first vs second):")
        for k, what, x, y in diffs:
            print("- %s, %s: %s vs %s" % (k, what, x, y))


if __name__ == "__main__":
    main()
