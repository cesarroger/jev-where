"""Shared helpers for the Jev Sightings maintainer tools. Standard library only.

These tools build skills/jev-where/sightings/sightings.jsonl. They never run
code from the projects they look at, and they never store awesome-jev text or
project code in the repo: only names, links, and our own words.
"""
import datetime
import importlib.util
import json
import pathlib
import re
import subprocess
import urllib.parse

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
WORK = HERE / "work"
RADAR_PATH = ROOT / "skills" / "jev-where" / "scripts" / "jev_radar.py"
SIGHTINGS_PATH = ROOT / "skills" / "jev-where" / "sightings" / "sightings.jsonl"
INDEX_PATH = ROOT / "SIGHTINGS.md"

SCHEMA = "jev-where/sightings@1"
LIST_REPO = "yibie/awesome-jev"
LIST_RAW = "https://raw.githubusercontent.com/yibie/awesome-jev/main/categories/"
CORE_CATEGORIES = ["classification-routing", "verification-guardrails", "scoring-ranking", "agent-decisions"]
TOPUP_CATEGORIES = ["content-moderation", "data-labeling-curation", "evaluation-benchmarking"]

# Stable slugs for the 14 patterns in skills/jev-where/references/patterns.md, in order.
PATTERNS = [
    "intent-routing", "model-routing", "fuzzy-check", "multi-label", "severity",
    "rubric-judge", "approval-gate", "moderation", "output-verification",
    "agent-guardrail", "agent-next-step", "pick-value", "duplicate-match", "relevance-rerank",
]
SHAPES = ["choice", "score", "noul"]
STATUSES = ["verified", "no-jev-found", "gone", "private"]
READER_STATUSES = ["verified", "no-jev-found", "unsure"]
KINDS = ["app", "library", "integration", "demo", "benchmark"]
PLACES = ["app", "example", "eval", "test"]
VIAS = ["sdk", "http", "adapter", "integration"]
EVIDENCE = ["tests", "benchmark", "production", "ci"]

RECORD_KEYS = ["repo", "name", "status", "verified", "sha", "kind", "lang", "stack", "calls",
               "about", "evidence", "health", "listed_in"]
CALL_KEYS = ["permalink", "via", "shapes", "pattern", "decides", "confidence", "batched", "in"]

MAX_WORDS = 30
QUIET_DAYS = 180


def load_radar():
    """Import Jev's Radar from the skill so the tools reuse its walker and masking."""
    spec = importlib.util.spec_from_file_location("jev_radar", str(RADAR_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


radar = load_radar()


def load_signals():
    data = json.loads((HERE / "signals.json").read_text())
    for s in data["signals"]:
        s["re"] = re.compile(s["pattern"])
    return data["signals"]


SIGNALS = load_signals()
LEVEL_RANK = {"strong": 3, "medium": 2, "weak": 1}


def line_signals(line):
    """Return the signals that match one line, strongest first."""
    found = [s for s in SIGNALS if s["re"].search(line)]
    return sorted(found, key=lambda s: -LEVEL_RANK[s["level"]])


RE_UNSAFE_NAME = re.compile(r"[`|<>\[\]@\\]")
RE_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def clean_name(name, limit=60):
    """A listing's display name made safe for Markdown tables, PR bodies and reports."""
    name = re.sub(r"[\x00-\x1f\x7f]", " ", name or "")
    name = RE_UNSAFE_NAME.sub("", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:limit].strip() or None


def days_between(a, b):
    return (datetime.date.fromisoformat(b[:10]) - datetime.date.fromisoformat(a[:10])).days


def today():
    return datetime.date.today().isoformat()


def repo_key(repo):
    return repo.lower()


RE_GITHUB = re.compile(r"^https?://(?:www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")


def github_repo(url):
    """owner/name for a GitHub project URL, or None."""
    m = RE_GITHUB.match(url.strip())
    if not m:
        return None
    owner, name = m.group(1), m.group(2)
    if name.endswith(".git"):
        name = name[:-4]
    if owner.lower() in ("orgs", "topics", "sponsors", "features", "marketplace") or not name:
        return None
    return "%s/%s" % (owner, name)


def gh_api(path):
    """GET a GitHub API path through the gh CLI. Returns (status, data or None)."""
    try:
        out = subprocess.run(["gh", "api", "-i", path], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return 0, None
    text = out.stdout.replace("\r\n", "\n")
    head, _, body = text.partition("\n\n")
    m = re.match(r"HTTP/\S+ (\d{3})", head)
    status = int(m.group(1)) if m else 0
    try:
        data = json.loads(body) if body.strip() else None
    except ValueError:
        data = None
    return status, data


def ordered(d, keys):
    return {k: d.get(k) for k in keys}


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def read_jsonl(path):
    path = pathlib.Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path, rows):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(dumps(r) + "\n" for r in rows))


def read_json(path, default=None):
    path = pathlib.Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text())


def write_json(path, data):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")


def word_count(text):
    return len(re.findall(r"\S+", text or ""))


def words(text):
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def shared_run(a, b, n=6):
    """True when texts a and b share a run of n or more words."""
    wa, wb = words(a), words(b)
    if len(wa) < n or len(wb) < n:
        return False
    grams = {tuple(wb[i:i + n]) for i in range(len(wb) - n + 1)}
    return any(tuple(wa[i:i + n]) in grams for i in range(len(wa) - n + 1))


def permalink(repo, sha, path, start, end):
    lines = "L%d" % start if end in (None, start) else "L%d-L%d" % (start, end)
    return "https://github.com/%s/blob/%s/%s#%s" % (repo, sha, urllib.parse.quote(path), lines)
