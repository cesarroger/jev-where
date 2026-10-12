---
type: llm
---
PASS if all of these hold:
- the reply lists at least 5 ranked ideas, each tied to a file in the helpdesk app
- each idea gives a Choice, Score, or Noul question with its options, levels, or what counts as yes
- confidence cutoffs are labelled as starting points to tune on labeled data
- each idea has a poor-fit note
- the reply ends by offering to draft a starter integration, without drafting it
FAIL if the reply states Jev prices, latency, or accuracy as facts, includes integration code, or misses any PASS condition.
