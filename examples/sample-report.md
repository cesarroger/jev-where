# Example: `/jev-where` on the helpdesk fixture

A real run of JEV WHERE? v0.3 on [`evals/helpdesk-report/app`](../evals/helpdesk-report/app), a fake
support-ticket service built to test the plugin, with live precedent lookup on 2026-10-12. Every
cited precedent was checked against the awesome-jev category files downloaded in that run. Figures
quoted from list entries are the entries' own claims, unverified. The fixture has a single commit,
so Jev's Radar found no hot Footprints here.

---

Scope: I analyzed the current project (one Python helpdesk app: 8 code files under `helpdesk/` plus `README.md`). I skipped `.env` because it's a secret file and wasn't opened. I read `helpdesk/settings.py` for setting names only. The app does not call Jev today. Jev's Radar ran with Footprints and found no rules that people keep patching. Run date: 2026-10-12. Precedent lookup worked. I fetched these awesome-jev categories: Classification & Routing, Content Moderation, Verification & Guardrails, and Scoring & Ranking. Listings on awesome-jev are not endorsements.

Choice picks one option from a list. Score places something on ordered levels. Noul is the probability that a yes/no statement is true.

| Rank | Idea | Shape | Effort | Value | Risk |
| --- | --- | --- | --- | --- | --- |
| 1 | Route new tickets to a team | Choice | S | High | Low |
| 2 | Score ticket urgency | Score | S | High | Low |
| 3 | Swap the "is angry" LLM call for a Noul | Noul | S | Medium | Low |
| 4 | Decide which tickets to hold for abuse | Noul ×2 | M | Medium | Medium |
| 5 | Gate auto-refunds on what the customer actually asks | Noul ×2 | M | High per case | High |
| 6 | Rank help-article suggestions | Noul per candidate | S | Low | Low |
| 7 | Close tickets on "resolved" replies | Noul | S | Low | Medium |

### 1. Route new tickets to a team
- **Where:** `helpdesk/router.py:14` (`route`), with its regexes at `helpdesk/router.py:5-8`.
- **Today:** The first regex that matches subject plus body wins. They are checked in a fixed order: billing, technical, account, sales, and "general" if none match. A ticket that mentions both an invoice and an error always goes to billing. Words like "card" match even when they aren't about payment.
- **Jev decision:** Choice: "Which team should handle the request in this ticket?"
  - `billing`: charges, invoices, refunds, payment methods
  - `technical`: errors, bugs, crashes, API or integration problems
  - `account`: login, password, 2FA, locked accounts, username changes
  - `sales`: pricing, quotes, upgrades, plans, discounts
  - `general`: none of these, or unclear
  - State: `ticket.subject`, `ticket.body`
- **Confidence handling (starting point; tune on labeled data):**
  - Confidence ≥ 0.8: route.
  - 0.5 to 0.8: route, and flag for a quick check.
  - Below 0.5, or on any Jev error: fall back to the current `route()` regex.
- **What Jev Sees:** personal (customer messages). Send only the subject and body. Strip signatures, email addresses and phone numbers. Don't send the order record or customer IDs.
- **Precedent:**
  - [jev-cookbook](https://github.com/nexibeo/jev-cookbook) (Classification & Routing): runnable recipes that route support tickets with Choice and Noul questions and send low-confidence answers to human review. This is the same task.
  - [Jev email intent workflow](https://github.com/GiesN/typesafe-jev-workflow) (Classification & Routing): a typed Choice sends each inbound email to the matching handler. Same dispatch shape, with fewer options.
- **Benefit:** The team is chosen from what the ticket means, not from the first keyword in a fixed order.
- **Main risk:** The option definitions must match how the teams really split work. Otherwise ambiguous tickets still land in the wrong place.
- **Poor fit if:** tickets start arriving with a structured category field (use the field instead), or volume drops to a handful a day.
- **Why this rank:** Almost every ticket goes through it (about 4,000 a day per the README, minus held and refunded ones). Today it is a first-match regex that ignores context. Misroutes are cheap and reversible: a reassignment and some delay.
- **Effort:** S

### 2. Score ticket urgency
- **Where:** `helpdesk/router.py:22` (`priority`), using `URGENT_WORDS` at `helpdesk/router.py:11`.
- **Today:** Counts urgent words as substrings. Two or more hits, or "!!!", gives 2. One hit gives 1. Otherwise 0. "down" matches "download", and a calm description of a real outage can score 0.
- **Jev decision:** Score: "How urgent is the issue described in this ticket?"
  - `0`: a routine question or request with no deadline, and work isn't blocked. This also covers "nothing applies".
  - `1`: inconvenient, or blocks one person, but there is a workaround or it can wait.
  - `2`: blocks the customer's work or many users: an outage, data loss, or revenue stopped.
  - These keep today's 0 to 2 scale, so the queue code doesn't change.
  - State: `ticket.subject`, `ticket.body`
- **Confidence handling (starting point; tune on labeled data):**
  - Round the position to the nearest level, and keep the unrounded position for sorting within a level.
  - Confidence ≥ 0.8: use the level.
  - 0.5 to 0.8: use it, and flag for a quick check.
  - Below 0.5, or on any error: fall back to the current `priority()` word count.
- **What Jev Sees:** personal. Same fields as idea 1, sent in the same request.
- **Precedent:**
  - [Jev-Mail](https://github.com/vynnlee/jev-mail) (Classification & Routing): Jev scores urgency, importance and category for incoming mail and sends uncertain mail to review.
  - [JevBystander](https://github.com/Nisaka520/JevBystander) (Classification & Routing): a 0 to 3 urgency Score asked in one batched request alongside intent questions.
- **Benefit:** Urgency is judged on the situation, not on punctuation or substrings.
- **Main risk:** The levels can drift from what the support team means by "urgent". Write them with the support leads.
- **Poor fit if:** priority should come from contract or SLA tiers. Look the tier up in code, and use Jev only for the urgency described in the text.
- **Why this rank:** It runs on the same roughly 4,000 tickets a day. The substring count both over-fires and under-fires. Mistakes cost a middling amount (a missed SLA or an inflated queue) but can be reversed.
- **Effort:** S

### 3. Swap the "is angry" LLM call for a Noul
- **Where:** `helpdesk/sentiment.py:7` (`is_angry`), with the LLM call at `helpdesk/sentiment.py:8`.
- **Today:** Asks gpt-4o-mini a YES/NO question and treats any answer starting with "YES" as angry. An angry ticket goes to a senior agent. The call has no timeout or error handling.
- **Jev decision:** Noul: "The customer who wrote this ticket is angry or frustrated with the company, its product, or its staff."
  - Yes means clear anger or frustration aimed at the company: repeated failures, complaints, or threats to leave.
  - A neutral tone, or annoyance at their own mistake, counts as no.
  - State: `ticket.body`
- **Confidence handling (starting point; tune on labeled data):**
  - p ≥ 0.8: send to a senior agent.
  - p ≤ 0.2: normal queue.
  - In between, or on a Jev error: use the current LLM call. Wrap that call in a timeout and try/except so a failure returns "not angry" (the normal queue) instead of crashing the ticket.
- **What Jev Sees:** personal. Send the body only, with the signature stripped. The same body already goes to OpenAI today, so switching moves it to TypeSafe instead. Check your data policy.
- **Precedent:**
  - [Vibefilter](https://github.com/vibefilter/filament) (Classification & Routing): a Noul per row on "The customer is angry.", keeping rows at or above 0.8. Its listing reports matching the demo's own mood labels on 861 of 1,000 reviews (from the listing, unverified).
  - [Notra](https://github.com/usenotra/notra) (Classification & Routing): a production platform that moved classifiers off an LLM and onto Jev yes/no decisions behind a flag. It is a similar swap.
- **Benefit:** You get a probability you can put a threshold on, instead of parsing free text. It can ride in the same request as ideas 1 and 2, which would let you drop the separate LLM call. Measure cost and latency yourself.
- **Main risk:** "Angry" is subjective. The cutoff decides how many tickets reach senior agents.
- **Poor fit if:** the senior-agent rule needs a written reason for each ticket. Jev returns probabilities, not explanations.
- **Why this rank:** It runs on the same roughly 4,000 tickets a day. Today it is a label-only LLM call, parsed by prefix and unguarded. Mistakes are cheap: some senior time, or a junior agent with an upset customer. It ranks below 1 and 2 because an LLM is probably less weak than those regex rules.
- **Effort:** S

### 4. Decide which tickets to hold for abuse
- **Where:** `helpdesk/abuse.py:7` (`should_hold`), with the regex at `helpdesk/abuse.py:4`.
- **Today:** A five-word regex (insults, "scam", a masked swear word) holds the ticket for review, and nothing else in the pipeline runs. A customer reporting a scam gets held. Abuse without those words gets through.
- **Jev decision:** Noul ×2
  - Noul: "This ticket insults, demeans, or uses slurs against support staff or company employees." Yes means abuse aimed at people. Swearing at a product or situation ("this stupid app") counts as no.
  - Noul: "This ticket threatens violence or harm to a person." Yes means any such threat.
  - State: `ticket.body`
- **Confidence handling (starting point; tune on labeled data):**
  - Any one triggers: hold if either Noul has p ≥ 0.8.
  - Pass if both are ≤ 0.2.
  - Otherwise, or on any error, the current regex decides.
  - A hold already goes to a person, so the default reversible cutoffs fit.
- **What Jev Sees:** personal. Send the body only.
- **Precedent:**
  - [profanity-checker](https://github.com/4rays/profanity-checker) (Content Moderation): one Noul for literal profanity and a second for disguised spellings. The threshold and the `max()` "any one triggers" policy live in code.
  - [mastra-jev-moderation](https://github.com/CodeAlive-AI/mastra-jev-moderation) (Content Moderation): a yes/no block question plus a category Choice in one request, failing open behind a deadline. Its listing reports 9/9 hostile and 0/49 real messages blocked in production (from the listing, unverified).
- **Benefit:** Customers who report scams or vent about a product stop getting held, and abuse that avoids the five words is caught.
- **Main risk:** An abusive ticket that slips through reaches an agent. The abuse policy must be written down and agreed.
- **Poor fit if:** holds are rare and reviewers clear them in minutes. Then the regex's false holds cost little.
- **Why this rank:** Every ticket goes through it (about 4,000 a day), and it gates the whole pipeline. Today it is a tiny word list that both over-holds and misses. Mistakes cost a middling amount: a real customer waits, or an agent sees abuse. It needs an agreed policy, so it is M.
- **Effort:** M

### 5. Gate auto-refunds on what the customer actually asks
- **Where:** `helpdesk/refunds.py:6` (`auto_refund`), with substring checks at `helpdesk/refunds.py:8-9`.
- **Today:** It refunds automatically when the body contains ("refund" or "money back") and ("charged twice" or "double charge"), and the order is $50 or less. No agent ever sees the ticket. The substrings ignore negation and context: "non-refundable" contains "refund".
- **Jev decision:** Noul ×2
  - Noul: "In this ticket, the customer asks for their money back." Yes means an explicit request for a refund or reversal. Questions about refund policy, or "I don't want a refund", count as no.
  - Noul: "In this ticket, the customer says they were charged more than once for the same purchase." Yes means a duplicate-charge claim. Disputing a single charge counts as no.
  - State: `ticket.body` only. The order amount stays in code.
- **Confidence handling (starting point; tune on labeled data):**
  - Moving money is costly, so all must pass. Refund only when both Nouls have p ≥ 0.9, `order.amount_usd` is $50 or less, and, where the payment records allow it, code confirms a second charge on that order.
  - Everything else goes through normal routing to billing, which is the manual flow.
  - Jev errors or timeouts also go to the manual flow. Never refund on an error (fail closed).
  - Don't fall back to the substring rule; that is the weak part.
- **What Jev Sees:** personal, and sensitive if customers paste card details. Send the body only, with digit runs and card numbers masked. Never send the order record or the amount.
- **Precedent:**
  - [local-decider](https://github.com/pusucip25/local-decider) (Verification & Guardrails): a rule chain runs first, and Jev is asked only where no rule decides. Its listing reports 0 false allows on irreversible tools in 112 labelled cases (from the listing, unverified). It gates agent actions, not refunds, but it has the same shape: rules first, Jev for the fuzzy part, fail closed.
  - [pi-verdict](https://github.com/jesset/pi-verdict) (Verification & Guardrails): an allow/ask/deny gate where errors and timeouts deny. Its listing calls it experimental.
- **Benefit:** No more refunds triggered by "non-refundable" or by a customer who isn't asking for money back. The $50 cap stays exact, in code.
- **Main risk:** A wrong yes sends money out, and the ticket never reaches a person.
- **Poor fit if:** the payment system can detect duplicate charges itself. Check the records in code and keep only the "asks for money back" Noul. Also a poor fit if refund volume is tiny: send them all to billing.
- **Why this rank:** Volume isn't visible (only tickets with an order). The substring rule ignores negation. Mistakes are costly and irreversible: up to $50 each, with no human review. The value per case is high, but it needs a policy agreed and carries the most risk, so it comes after the reversible ideas.
- **Effort:** M

### 6. Rank help-article suggestions
- **Where:** `helpdesk/kb.py:4` (`suggest_articles`), sorting at `helpdesk/kb.py:10`.
- **Today:** Sorts all articles by how many words the body shares with each title and returns the top 3.
- **Jev decision:** one Noul per candidate: "The help article titled `title` would help answer the request in this ticket."
  - Yes means the article covers the customer's actual problem.
  - Code keeps the word-overlap pass as a shortlist of about 10 articles, then asks one Noul per shortlisted article.
  - State: `ticket.body`, `article.title` for each candidate.
- **Confidence handling (starting point; tune on labeled data):**
  - Show candidates with p ≥ 0.8, sorted by p.
  - Drop candidates with p ≤ 0.2.
  - Fill any remaining slots from the current overlap order.
  - On error, use the current overlap order.
- **What Jev Sees:** personal (the body) plus internal or public article titles. Send the body and the candidate titles only.
- **Precedent:**
  - [jevsearch](https://github.com/kylemclaren/jevsearch) (Scoring & Ranking): sends keyword hits to Jev as one Noul per page and re-orders them in code. Its own benchmark reports Hit@1 of 83% against 41% for keywords alone (from the listing, unverified).
  - [Jev RAG](https://github.com/aifabrice/jev-rag) (Scoring & Ranking): a keyword-ranking (BM25) shortlist followed by a batched Noul relevance question per passage, with a runnable demo and a public benchmark.
- **Benefit:** Suggestions follow what the ticket means rather than shared title words.
- **Main risk:** Little gain on a low-stakes feature, and one more question per candidate on every ticket.
- **Poor fit if:** agents rarely use suggestions, the knowledge base is too large to judge per article, or a vector search already does well. This is retrieval reranking. A report on the awesome-jev list found that Jev reranking alone did not beat vector search. That is unverified, and it wasn't in the categories fetched this run, so it isn't linked here. Measure against the current suggestions and an embedding search before committing.
- **Why this rank:** It runs on the same roughly 4,000 tickets a day, and title-word overlap is weak. But mistakes are nearly free (an agent ignores a poor suggestion), and reranking is a known weak spot.
- **Effort:** S

### 7. Close tickets on "resolved" replies
- **Where:** `helpdesk/autoclose.py:7` (`should_close`).
- **Today:** Closes only when the whole reply is a bare thanks (`THANKS_ONLY`, an anchored regex). "Thanks, that fixed it!" stays open.
- **Jev decision:** Noul: "In this reply, the customer says the issue is resolved and asks for nothing more."
  - Yes means a confirmation that it works, with no new question or complaint.
  - State: the reply text.
- **Confidence handling (starting point; tune on labeled data):**
  - Keep the regex as the first pass, and ask Jev only about replies it doesn't match.
  - Closing a customer's ticket is costly, so close only at p ≥ 0.9, and only if code finds no question mark in the reply.
  - Otherwise, or on error, leave the ticket open, which is today's behaviour.
- **What Jev Sees:** personal. Send the reply text only, without quoted earlier messages or signatures.
- **Precedent:** none found in the categories fetched.
- **Benefit:** Fewer tickets for agents to close by hand.
- **Main risk:** Closing a ticket where the customer raised a new problem after saying thanks.
- **Poor fit if:** reply volume is small, or agents close these quickly anyway. Then keep the regex alone.
- **Why this rank:** Reply volume isn't visible, and today's rule is narrow but precise. A wrong close reaches the customer. The win is small and the risk is real.
- **Effort:** S

## Power Jewels
New things Jev could add, using data the app already has.
- **Churn-risk flag:**
  - **Data:** ticket bodies in `handle_new_ticket` (`helpdesk/pipeline.py:5`) and customer replies in `handle_reply` (`helpdesk/pipeline.py:19`).
  - **Question:** Noul: "In this message, the customer says they plan to cancel, not renew, or switch to another provider." Yes means an explicit intent to leave. General frustration counts as no.
  - **What the app does:** at p ≥ 0.8, tag the ticket and notify the account owner. Otherwise do nothing.
  - **What Jev Sees:** personal. Send the message text only.
  - **Precedent:** same Noul-on-a-customer-statement pattern as Vibefilter (see idea 3).
- **"Still broken" reply flag:**
  - **Data:** the reply in `handle_reply` (`helpdesk/pipeline.py:19`). Today it is only checked for a bare thanks, and the `ticket` passed alongside it isn't used.
  - **Question:** Noul: "In this reply, the customer says the problem is still happening or the suggested fix did not work."
  - **What the app does:** at p ≥ 0.8, flag the ticket back to its agent, or bump it one priority level, instead of leaving it waiting.
  - **What Jev Sees:** personal. Send the reply text only, without quoted history.
  - **Precedent:** none found in the categories fetched.

## One request, several questions
- **Each new ticket (`handle_new_ticket`, `helpdesk/pipeline.py:5`):** ideas 1 to 5 all read `ticket.body` (idea 1 adds the subject). Idea 6 can join once code has the article shortlist. They can go in one Jev request. Each answer is independent, so code can use or ignore each one.
  - The pipeline stops early: a hold (idea 4) skips everything after it, and an auto-refund (idea 5) skips routing.
  - One request per ticket is the better choice here. It is simplest and needs one round trip. Only the answers for held or refunded tickets go unused, which is probably a small share.
  - Code applies the hold, then the refund gate, then everything else.
  - Switch to two stages (the gate questions first, the rest only for tickets that continue) if held or refunded tickets turn out to be a large share.
- **Each customer reply (`handle_reply`, `helpdesk/pipeline.py:19`):** idea 7 and both Power Jewels read the reply text and can share one request.

## Not Jev's Job
- `helpdesk/refunds.py:3` (`AUTO_REFUND_LIMIT_USD`): a money cap set by policy, compared exactly against `order.amount_usd`. What would change my mind: nothing about the cap itself. Even limits that vary by customer history would be a lookup in code.
- `helpdesk/pipeline.py:8` (`handle_new_ticket`, the "order exists" check): this is a data-presence fact. What would change my mind: refund requests arriving without an attached order. Then code could find candidate orders and Jev could pick one with a Choice over those candidates.
- `helpdesk/autoclose.py:4` (`THANKS_ONLY`): an anchored, narrow, precise regex. Keep it as the first pass in idea 7. What would change my mind: seeing it close tickets that still needed help.

## Off the Map
- `.env`: a secret file, not opened. There is nothing to cover; it should hold config, not decisions.
- **Whatever calls `handle_new_ticket` and `handle_reply`** (web handler, email ingest, or queue): it isn't in this folder, and nothing in the app calls these functions. The volume figure comes only from the README. To cover it next: `/jev-where <path to that service>`
- `helpdesk/settings.py`: read for setting names only, because it holds a secret. No decision logic was found by name.

## Also noticed
- `helpdesk/settings.py:3`: hardcoded secret (`SIGNING_SECRET`, value not shown). Move it to the environment or a secret store, and rotate it.
- `helpdesk/sentiment.py:8` (`is_angry`): the LLM call has no timeout, try/except or retry. A failure, or an empty answer hitting `.strip()`, fails the whole new-ticket result.
- `helpdesk/sentiment.py:12`: the raw ticket body is pasted into the prompt, so a customer can steer the YES/NO answer. The full body is also sent to a third party.
- `helpdesk/pipeline.py:6`, `helpdesk/router.py`, `helpdesk/refunds.py`: direct `ticket["subject"]`, `ticket["body"]` and `order["amount_usd"]` lookups raise KeyError when a field is missing.

## Start here
Start with idea 1, routing. It touches almost every ticket, today's rule is the weakest kind (first-match regex), mistakes are cheap and reversible, and it is a single call site with an existing fallback. Run it in shadow mode next to `route()` first. Once it holds up, add ideas 2 and 3 to the same request. Evaluate it on a small labeled set of real inputs: run the current approach and Jev side by side, then compare accuracy, accuracy on the cases Jev would handle automatically, how often it falls back, and the cost and latency you measure yourself.

Want me to draft a minimal starter integration for one of these ideas? Tell me which one. I'll read the current TypeSafe docs first (and tell you if I can't reach them), and show the code here without changing any files. I can also save this report as a Treasure Map (`jev-where-map.json`) so the next run can show what changed.
