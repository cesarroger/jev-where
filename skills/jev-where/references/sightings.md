# Jev Sightings

Jev Sightings is this plugin's own list of projects where Jev was actually
spotted in the code. Each verified entry links to the exact lines that ask
Jev a typed question, pinned to the commit that was read, and records:
- the shape and the kind of decision
- how the code handles confidence
- the language

The projects were discovered through awesome-jev, then read and audited. The
descriptions are our own words. Use Sightings first when looking for
precedents, then the live awesome-jev list for projects not read yet.

## Contents

- Loading the file
- Format
- Searching
- Live recheck
- Choosing and citing
- Treasure Map fields

## Loading the file

1. Run the fetcher's `sightings` target (see SKILL.md step 4). It saves
   `sightings.jsonl` into its folder: the newest copy from GitHub when it can
   get one in the expected format, or else the copy bundled with the skill.
   Its status line says which copy it used, the generated date, and the
   verified count.
2. If it says `sightings: none`, skip Sightings for this run and say so in one
   line.
3. Use the status line for the scope lines, with the reason when it fell
   back, for example "Jev Sightings: 75 verified (bundled copy, 2026-10-12;
   live copy unavailable: HTTP 404)". The copy you used doesn't change the
   labels: a bundled sighting that passes today's recheck is "live today".

Never read the whole file; it can be several hundred KB. Search it.

## Format

One JSON object per line, written compactly, with keys always in this order,
so a single regex can match across fields:

```text
{"meta":{"schema":"jev-where/sightings@1","generated":"…","verified":N,…}}
{"repo":"owner/name","name":"…","status":"verified","verified":"YYYY-MM-DD","sha":"…","kind":"app","lang":["TypeScript"],"stack":[…],"calls":[{"permalink":"https://github.com/owner/name/blob/<sha>/path#L40-L52","via":"sdk","shapes":["noul"],"pattern":"moderation","decides":"…","confidence":"…","batched":true,"in":"app"}],"about":"…","evidence":[…],"health":{"archived":false,"quiet":false},"listed_in":["content-moderation"]}
{"repo":"owner/other","name":"…","status":"no-jev-found","sha":"…","listed_in":[…]}
```

| Field | Meaning |
| --- | --- |
| `status` | `verified` (Jev call found), `no-jev-found` (read; it doesn't call Jev), `gone` (deleted from GitHub), `private` |
| `verified` | When the call was confirmed |
| `kind` | `app`, `library`, `integration`, `demo` or `benchmark` |
| `calls[].pattern` | The pattern's Sightings tag in `patterns.md`, such as `approval-gate` |
| `calls[].via` | `sdk` or `http` call Jev directly; `integration` goes through a platform node or plugin; `adapter` is TypeSafe's drop-in that answers the same questions with other LLMs, not Jev |
| `calls[].in` | `app` code, an `example`, an `eval` (benchmark or evaluation code), or a `test` |
| `decides`, `confidence`, `about` | Our own words; quote them only as short paraphrases |
| `health` | `archived` on GitHub; `quiet` means no push in 180 days; `missing` is the date GitHub first stopped finding it |

## Searching

Use the Grep tool, or one plain `grep -n -i -E '<pattern>' <file>` per
search, never piped. Because the key order is fixed, these regexes work:

| To find | Regex |
| --- | --- |
| Verified projects for a pattern | `"status":"verified".*"pattern":"approval-gate"` |
| …asking a given shape in that same call | `"shapes":\[[^]]*"noul"[^]]*\],"pattern":"approval-gate"` |
| …in the app's language | `"status":"verified".*"lang":\[[^]]*"Python".*"pattern":"approval-gate"` |
| A project seen on awesome-jev | `"repo":"owner/name"` (case-insensitive) |
| The meta line | `^\{"meta"` |

Search each decision point's pattern tag first. If that finds nothing, try
neighbouring tags, for example `fuzzy-check` for a keyword gate, or
`severity` for a priority score. Then fall back to the live list.

## Live recheck

Before citing sightings, check that the projects still exist, with one
fetcher call listing them all, for example
`... jev_fetch.py --dir <folder> repo:owner/one repo:owner/two`. It rechecks at
most 10 projects per call. That caps the rechecks, not the citations: label
any further sightings "not rechecked today". Skip the recheck entirely when
there is no network.

Each project gets one status line:
- **`live`:** cite it.
- **`live, archived`:** cite it, labelled archived.
- **`live, renamed to …`:** cite it under the new name. The permalink still
  works.
- **`gone (HTTP 404)`:** don't cite it. Note once: "N sightings dropped: gone
  from GitHub".
- **`not rechecked (…)`**, for example a rate limit: cite it anyway, labelled
  "not rechecked today".

## Choosing and citing

For each idea, pick 1 or 2 verified sightings, preferring in this order:
1. the same pattern tag and shape
2. the same language as the app
3. `in: app` and `kind: app` over examples, evals, demos, and benchmarks
4. visible evidence (`tests`, `production`)
5. not archived and not quiet

Use a `via: adapter` sighting only when nothing else fits, and say that it
uses the adapter rather than Jev.

Cite it like this, copying the repo, name and permalink exactly from the line:

```markdown
- **Precedent:** Jev sighting, [Name](https://github.com/owner/name): a Noul
  check at [path/file.ts:40](<permalink>), TypeScript; <what it decides and how
  it handles low confidence, in a few words>. Why it's similar: <one line>.
  (verified 2026-10-14, live today)
```

The label at the end is one of:
- `(verified <date>, live today)`
- `(verified <date>, not rechecked today)`
- `(verified <date>, archived)`

Write the shown path and line as the file name plus the first line of the
permalink's range.

When awesome-jev lists a project that Sightings marks `no-jev-found` or
`gone`, don't cite it. Count only the ones that matched your searches, the
ones you would otherwise have cited, and note them once: "Skipped N listed
projects that Jev Sightings found don't call Jev or are gone." Cite a live-list entry that Sightings hasn't read as
"listed on awesome-jev, not yet verified".

## Treasure Map fields

In `jev-where-map.json` (schema `@2`), a precedent from Sightings adds:
`"sighting": true`, `"permalink"`, and `"verified"` (the date). A live-list
precedent has `"sighting": false` and no permalink.
