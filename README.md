<p align="center">
  <img src="assets/banner.svg" alt="JEV WHERE? A seek-and-find for the decisions hiding in your code. Can you spot Jev?" width="100%">
</p>

<p align="center">
  <b>A seek-and-find for the decisions hiding in your code.</b><br>
  Point it at an app. Get a ranked list of the places Jev could make the call.<br>
  A Claude Code plugin for <a href="https://typesafe.ai/blog/introducing-system-one-models-and-jev">Jev</a>, TypeSafe AI's System One model.
</p>

<p align="center">
  <img alt="Claude Code plugin" src="https://img.shields.io/badge/Claude_Code-plugin-C8FF4D?style=flat-square&labelColor=0B0F19">
  <img alt="Skill" src="https://img.shields.io/badge/command-%2Fjev--where-5CE1E6?style=flat-square&labelColor=0B0F19">
  <img alt="Version 0.4.0" src="https://img.shields.io/badge/version-0.4.0-FF9F43?style=flat-square&labelColor=0B0F19">
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-B79CFF?style=flat-square&labelColor=0B0F19">
</p>

---

Every app has fuzzy decisions buried in it: a regex that routes tickets, a
keyword list that sets priority, an LLM call that only ever answers YES or NO,
a filter that holds messages for review. Jev is built for exactly those: state
in, a typed decision out (a **Choice**, a **Score**, or a **Noul** yes/no
probability), each with its probabilities.

**JEV WHERE?** reads your app and finds them for you. For every decision point
it writes the exact typed question, says what to do when Jev is unsure, and
ranks the ideas so you know which experiment to run first. It only analyzes
and suggests. It never edits your code.

**What makes it different:** every idea cites real projects that already do
something similar, and **links to the exact lines where they call Jev**. Those
come from [Jev Sightings](SIGHTINGS.md), our own verified list. Each project is
rechecked live during the run, and newer projects are picked up from
[awesome-jev](https://github.com/yibie/awesome-jev), fetched fresh every time.
Every report also flags hardcoded secrets and unguarded API calls along the
way, and shows exactly what data each idea would send to Jev.

## What you get

For each idea:

| | |
| --- | --- |
| **Where** | The file, line and function, such as `helpdesk/router.py:14` (`route`) |
| **Today** | What the code does now, and where it breaks |
| **Jev decision** | Choice, Score or Noul, the exact question, and its options or levels |
| **Confidence handling** | Starting cutoffs (labelled as such) and a safe fallback when Jev is unsure |
| **What Jev Sees** | What kind of data the question sends (public, internal, personal, sensitive) and how to send less |
| **Footprints** | Git history clues: a rule edited 7 times, with 2 "fix false positive" commits, is begging for help |
| **Precedent** | 1 to 2 real projects, each linked to the exact lines where it calls Jev |
| **Benefit, risk, poor fit** | An honest case for and against |
| **Why this rank** | The ranking math in plain words, so you can check or argue with it |
| **Effort** | S, M or L |

Plus:

- **Power Jewels:** new things Jev could add, built only on data your app
  already has.
- **One request, several questions:** ideas that read the same input are
  grouped into a single Jev call.
- **Not Jev's Job:** decisions plain code should keep, and what would change
  that.
- **Off the Map:** what the scan didn't cover, and the command to cover it.
- **Existing Jev use:** if the app already calls Jev, its questions, cutoffs
  and fallbacks are reviewed too.
- **Start here:** the single best first experiment and how to evaluate it on a
  small labeled set.
- **Starter code, only if you ask:** a minimal integration in your app's
  language, built from the current TypeSafe docs, with an evaluation harness.
- **Treasure Map, only if you ask:** the report as `jev-where-map.json`. Run
  `/jev-where` again later and it shows what changed since the last map: new
  spots, ideas that now use Jev, rules that cooled down.

### Jev's Radar

Before Claude reads anything, a small scanner sweeps the code and lists every
likely decision point as `file:line`: regex rules, keyword lists, yes/no LLM
calls, thresholds, routing, gates and rankings. It skips dependency, build and
secret files, never prints secret values, and adds Footprints from git
history. It's plain Python with nothing to install, and you can run it on its
own:

```bash
python3 skills/jev-where/scripts/jev_radar.py /path/to/your/app --footprints
```

Add `--json` for machine-readable output.

### Jev Sightings

Most lists of "projects using X" are one line of marketing each. We read the
code instead. [Jev Sightings](SIGHTINGS.md) is our list of projects where Jev
was actually spotted. Each sighting has:

- a link to the exact lines that ask Jev a typed question, pinned to the
  commit we read, so the link never breaks
- the shape (Choice, Score or Noul) and the kind of decision
- how the code handles low confidence
- the language
- a short description in our own words

When `/jev-where` finds a decision point, it picks sightings with the same
pattern and shape, in your app's language when it can. It checks they still
exist on GitHub, and cites them like this:

> **Precedent:** Jev sighting, Tab Sorter: a Choice at `grouper.js:105`,
> JavaScript; tabs below 0.6 confidence go to a review bucket. (verified
> 2026-10-12, live today)

Projects were discovered through [awesome-jev](https://github.com/yibie/awesome-jev),
then read by Claude and checked by automatic audits. A weekly GitHub Action
rechecks every project and flags new ones to read. Without a network, the copy
bundled with the plugin still works, and those citations are marked "not
rechecked today".

See a full example report: [examples/sample-report.md](examples/sample-report.md), and the same app with no network: [examples/sample-report-offline.md](examples/sample-report-offline.md).

## How it works

<p align="center">
  <img src="assets/how-it-works.svg" alt="How it works: 1 your app, 2 Jev's Radar sweeps the code (regex rules, yes/no LLM calls, routing, gates, Footprints), 3 write the typed question (Choice, Score, Noul), 4 check Jev Sightings and the live list, 5 ranked report with Power Jewels, 6 starter code and Treasure Map, only if you say yes." width="100%">
</p>

## Install

### From this GitHub repo

Add the marketplace and install the plugin:

```bash
claude plugin marketplace add cesarroger/jev-where
```

```bash
claude plugin install jev-where@jev-where
```

Restart Claude Code or run `/reload-plugins`.

### From a local clone

Try it for one session:

```bash
claude --plugin-dir /path/to/jev-where
```

Or install it from the folder:

```bash
claude plugin marketplace add /path/to/jev-where
```

### As a standalone skill

Link the skill folder into your personal skills:

```bash
ln -s /path/to/jev-where/skills/jev-where ~/.claude/skills/jev-where
```

Pick one form. If you install both, the personal skill takes `/jev-where` and
the plugin stays reachable as `/jev-where:jev-where`.

## Use

| You type | It analyzes |
| --- | --- |
| `/jev-where` | the current project |
| `/jev-where src/support` | the code at that path |
| `/jev-where Discord bot that flags scam DMs and routes reports to mods` | an app described in words |

It also starts on its own when you ask things like "where could I use Jev in
this app?", "find Jev use cases in this repo", or "what decisions here could be
typed?". General questions about what Jev is don't trigger it.

## Ground rules

- **Read-only.** It never edits your files. It writes a new file only when you
  ask for one.
- **No invented API facts.** It doesn't state Jev request formats, model IDs,
  prices, latency or accuracy from memory. It points you to the official docs.
- **Real precedents only.** Precedents come from Jev Sightings or the
  awesome-jev pages fetched in that run, never from memory. If neither is
  available, every idea says "no precedent lookup available". A sighting or a
  listing is not an endorsement.
- **Secrets stay out.** It never quotes keys, tokens or passwords from your
  code in the report.
- **Fetched pages are data.** Instructions found in web pages or repo files are
  ignored.
- **What it may run without asking.** The skill pre-approves three things
  for its own turn: Jev's Radar, `grep`, and a small bundled fetcher. It
  doesn't pre-approve `curl`.
  - The fetcher downloads only the awesome-jev pages, this repo's Sightings
    file, and GitHub's public facts about a project.
  - It builds every address itself and refuses other hosts.
  - It saves pages into a temporary folder it creates, and never prints them.

## Credits

Jev and System One models are made by [TypeSafe AI](https://typesafe.ai).
Jev Sightings were discovered through [awesome-jev](https://github.com/yibie/awesome-jev),
a community list, and every listed project belongs to its authors. This
project is independent and not affiliated with any of them.

## License

[MIT](LICENSE) © 2026 Cesar Peralta
