# Treasure Map (`jev-where-map.json`)

The Treasure Map is the JEV WHERE? report as a JSON file, so it can be
tracked over time, compared between runs, and read by the starter-integration
step. Write it only when the user asks. It is a new file in the project root
(or a path the user names); never overwrite one without asking.

## Rules

- Same content as the Markdown report, no extra claims. Never include secret
  values; locations only.
- Precedents keep their exact names and URLs from this run's fetch, plus the
  fetch date. If the lookup failed, set `precedent_lookup.status` to `"failed"`
  and leave every `precedents` list empty.
- Cutoffs are starting points; keep the `"starting_point": true` flag.
- Use `null` for anything not visible, never a guess.

## Shape

```json
{
  "schema": "jev-where/treasure-map@1",
  "generated": "2026-10-12",
  "project": "relative or absolute path that was scanned",
  "uses_jev_today": false,
  "precedent_lookup": {
    "status": "ok",
    "date": "2026-10-12",
    "categories": ["Classification & Routing"],
    "note": null
  },
  "ideas": [
    {
      "id": "route-tickets",
      "rank": 1,
      "title": "Route tickets to the right team",
      "where": [{"path": "helpdesk/router.py", "line": 14, "function": "route"}],
      "today": "first-match regex picks a team",
      "questions": [
        {
          "type": "choice",
          "text": "Which team should handle the request in this ticket?",
          "options": {"billing": "charges, invoices, refunds", "general": "none of these"},
          "state": ["ticket.subject", "ticket.body"]
        }
      ],
      "confidence": {
        "starting_point": true,
        "bands": ["confidence >= 0.8: route", "0.5-0.8: route and flag", "< 0.5: current regex"],
        "fallback": "current route() regex",
        "combine": null
      },
      "jev_sees": {"level": "personal", "send_less": "send subject and body only; strip signatures and email addresses"},
      "footprints": {"edits": 7, "recent_90d": 3, "fixes": 2, "complaints": 1},
      "precedents": [{"name": "jev-cookbook", "url": "https://github.com/nexibeo/jev-cookbook", "category": "Classification & Routing"}],
      "benefit": "...",
      "main_risk": "...",
      "poor_fit_if": "...",
      "why_this_rank": "every ticket x first-match regex x cheap misroutes",
      "effort": "S",
      "value": "high",
      "risk": "low"
    }
  ],
  "groups": [{"input": "each new ticket", "ideas": ["route-tickets"]}],
  "power_jewels": [
    {"id": "churn-risk", "title": "...", "where": [], "questions": [], "jev_sees": {}, "precedents": []}
  ],
  "not_jevs_job": [{"path": "...", "line": 0, "function": "...", "reason": "...", "change_my_mind": "..."}],
  "off_the_map": [{"area": "node_modules", "why": "dependencies", "next": "/jev-where <path>"}],
  "existing_jev_use": [],
  "also_noticed": [{"path": "helpdesk/settings.py", "line": 3, "risk": "hardcoded secret (value not shown)"}],
  "start_here": "route-tickets"
}
```

`id` values are short, stable slugs built from what the idea does, so the next
run can match ideas even if their rank or wording changes.

## Since the last map

If a `jev-where-map.json` from an earlier run exists, read it before writing
the report and add this section before "Start here". Match ideas by `id`,
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
