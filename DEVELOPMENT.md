# Developing JEV WHERE?

Notes for working on the plugin itself. Using it doesn't need any of this; see
the [README](README.md).

## Project layout

```text
jev-where/
├── .claude-plugin/
│   ├── plugin.json                  plugin manifest (bump "version" on release)
│   └── marketplace.json             lets `claude plugin install` find it
├── skills/jev-where/
│   ├── SKILL.md                     the workflow
│   ├── scripts/jev_radar.py         Jev's Radar: the read-only scanner, with Footprints
│   ├── scripts/jev_fetch.py         the allowlisted fetcher the skill uses instead of curl
│   ├── sightings/sightings.jsonl    Jev Sightings, bundled (generated; don't edit by hand)
│   └── references/
│       ├── patterns.md              decision point → Choice / Score / Noul, cutoffs, data levels
│       ├── sightings.md             how the skill loads, searches, rechecks and cites Sightings
│       ├── starter-integration.md   used only when the user asks for starter code
│       └── treasure-map.md          the jev-where-map.json format, used only when asked
├── tools/sightings/                 maintainer tools that build Jev Sightings (never loaded by the skill)
├── SIGHTINGS.md                     the public index of Sightings (generated)
├── .github/workflows/               the weekly Sightings refresh
├── tests/                           unit tests for Jev's Radar, the fetcher and the Sightings tools
├── evals/                           `claude plugin eval` suite with a fake helpdesk app
├── examples/                        full runs on the fake helpdesk app, with and without network
└── assets/
    ├── banner.svg                   the seek-and-find banner
    ├── how-it-works.svg             the hand-drawn diagram, fonts embedded
    ├── social-preview.png           1280×640 card for GitHub's social preview (public repos only)
    └── src/                         sources for the artwork (see below)
```

## Tests

### Jev's Radar, the fetcher and the Sightings tools

Quick unit tests, offline, no Claude session needed:

```bash
python3 -m unittest discover -s tests
```

### The skill

The `evals/` folder holds a suite for Claude Code's built-in
[`claude plugin eval`](https://code.claude.com/docs/en/plugin-evals) runner
(Claude Code 2.1.269 or later, signed in). It checks that the skill triggers on
the right requests and not on near-misses, asks for a description in an empty
project, runs Jev's Radar, produces a grounded report with every required section,
cites pinned Jev Sightings (falling back to the bundled copy offline), never
leaks the fake app's secrets, and never edits files.

Each run is a real Claude session and counts against your plan's usage. From
the repo root:

```bash
claude plugin eval . --tag trigger
```

```bash
claude plugin eval . --tag network --allow-tools "Bash(python3 *)" "WebFetch(domain:raw.githubusercontent.com)" "WebFetch(domain:api.github.com)"
```

```bash
claude plugin eval . --tag offline --allow-tools "Bash(python3 *)"
```

Add `--runs 1 --ablation none` while iterating to cut the cost.

To check the manifests:

```bash
claude plugin validate --strict .
```

## Jev Sightings

Jev Sightings is built by the tools in `tools/sightings/`. They use the
standard library only and keep their working files in `tools/sightings/work/`
(gitignored). They store no awesome-jev text and no project code in the repo,
only names, links, pinned permalinks and our own words, and they never run
code from the projects they read.

### Weekly refresh

`.github/workflows/sightings-refresh.yml` runs every Monday and on demand.
- **Projects:** it rechecks every project. One that stops being found gets a
  week's grace before it's marked gone, and keeps its facts in case it comes
  back. Archived, quiet and renamed projects are updated.
- **Unread list:** it lists the Sightings categories' projects we haven't read
  in `tools/sightings/waiting.json`.
- **Pull request:** it keeps one pull request, `sightings/refresh`, up to date
  when anything changed.

It needs no API keys. Turn on Settings → Actions → General → "Allow GitHub
Actions to create and approve pull requests".

### Reading new projects

When the refresh PR lists projects waiting to be read:

1. Queue them and check their health:

   ```bash
   python3 -I tools/sightings/harvest.py --categories all
   ```

   ```bash
   python3 -I tools/sightings/health.py
   ```

2. Clone, scan and cut snippets. Clones go to a fresh temp folder and are
   deleted afterwards. Use `--only owner/name,...` for just the waiting ones:

   ```bash
   python3 -I tools/sightings/locate.py
   ```

3. Ask Claude to read the new candidates by following
   `tools/sightings/READER.md`, writing one JSON line per project to
   `tools/sightings/work/reads/<batch>.jsonl`.
4. Audit the answers. Anything flagged gets a second read by a stronger
   model, written to a reads file that sorts later. When several files answer
   the same project, the last one in name order wins, so name first reads
   `a-…`, second reads `b-…` and reviewer fixes `c-…`. Add `--final` to see
   what the build will trim:

   ```bash
   python3 -I tools/sightings/audit.py tools/sightings/work/reads/*.jsonl
   ```

5. Build the file and the index. The build audits each answer again exactly
   as it will publish it: fixable problems such as a copied phrase or one bad
   call are trimmed, and anything else is left out. Then it validates the
   result:

   ```bash
   python3 -I tools/sightings/build.py tools/sightings/work/reads/*.jsonl
   ```

Add `--check --links` to `build.py` to also open every permalink on GitHub.
`tools/sightings/coverage.py` shows how many verified sightings each pattern
has in Python and JS/TS, and `--select N` picks the next unread projects that
fill the gaps.

To compare two readers on the same projects (for example a cheaper model
against a stronger one), use `tools/sightings/compare.py`. The detection
signals live in `tools/sightings/signals.json`, each pinned to the official
TypeSafe file it came from; update them when the SDKs change.

## Artwork

- **Banner:** `assets/src/make_banner.py` writes `assets/banner.svg`. Change
  `SEED` to reshuffle the crowd, or `JEV_AT` to move Jev.
- **Diagram:** `assets/src/make_diagram.py` writes
  `assets/src/how-it-works.excalidraw`, which also opens at excalidraw.com
  for hand edits. `assets/src/render_diagram.html` turns it into
  `assets/how-it-works.svg` with Excalidraw's own exporter, loaded from a CDN,
  so nothing needs installing: paste the scene JSON into the page, open it in
  a browser, and copy the SVG. If you edit the `.excalidraw` file by hand,
  stop regenerating it from the script, or your edits get overwritten.
- **Social preview:** `assets/social-preview.png`. GitHub only accepts it on a
  public repo, under Settings → General → Social preview.

## Releasing

1. Bump `version` in `.claude-plugin/plugin.json` and the version badge in
   `README.md`.
2. Run the unit tests, `python3 -I tools/sightings/build.py --check`, and
   `claude plugin validate --strict .`.
3. Run a fresh `/jev-where` on `evals/helpdesk-report/app` and refresh
   `examples/` if the report format changed.
