"""Tests for Jev's Radar. Run from the repo root: python3 -m unittest discover tests"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import textwrap
import unittest

RADAR = pathlib.Path(__file__).resolve().parent.parent / "skills" / "jev-where" / "scripts" / "jev_radar.py"
FAKE_KEY = "fixture-not-a-real-key-0123456789"
FAKE_ENV = "env-secret-ZZZ-should-never-print"


def write(root, rel, text):
    path = pathlib.Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip())


def radar(*args):
    out = subprocess.run([sys.executable, "-I", str(RADAR), *args], capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise AssertionError(out.stderr)
    return out.stdout


def make_app(root):
    write(root, "app/router.py", '''
        import re

        URGENT_WORDS = ["urgent", "asap", "down"]
        BILLING = re.compile(r"\\b(refund|invoice)\\b", re.I)

        def route(ticket):
            if BILLING.search(ticket["body"]):
                return "billing"
            return "general"
        ''')
    write(root, "app/sentiment.py", '''
        from openai import OpenAI
        client = OpenAI()

        def is_angry(body):
            resp = client.chat.completions.create(
                model="m",
                messages=[{"role": "system", "content": "Answer only YES or NO."}],
            )
            return resp.choices[0].message.content.startswith("YES")
        ''')
    write(root, "app/refunds.py", '''
        AUTO_REFUND_LIMIT_USD = 50

        def auto_refund(ticket, order):
            return "refund" in ticket["body"] and order["amount"] <= AUTO_REFUND_LIMIT_USD
        ''')
    write(root, "app/kb.py", '''
        def suggest_articles(body, articles):
            return sorted(articles, key=lambda a: len(a), reverse=True)[:3]
        ''')
    write(root, "app/settings.py", 'OPENAI_API_KEY = "%s"\n' % FAKE_KEY)
    write(root, ".env", "DB_PASSWORD=%s\n" % FAKE_ENV)
    write(root, "node_modules/lib/index.js", "const r = new RegExp('x');\n")


class RadarTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        make_app(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_finds_each_kind(self):
        data = json.loads(radar(self.root, "--json"))
        kinds = {(h["path"], h["kind"]) for h in data["hits"]}
        self.assertIn(("app/sentiment.py", "llm_label_call"), kinds)
        self.assertIn(("app/router.py", "regex_rule"), kinds)
        self.assertIn(("app/router.py", "keywords"), kinds)
        self.assertIn(("app/router.py", "routing"), kinds)
        self.assertIn(("app/refunds.py", "threshold"), kinds)
        self.assertIn(("app/refunds.py", "gate"), kinds)
        self.assertIn(("app/kb.py", "ranking"), kinds)
        self.assertIn(("app/settings.py", "secret_in_code"), kinds)

    def test_skips_dependencies_and_secret_files(self):
        data = json.loads(radar(self.root, "--json"))
        paths = {h["path"] for h in data["hits"]}
        self.assertFalse(any(p.startswith("node_modules") for p in paths))
        self.assertIn("node_modules", data["skipped"]["dirs"])
        self.assertIn(".env", data["skipped"]["secret_files"])

    def test_never_prints_secret_values(self):
        for mode in ([], ["--json"]):
            out = radar(self.root, *mode)
            self.assertNotIn(FAKE_KEY, out)
            self.assertNotIn(FAKE_ENV, out)
            self.assertIn("***", out)

    def test_footprints_from_git_history(self):
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
                   GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")

        def git(*a):
            subprocess.run(["git", "-C", self.root, *a], check=True, capture_output=True, env=env)

        git("init", "-q")
        git("add", "app")
        git("commit", "-q", "-m", "initial")
        router = pathlib.Path(self.root) / "app/router.py"
        for words, msg in ((["urgent", "asap", "down", "outage"], "fix false positive in urgent words"),
                           (["urgent", "asap", "outage"], "tickets misrouted, drop down")):
            text = router.read_text().replace(
                router.read_text().splitlines()[2], "URGENT_WORDS = %s" % json.dumps(words))
            router.write_text(text)
            git("commit", "-q", "-am", msg)
        data = json.loads(radar(self.root, "--json", "--footprints"))
        hit = next(h for h in data["hits"] if h["path"] == "app/router.py" and "URGENT_WORDS" in h["snippet"])
        fp = hit["footprints"]
        self.assertGreaterEqual(fp["edits"], 3)
        self.assertGreaterEqual(fp["fixes"], 1)
        self.assertGreaterEqual(fp["complaints"], 1)
        self.assertGreaterEqual(data["footprints_hot"], 1)
        self.assertIn("hot rules", radar(self.root, "--footprints"))

    def test_footprints_say_when_nothing_is_hot(self):
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
                   GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
        for args in (["init", "-q"], ["add", "app"], ["commit", "-q", "-m", "initial"]):
            subprocess.run(["git", "-C", self.root, *args], check=True, capture_output=True, env=env)
        self.assertIn("no hot rules found", radar(self.root, "--footprints"))
        self.assertEqual(json.loads(radar(self.root, "--json", "--footprints"))["footprints_hot"], 0)

    def test_footprints_skip_quietly_outside_git(self):
        data = json.loads(radar(self.root, "--json", "--footprints"))
        self.assertIn("not a git repository", data["footprints"])


if __name__ == "__main__":
    unittest.main()
