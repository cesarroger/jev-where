# Example: `/jev-where` on the helpdesk fixture, with no network

A real run of the skill on [`evals/helpdesk-offline/app`](../evals/helpdesk-offline/app), with every network
tool blocked, lightly edited to match the skill's current wording rules. It shows what happens when the precedent lookup can't run: the
report says so once and labels every idea, and nothing is filled in from
memory. The fixture's fake secrets are flagged by location only.

---

Analyzed the current project, `helpdesk-offline/app`: a small Python inbound-email ticket pipeline (`helpdesk/`, 8 modules, plus a README that says "Roughly 4,000 tickets a day"). I read every source file. I skipped `.env` and did not open it, because no decision point depends on it. I found no existing Jev, TypeSafe or Noul use.
Precedent lookup failed: no network access in this session. Run date: 2026-10-11. No awesome-jev categories were fetched, so no idea cites a precedent.

Choice picks one option from a list. Score places something on ordered levels. Noul is the probability that a yes/no statement is true.

| Rank | Idea | Shape | Effort | Value | Risk |
| --- | --- | --- | --- | --- | --- |
| 1 | Team routing | Choice | S | High | Low |
| 2 | Ticket priority | Score | S | High | Low |
| 3 | Angry-customer flag | Noul | S | Medium | Low |
| 4 | Abuse hold | Noul (one per policy category) | M | High | Medium |
| 5 | Auto-close on "thanks" | Noul | S | Medium | Medium |
| 6 | Auto-refund approval | Noul (one per condition) | M | Medium | High |
| 7 | Help-article suggestions | Noul (one per article) | M | Low | Low |

### 1. Team routing
- **Where:** `helpdesk/router.py:14` (`route`). The patterns are at `helpdesk/router.py:4-9`, and it is called from `helpdesk/pipeline.py:12`.
- **Today:**
  - Four regexes run over subject plus body in a fixed order: billing, then technical, then account, then sales. The first match wins, and anything else goes to `general`.
  - Mixed tickets go to whichever team is checked first. "I can't log in after my payment failed" goes to billing (`payment`).
  - Short tokens catch unrelated text. "Can I get a quote for 500 seats?" goes to technical (`500`) before sales is checked.
- **Jev decision:** Choice: "Which team should handle the request in this ticket?"
  - `billing`: charges, invoices, refunds, payment methods
  - `technical`: bugs, errors, crashes, API or integration problems
  - `account`: login, passwords, 2FA, locked accounts, usernames
  - `sales`: pricing, quotes, upgrades, enterprise plans, discounts
  - `general`: none of the above (the no-match option, and today's default queue)
  - State: `ticket.subject`, `ticket.body`
- **Confidence handling (starting point; tune on labeled data):** Routing is reversible, so this uses the default cutoffs.
  - Confidence ≥ 0.8: route automatically.
  - 0.5 to 0.8: route, and flag the ticket for a quick check by the queue owner.
  - Below 0.5, or any error or timeout: use the current `route()` regex. It is today's behaviour, so it is safe to run.
- **Precedent:** no precedent lookup available
- **Benefit:** Fewer misroutes on mixed or paraphrased requests and less re-triage. Routing follows what the customer needs instead of the first keyword hit.
- **Main risk:** Some tickets fit two definitions (for example, a refund for a bug-caused charge). Those split the probability and fall back more often. Add a tie rule to the option definitions or handle it in code.
- **Poor fit if:** inbound tickets carry a structured category (a form dropdown or a help-center topic). Route on that field instead.
- **Effort:** S

### 2. Ticket priority
- **Where:** `helpdesk/router.py:22` (`priority`). The word list is at `helpdesk/router.py:11`, and it is called from `helpdesk/pipeline.py:13`.
- **Today:**
  - It counts substring hits for `urgent`, `asap`, `immediately`, `down`, `outage` and `can't work` in the lowercased body.
  - Two or more hits, or `!!!`, gives 2 (high). One hit gives 1 (normal). Anything else gives 0 (low).
  - `down` also matches "download", "downgrade" and "shutdown".
  - A curly apostrophe defeats "can't work".
  - The subject is ignored, so "URGENT: outage" in the subject alone scores 0.
- **Jev decision:** Score: "How urgent is the problem described in this ticket?"
  - `0`: a question or request where nothing is broken and there is no deadline. This level also covers tickets where nothing applies.
  - `1`: something is broken or inconvenient, but the customer can keep working (there is a workaround, or the deadline is not immediate).
  - `2`: the customer can't work right now, or their service is down or failing for their own users.
  - State: `ticket.subject`, `ticket.body`
  - The levels map one-to-one to today's 0/1/2, so nothing downstream changes.
- **Confidence handling (starting point; tune on labeled data):** Priority is reversible, so this uses the default cutoffs. Round the position to the nearest level first, and keep the unrounded position for sorting within a level.
  - Confidence ≥ 0.8: set the priority automatically.
  - 0.5 to 0.8: set it, and flag it for a quick check.
  - Below 0.5, or any error or timeout: use the current keyword count.
- **Precedent:** no precedent lookup available
- **Benefit:** Outages described without the trigger words get high priority. "Download" and "downgrade" no longer bump tickets, and urgency in the subject line counts.
- **Main risk:** A loud tone can be read as urgency. Keep the level definitions about impact, not wording, and check overstated tickets in the labeled set.
- **Poor fit if:** priority should come from SLA tier or plan, which code can look up. No such data is visible here. If you add it, combine the two in code (for example, the SLA floor or the Jev level, whichever is higher).
- **Effort:** S

### 3. Angry-customer flag
- **Where:** `helpdesk/sentiment.py:7` (`is_angry`), called from `helpdesk/pipeline.py:14`.
- **Today:**
  - Each open ticket makes one `gpt-4o-mini` chat completion. The system prompt is "Answer only YES or NO.", the user prompt is "Is this customer angry?" followed by the body, and the reply is parsed with `startswith("YES")`.
  - There is no timeout, retry or error handling, so an API error or empty content crashes `handle_new_ticket`.
  - The ticket body is pasted straight into the prompt.
- **Jev decision:** Noul: "The customer who wrote this ticket is angry or upset with the company."
  - Yes means the customer shows anger or strong frustration at the company or service: harsh tone, complaints about repeated failures, threats to cancel or escalate.
  - A calm problem report has a low probability.
  - State: `ticket.body`. Add `ticket.subject` too, since subjects often carry tone.
- **Confidence handling (starting point; tune on labeled data):** The flag is reversible, so this uses the default Noul cutoffs.
  - p ≥ 0.8: set `senior = true`.
  - p ≤ 0.2: set `senior = false`.
  - In between, or on any error or timeout: call the current gpt-4o-mini check. Wrap that fallback so a failure returns `false` instead of raising; today it can crash ticket intake, so it is not safe to run as is.
- **Precedent:** no precedent lookup available
- **Benefit:**
  - The flag becomes a typed probability, so no free-text parsing is needed.
  - The LLM call runs only for the unsure middle band.
  - An API failure no longer breaks ticket creation.
  - Measure cost and latency yourself.
- **Main risk:** "Angry" and "frustrated but polite" are hard to tell apart. If the yes cutoff is too low, senior agents get flooded. Tune it on labeled tickets.
- **Poor fit if:** senior capacity already matches today's flag rate, and the per-ticket LLM call's cost and reliability are acceptable to you. Then the gain is small.
- **Effort:** S

### 4. Abuse hold
- **Where:** `helpdesk/abuse.py:7` (`should_hold`). The regex is at `helpdesk/abuse.py:4`, and it runs first, from `helpdesk/pipeline.py:6`.
- **Today:**
  - Any match of `idiot|stupid|moron|scam(mers)?|f*k` in the body holds the ticket for review and stops the pipeline, so the ticket gets no refund check, queue, priority, senior flag or articles.
  - It holds "Is this email a scam?" and "I feel stupid, I can't find the setting".
  - It misses abuse that avoids these exact words.
- **Jev decision:** Noul, one per category in your abuse policy. Agree the category list first.
  - "This ticket insults, swears at, or demeans support staff or the company."
    - Yes means name-calling, slurs, or profanity aimed at people, including "you scammers".
    - A low probability means swearing about a situation, self-criticism ("I feel stupid"), asking whether something is a scam, or quoting someone else's message.
  - Add one more Noul for each further category your policy holds for, for example threats of harm.
  - State: `ticket.subject`, `ticket.body`
- **Confidence handling (starting point; tune on labeled data):** A hold is reversible, because a person reviews it. This uses the default Noul cutoffs for each category.
  - p ≥ 0.8: hold.
  - p ≤ 0.2: don't hold.
  - In between, or on any error or timeout: use the current regex.
  - Hold if any category says yes.
- **Precedent:** no precedent lookup available
- **Benefit:** Real complaints that happen to contain "scam" or "stupid" reach a team and the refund check instead of waiting in review. Abuse without the listed words gets caught.
- **Main risk:**
  - A missed hold sends abuse to an agent.
  - A wrong hold delays an already unhappy customer and skips the rest of the pipeline.
  - The review queue isn't visible in this code. Confirm that it exists and is staffed.
- **Poor fit if:** holds ever lead to bans or account action. Keep a person as the final decision there. It is also a poor fit if the regex hits so few tickets that review handles them easily.
- **Effort:** M

### 5. Auto-close on "thanks"
- **Where:** `helpdesk/autoclose.py:7` (`should_close`). The regex is at `helpdesk/autoclose.py:4`, and it is called from `helpdesk/pipeline.py:20` (`handle_reply`).
- **Today:**
  - It closes the ticket only when the whole reply is a bare `thanks`, `thank you`, `thx`, `ty` or `cheers`.
  - "Thanks, that fixed it!", or a thanks followed by a signature or quoted email, stays open.
  - A bare "thanks" sent after "we're looking into it" closes a ticket that isn't solved.
  - `handle_reply` receives `ticket` but never uses it.
- **Jev decision:** Noul: "In this reply, the customer confirms their issue is resolved and they need nothing more."
  - Yes means the customer says it works now, the answer solved it, or no further help is needed.
  - A low probability means thanks for a status update while still waiting, a new question, or a report that the problem persists.
  - State: `reply`, the latest customer reply. If the app can supply it from `ticket`, also add the agent's last message, so that "thanks" after "we're looking into it" reads as not resolved.
- **Confidence handling (starting point; tune on labeled data):** This uses the stricter costly-action row, not the reversible default. A wrong close drops a customer who still needs help, and the code shows no reopen path.
  - Close only at p ≥ 0.9, and only when the reply contains no `?` (a simple code check).
  - Everything else, and any error or timeout: leave the ticket open for an agent, as today.
- **Precedent:** no precedent lookup available
- **Benefit:** More resolved tickets close themselves, so agents spend less time on "thanks, fixed it" replies, and fewer tickets close too early.
- **Main risk:** A ticket closes while the customer still needs help. Judged without the agent's last message, a short reply can be ambiguous.
- **Poor fit if:** reply volume is low (it isn't visible in the code), or agents would rather close tickets themselves.
- **Effort:** S

### 6. Auto-refund approval
- **Where:** `helpdesk/refunds.py:6` (`auto_refund`). The limit is at `helpdesk/refunds.py:3`, and it is called from `helpdesk/pipeline.py:8`.
- **Today:**
  - It refunds automatically when the lowercased body contains "refund" or "money back", plus "charged twice" or "double charge", and the order is $50 or less.
  - Plain substring matching causes errors in both directions:
    - "This was non-refundable, but was I charged twice?" qualifies, even though no refund was asked for.
    - "I was billed two times, please reverse it" doesn't qualify.
  - It never checks the order for a second charge.
  - A refunded ticket skips routing, so no person ever sees it.
- **Jev decision:** Noul, one per condition. The refund policy stays in code.
  - First Noul: "The customer asks for money back for a charge."
    - Yes means the customer requests a refund, reversal or credit.
    - A low probability means refunds come up only in passing ("non-refundable"), the customer asks about the refund policy, or says they don't want one.
  - Second Noul: "The customer says they were charged more than once for the same purchase."
    - Yes means the customer states a duplicate or repeated charge for one order.
    - A low probability means they only wonder whether it happened, or report a different billing problem.
  - State: `ticket.subject`, `ticket.body`. Code keeps the `order` presence check and `order.amount_usd <= 50`.
- **Confidence handling (starting point; tune on labeled data):** A refund moves money and can't be pulled back, so this uses the costly row and fails closed.
  - Auto-refund only when all of these hold:
    - Both Nouls are p ≥ 0.9.
    - The amount check passes.
    - Code confirms a second charge on the order, where your payment data allows it (that data isn't visible in this app).
  - Everything else, and any error or timeout: no auto-refund. The ticket continues to normal routing, so a billing agent decides.
- **Precedent:** no precedent lookup available
- **Benefit:** Stray words ("non-refundable", "was I charged twice?") no longer trigger refunds. Paraphrased duplicate-charge claims reach the gate instead of being missed.
- **Main risk:** A wrong yes pays out money with no human review. Better language matching can also raise auto-refund volume. The gate trusts the customer's claim unless code checks the charges.
- **Poor fit if:**
  - Payment records can confirm duplicate charges directly. Then the data decides, and Jev only judges whether a refund is asked for.
  - Qualifying tickets are few enough for a billing agent to handle them all.
- **Effort:** M

### 7. Help-article suggestions
- **Where:** `helpdesk/kb.py:4` (`suggest_articles`). The scorer `overlap` is at `helpdesk/kb.py:7`, and it is called from `helpdesk/pipeline.py:15`.
- **Today:**
  - It ranks articles by how many whitespace-split words the body shares with each title, and keeps the top 3.
  - Punctuation isn't stripped, ties keep the input order, and articles with no overlap still fill the 3 slots.
  - Only agents see the result.
- **Jev decision:** Noul, one per article that code shortlists: "The help article titled `article.title` addresses the problem in this ticket."
  - Yes means the article covers the customer's actual problem or question.
  - A low probability means the article shares words but is about something else.
  - State: `ticket.body`, plus `article.title` for each shortlisted article
- **Confidence handling (starting point; tune on labeled data):** Suggestions are reversible and agent-only, so this uses the default Noul cutoffs.
  - p ≥ 0.8: show the article.
  - p ≤ 0.2: drop it.
  - In between: keep the current overlap order.
  - Any error: show the current top 3.
- **Precedent:** no precedent lookup available
- **Benefit:** Fewer irrelevant suggestions. When nothing fits, the slots stay empty instead of filling with zero-overlap articles.
- **Main risk:** Titles alone carry little signal, so many articles may land in the unsure band.
- **Poor fit if:**
  - This is retrieval reranking. A report on the awesome-jev list found Jev reranking alone did not beat vector search. That is unverified, and this run could not check it.
  - The help center is large, with too many candidates to judge one by one.
  - Agents rarely use the suggestions.
  - Proper full-text or vector search is likely the better first step. Measure it before adding Jev.
- **Effort:** M

## One request, several questions
- **Each new ticket (`ticket.subject` and `ticket.body`):** ideas 1, 2, 3, 4 and 6 can go in one Jev request. Each answer is independent, so code can use or ignore each one. Keep today's order in code:
  - Act on the abuse answer (4) first.
  - Then the refund answers (6), only when there is an order.
  - Then queue, priority and senior flag (1, 2, 3).
- Idea 7 reads the same ticket plus article titles. It can join this request only if code shortlists the articles first and adds their titles to the state.
- Idea 5 reads customer replies, not new tickets, so it is a separate call.

## Also noticed
- `helpdesk/settings.py:3` hardcodes `SIGNING_SECRET` in source (value not shown). If it is a real secret, move it to your secret store or environment and rotate it.

## Start here
Start with idea 1, team routing, and ask the priority Score from idea 2 in the same request. Every ticket goes through `route()`, a misroute only costs a re-triage, and the regex router is a ready fallback. Labels are cheap: the team that actually ended up handling each ticket, if you track re-triage. Leave the refund gate (idea 6) for later, because it moves money and needs an agreed policy and a payment-data check first. Evaluate it on a small labeled set of real inputs: run the current approach and Jev side by side, then compare accuracy, accuracy on the cases Jev would handle automatically, how often it falls back, and the cost and latency you measure yourself.

Want me to draft a minimal starter integration for one of these ideas? Tell me which one. I'll read the current TypeSafe docs first and show the code here without changing any files.
