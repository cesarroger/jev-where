# Example: `/jev-where` on the helpdesk fixture

A real run of the skill on [`evals/helpdesk-report/app`](../evals/helpdesk-report/app), a fake support-ticket
service built to test the plugin, with live precedent lookup on 2026-10-11. Every
cited precedent was checked against the awesome-jev category files fetched that
day. Figures quoted from list entries are the entries' own claims, unverified.
For the same app with no network, see [sample-report-offline.md](sample-report-offline.md).

---

I analyzed the helpdesk app in the current project: `README.md` and all 8 files in `helpdesk/` (113 lines). I did not open `.env`. The app doesn't use Jev today. The precedent lookup ran on 2026-10-11 and fetched four awesome-jev categories: Classification & Routing, Verification & Guardrails, Content Moderation, and Scoring & Ranking.

Listings on awesome-jev are not endorsements.

Choice picks one option from a list. Score places something on ordered levels. Noul is the probability that a yes/no statement is true.

| Rank | Idea | Shape | Effort | Value | Risk |
| --- | --- | --- | --- | --- | --- |
| 1 | Team routing for new tickets | Choice | S | High | Low |
| 2 | Ticket priority | Score | S | High | Low |
| 3 | Angry-customer flag (replaces the YES/NO LLM call) | Noul | S | Medium | Low |
| 4 | Abuse hold | Noul ×2 | M | High | Medium |
| 5 | Auto-close on a customer reply | Noul ×2 | M | Medium | Medium |
| 6 | Auto-refund approval | Noul ×2, policy in code | M | Medium | High |
| 7 | Help-article suggestions | Noul per article | M | Low | Low |

### 1. Team routing for new tickets
- **Where:** `helpdesk/router.py:14` (`route`), with the regexes at `helpdesk/router.py:4-9`. It is called from `helpdesk/pipeline.py:12`.
- **Today:** Four regexes run over the subject and body. The first match wins, in a fixed order: billing, technical, account, sales. Anything else goes to `general`. On mixed tickets the order decides:
  - "refund for the API error" goes to billing.
  - "can't log in to update my card" goes to billing.
  - "a quote for 500 seats" goes to technical, because the technical regex matches `500`.

  This runs on every open ticket. The README says "Roughly 4,000 tickets a day" (`README.md:6`). A misroute costs a transfer and a delay, and it can be undone.
- **Jev decision:** Choice: "Which team should handle the request in this ticket?"
  - `billing`: charges, invoices, refunds, payment methods
  - `technical`: errors, bugs, crashes, API or integration problems, something not working
  - `account`: login, password, 2FA, locked accounts, username or profile changes
  - `sales`: pricing, quotes, upgrades, enterprise plans, discounts
  - `general` (no match): none of the above, or not enough information to tell
  - State: `ticket.subject`, `ticket.body`
- **Confidence handling (starting point; tune on labeled data):**
  - Confidence ≥ 0.8: route to the chosen queue.
  - 0.5 to 0.8: route there and tag the ticket for a quick routing check.
  - Below 0.5, or on an error or timeout: use today's `route()` regex result.

  Every outcome can be undone, so no human gate is needed.
- **Precedent:**
  - [jev-cookbook](https://github.com/nexibeo/jev-cookbook) (Classification & Routing): runnable recipes that route support tickets with Choice and Noul questions and send low-confidence answers to human review. It is the same job with the same fallback idea.
  - [Jev email intent workflow](https://github.com/GiesN/typesafe-jev-workflow) (Classification & Routing): a Choice routes each inbound email to a handler, like this app's email-to-ticket entry point. It has only two options (`invoice`, `general`).
- **Benefit:** Mixed-topic tickets go to the team that owns the actual problem instead of the first keyword. Wording outside the regexes ("I was billed two times", "the dashboard won't load") stops landing in `general`.
- **Main risk:** Team boundaries that people find fuzzy, such as "refund because the feature is broken", will also be fuzzy for Jev. Expect those in the middle band.
- **Poor fit if:** the inbound address or a form field already names the team (use that field), or transfers between queues are already rare.
- **Effort:** S

### 2. Ticket priority
- **Where:** `helpdesk/router.py:22` (`priority`), with the word list at `helpdesk/router.py:11`. It is called from `helpdesk/pipeline.py:13`.
- **Today:** It counts words from `URGENT_WORDS` in the body only and ignores the subject:
  - 2 or more hits, or "!!!", gives priority 2.
  - 1 hit gives 1.
  - Otherwise 0.

  This is plain substring matching, so "down" fires on "download" and "dropdown". An outage worded as "nobody on our team can sign in" scores 0. It runs on every open ticket. A wrong priority delays urgent tickets or pushes routine ones ahead, and it can be undone.
- **Jev decision:** Score: "How urgent is the issue in this ticket for the customer?"
  - `0` (low): a question, feedback, or request where nothing is broken and there's no deadline. This level also covers tickets that describe no problem at all.
  - `1` (normal): something isn't working for this customer, but they have a workaround or no time pressure.
  - `2` (high): the customer can't work or can't take payments, a service is down for many of their users, or they name a deadline of today.
  - State: `ticket.subject`, `ticket.body`
- **Confidence handling (starting point; tune on labeled data):**
  - Round the position to the nearest level first.
  - Confidence ≥ 0.8: use that level.
  - 0.5 to 0.8: use it and flag the ticket for a quick check.
  - Below 0.5, or on an error or timeout: use today's `priority()`.

  Keep the unrounded position as a sort key within each level, so the most urgent "normal" tickets come first.
- **Precedent:**
  - [jev-oncall](https://github.com/mingleiw/jev-oncall) (Classification & Routing): asks a severity Score and an owning-team Choice in one call per alert and sends a middle band to a person. It falls back to configured severity on any error or timeout, the way this would fall back to `priority()`. The entry reports latency and cost from a 300-alert run; those are its own figures, unverified.
  - [Jev-Mail](https://github.com/vynnlee/jev-mail) (Classification & Routing): scores the urgency of incoming email and sends uncertain mail to review.
- **Benefit:** Priority follows impact instead of word counts and exclamation marks. The subject line counts, and you get an order within each level.
- **Main risk:** A real outage scored 0 or 1 waits in the queue. During the trial, you could stop Jev from lowering a ticket below the keyword result. That departs from the default bands, and the reason is that a missed outage costs more than an over-prioritized question.
- **Poor fit if:** priority really comes from plan tier or SLA terms that code can look up. In that case use the lookup, and keep Jev only for how urgent the issue itself is.
- **Effort:** S

### 3. Angry-customer flag (replaces the YES/NO LLM call)
- **Where:** `helpdesk/sentiment.py:7` (`is_angry`). It is called from `helpdesk/pipeline.py:14`.
- **Today:** Each open ticket gets one `gpt-4o-mini` chat call with "Answer only YES or NO." and "Is this customer angry?". The reply is parsed with `startswith("YES")`, and a yes sends the ticket to a senior agent. The call has no timeout or error handling. A wrong answer either spends senior time on a calm ticket or leaves an angry customer with a junior agent. It can be undone.
- **Jev decision:** Noul: "The customer who wrote this ticket is angry or strongly frustrated with the company or its service."
  - Counts as yes: clear anger or frustration aimed at the company, product, or staff, such as complaints about repeated failures, threats to leave, or insults.
  - Doesn't count: urgency alone, a polite report of a problem, or sadness.
  - State: `ticket.body`
- **Confidence handling (starting point; tune on labeled data):**
  - p ≥ 0.8: senior agent.
  - p ≤ 0.2: normal queue.
  - Between, or if Jev errors: use today's gpt-4o-mini call.

  Wrap today's call in a timeout and try/except. A failure should then give `senior = False` and still create the ticket, instead of failing all of `handle_new_ticket`.
- **Precedent:** [Vibefilter](https://github.com/vibefilter/filament) (Classification & Routing): asks a Noul on "The customer is angry." for each row and keeps rows at or above 0.8, which is almost the same statement and cutoff. The entry reports matching its demo's mood labels on 861 of 1,000 reviews. That is the entry's own figure on demo data, unverified.
- **Benefit:** You get a probability with a tunable cutoff instead of parsing free text. The LLM is only called for the uncertain middle. This question can go in the same request as ideas 1 and 2.
- **Main risk:** Sarcasm and polite-but-furious messages. The cutoff can also drift from what senior agents actually want to pick up.
- **Poor fit if:** the current call is already accurate and cheap enough and you won't batch it with the other ticket questions. Then the main gain is robustness, which a try/except alone also gives.
- **Effort:** S

### 4. Abuse hold
- **Where:** `helpdesk/abuse.py:7` (`should_hold`), with the regex at `helpdesk/abuse.py:4`. It runs first, in `helpdesk/pipeline.py:6`.
- **Today:** A regex matches "idiot", "stupid", "moron", "scam" or "scammers", and starred spellings of one swear word. Any match returns `held_for_review` and stops the pipeline: no queue, no priority, no refund check. It runs on every new ticket (about 4,000 a day).
  - False positives hold real customers, sometimes fraud victims: "I think this email was a scam", "sorry if this is a stupid question".
  - False negatives let insults or threats in other words or spellings through to agents.

  A hold can be undone, but the code doesn't show how held tickets get reviewed.
- **Jev decision:** Noul, one per policy category:
  - "This ticket insults, swears at, or harasses support staff or the company's employees."
    - Counts as yes: abuse aimed at people, including disguised spellings.
    - Doesn't count: calling a charge or an email a scam, or criticizing the product.
  - "This ticket threatens violence or other harm against a person."
    - Counts as yes: any threat of harm, including a conditional one.
  - State: `ticket.body`
- **Confidence handling (starting point; tune on labeled data):**
  - Hold if either Noul is p ≥ 0.8.
  - Don't hold if both are ≤ 0.2, even when the regex matches. This is what frees the "scam" reports.
  - Anything else, or an error: use today's regex.

  These are the defaults for an action that can be undone, because a hold can be released. If a hold ever triggers a ban, a block, or a message to the customer, switch to the costly cutoffs and have a person decide.
- **Precedent:**
  - [profanity-checker](https://github.com/4rays/profanity-checker) (Content Moderation): one Noul for literal profanity and a second for disguised spellings, with the threshold and policy in code. That is the same split as the regex's handling of starred spellings.
  - [mastra-jev-moderation](https://github.com/CodeAlive-AI/mastra-jev-moderation) (Content Moderation): one block question plus a category Choice in one request, cut at 0.7, failing open behind a deadline. The entry reports that in production it blocked 9/9 hostile and 0/49 real messages. Those are its own figures, unverified.
- **Benefit:** Fewer real customers get held, which also means fewer refund checks and routings skipped. Abuse worded outside the list gets caught.
- **Main risk:** The abuse policy is vague today, and Jev will apply whatever the statements say. The wording needs agreement from whoever reviews holds.
- **Poor fit if:** holds are rare and reviewed within minutes, so a false positive costs little.
- **Effort:** M

### 5. Auto-close on a customer reply
- **Where:** `helpdesk/autoclose.py:7` (`should_close`), with the regex at `helpdesk/autoclose.py:4`. It is called from `helpdesk/pipeline.py:20` (`handle_reply`).
- **Today:** It closes the ticket when the latest reply is only "thanks", "thank you", "thx", "ty", or "cheers". The thread isn't used, even though `handle_reply` receives `ticket`. So it misses "Thanks, that fixed it!", and it closes on a "thanks" sent after "we're still looking into it". Reply volume is not visible. A wrong close reaches the customer, so this counts as costly.
- **Jev decision:** Noul, two statements:
  - "In the latest reply, the customer says their issue is resolved or that they need nothing more."
    - Counts as yes: an explicit confirmation, or a thank-you that ends the conversation after a fix.
  - "In the latest reply, the customer asks something new or says the problem is still happening."
    - Counts as yes: any open question or remaining problem.
  - State: `latest_reply`, the agent's previous message, `ticket.subject`
- **Confidence handling (starting point; tune on labeled data):**
  - Close only when the first Noul is ≥ 0.9 and the second is ≤ 0.1. The 0.1 mirrors the 0.9 bar, because a wrong close reaches the customer.
  - Where your data allows, also require a code check, for example that an agent replied after the customer's last question.
  - Everything else stays open for an agent to close, which is today's manual flow.
  - Errors and timeouts: leave the ticket open.

  This is stricter than today for a bare "thanks" Jev is unsure about. Leaving those open is the safe direction.
- **Precedent:**
  - [jev-cookbook](https://github.com/nexibeo/jev-cookbook) (Classification & Routing): support-ticket recipes with Noul questions, sending low-confidence answers to human review.
  - [TryJevAI](https://tryjevai.com/) (Verification & Guardrails): a public playground that uses an explicit `Unresolved` option to tell a mentioned time from an agreed one before treating it as settled. It has the same "act only when it's clearly settled" shape in another domain. It is a playground, not production use.
- **Benefit:** More truly resolved tickets close automatically, and fewer close on a polite "thanks" while the problem is still open.
- **Main risk:** Closing a ticket the customer still needs. The code doesn't show whether closing also sends the customer an email.
- **Poor fit if:** reply volume is small, or reopen rates are already low.
- **Effort:** M

### 6. Auto-refund approval
- **Where:** `helpdesk/refunds.py:6` (`auto_refund`), with the limit at `helpdesk/refunds.py:3`. It is called from `helpdesk/pipeline.py:8`.
- **Today:** It approves when all three hold:
  - the lower-cased body contains "refund" or "money back";
  - it also contains "charged twice" or "double charge";
  - `order["amount_usd"] <= 50`.

  Substring matching ignores negation ("I was not charged twice") and other wording ("billed two times"). Nothing here checks that a duplicate charge actually exists, or that the order wasn't already refunded. The code that moves the money isn't in this folder. It runs on new tickets that have an order and weren't held; that volume is not visible. A wrong approval sends out up to $50 and is hard to undo.
- **Jev decision:** Noul, one per condition. The refund policy stays in code.
  - "This ticket asks for money back."
    - Counts as yes: an explicit request for a refund, reversal, or credit.
  - "This ticket says the customer was charged more than once for the same purchase."
    - Counts as yes: the customer states a duplicate charge.
    - Doesn't count: a denial, or a question about whether it happened.
  - State: `ticket.body`. `order.amount_usd` stays in code.
- **Confidence handling (starting point; tune on labeled data):** Auto-refund only when all of these hold:
  - both Nouls are ≥ 0.9;
  - the amount is ≤ $50 (checked in code);
  - where you have payment records, they show two charges for this order and no earlier refund.

  Everything else gets no auto-refund, and the ticket continues to normal routing so a person in billing handles it. Errors and timeouts also mean no auto-refund (fail closed).
- **Precedent:**
  - [jev-risk-check-provider](https://github.com/caiovicentino/jev-risk-check-provider) (Verification & Guardrails): in agent payments, Jev answers typed Noul/Choice/Score questions and code controls the final score. That is the same split as here: Jev judges, code decides. Its scale-run and red-team figures are the entry's own, unverified.
  - [pi-verdict](https://github.com/jesset/pi-verdict) (Verification & Guardrails): deterministic rules settle clear cases first, uncertain cases go to a person, and errors or timeouts deny. That is the fail-closed shape this gate needs. The entry calls itself experimental.
- **Benefit:** Negated or hypothetical mentions stop triggering refunds, and real duplicate-charge requests in other words can qualify.
- **Main risk:** Jev recognizes more wordings, so more money may move automatically. Without the payment-record check, the customer's claim alone decides. Keep the code checks.
- **Poor fit if:** you'd rather a person approve every refund, or refund tickets are few.
- **Effort:** M (L if you need to add the payment-record check)

### 7. Help-article suggestions
- **Where:** `helpdesk/kb.py:4` (`suggest_articles`). It is called from `helpdesk/pipeline.py:15`.
- **Today:** It ranks every article by how many words its title shares with the body. Punctuation isn't stripped and stopwords count. It always returns the top 3, even when none fits. Agents are the only ones who see the suggestions. It runs on every open ticket. A wrong suggestion costs an agent a glance.
- **Jev decision:** Noul per candidate. First, code builds a shortlist, for example today's overlap score or BM25, top 20.
  - Per shortlisted article: "This article would help an agent resolve the issue in this ticket."
    - Counts as yes: the article covers the customer's actual problem, not just shared words.
  - One more Noul: "At least one of these articles addresses the issue in this ticket." This lets you show nothing.
  - State: `ticket.body`, plus each candidate's `title` (and a summary, if you have one)
- **Confidence handling (starting point; tune on labeled data):**
  - If the "at least one" Noul is ≤ 0.2, show no suggestions.
  - Otherwise show up to 3: first the articles at p ≥ 0.8, sorted by p, then the in-between ones in today's overlap order. Never show articles at ≤ 0.2.
  - Errors: use today's ranking.
- **Precedent:**
  - [jevsearch](https://github.com/kylemclaren/jevsearch) (Scoring & Ranking): takes keyword hits first, sends the top 20 to Jev with a Noul per page and a Noul on whether any page answers, then reorders or drops hits in code. Its own benchmark on the 109-page TypeSafe docs reports Hit@1 of 83% against 41% for keywords alone. That is the entry's figure, unverified.
  - [Jev RAG](https://github.com/aifabrice/jev-rag) (Scoring & Ranking): a BM25 shortlist followed by batched Noul relevance questions, with a runnable demo and a public benchmark.
- **Benefit:** Suggestions match the problem rather than shared words, and agents see nothing instead of three irrelevant articles.
- **Main risk:** Spending Jev calls on suggestions agents may ignore anyway.
- **Poor fit if:**
  - This is retrieval reranking. A report on the awesome-jev list found Jev reranking alone did not beat vector search. That is unverified, and it wasn't in the categories fetched this run, so it isn't linked. Compare against vector search or BM25 before committing.
  - Titles are the only state you have.
  - The article catalog is too large to shortlist well.
- **Effort:** M

## One request, several questions
- **Each new ticket:** ideas 1, 2, 3, 4 and 6 can go in one Jev request (idea 6 only when the ticket has an order). Each answer is independent, so code can use or ignore each one. Code still applies them in the pipeline's order: hold, then refund, then routing. Idea 7's per-article questions can join the request if the shortlist is part of the state.
- **Each customer reply:** idea 5's two questions can go in one Jev request. Each answer is independent, so code can use or ignore each one.

## Also noticed
- `helpdesk/settings.py:3`: a hardcoded `SIGNING_SECRET` in source. The file's docstring says it is fake. If a real value ever lands here, move it to the environment or a secret manager and rotate it.
- `helpdesk/sentiment.py:8`: the OpenAI call has no timeout or error handling. An API error or a slow response makes `handle_new_ticket` fail for every ticket that reaches it.
- `helpdesk/sentiment.py:12`: the ticket body goes straight into the prompt, so a customer can write text that steers the YES/NO answer.
- `helpdesk/pipeline.py:6`: the abuse hold runs before the refund check and returns early. A ticket like "you scammers charged me twice" is held, and never gets a refund check, a queue, or a priority.
- `helpdesk/refunds.py:10`: the approval doesn't check that the order really was charged twice, or that it wasn't already refunded.

## Start here
Start with idea 1, team routing:
- It runs on every ticket (about 4,000 a day).
- A misroute is cheap to undo.
- The existing regex is a ready fallback.
- Your ticket history already gives you labels: the queue each ticket ended up in after transfers.

Once it holds up, add ideas 2 and 3 to the same request.

Evaluate it on a small labeled set of real inputs. Run the current approach and Jev side by side, then compare:
- accuracy;
- accuracy on the cases Jev would handle automatically;
- how often it falls back;
- the cost and latency you measure yourself.

Want me to draft a minimal starter integration for one of these ideas? Tell me which one. I'll read the current TypeSafe docs first (and tell you if I can't reach them), and show the code here without changing any files.
