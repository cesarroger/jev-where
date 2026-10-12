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
│   └── references/
│       ├── patterns.md              decision point → Choice / Score / Noul, cutoffs, data levels
│       ├── starter-integration.md   used only when the user asks for starter code
│       └── treasure-map.md          the jev-where-map.json format, used only when asked
├── tests/                           unit tests for Jev's Radar
├── evals/                           `claude plugin eval` suite with a fake helpdesk app
├── examples/                        full runs on the fake helpdesk app, with and without network
└── assets/
    ├── banner.svg                   the seek-and-find banner
    ├── how-it-works.svg             the hand-drawn diagram, fonts embedded
    ├── social-preview.png           1280×640 card for GitHub's social preview (public repos only)
    └── src/                         sources for the artwork (see below)
```

## Tests

### Jev's Radar

Quick unit tests, no Claude session needed:

```bash
python3 -m unittest discover -s tests
```

### The skill

The `evals/` folder holds a suite for Claude Code's built-in
[`claude plugin eval`](https://code.claude.com/docs/en/plugin-evals) runner
(Claude Code 2.1.269 or later, signed in). It checks that the skill triggers on
the right requests and not on near-misses, asks for a description in an empty
project, runs Jev's Radar, produces a grounded report with the v0.3 sections,
labels missing precedents when offline, never leaks the fake app's secrets, and
never edits files.

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
2. Run the radar tests and `claude plugin validate --strict .`.
3. Run a fresh `/jev-where` on `evals/helpdesk-report/app` and refresh
   `examples/` if the report format changed.
