#!/usr/bin/env python3
"""Jev's Radar: sweep a codebase for fuzzy decision points before Claude reads it.

Prints a compact, repeatable list of `path:line` hits grouped by kind, so the
JEV WHERE? skill reads hotspots instead of every file. It never prints secret
values: secret files (.env, keys) are skipped and secret-looking values in
code are masked. With --footprints it also checks git history for rules that
keep getting edited or fixed. Standard library only (Python 3.8+).

Usage:
    python3 jev_radar.py [PATH] [--footprints] [--json] [--max-per-kind N]
"""
import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
import time

VERSION = 1

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", "bower_components", ".venv", "venv",
    "env", "site-packages", "__pycache__", ".mypy_cache", ".pytest_cache", ".tox", "dist",
    "build", "out", ".next", ".nuxt", ".svelte-kit", "target", "coverage", ".gradle",
    ".idea", ".vscode", ".codegraph", ".terraform", "Pods", "DerivedData",
}
SECRET_FILES = [
    ".env", ".env.*", "*.env", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa*", "id_ed25519*",
    "credentials*", "*.keystore", "secrets.*",
]
SKIP_FILES = [
    "*.min.js", "*.min.css", "*.map", "*.lock", "package-lock.json", "yarn.lock",
    "pnpm-lock.yaml", "poetry.lock", "Cargo.lock", "go.sum", "composer.lock",
]
CODE_EXT = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".rb", ".java", ".kt",
    ".kts", ".cs", ".php", ".rs", ".swift", ".scala", ".ex", ".exs", ".dart", ".lua",
    ".yaml", ".yml", ".toml",
}
MAX_BYTES = 1_000_000

KINDS = [
    ("existing_jev", "Existing Jev or TypeSafe use"),
    ("llm_label_call", "LLM call that seems to return only a label, score, or yes/no"),
    ("llm_call", "Other LLM call (check what it returns)"),
    ("regex_rule", "Regex rule"),
    ("keywords", "Keyword list or substring check"),
    ("threshold", "Hard-coded threshold or limit"),
    ("routing", "Routing, dispatch, or classification function"),
    ("gate", "Gate, approval, or filter function"),
    ("ranking", "Ranking, scoring, or priority"),
    ("secret_in_code", "Secret-looking value in code (masked)"),
]
KIND_ORDER = {k: i for i, (k, _) in enumerate(KINDS)}

RE_EXISTING_JEV = re.compile(r"(?i)\btypesafe\b|\bnoul\b|\bjev\b")
RE_LLM_CALL = re.compile(
    r"(?:chat\.completions|messages|responses|completions)\.create\s*\("
    r"|\bgenerate(?:Text|Object)\s*\(|\bstreamText\s*\("
    r"|\b(?:llm|chat|model|chain)\.(?:invoke|predict|generate|run)\s*\("
    r"|\bcompletion\s*\(|\bChat(?:OpenAI|Anthropic)\s*\("
)
RE_LABEL_CUE = re.compile(
    r"(?i)answer only|respond only|reply only|only (?:answer|respond|reply|return|output)"
    r"|\byes or no\b|\byes/no\b|true or false|one word|single word"
    r"|return (?:only )?(?:the |a )?(?:label|category|class|score|number)"
    r"|\bclassify\b|\bcategori[sz]e\b|\bsentiment\b|rate (?:it |this )?(?:from )?[01] ?(?:to|-) ?(?:5|10)"
    r"|startswith\(\s*[\"'](?:yes|no|true|false)"
)
RE_REGEX = re.compile(
    r"\bre\.(?:compile|search|match|fullmatch|findall|finditer|sub)\s*\("
    r"|new RegExp\s*\(|/[^/\n]{2,}/[gimsuy]*\.test\s*\(|\.match\(\s*/"
    r"|regexp\.(?:MustCompile|Compile)\s*\(|\bRegex\s*\(|=~\s*/"
)
RE_KEYWORD_LIST = re.compile(
    r"^\s*(?:export\s+)?(?:const\s+|let\s+|var\s+|final\s+|static\s+)*"
    r"([A-Za-z_][A-Za-z0-9_]*(?:WORDS|KEYWORDS|TERMS|PHRASES|BANNED|BLOCK|ALLOW|DENY|STOP|SPAM|URGENT|LIST)"
    r"[A-Za-z0-9_]*)\s*[:=]\s*[\[\{\(]",
    re.IGNORECASE,
)
RE_SUBSTRING = re.compile(
    r"[\"'][^\"'\n]{2,40}[\"']\s+(?:not\s+)?in\s+[A-Za-z_][\w\.\[\]\"']*"
    r"|\.includes\(\s*[\"'][^\"']{2,40}[\"']\s*\)|strings\.Contains\(|\.contains\(\s*\""
)
RE_THRESHOLD = re.compile(
    r"\b[A-Z][A-Z0-9_]*(?:LIMIT|THRESHOLD|CUTOFF|MIN|MAX|SCORE|CONFIDENCE)[A-Z0-9_]*\s*[:=]\s*-?\d"
    r"|[<>]=?\s*0?\.\d+\b"
)
RE_DEF_STRICT = re.compile(
    r"^\s*(?:async\s+def|def|(?:export\s+)?(?:async\s+)?function|func|fn)\s+([A-Za-z_][A-Za-z0-9_]*)"
    r"|^\s*(?:export\s+)?(?:const|let)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?\("
)
RE_ROUTING_NAME = re.compile(r"(?i)route|dispatch|classif|triage|categori|assign|pick_|choose|select_|which_|queue_for")
RE_GATE_NAME = re.compile(
    r"(?i)^should_|^can_|allow|approve|block|hold|moderat|flag|eligib|permit|is_spam|is_abuse"
    r"|is_angry|is_toxic|is_urgent|is_fraud|auto_|guard|screen"
)
RE_RANK_NAME = re.compile(r"(?i)score|rank|priorit|relevan|sever|urgen|suggest|recommend|sort_by")
RE_SORT = re.compile(r"\bsorted\s*\([^)]*key\s*=|\.sort\s*\(\s*(?:key\s*=|\(|function|\w+\s*=>)|\.sort_by\b|order_by\(")
RE_COMMENT = re.compile(r"^\s*(?:#|//|/\*|\*|--|;)")

RE_SECRET_ASSIGN = re.compile(
    r"(?i)\b([A-Za-z0-9_]*(?:API_?KEY|SECRET|TOKEN|PASSW(?:OR)?D|PASSWD|PWD|DSN|DATABASE_URL|DB_URL"
    r"|CREDENTIAL|PRIVATE_?KEY|ACCESS_?KEY|AUTH)[A-Za-z0-9_]*)(\s*[:=]\s*)([\"'])([^\"'\n]{4,})\3"
)
RE_URL_CREDS = re.compile(r"://[^/\s:@]+:[^/\s@]+@")
RE_KNOWN_TOKEN = re.compile(r"\b(?:sk|pk|rk|ghp|gho|ghs|xox[abprs]|AKIA|AIza)[-_A-Za-z0-9]{8,}")
RE_LONG_TOKEN = re.compile(r"(?<![A-Za-z0-9_\-])[A-Za-z0-9_\-+/=]{32,}(?![A-Za-z0-9_\-])")

FIX_RE = re.compile(
    r"(?i)\b(?:fix(?:es|ed)?|bug|revert|hotfix|patch|false (?:positive|negative)s?|misrout\w*"
    r"|wrong (?:team|queue|label|category|priority)|miscategori[sz]\w*|not flagged|let through|too many)\b"
)
COMPLAINT_RE = re.compile(
    r"(?i)false (?:positive|negative)|misrout|wrong (?:team|queue|label|category|priority)"
    r"|miscategori|not flagged|let through|got through|too (?:many|strict|loose)"
)


def mask(text):
    """Hide secret values in one line of code. Never returns the original value."""
    text = RE_SECRET_ASSIGN.sub(lambda m: m.group(1) + m.group(2) + m.group(3) + "***" + m.group(3), text)
    text = RE_URL_CREDS.sub("://***:***@", text)
    text = RE_KNOWN_TOKEN.sub("***", text)
    text = RE_LONG_TOKEN.sub("***", text)
    return text


def is_secret_file(name):
    return any(fnmatch.fnmatch(name, p) for p in SECRET_FILES)


def skip_file(name):
    return any(fnmatch.fnmatch(name, p) for p in SKIP_FILES)


def walk(root):
    """Yield (relative_path, absolute_path) for code files; record what was skipped."""
    skipped = {"dirs": set(), "secret_files": [], "large_files": []}
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        keep = []
        for d in sorted(dirnames):
            if d in SKIP_DIRS or d.endswith(".egg-info"):
                skipped["dirs"].add(d)
            else:
                keep.append(d)
        dirnames[:] = keep
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            if is_secret_file(name):
                skipped["secret_files"].append(rel)
                continue
            if skip_file(name) or os.path.splitext(name)[1].lower() not in CODE_EXT:
                continue
            try:
                if os.path.getsize(full) > MAX_BYTES:
                    skipped["large_files"].append(rel)
                    continue
            except OSError:
                continue
            files.append((rel, full))
    return files, skipped


def scan_file(rel, full):
    try:
        with open(full, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.read().split("\n")
    except OSError:
        return []
    hits = []
    current_fn = ""
    for i, raw in enumerate(lines, start=1):
        line = raw.rstrip()
        if not line.strip():
            continue
        m = RE_DEF_STRICT.match(line)
        if m:
            current_fn = m.group(1) or m.group(2) or current_fn
        kinds = []
        comment = bool(RE_COMMENT.match(line))
        if RE_SECRET_ASSIGN.search(line) and not comment:
            kinds.append("secret_in_code")
        if RE_EXISTING_JEV.search(line) and not rel.lower().endswith((".yaml", ".yml", ".toml")):
            kinds.append("existing_jev")
        if not comment:
            if RE_LLM_CALL.search(line):
                window = "\n".join(lines[max(0, i - 8): min(len(lines), i + 8)])
                kinds.append("llm_label_call" if RE_LABEL_CUE.search(window) else "llm_call")
            if RE_REGEX.search(line):
                kinds.append("regex_rule")
            if RE_KEYWORD_LIST.search(line) or RE_SUBSTRING.search(line):
                kinds.append("keywords")
            if RE_THRESHOLD.search(line):
                kinds.append("threshold")
            if m:
                name = m.group(1) or m.group(2) or ""
                if RE_ROUTING_NAME.search(name):
                    kinds.append("routing")
                elif RE_GATE_NAME.search(name):
                    kinds.append("gate")
                elif RE_RANK_NAME.search(name):
                    kinds.append("ranking")
            if RE_SORT.search(line):
                kinds.append("ranking")
        if not kinds:
            continue
        kinds = sorted(set(kinds), key=lambda k: KIND_ORDER[k])
        snippet = mask(line.strip())
        if len(snippet) > 120:
            snippet = snippet[:117] + "..."
        hits.append({
            "kind": kinds[0],
            "also": kinds[1:],
            "path": rel,
            "line": i,
            "function": current_fn,
            "snippet": snippet,
        })
    return hits


def git_root(root):
    try:
        out = subprocess.run(["git", "-C", root, "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else None


def footprints(repo, abs_path, line, now):
    """Count commits that touched lines around `line`, recent ones, and fix-like ones."""
    rel = os.path.relpath(os.path.realpath(abs_path), os.path.realpath(repo))
    start, end = max(1, line - 2), line + 2
    try:
        out = subprocess.run(
            ["git", "-C", repo, "log", "-L%d,%d:%s" % (start, end, rel), "--format=__FP__%H%x09%ct%x09%s"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    edits = recent = fixes = 0
    for row in out.stdout.splitlines():
        if not row.startswith("__FP__"):
            continue
        parts = row[6:].split("\t", 2)
        if len(parts) < 3:
            continue
        edits += 1
        try:
            if now - int(parts[1]) <= 90 * 86400:
                recent += 1
        except ValueError:
            pass
        if FIX_RE.search(parts[2]):
            fixes += 1
    complaints = 0
    try:
        log = subprocess.run(["git", "-C", repo, "log", "--format=%s", "--", rel],
                             capture_output=True, text=True, timeout=10)
        complaints = sum(1 for s in log.stdout.splitlines() if COMPLAINT_RE.search(s))
    except (OSError, subprocess.SubprocessError):
        pass
    heat = edits + 2 * recent + 3 * fixes + 2 * complaints
    return {"edits": edits, "recent_90d": recent, "fixes": fixes, "complaints": complaints, "heat": heat}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Jev's Radar: find fuzzy decision points (read-only).")
    ap.add_argument("path", nargs="?", default=".", help="project folder to scan (default: current folder)")
    ap.add_argument("--footprints", action="store_true", help="add git history clues (needs git)")
    ap.add_argument("--json", action="store_true", help="print JSON instead of text")
    ap.add_argument("--max-per-kind", type=int, default=40, help="cap hits shown per kind (default 40)")
    ap.add_argument("--footprints-limit", type=int, default=30, help="max hits to check in git (default 30)")
    args = ap.parse_args(argv)

    root = os.path.realpath(os.path.abspath(args.path))
    if not os.path.isdir(root):
        print("Jev's Radar: not a folder: %s" % args.path, file=sys.stderr)
        return 2

    files, skipped = walk(root)
    hits = []
    for rel, full in files:
        hits.extend(scan_file(rel, full))
    hits.sort(key=lambda h: (KIND_ORDER[h["kind"]], h["path"], h["line"]))

    fp_note = None
    if args.footprints:
        repo = git_root(root)
        if not repo:
            fp_note = "not a git repository; Footprints skipped"
        else:
            now = int(time.time())
            checkable = [h for h in hits if h["kind"] not in ("secret_in_code", "existing_jev")]
            for h in checkable[: args.footprints_limit]:
                fp = footprints(repo, os.path.join(root, h["path"]), h["line"], now)
                if fp:
                    h["footprints"] = fp
            if len(checkable) > args.footprints_limit:
                fp_note = "checked the first %d of %d hits" % (args.footprints_limit, len(checkable))

    def is_hot(fp):
        return bool(fp) and (fp["edits"] >= 2 or fp["fixes"] or fp["complaints"])

    hot = sum(1 for h in hits if is_hot(h.get("footprints")))

    shown, hidden = [], {}
    per_kind = {}
    for h in hits:
        per_kind[h["kind"]] = per_kind.get(h["kind"], 0) + 1
        if per_kind[h["kind"]] <= args.max_per_kind:
            shown.append(h)
        else:
            hidden[h["kind"]] = hidden.get(h["kind"], 0) + 1

    report = {
        "tool": "jev-radar",
        "version": VERSION,
        "root": root,
        "scanned_files": len(files),
        "skipped": {
            "dirs": sorted(skipped["dirs"]),
            "secret_files": skipped["secret_files"],
            "large_files": skipped["large_files"],
        },
        "counts": per_kind,
        "hits": shown,
        "hidden_over_cap": hidden,
        "footprints": fp_note or ("on" if args.footprints else "off"),
        "footprints_hot": hot if args.footprints else None,
    }

    if args.json:
        print(json.dumps(report, indent=1))
        return 0

    print("Jev's Radar: %s" % root)
    print("Scanned %d code files." % len(files))
    if skipped["dirs"]:
        print("Skipped folders: %s" % ", ".join(sorted(skipped["dirs"])))
    if skipped["secret_files"]:
        print("Skipped secret files (not opened): %s" % ", ".join(skipped["secret_files"]))
    if skipped["large_files"]:
        print("Skipped large files: %s" % ", ".join(skipped["large_files"]))
    if args.footprints:
        if fp_note and fp_note.startswith("not a git"):
            print("Footprints: %s" % fp_note)
        elif hot:
            print("Footprints: %d hot rules (edited 2+ times, or touched by fix or complaint commits)%s"
                  % (hot, "; " + fp_note if fp_note else ""))
        else:
            print("Footprints: ran, no hot rules found (nothing edited 2+ times or touched by fix or "
                  "complaint commits)%s" % ("; " + fp_note if fp_note else ""))
    if not hits:
        print("No decision points found.")
        return 0
    for kind, label in KINDS:
        group = [h for h in shown if h["kind"] == kind]
        if not group:
            continue
        print("\n[%s] %s (%d)" % (kind, label, per_kind[kind]))
        for h in group:
            where = "%s:%d" % (h["path"], h["line"])
            fn = (" " + h["function"]) if h["function"] else ""
            also = (" +" + ",".join(h["also"])) if h["also"] else ""
            print("  %s%s%s  %s" % (where, fn, also, h["snippet"]))
            fp = h.get("footprints")
            if is_hot(fp):
                print("    footprints: edited %d times (%d in the last 90 days), %d fix-like, %d complaint commits"
                      % (fp["edits"], fp["recent_90d"], fp["fixes"], fp["complaints"]))
        if hidden.get(kind):
            print("  ... %d more %s hits (raise --max-per-kind to see them)" % (hidden[kind], kind))
    return 0


if __name__ == "__main__":
    sys.exit(main())
