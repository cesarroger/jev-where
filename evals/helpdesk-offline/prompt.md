---
description: Same audit with no network tools granted. Run WITHOUT --allow-tools. The live lookups fail, so precedents come only from the bundled Jev Sightings, labelled "not rechecked today", and nothing else is linked.
tags: [report, offline]
max_turns: 60
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Agent]
expected_outcome: One plain sentence saying the live lookup failed, sightings from the bundled copy labelled "not rechecked today" (or "no precedent lookup available" if none fit), no invented links.
---
Where could I use Jev in our helpdesk app? Its code is in the read-only directory named `app` that was added to this session. Give me the ranked list.
