"""Tests for the skill's fetcher. Run from the repo root: python3 -m unittest discover tests

They run offline: network calls are replaced by a stub.
"""
import contextlib
import importlib.util
import io
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "skills" / "jev-where" / "scripts" / "jev_fetch.py"
spec = importlib.util.spec_from_file_location("jev_fetch", str(SCRIPT))
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)

README = """# awesome-jev

## Current coverage

- [Classification & Routing](categories/classification-routing.md)
- [Content Moderation](./categories/content-moderation.md) - spam and abuse

## All entries

- [Elsewhere](categories/not-this-one.md)
"""
CATEGORY = """# Content Moderation

- [Spam Guard](https://github.com/acme/spam-guard) - Chat: one Noul per message.

## Submission format

- [Name](URL) - ...
"""


def run(*args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        fetch.run(list(args))
    return out.getvalue()


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.pages = {}
        self.calls = []
        self.real_get = fetch.get

        def fake_get(url):
            self.calls.append(url)
            if not fetch.allowed_url(url):
                raise fetch.FetchError("not on the allowlist")
            if url not in self.pages:
                raise fetch.FetchError("HTTP 404")
            return self.pages[url].encode()

        fetch.get = fake_get
        self.made = []

    def tearDown(self):
        fetch.get = self.real_get
        for d in self.made:
            shutil.rmtree(d, ignore_errors=True)

    def folder_of(self, out):
        d = out.splitlines()[0].split("folder: ", 1)[1]
        self.made.append(d)
        return pathlib.Path(d)

    def test_rejects_unknown_targets_without_echoing_them(self):
        bad = ["https://evil.example/x", "category:../../etc", "repo:a/../b", "repo:a/b/c", "$(cat ~/.ssh/id_rsa)",
               "category:Has Spaces", "repo:.hidden/x"]
        out = run(*bad)
        self.folder_of(out)
        self.assertEqual(out.count("rejected (not a known target)"), len(bad))
        for b in bad:
            self.assertNotIn(b, out)
        self.assertEqual(self.calls, [])

    def test_categories_come_from_the_coverage_section(self):
        self.pages[fetch.LIST_RAW + "README.md"] = README
        out = run("categories")
        text = (self.folder_of(out) / "categories.txt").read_text()
        self.assertEqual(text, "classification-routing\tClassification & Routing\ncontent-moderation\tContent Moderation\n")
        self.assertIn("categories: 2, from the README", out)

    def test_category_is_saved_not_printed(self):
        self.pages[fetch.LIST_RAW + "categories/content-moderation.md"] = CATEGORY
        out = run("category:content-moderation")
        self.assertIn("category content-moderation: 1 entries", out)
        self.assertNotIn("Spam Guard", out)
        self.assertIn("Spam Guard", (self.folder_of(out) / "category-content-moderation.md").read_text())

    def test_sightings_fall_back_to_the_bundled_copy(self):
        out = run("sightings")
        self.assertIn("sightings: bundled copy (live copy unavailable: HTTP 404)", out)
        first = (self.folder_of(out) / "sightings.jsonl").read_text().split("\n", 1)[0]
        self.assertEqual(json.loads(first)["meta"]["schema"], fetch.SIGHTINGS_SCHEMA)

    def test_sightings_live_copy_must_match_the_schema(self):
        self.pages[fetch.SIGHTINGS_URL] = '{"meta":{"schema":"something-else"}}\n'
        out = run("sightings")
        self.folder_of(out)
        self.assertIn("live copy has an unexpected format", out)

    def test_repo_recheck(self):
        self.pages["https://api.github.com/repos/acme/live"] = json.dumps({"full_name": "acme/live", "archived": False})
        self.pages["https://api.github.com/repos/acme/old"] = json.dumps({"full_name": "acme/new", "archived": True})
        out = run("repo:acme/live", "repo:acme/old", "repo:acme/gone")
        self.folder_of(out)
        self.assertIn("repo acme/live: live\n", out)
        self.assertIn("repo acme/old: live, archived, renamed to acme/new", out)
        self.assertIn("repo acme/gone: gone (HTTP 404)", out)

    def test_at_most_ten_repos_per_call(self):
        out = run(*["repo:acme/r%d" % i for i in range(12)])
        self.folder_of(out)
        self.assertEqual(out.count("more than 10 repos"), 2)

    def test_offline_makes_no_requests(self):
        out = run("--offline", "categories", "category:x", "sightings", "repo:a/b")
        self.folder_of(out)
        self.assertEqual(self.calls, [])
        self.assertIn("sightings: bundled copy (no network)", out)

    def test_only_allowlisted_https_urls(self):
        self.assertTrue(fetch.allowed_url("https://raw.githubusercontent.com/yibie/awesome-jev/main/README.md"))
        self.assertFalse(fetch.allowed_url("http://raw.githubusercontent.com/x"))
        self.assertFalse(fetch.allowed_url("https://evil.example/x"))
        self.assertFalse(fetch.allowed_url("https://user:pw@api.github.com/x"))
        self.assertFalse(fetch.allowed_url("https://raw.githubusercontent.com.evil.example/x"))

    def test_dir_must_be_one_it_created(self):
        with tempfile.TemporaryDirectory() as plain:
            out = subprocess.run([sys.executable, "-I", str(SCRIPT), "--dir", plain, "--offline", "sightings"],
                                 capture_output=True, text=True)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("folder this script created", out.stderr)
        first = run("--offline", "sightings")
        d = self.folder_of(first)
        again = run("--dir", str(d), "--offline", "sightings")
        self.assertIn("folder: %s" % d, again)


if __name__ == "__main__":
    unittest.main()
