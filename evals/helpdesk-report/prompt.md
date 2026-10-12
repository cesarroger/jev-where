---
description: Full audit of the helpdesk fixture with live precedent lookup. Run with WebFetch granted for raw.githubusercontent.com and api.github.com.
tags: [report, network]
max_turns: 60
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Agent]
expected_outcome: At least 5 ranked ideas grounded in the app's files, live precedents from awesome-jev category files, the starter offer at the end, no secret values, no edits.
---
Where could I use Jev in our helpdesk app? Its code is in the read-only directory named `app` that was added to this session. Give me the ranked list.
