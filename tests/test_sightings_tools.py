"""Tests for the Jev Sightings maintainer tools. Run from the repo root: python3 -m unittest discover tests

They run offline: no cloning, and GitHub answers come from a fake fetcher.
"""
import json
import pathlib
import sys
import tempfile
import textwrap
import unittest

TOOLS = pathlib.Path(__file__).resolve().parent.parent / "tools" / "sightings"
sys.path.insert(0, str(TOOLS))

import audit  # noqa: E402
import build  # noqa: E402
import common  # noqa: E402
import compare  # noqa: E402
import harvest  # noqa: E402
import health  # noqa: E402
import locate  # noqa: E402
import refresh  # noqa: E402

SHA = "a" * 40
FAKE_SECRET = "zz-fixture-secret-value-0123456789abcdef"

CATEGORY = """\
# Content Moderation

## Projects

- [Spoiler Guard](https://github.com/acme/spoiler-guard) `{type: extension}` - Media: hides spoilers in comments with one yes/no question per comment.
- [Docs Only](https://example.com/post) - Blog: a write-up about moderation.
- [Twice Listed](https://github.com/acme/twice.git) - Media: listed in two categories.

## Submission format

- [Name](URL) - ...
"""
OTHER = "- [Twice Listed](https://github.com/acme/twice) - Tools: the same project again.\n"


def write(root, rel, text):
    path = pathlib.Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip())


def make_repo(root):
    write(root, "src/check.ts", '''
        import { noul, TypeSafeClient } from "@typesafe-ai/sdk";

        const client = new TypeSafeClient();
        const apiKey = "%s";

        export async function isSpoiler(comment: string, title: string) {
          const res = await client.systemOne({
            state: { comment, title },
            questions: { spoiler: noul("The comment reveals a plot event of the title.") },
          });
          return res.nouls.spoiler.probability > 0.7;
        }
        ''' % FAKE_SECRET)
    write(root, "tests/check.test.ts", '''
        import { TypeSafeClient } from "@typesafe-ai/sdk";
        test("calls jev", async () => { await new TypeSafeClient().systemOne({ state: {}, questions: {} }); });
        ''')
    write(root, "README.md", '''
        # Spoiler Guard
        A tiny browser helper that keeps spoilers out of the comment section using Jev.
        ''')
    write(root, "package.json", '{"dependencies": {"@typesafe-ai/sdk": "^0.6.0"}}\n')
    write(root, "node_modules/@typesafe-ai/sdk/index.js", "export class TypeSafeClient { systemOne() {} }\n")
    write(root, ".env", "TYPESAFE_API_KEY=%s\n" % FAKE_SECRET)


def candidate(root):
    found = locate.scan_tree(root)
    return dict(found, repo="acme/spoiler-guard", full_name="acme/spoiler-guard", sha=SHA, default_branch="main")


def good_read():
    return {"repo": "acme/spoiler-guard", "status": "verified", "kind": "app", "lang": ["TypeScript"],
            "stack": ["Chrome extension"],
            "calls": [{"path": "src/check.ts", "start": 7, "end": 12, "via": "sdk", "shapes": ["noul"],
                       "pattern": "moderation", "decides": "whether a comment gives away part of a story",
                       "confidence": "treats it as a spoiler above 0.7", "batched": False, "in": "app"}],
            "about": "browser helper that hides story spoilers in comments", "evidence": [], "notes": None}


class FakeGitHub:
    def __init__(self, repos):
        self.repos = repos

    def __call__(self, path):
        parts = path.split("/")
        repo = "/".join(parts[1:3])
        info = self.repos.get(repo)
        if info is None:
            return 404, {"message": "Not Found"}
        if len(parts) > 3 and parts[3] == "commits":
            return 200, {"sha": info.get("sha", SHA)}
        return 200, dict({"full_name": repo, "private": False, "archived": False, "fork": False,
                          "default_branch": "main", "size": 10, "language": "TypeScript",
                          "pushed_at": common.today() + "T00:00:00Z", "stargazers_count": 1}, **info)


class HarvestTests(unittest.TestCase):
    def test_parses_entries_and_skips_the_template(self):
        entries = harvest.parse_category(CATEGORY)
        self.assertEqual([e["name"] for e in entries], ["Spoiler Guard", "Docs Only", "Twice Listed"])
        self.assertTrue(entries[0]["summary"].startswith("Media:"))

    def test_merge_keeps_github_projects_once_with_every_category(self):
        queue, summaries = harvest.merge({"content-moderation": CATEGORY, "infra": OTHER})
        self.assertEqual([q["repo"] for q in queue], ["acme/spoiler-guard", "acme/twice"])
        self.assertEqual(queue[1]["categories"], ["content-moderation", "infra"])
        self.assertEqual(len(summaries["acme/twice"]), 2)


class LocateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        make_repo(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_picks_the_app_call_first_and_labels_tests(self):
        found = locate.scan_tree(self.tmp.name)
        first = found["sites"][0]
        self.assertEqual((first["path"], first["in"]), ("src/check.ts", "app"))
        self.assertIn("call", first["ids"])
        self.assertIn("test", {s["in"] for s in found["sites"]})
        self.assertEqual(found["deps"][0]["path"], "package.json")
        self.assertIn("TypeScript", found["languages"])

    def test_skips_dependencies_and_secret_files_and_masks_values(self):
        found = locate.scan_tree(self.tmp.name)
        dumped = json.dumps(found)
        self.assertNotIn("node_modules", dumped)
        self.assertNotIn(".env", [s["path"] for s in found["sites"]])
        self.assertNotIn(FAKE_SECRET, dumped)

    def test_no_signal_tree_has_no_sites(self):
        with tempfile.TemporaryDirectory() as empty:
            write(empty, "main.py", "print('hello')\n")
            found = locate.scan_tree(empty)
        self.assertEqual(found["sites"], [])
        self.assertFalse(any(found["signal_counts"].values()))

    def test_place(self):
        self.assertEqual(locate.place("examples/demo.py"), "example")
        self.assertEqual(locate.place("docs/guide.md"), "example")
        self.assertEqual(locate.place("pkg/foo_test.go"), "test")
        self.assertEqual(locate.place("src/jev/client/tests.rs"), "test")
        self.assertEqual(locate.place("src/app.py"), "app")
        self.assertEqual(locate.place("benchmarks/run.py"), "eval")


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        make_repo(self.tmp.name)
        self.cand = candidate(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def problems(self, read, summaries=()):
        return audit.audit_one(read, self.cand, list(summaries))

    def test_good_read_passes(self):
        self.assertEqual(self.problems(good_read()), [])

    def test_bad_values_are_flagged(self):
        r = good_read()
        r["calls"][0]["shapes"] = ["maybe"]
        r["calls"][0]["pattern"] = "vibes"
        joined = "; ".join(self.problems(r))
        self.assertIn("bad shapes", joined)
        self.assertIn("bad pattern", joined)

    def test_range_outside_the_snippet_is_flagged(self):
        r = good_read()
        r["calls"][0]["start"], r["calls"][0]["end"] = 400, 405
        self.assertIn("not inside a snippet", "; ".join(self.problems(r)))

    def test_copied_text_links_and_secrets_are_flagged(self):
        r = good_read()
        r["about"] = "keeps spoilers out of the comment section using Jev"
        self.assertIn("copies 6+ words from the README", "; ".join(self.problems(r)))
        r["about"] = "see https://example.com"
        self.assertIn("contains a link", "; ".join(self.problems(r)))
        r["about"] = "token sk-FAKE-for-tests-only"
        self.assertIn("secret", "; ".join(self.problems(r)))
        r = good_read()
        r["calls"][0]["decides"] = "hides spoilers in comments with one yes/no question per comment"
        self.assertIn("awesome-jev summary", "; ".join(self.problems(r, harvest.parse_category(CATEGORY)[0]["summary"].split("\n"))))

    def test_blank_shapes_go_to_a_second_read(self):
        r = good_read()
        r["calls"][0]["shapes"] = []
        self.assertIn("call 1: shapes left blank", self.problems(r))

    def test_second_read_trims_fixable_problems(self):
        r = good_read()
        r["about"] = "keeps spoilers out of the comment section using Jev"
        r["calls"][0]["shapes"] = []
        r["calls"].append(dict(r["calls"][0], start=400, end=405))
        key = "acme/spoiler-guard"
        result = audit.audit({key: r}, {key: self.cand}, {}, final=True)
        self.assertEqual(result["repaired"], ["acme/spoiler-guard"])
        fixed = audit.repair(r, self.cand, [])
        self.assertIsNone(fixed["about"])
        self.assertEqual(len(fixed["calls"]), 1)

    def test_jev_files_are_listed(self):
        self.assertIn("src/check.ts", self.cand["jev_files"])
        self.assertNotIn("README.md", self.cand["jev_files"])

    def test_status_and_calls_must_agree(self):
        r = good_read()
        r["calls"] = []
        self.assertIn("verified with no calls", self.problems(r))
        r = good_read()
        r["status"] = "unsure"
        r["notes"] = "wrapper not visible"
        self.assertTrue(any(p.startswith("reader unsure") for p in self.problems(r)))


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        make_repo(root / "repo")
        self.cand = candidate(root / "repo")
        self.queue = [{"repo": "acme/spoiler-guard", "name": "Spoiler Guard", "url": "https://github.com/acme/spoiler-guard",
                       "categories": ["content-moderation"]},
                      {"repo": "acme/gone", "name": "Gone", "url": "https://github.com/acme/gone", "categories": ["agent-decisions"]}]
        self.health = {"acme/spoiler-guard": {"repo": "acme/spoiler-guard", "exists": True, "full_name": "acme/spoiler-guard",
                                              "archived": False, "pushed": common.today()},
                       "acme/gone": {"repo": "acme/gone", "exists": False}}
        self.out = root / "sightings.jsonl"
        self.index = root / "SIGHTINGS.md"

    def tearDown(self):
        self.tmp.cleanup()

    def records(self, existing=(), date="2026-10-14"):
        return build.build_records(list(existing), self.queue, self.health, {"acme/spoiler-guard": self.cand},
                                   {"acme/spoiler-guard": good_read()}, {}, date)

    def test_writes_a_valid_file_and_index(self):
        recs = self.records()
        build.write_outputs(recs, "2026-10-14", self.out, self.index)
        self.assertEqual(build.check(self.out), [])
        rows = common.read_jsonl(self.out)
        self.assertEqual(rows[0]["meta"]["verified"], 1)
        verified = rows[[r.get("repo") for r in rows].index("acme/spoiler-guard")]
        self.assertEqual(verified["calls"][0]["permalink"],
                         "https://github.com/acme/spoiler-guard/blob/%s/src/check.ts#L7-L12" % SHA)
        self.assertEqual(recs["acme/gone"]["status"], "gone")
        line = self.out.read_text().splitlines()[2]
        self.assertTrue(line.startswith('{"repo":"acme/spoiler-guard","name":"Spoiler Guard","status":"verified"'))
        text = self.index.read_text()
        self.assertIn("## moderation", text)
        self.assertIn("[src/check.ts:7]", text)

    def test_keeps_the_first_verified_date_while_the_commit_is_unchanged(self):
        first = self.records(date="2026-10-14")
        again = self.records(existing=first.values(), date="2026-11-01")
        self.assertEqual(again["acme/spoiler-guard"]["verified"], "2026-10-14")

    def build_with(self, read, existing=(), health=None, cands=None):
        return build.build_records(list(existing), self.queue, health or self.health,
                                   {"acme/spoiler-guard": self.cand} if cands is None else cands,
                                   {"acme/spoiler-guard": read}, {}, "2026-10-14")

    def test_unsure_or_broken_answers_are_left_out(self):
        self.assertNotIn("acme/spoiler-guard", self.build_with(dict(good_read(), status="unsure", notes="x")))
        broken = good_read()
        broken["calls"][0].update(start=400, end=405)
        self.assertNotIn("acme/spoiler-guard", self.build_with(broken))

    def test_the_build_trims_what_it_publishes(self):
        r = good_read()
        r["about"] = "keeps spoilers out of the comment section using Jev"
        r["calls"].append(dict(r["calls"][0], path="src/other.ts"))
        rec = self.build_with(r)["acme/spoiler-guard"]
        self.assertIsNone(rec["about"])
        self.assertEqual(len(rec["calls"]), 1)

    def test_a_renamed_repo_keeps_its_record_without_a_new_read(self):
        old = self.records()["acme/spoiler-guard"]
        health = dict(self.health, **{"acme/spoiler-guard": dict(self.health["acme/spoiler-guard"], full_name="acme/new-name")})
        recs = self.build_with(None, existing=[old], health=health, cands={})
        self.assertEqual(recs["acme/spoiler-guard"]["status"], "verified")

    def test_a_gone_repo_keeps_its_facts(self):
        old = self.records()["acme/spoiler-guard"]
        health = dict(self.health, **{"acme/spoiler-guard": {"repo": "acme/spoiler-guard", "exists": False}})
        rec = self.build_with(None, existing=[old], health=health, cands={})["acme/spoiler-guard"]
        self.assertEqual(rec["status"], "gone")
        self.assertTrue(rec["calls"])

    def test_names_from_the_list_are_made_safe(self):
        self.assertEqual(common.clean_name("Hi @everyone | <b>`x`</b>\nnext"), "Hi everyone bx/b next")
        self.queue[0]["name"] = "Evil @team [link](x)"
        rec = self.records()["acme/spoiler-guard"]
        self.assertEqual(rec["name"], "Evil team link(x)")

    def test_check_catches_a_bad_file(self):
        recs = self.records()
        build.write_outputs(recs, "2026-10-14", self.out, self.index)
        rows = common.read_jsonl(self.out)
        for r in rows:
            if r.get("status") == "verified":
                r["calls"][0]["permalink"] = "https://example.com/x"
        common.write_jsonl(self.out, rows)
        self.assertIn("acme/spoiler-guard: bad permalink", build.check(self.out))


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.recs = {
            "acme/live": {"repo": "acme/live", "name": "Live", "status": "verified",
                          "health": {"archived": False, "quiet": False}, "listed_in": ["x"]},
            "acme/old": {"repo": "acme/old", "name": "Old", "status": "verified",
                         "health": {"archived": False, "quiet": False}, "listed_in": ["x"]},
            "acme/deleted": {"repo": "acme/deleted", "name": "Deleted", "status": "no-jev-found", "listed_in": ["x"]},
        }

    def test_marks_gone_and_archived_and_leaves_the_rest(self):
        fake = FakeGitHub({"acme/live": {}, "acme/old": {"archived": True}})
        changes = dict(refresh.recheck(self.recs, fake, "2026-10-19"))
        self.assertEqual(self.recs["acme/deleted"]["status"], "gone")
        self.assertTrue(self.recs["acme/old"]["health"]["archived"])
        self.assertNotIn("acme/live", changes)
        self.assertIn("archived", changes["acme/old"])

    def test_a_missing_verified_project_gets_a_week(self):
        self.recs["acme/live"]["calls"] = [{"permalink": "x"}]
        gone = FakeGitHub({})
        refresh.recheck(self.recs, gone, "2026-10-19")
        self.assertEqual(self.recs["acme/live"]["status"], "verified")
        self.assertEqual(self.recs["acme/live"]["health"]["missing"], "2026-10-19")
        self.assertEqual(refresh.recheck(self.recs, gone, "2026-10-21"), [])
        refresh.recheck(self.recs, gone, "2026-10-26")
        self.assertEqual(self.recs["acme/live"]["status"], "gone")
        self.assertTrue(self.recs["acme/live"]["calls"])
        changes = dict(refresh.recheck(self.recs, FakeGitHub({"acme/live": {}}), "2026-11-02"))
        self.assertEqual(self.recs["acme/live"]["status"], "verified")
        self.assertIn("back on GitHub", changes["acme/live"])
        self.assertNotIn("missing", self.recs["acme/live"]["health"])

    def test_a_rename_is_recorded_once(self):
        fake = FakeGitHub({"acme/live": {"full_name": "acme/renamed"}, "acme/renamed": {}, "acme/old": {}})
        changes = dict(refresh.recheck(self.recs, fake, "2026-10-19"))
        self.assertIn("renamed to acme/renamed", changes["acme/live"])
        self.assertIn("acme/renamed", self.recs)
        self.assertNotIn("acme/live", self.recs)
        again = dict(refresh.recheck(self.recs, fake, "2026-10-26"))
        self.assertNotIn("acme/renamed", again)

    def test_lists_projects_we_have_not_read(self):
        queue, _ = harvest.merge({"content-moderation": CATEGORY})
        new = refresh.waiting({"acme/spoiler-guard": {}}, queue)
        self.assertEqual([q["repo"] for q in new], ["acme/twice"])
        renamed = FakeGitHub({"acme/twice": {"full_name": "acme/spoiler-guard"}})
        self.assertEqual(refresh.waiting({"acme/spoiler-guard": {}}, queue, renamed), [])
        self.assertEqual(refresh.waiting({}, queue, FakeGitHub({"acme/spoiler-guard": {}})), [queue[0]])
        self.assertIn("1 listed projects not read yet", refresh.summary([], new, "2026-10-19"))


class HealthAndCompareTests(unittest.TestCase):
    def test_health_check(self):
        fake = FakeGitHub({"acme/a": {"sha": "b" * 40}})
        self.assertEqual(health.check("acme/missing", fake), {"repo": "acme/missing", "exists": False})
        info = health.check("acme/a", fake)
        self.assertTrue(info["exists"])
        self.assertEqual(info["sha"], "b" * 40)

    def test_compare_counts_agreement(self):
        a = {"acme/spoiler-guard": good_read()}
        b = {"acme/spoiler-guard": dict(good_read(), calls=[dict(good_read()["calls"][0], pattern="fuzzy-check")])}
        keys, both, rows, diffs = compare.compare(a, b)
        self.assertEqual((rows["status"], rows["shapes"], rows["pattern"], rows["call site"]), (1, 1, 0, 1))
        self.assertEqual(diffs[0][1], "pattern")

    def test_pattern_tags_match_the_skill(self):
        import re
        text = (TOOLS.parent.parent / "skills" / "jev-where" / "references" / "patterns.md").read_text()
        self.assertEqual(re.findall(r"Sightings tag:\*\* `([a-z-]+)`", text), common.PATTERNS)

    def test_signals_name_their_sources(self):
        data = json.loads((TOOLS / "signals.json").read_text())
        for s in data["signals"]:
            if s["source"]:
                self.assertIn(s["source"], data["sources"])
        self.assertEqual(common.line_signals("    response = client.system_one(")[0]["id"], "call")
        self.assertEqual(common.line_signals("talks about jev")[0]["level"], "weak")
        self.assertEqual(common.line_signals('  "type": "noul",')[0]["id"], "wire-type")
        self.assertEqual(common.line_signals('model: "typesafe-ai/jev",')[0]["id"], "gateway-model")


if __name__ == "__main__":
    unittest.main()
