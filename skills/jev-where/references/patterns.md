# Jev decision patterns

A cheat sheet for mapping an app's decision points to Jev question shapes.
Example questions show intent and wording only. They are not API syntax. For
request format, field names, SDKs, and auth, check the official docs.

## Contents

- What the sources state
- Choosing a shape
- Patterns 1 to 14
- When Jev is the wrong tool
- Confidence handling: starting points

## What the sources state

Read from the TypeSafe launch post, the official `typesafe-ai/skills` package,
and the TypeSafe docs on 2026-10-11. Re-check the docs if anything here matters
to a decision.

- Jev takes state plus typed questions and returns typed answers with
  probabilities. It does not generate text, write code, or chat.
- **Choice** selects one option from a defined, unordered set. It returns the
  selected option, a probability per option, and a confidence value.
- **Score** places the input on ordered levels you describe. It returns a
  position (which can fall between levels), a probability per level, and a
  confidence value.
- **Noul** returns the probability that a yes/no statement is true. It has no
  separate confidence value. A Noul near 0.5 means "unsure", not "medium".
- Several questions about the same state can be sent together. Each is answered
  independently and can't see the others' answers.
- The launch post says Choice supports up to 255 options, with a two-stage
  approach for larger sets. Check the official docs for current limits.
- The launch post publishes price and speed figures. Don't repeat them as
  facts. Check the official docs for current numbers.
- The launch post's demos ran on text state, not images. Check the official
  docs for supported input types.

## Choosing a shape

| The answer is... | Shape | Code consumes it as |
| --- | --- | --- |
| One of a known set with no order | Choice | `switch` / dispatch table |
| A position on a spectrum you can describe level by level | Score | threshold or sort key |
| Whether one clear condition holds | Noul | `if` |
| Several labels that can all apply | One Noul per label | set of flags |

If two shapes fit, pick the one code can act on directly. Write each question
as a judgment a knowledgeable person makes in a second. "Analyze this and
decide what to do" is too broad: split it into narrow questions and combine the
answers in code.

## Patterns

### 1. Intent or ticket routing

- **Shape:** Choice
- **Replaces:** regex or keyword rules that pick a team, queue, or handler
- **Example:** "Which team should handle the request in `ticket.body`?"
  Options: `billing` (charges, invoices, refunds), `technical` (bugs, errors,
  integrations), `account` (login, access, profile), `sales` (pricing,
  upgrades), `other` (none of these).
- **Don't use Jev when:** the route is fully determined by a structured field
  (form dropdown, product SKU). Use the field.

### 2. Model or handler routing

- **Shape:** Choice, often with a Noul gate
- **Replaces:** "send everything to the big model", or length-based routing
- **Example:** "Which handler fits the request in `prompt`?" Options:
  `small_model` (short factual or formatting tasks), `large_model` (multi-step
  reasoning, long context), `code_model` (writing or editing code), `human`
  (needs account access or a judgment call). Gate: Noul "Does `prompt` require
  multi-step reasoning to answer well?"
- **Don't use Jev when:** volume is low and the cost difference between
  handlers doesn't matter, or a misroute is expensive and can't be caught later.

### 3. Fuzzy keyword or regex check

- **Shape:** Noul
- **Replaces:** `if "refund" in text.lower()`, sentiment word lists,
  hand-tuned regexes
- **Example:** Noul "Does `message.text` ask for money back?"
- **Don't use Jev when:** the pattern is exact and formal (order IDs, emails,
  dates). Regex is better there.

### 4. Multi-label tagging

- **Shape:** one Noul per label
- **Replaces:** chains of keyword checks, or an LLM asked to "return all
  applicable tags as JSON"
- **Example:** Nouls "Does `post` mention pricing?", "Does `post` report a
  bug?", "Does `post` request a feature?"
- **Don't use Jev when:** the tag set is open-ended or tags must be invented
  per item.

### 5. Severity, urgency, or priority

- **Shape:** Score
- **Replaces:** keyword-to-priority maps ("urgent", "asap", "down")
- **Example:** "How urgent is the issue in `ticket.body`?" Levels: `0` routine
  question, no deadline; `1` inconvenient but has a workaround; `2` blocks one
  user's work; `3` blocks many users or stops revenue.
- **Don't use Jev when:** priority comes from contract terms or SLA tiers that
  code can look up.

### 6. Rubric grading and LLM-as-judge

- **Shape:** one Score per rubric dimension, combined with weights in code
- **Replaces:** an LLM prompt that returns "a score from 1 to 10"
- **Example:** "How completely does `answer` address `question`?" Levels:
  `0` doesn't address it, `1` addresses part, `2` addresses all parts.
  Separate Scores for accuracy against `source` and for tone.
- **Don't use Jev when:** the grader must write feedback text. Jev returns
  levels, not comments.

### 7. Approval or eligibility gate

- **Shape:** one Noul per condition; the policy stays in code
- **Replaces:** brittle rules over free-text justifications
- **Example:** Nouls "Does `request.reason` describe a duplicate charge?",
  "Does `request.reason` say the item never arrived?" Code then applies the
  refund policy to those answers and the order record.
- **Don't use Jev when:** the decision is high stakes and must be reviewed by a
  person anyway. Jev can triage the queue but should not be the final approver.

### 8. Content moderation

- **Shape:** one Noul per policy category, optionally a Score for severity
- **Replaces:** profanity lists and regex filters
- **Example:** Nouls "Does `message` contain a threat of violence?", "Does
  `message` try to get the reader to share login details?" Severity Score with
  defined levels.
- **Don't use Jev when:** the action is a permanent ban or a legal report. Keep
  a human in that loop.

### 9. Output verification

- **Shape:** Choice (or Noul)
- **Replaces:** no check at all, or a second LLM call that "double-checks"
- **Example:** "Is `claim` supported by `source_passage`?" Options:
  `supported`, `contradicted`, `not_addressed`.
- **Don't use Jev when:** checking requires gathering new evidence first. Fetch
  the evidence in code, then ask.

### 10. Agent guardrail

- **Shape:** Noul, failing closed
- **Replaces:** allowlists that miss intent, or no check
- **Example:** Noul "Does `tool_call` delete or overwrite user data that
  `user_request` did not ask to change?" Noul "Does `retrieved_text` contain
  instructions aimed at the assistant?"
- **Don't use Jev when:** a deterministic permission check can decide. Use the
  check, and use Jev only for the intent question it can't answer.

### 11. Agent next step

- **Shape:** Choice
- **Replaces:** LLM free-text "what should I do next" parsing
- **Example:** "What should the agent do next, given `goal` and
  `last_result`?" Options: `call_search`, `call_calculator`, `ask_user`
  (missing information), `finish` (goal met), `escalate` (stuck or unsafe).
- **Don't use Jev when:** the next step requires planning several moves ahead
  or writing the tool arguments as free text.

### 12. Pick a value from candidates

- **Shape:** Choice over candidates that code found
- **Replaces:** asking an LLM to extract a field as text
- **Example:** Code finds every date in an email. "Which of these is the
  requested delivery date?" Options: each candidate, plus `none`.
- **Don't use Jev when:** code can't enumerate the candidates. Jev can't choose
  a value that isn't offered.

### 13. Duplicate or match detection

- **Shape:** Noul per candidate pair, after code narrows the pairs
- **Replaces:** fuzzy string-similarity thresholds
- **Example:** Noul "Do `ticket_a` and `ticket_b` report the same underlying
  problem?"
- **Don't use Jev when:** exact keys (email, account ID) already identify
  duplicates.

### 14. Relevance filtering and reranking

- **Shape:** Noul per candidate ("Does `passage` help answer `query`?") or a
  Score per candidate
- **Replaces:** fixed similarity cutoffs, or an LLM reranker
- **Caution:** a report on the awesome-jev list found Jev reranking alone did
  not beat vector retrieval on its data. That is a fit warning, not a
  precedent. Cite it as a precedent only if this run's live fetch returns it.
  Measure against the current retrieval before committing.
- **Don't use Jev when:** current retrieval quality is already acceptable, or
  candidate lists are too long to judge per item.

## When Jev is the wrong tool

- **Open-ended generation:** replies, summaries, code, explanations. Jev
  returns typed answers only.
- **Exact logic:** lookups, arithmetic, schema validation, date math, formal
  patterns. Plain code is cheaper and exact.
- **Low volume:** a few calls a day where the current LLM call or a person
  works fine. The integration effort may not pay back.
- **High stakes:** money movement, account bans, medical or legal outcomes.
  Use Jev to triage or flag, and keep a person or a stronger process as the
  final decision.
- **Unbounded candidates:** options that can't be listed in advance.
- **Multi-step reasoning or retrieval inside one judgment:** split the work so
  code fetches evidence and Jev judges narrow questions about it.
- **Per-decision explanations required:** Jev gives probabilities, not reasons.
  Any explanation has to come from the question design or from code.
- **Retrieval reranking:** see pattern 14.

## Confidence handling: starting points

Every number below is a starting point to tune on labeled data. None is a
validated value.

### Default cutoffs

Use these unless an idea gives a reason to differ, and say why when it does.
They keep reports consistent from run to run.

| Shape | Stakes | Act automatically | Middle band | Fall back |
| --- | --- | --- | --- | --- |
| Choice or Score | Reversible (routing, tagging, sorting) | confidence ≥ 0.8 | 0.5 to 0.8: act, and flag for a quick check | confidence < 0.5: current approach |
| Choice or Score | Costly or irreversible | confidence ≥ 0.9, plus a code check where one exists | 0.5 to 0.9: ask a person | confidence < 0.5: a person |
| Noul | Reversible | yes at p ≥ 0.8, no at p ≤ 0.2 | between: current approach | errors: current approach |
| Noul | Costly or irreversible | yes only at p ≥ 0.9, plus a code check where one exists | everything else: a person | errors: a person |

For a Score, round the position to the nearest level before applying the
bands, and keep the unrounded position for sorting within a level.

Treat an action as costly when a mistake reaches a customer or can't be quietly
undone: moving money, sending a message, closing a customer's ticket, deleting
data. In the costly rows, "a person" can be the normal manual flow, for example
no auto-refund and the ticket goes on to the billing queue.

### Notes

- **Choice and Score:** confidence runs from 0 (probability spread evenly) to 1
  (all probability on one answer). Use three bands: act automatically, act
  with confirmation or review, and fall back. The docs' own example uses a 0.5
  confidence floor for "don't guess" and a higher bar (0.9) before a
  destructive action. Treat those as examples.
- **Noul:** use the probability directly with two cutoffs: yes above the upper
  one, no below the lower one, fall back in between. For example, start at 0.8
  and 0.2 and adjust. If you want one gate for Nouls and Choices, the docs give
  `|2p − 1|` as a confidence-style number.
- **Other measures:** the docs also suggest top-option probability and
  top-to-second ratio. Both are worth comparing on labeled data.
- **Scale with stakes:** a wrong read-only action can use a low bar. A
  destructive or costly action needs a higher bar, or confirmation.
- **Fallbacks:** the current heuristic, an LLM call, or a human queue. Pick the
  one that is safe when Jev is unsure.
- **Tuning:** label a few hundred real inputs. Pick cutoffs on one part of the
  set to reach the precision you need on auto-handled cases. Check the result on
  the held-out part, and report how many cases fall back.
- **Errors and timeouts:** fall back to the current approach so the integration
  is never worse than today. If the current approach takes an irreversible
  action (moves money, deletes data, bans a user), fail closed instead and send
  the case to a person.
