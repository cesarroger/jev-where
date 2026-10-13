# Treasure Map (`jev-where-map.json`)

The Treasure Map is the JEV WHERE? report as a JSON file, so it can be
tracked over time, compared between runs, and read by the starter-integration
step. Write it only when the user asks. It is a new file in the project root
(or a path the user names); never overwrite one without asking.

## Rules

- Same content as the Markdown report, no extra claims. Never include secret
  values; locations only.
- Precedents keep their exact names and URLs from Jev Sightings or this run's
  awesome-jev fetch. A sighting also keeps its permalink and verified date
  (`"sighting": true`); a live-list entry has `"sighting": false`. If neither
  source was available, set `precedent_lookup.status` to `"failed"` and leave
  every `precedents` list empty.
- Cutoffs are starting points; keep the `"starting_point": true` flag.
- Use `null` for anything not visible, never a guess.

## Shape

An illustration only, for a made-up expense-report app. The values are not
from any real run, and precedents must come from the run's own fetch.

```json
{
  "schema": "jev-where/treasure-map@2",
  "generated": "2026-10-12",
  "project": "relative or absolute path that was scanned",
  "uses_jev_today": false,
  "precedent_lookup": {
    "status": "ok",
    "date": "2026-10-12",
    "sightings": {"copy": "live", "generated": "2026-10-12", "verified": 74},
    "categories": ["Verification & Guardrails"],
    "note": null
  },
  "ideas": [
    {
      "id": "receipt-matches-category",
      "rank": 1,
      "title": "Check that the receipt matches the expense category",
      "where": [{"path": "expenses/review.py", "line": 42, "function": "check_receipt"}],
      "today": "keyword list decides whether the receipt text fits the chosen category",
      "questions": [
        {
          "type": "noul",
          "text": "The receipt text describes a purchase that fits the expense category the employee chose.",
          "yes_means": "the items or merchant clearly belong to that category",
          "state": ["receipt.text", "expense.category"]
        }
      ],
      "confidence": {
        "starting_point": true,
        "bands": ["p >= 0.8: approve check", "p <= 0.2: send to finance", "between: current keyword rule"],
        "fallback": "current keyword rule",
        "combine": null
      },
      "jev_sees": {"level": "personal", "send_less": "send line items and merchant only; strip card numbers and names"},
      "footprints": {"edits": 6, "recent_90d": 2, "fixes": 3, "complaints": 1},
      "precedents": [
        {"name": "<name from the Sightings line>", "url": "<exact repo URL>", "sighting": true,
         "permalink": "<exact permalink from the Sightings line>", "verified": "<date from the line>"},
        {"name": "<entry name from this run's fetch>", "url": "<exact URL from the entry>", "sighting": false,
         "category": "<category file>"}
      ],
      "benefit": "...",
      "main_risk": "...",
      "poor_fit_if": "...",
      "why_this_rank": "every expense report x brittle keyword list x finance rework on mistakes",
      "effort": "S",
      "value": "high",
      "risk": "low"
    }
  ],
  "groups": [{"input": "each submitted expense", "ideas": ["receipt-matches-category"]}],
  "power_jewels": [
    {"id": "duplicate-receipt", "title": "...", "where": [], "questions": [], "jev_sees": {}, "precedents": []}
  ],
  "not_jevs_job": [{"path": "expenses/limits.py", "line": 9, "function": "over_limit", "reason": "exact amount comparison", "change_my_mind": "limits that depend on free-text justification"}],
  "off_the_map": [{"area": "vendor/", "why": "dependencies", "next": "/jev-where <path>"}],
  "existing_jev_use": [],
  "also_noticed": [{"path": "config/payments.py", "line": 7, "risk": "hardcoded API key (value not shown)"}],
  "start_here": "receipt-matches-category"
}
```

`id` values are short, stable slugs built from what the idea does, so the next
run can match ideas even if their rank or wording changes.

## Since the last map

If a `jev-where-map.json` from an earlier run exists, read it before writing
the report and add this section before "Start here". Maps with schema `@1`
are fine too; their precedents just lack the sighting fields. Match ideas by `id`,
falling back to the same `where` location.

```markdown
## Since the last map (<old date> → <today>)
- **New spots:** ideas found now that weren't on the old map
- **Gone from the code:** old ideas whose code no longer matches; often shipped
  with Jev or removed. Say which, if the code shows it
- **Now using Jev:** old ideas where the code now calls Jev
- **Footprints:** ideas whose rule got hotter or cooled down since then
- **Unchanged:** a count only
```

If the user then asks for a new map, write it as a new file or replace the old
one only after they confirm.
