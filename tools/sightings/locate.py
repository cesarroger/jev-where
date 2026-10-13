#!/usr/bin/env python3
"""Find where each queued project calls Jev, and cut small snippets for the readers.

For each healthy repo: shallow-clone it (latest commit only) into a fresh temp folder, scan the text
for the signals in signals.json, write up to 8 masked snippets (about 20 lines
either side of each call site) to work/candidates/<owner__name>.json, then
delete the clone. Nothing from the clone is ever run, built or installed.

Usage:
    python3 -I tools/sightings/locate.py [--only owner/a,owner/b] [--limit N] [--force]
"""
import argparse
import concurrent.futures
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common  # noqa: E402

radar = common.radar
EXTRA_EXT = {".vue", ".svelte", ".astro", ".html", ".ipynb", ".json", ".md", ".mdx"}
MANIFESTS = {"package.json", "pyproject.toml", "setup.py", "setup.cfg", "Cargo.toml", "go.mod", "Gemfile",
             "build.gradle", "build.sbt", "pom.xml", "deno.json"}
RE_REQUIREMENTS = re.compile(r"^requirements.*\.txt$")
DOC_EXT = {".md", ".mdx"}
RE_SEND = re.compile(
    r"\bfetch\s*\(|\baxios\b|\.(?:post|request|send)\s*\(|\brequests\.\w+\s*\(|\bhttpx\.\w+\s*\("
    r"|\burlopen\s*\(|NewRequest\w*\s*\(|\.Do\s*\(|\breqwest\b|HttpRequest|WebClient|RestTemplate|\bcurl\b"
)
RADIUS = 20
MAX_SITES = 8
MAX_PER_FILE = 2
MAX_LINE = 240
README_LINES = 60
LANG_BY_EXT = {
    ".py": "Python", ".ipynb": "Python", ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript",
    ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript", ".vue": "Vue", ".svelte": "Svelte",
    ".go": "Go", ".rb": "Ruby", ".java": "Java", ".kt": "Kotlin", ".cs": "C#", ".php": "PHP", ".rs": "Rust",
    ".swift": "Swift", ".scala": "Scala", ".ex": "Elixir", ".exs": "Elixir", ".dart": "Dart", ".lua": "Lua",
}
RE_TEST = re.compile(r"(?i)(^|/)(tests?|__tests__|spec|specs|e2e)/|(^|/)(test_[^/]*|tests?\.[a-z]+)$|[._-](test|spec)\.[a-z]+$")
RE_EVAL = re.compile(r"(?i)(^|/)(bench|benchmarks?|evals?|evaluations?)/")
RE_EXAMPLE = re.compile(r"(?i)(^|/)(examples?|demos?|samples?|cookbooks?|notebooks?|playground|docs?)/")


def place(rel):
    if RE_TEST.search(rel):
        return "test"
    if RE_EVAL.search(rel):
        return "eval"
    if RE_EXAMPLE.search(rel) or os.path.splitext(rel)[1].lower() in DOC_EXT:
        return "example"
    return "app"


def is_manifest(name):
    return name in MANIFESTS or bool(RE_REQUIREMENTS.match(name))


def walk(root):
    """Text files worth scanning, reusing the radar's skip rules."""
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in radar.SKIP_DIRS and not d.endswith(".egg-info"))
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if os.path.islink(full) or radar.is_secret_file(name) or radar.skip_file(name):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext not in radar.CODE_EXT and ext not in EXTRA_EXT and not is_manifest(name):
                continue
            if ext == ".json" and name != "package.json" and not name.endswith(".workflow.json"):
                continue
            try:
                if os.path.getsize(full) > radar.MAX_BYTES:
                    continue
            except OSError:
                continue
            files.append((os.path.relpath(full, root), full))
    return files


def read_lines(full):
    try:
        with open(full, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read().split("\n")
    except OSError:
        return []


def clip(line):
    line = radar.mask(line.rstrip())
    return line if len(line) <= MAX_LINE else line[:MAX_LINE] + " …"


def snippet(lines, lineno, radius=RADIUS):
    start = max(1, lineno - radius)
    end = min(len(lines), lineno + radius)
    body = "\n".join("%d: %s" % (i, clip(lines[i - 1])) for i in range(start, end + 1))
    return start, end, body


def score(hit):
    """Prefer the line that sends the request, in app code, over constants, tests and docs."""
    ids = set(hit["ids"])
    if {"endpoint", "api-host"} & ids and hit.get("send"):
        base = 120
    elif "call" in ids:
        base = 100
    elif "send" in ids:
        base = 80
    elif "endpoint" in ids:
        base = 75
    elif "api-host" in ids:
        base = 70
    else:
        base = {3: 50, 2: 20, 1: 1}[hit["rank"]]
    return base + {"app": 30, "example": 5, "eval": 5, "test": 0}[hit["in"]]


def scan_tree(root):
    """Scan a checked-out tree. Returns signal counts, manifest evidence and chosen sites."""
    hits, deps, langs, counts = [], [], {}, {"strong": 0, "medium": 0, "weak": 0}
    jev_files = {}
    ids = {}
    files = walk(root)
    cache = {}
    for rel, full in files:
        lines = read_lines(full)
        name = os.path.basename(rel)
        ext = os.path.splitext(name)[1].lower()
        if ext in LANG_BY_EXT:
            langs[LANG_BY_EXT[ext]] = langs.get(LANG_BY_EXT[ext], 0) + 1
        for i, line in enumerate(lines, 1):
            found = common.line_signals(line)
            if not found:
                continue
            for s in found:
                counts[s["level"]] += 1
                ids[s["id"]] = ids.get(s["id"], 0) + 1
            top = found[0]
            if is_manifest(name):
                if top["level"] == "strong":
                    deps.append({"path": rel, "line": i, "ids": sorted({s["id"] for s in found})})
                continue
            cache[rel] = lines
            if top["level"] == "strong" and ext not in DOC_EXT:
                jev_files.setdefault(rel, set()).update(s["id"] for s in found if s["level"] == "strong")
            hits.append({"path": rel, "line": i, "rank": common.LEVEL_RANK[top["level"]],
                         "level": top["level"], "ids": sorted({s["id"] for s in found}),
                         "via": next((s["via"] for s in found if s["via"]), None), "in": place(rel),
                         "send": bool(RE_SEND.search(line))})
    hits += send_hits(hits, cache)
    hits.sort(key=lambda h: (-score(h), h["path"], h["line"]))
    sites, per_file = [], {}
    for h in hits:
        if len(sites) >= MAX_SITES:
            break
        if per_file.get(h["path"], 0) >= MAX_PER_FILE:
            continue
        if any(s["path"] == h["path"] and abs(s["line"] - h["line"]) <= 2 * RADIUS for s in sites):
            continue
        start, end, body = snippet(cache[h["path"]], h["line"])
        sites.append(dict(h, start=start, end=end, snippet=body))
        per_file[h["path"]] = per_file.get(h["path"], 0) + 1
    for s in sites:
        s.pop("rank", None)
        s.pop("send", None)
    return {
        "files_scanned": len(files),
        "signal_counts": counts,
        "signal_ids": ids,
        "deps": deps[:10],
        "languages": sorted(langs, key=lambda k: -langs[k])[:4],
        "sites": sites,
        "jev_files": {k: sorted(v) for k, v in sorted(jev_files.items())},
        "readme": readme_excerpt(root),
    }


def send_hits(hits, cache):
    """HTTP sends in code files that also hold a strong or medium Jev signal.

    Hand-written clients often keep the API address in one place and send the
    request elsewhere in the same file; this finds the send."""
    files = {h["path"] for h in hits if h["rank"] >= 2 and os.path.splitext(h["path"])[1].lower() not in DOC_EXT}
    taken = {(h["path"], h["line"]) for h in hits}
    out = []
    for rel in sorted(files):
        for i, line in enumerate(cache[rel], 1):
            if (rel, i) in taken or not RE_SEND.search(line) or radar.RE_COMMENT.match(line):
                continue
            out.append({"path": rel, "line": i, "rank": 2, "level": "medium", "ids": ["send"], "via": "http",
                        "in": place(rel)})
    return out


def readme_excerpt(root):
    for name in ("README.md", "readme.md", "Readme.md", "README.MD", "README.rst", "README"):
        path = os.path.join(root, name)
        if os.path.isfile(path) and not os.path.islink(path):
            return "\n".join(clip(l) for l in read_lines(path)[:README_LINES])
    return ""


def clone(repo, branch, dest):
    env = dict(os.environ, GIT_LFS_SKIP_SMUDGE="1", GIT_TERMINAL_PROMPT="0")
    cmd = ["git", "-c", "core.symlinks=false", "-c", "protocol.file.allow=never", "-c", "core.hooksPath=/dev/null",
           "-c", "credential.helper=",
           "clone", "--quiet", "--depth", "1", "--single-branch", "--no-tags"]
    if branch:
        cmd += ["--branch", branch]
    cmd += ["https://github.com/%s.git" % repo, dest]
    subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300, check=True)
    out = subprocess.run(["git", "-C", dest, "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    return out.stdout.strip()


def locate(info, max_kb):
    repo = info.get("full_name") or info["repo"]
    base = {"repo": info["repo"], "full_name": repo}
    if (info.get("size_kb") or 0) > max_kb:
        return dict(base, skipped="larger than %d MB" % (max_kb // 1024))
    tmp = tempfile.mkdtemp(prefix="sightings-")
    try:
        dest = os.path.join(tmp, "repo")
        try:
            sha = clone(repo, info.get("default_branch"), dest)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            return dict(base, skipped="clone failed: %s" % type(e).__name__)
        found = scan_tree(dest)
        result = dict(base, sha=sha, default_branch=info.get("default_branch"), api_language=info.get("language"),
                      **found)
        if not any(found["signal_counts"].values()):
            result["auto"] = "no-jev-found"
        return result
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def out_name(repo):
    return repo.replace("/", "__") + ".json"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--health", default=str(common.WORK / "health.json"))
    ap.add_argument("--out-dir", default=str(common.WORK / "candidates"))
    ap.add_argument("--only", help="comma-separated owner/name list")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--force", action="store_true", help="redo repos that already have a candidates file")
    ap.add_argument("--max-mb", type=int, default=2500, help="skip repos whose GitHub size is larger")
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args(argv)
    health = common.read_json(args.health, {})
    todo = list(health.values())
    if args.only:
        wanted = {common.repo_key(r.strip()) for r in args.only.split(",") if r.strip()}
        todo = [h for h in todo if common.repo_key(h["repo"]) in wanted]
    todo = [h for h in todo if h.get("exists") and not h.get("private")]
    out_dir = pathlib.Path(args.out_dir)
    if not args.force:
        todo = [h for h in todo if not (out_dir / out_name(h["repo"])).exists()]
    if args.limit:
        todo = todo[: args.limit]
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for result in pool.map(lambda h: locate(h, args.max_mb * 1024), todo):
            common.write_json(out_dir / out_name(result["repo"]), result)
            done += 1
            flag = result.get("skipped") or result.get("auto") or "%d sites" % len(result.get("sites", []))
            print("[%d/%d] %s: %s" % (done, len(todo), result["repo"], flag), flush=True)


if __name__ == "__main__":
    main()
