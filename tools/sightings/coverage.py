#!/usr/bin/env python3
"""Show how well Jev Sightings covers each pattern and language, and pick what to read next.

Targets: at least 3 verified sightings per pattern, and the 7 most common
patterns covered in both Python and JS/TS (JavaScript or TypeScript).

Usage:
    python3 -I tools/sightings/coverage.py                 # coverage table
    python3 -I tools/sightings/coverage.py --select 50     # also pick the next 50 unread projects
"""
import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common  # noqa: E402

PER_PATTERN = 3
BOTH_LANGS = ["intent-routing", "fuzzy-check", "severity", "approval-gate", "moderation",
              "output-verification", "agent-guardrail"]
FAMILY = {"Python": "Python", "TypeScript": "JS/TS", "JavaScript": "JS/TS"}

# Words in a listing that hint at a pattern, used only to choose what to read next.
HINTS = {
    "intent-routing": r"rout|triage|classif|dispatch|categor|inbox|ticket|queue",
    "model-routing": r"model rout|which model|llm rout|cheap|tier",
    "fuzzy-check": r"regex|keyword|lint|grep|rule|detect",
    "multi-label": r"\btag|label|multi",
    "severity": r"priorit|severity|urgen|risk|score",
    "rubric-judge": r"judge|rubric|grade|eval",
    "approval-gate": r"approv|gate|eligib|permission|allow|merge",
    "moderation": r"moderat|spam|abuse|toxic|scam|phish|spoiler|nsfw",
    "output-verification": r"verif|hallucin|ground|fact|faithful|correct|citation",
    "agent-guardrail": r"guardrail|block|safe|dangerous|tool call|command|sandbox",
    "agent-next-step": r"next step|stop|retry|escalat|loop|done|continue",
    "pick-value": r"extract|pick|field|select|choose",
    "duplicate-match": r"duplicat|dedup|match|same|merge",
    "relevance-rerank": r"rerank|relevan|retriev|search|rank",
}


def verified_rows(path=common.SIGHTINGS_PATH):
    return [r for r in common.read_jsonl(path) if r.get("status") == "verified"]


def tally(rows):
    counts = {p: {"all": 0, "Python": 0, "JS/TS": 0, "other": 0} for p in common.PATTERNS}
    for r in rows:
        fams = {FAMILY.get(l, "other") for l in r.get("lang", [])} or {"other"}
        for p in {c["pattern"] for c in r["calls"]}:
            counts[p]["all"] += 1
            for f in fams:
                counts[p][f] += 1
    return counts


def gaps(counts):
    """What each pattern still needs: {pattern: set of 'any', 'Python', 'JS/TS'}."""
    need = {}
    for p, c in counts.items():
        want = set()
        if c["all"] < PER_PATTERN:
            want.add("any")
        if p in BOTH_LANGS:
            want |= {f for f in ("Python", "JS/TS") if c[f] == 0}
        if want:
            need[p] = want
    return need


def table(counts):
    need = gaps(counts)
    lines = ["| Pattern | Verified | Python | JS/TS | Other | Target |", "| --- | --- | --- | --- | --- | --- |"]
    for p in common.PATTERNS:
        c = counts[p]
        lines.append("| %s | %d | %d | %d | %d | %s |" % (p, c["all"], c["Python"], c["JS/TS"], c["other"],
                                                         "met" if p not in need else "needs " + ", ".join(sorted(need[p]))))
    met = sum(1 for p in common.PATTERNS if p not in need)
    lines.append("\n%d of %d patterns meet the target." % (met, len(common.PATTERNS)))
    return "\n".join(lines)


def select(n, need, queue, health, summaries, done):
    """Rank unread, healthy projects by how many open gaps their listing hints at."""
    scored = []
    for q in queue:
        key = common.repo_key(q["repo"])
        h = health.get(key, {})
        if key in done or not h.get("exists") or h.get("private"):
            continue
        text = " ".join([q["name"]] + summaries.get(key, [])).lower()
        fam = FAMILY.get(h.get("language") or "", "other")
        score = 0
        for p, want in need.items():
            if re.search(HINTS[p], text):
                score += 2 if "any" in want else 0
                score += 3 if fam in want else 0
        score += 1 if re.search(r"test|production|benchmark|eval", text) else 0
        score += 1 if fam in ("Python", "JS/TS") else 0
        scored.append((-score, key, q["repo"]))
    scored.sort()
    return [repo for _, _, repo in scored[:n]]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--select", type=int, default=0, help="pick this many unread projects to read next")
    ap.add_argument("--out", default=str(common.WORK / "next.json"))
    args = ap.parse_args(argv)
    counts = tally(verified_rows())
    print(table(counts))
    if args.select:
        done = {common.repo_key(r["repo"]) for r in common.read_jsonl(common.SIGHTINGS_PATH) if "meta" not in r}
        done |= {common.repo_key(p.stem.replace("__", "/")) for p in (common.WORK / "candidates").glob("*.json")
                 if common.read_json(p).get("sites") is not None and _read_already(p)}
        picked = select(args.select, gaps(counts), common.read_json(common.WORK / "queue.json", []),
                        common.read_json(common.WORK / "health.json", {}),
                        common.read_json(common.WORK / "summaries.json", {}), done)
        common.write_json(args.out, picked)
        print("\npicked %d projects -> %s" % (len(picked), args.out))


def _read_already(cand_path):
    """True when some reads file already answers this candidate."""
    key = common.repo_key(common.read_json(cand_path)["repo"])
    for p in (common.WORK / "reads").glob("*.jsonl"):
        if any(common.repo_key(r.get("repo", "")) == key for r in common.read_jsonl(p)):
            return True
    return False


if __name__ == "__main__":
    main()
