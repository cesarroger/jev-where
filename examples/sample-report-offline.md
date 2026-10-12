# Example: `/jev-where` with no network

A real run of JEV WHERE? v0.3 on [`evals/helpdesk-offline/app`](../evals/helpdesk-offline/app), a fake
support-ticket service built to test the plugin, with every network tool blocked. It shows what
happens when the precedent lookup can't run: the report says so once, labels every idea, and fills
nothing in from memory. The fake app's secrets are flagged by location only.

---

Analyzed the current project, `helpdesk-offline/app`: the 8 Python files in `helpdesk/` plus the README. I skipped `.env` without opening it because it is a secret file, and read only variable names in `helpdesk/settings.py`. The app does not call Jev yet. Jev's Radar found no Footprints. Run date: 2026-10-12. Precedent lookup failed: no network access in this session.

Choice picks one option from a list. Score places something on ordered levels. Noul is the probability that a yes/no statement is true.

| Rank | Idea | Shape | Effort | Value | Risk |
| --- | --- | --- | --- | --- | --- |
| 1 | Ticket queue routing | Choice | S | High | Low |
| 2 | Ticket priority | Score | S | High | Medium |
| 3 | Angry-customer flag (replace the YES/NO LLM call) | Noul | S | Medium | Low |
| 4 | Abuse hold | Noul ×2 | M | Medium | Medium |
| 5 | Auto-close on a "thanks" reply | Noul | M | Medium | Medium |
| 6 | Auto-refund claim check | Noul ×2 | M | Medium | High |
| 7 | Help-article suggestions | Noul (one per article) | M | Low | Low |

### 1. Ticket queue routing
- **Where:** `helpdesk/router.py:14` (`route`), with the patterns at `helpdesk/router.py:5-8`. Called from `helpdesk/pipeline.py:12`.
- **Today:** The code joins the subject and body and returns the first regex that matches, in a fixed order: billing, then technical, account, sales, else `general`. Any billing word ("card", "charge", "refund") beats every other topic. "500" in the technical pattern also matches dollar amounts.
- **Jev decision:** Choice: "Which team should handle the request in this ticket?"
  - `billing`: charges, invoices, refunds, payment methods
  - `technical`: errors, bugs, crashes, API or integration problems
  - `account`: login, passwords, 2FA, locked accounts, usernames
  - `sales`: pricing, quotes, upgrades, enterprise plans, discounts
  - `general`: none of these. This is the no-match option. It keeps today's fallback queue name, so downstream code doesn't change.
  - State: `ticket.subject`, `ticket.body`
- **Confidence handling (starting point; tune on labeled data):**
  - Confidence ≥ 0.8: set the queue.
  - 0.5 to 0.8: set the queue and flag it for a quick check.
  - Below 0.5, or on errors and timeouts: use the current regex `route()`. It cannot fail, so it is a safe fallback.
- **What Jev Sees:** personal (the customer's subject and body). Send only those two fields. Strip email signatures, phone numbers and addresses first. Send no sender email and no order data.
- **Precedent:** no precedent lookup available
- **Benefit:** A ticket that touches two topics ("my card is fine but the API returns 500") goes to the team it needs, not to whichever regex comes first in the list.
- **Main risk:** The team definitions agents actually use may differ from these one-line definitions. A misroute still costs a handoff.
- **Poor fit if:** tickets start arriving with a reliable category field, such as a form dropdown (then use the field), or a labeled sample shows today's misroute rate is already low.
- **Why this rank:** It runs on every open ticket (about 4,000 a day, per the README). Today's first-match regex is weak and biased by its order. Each mistake costs a modest, reversible handoff delay. No Footprints.
- **Effort:** S

### 2. Ticket priority
- **Where:** `helpdesk/router.py:22` (`priority`), with the word list at `helpdesk/router.py:11`. Called from `helpdesk/pipeline.py:13`.
- **Today:** The code counts how many `URGENT_WORDS` ("urgent", "asap", "immediately", "down", "outage", "can't work") appear as substrings of the lowercased body. Two or more hits, or "!!!", gives 2. One hit gives 1. Otherwise 0.
  - Because it matches substrings, "download" and "dropdown" count as "down".
  - A curly apostrophe means "can't work" doesn't match.
  - A real outage described without these words gets 0.
- **Jev decision:** Score: "How urgent is the problem described in this ticket?"
  - `0`: a routine question or request with no deadline, or nothing urgent described
  - `1`: one customer is inconvenienced or partly blocked, or has a workaround
  - `2`: a customer cannot work, or a service is down or failing for many users
  - State: `ticket.subject`, `ticket.body`. Today only the body is read; adding the subject is new.
- **Confidence handling (starting point; tune on labeled data):**
  - Round the position to the nearest level. Keep the unrounded position as a sort key within a level.
  - Confidence ≥ 0.8: set the priority.
  - 0.5 to 0.8: set the priority and flag it for a quick check.
  - Below 0.5, or on errors: use the current keyword count.
  - The levels match today's 0/1/2, so queue code doesn't change. Confirm the level wording with support leads.
- **What Jev Sees:** personal (subject and body). Strip signatures and contact details. Send it in the same request as idea 1.
- **Precedent:** no precedent lookup available
- **Benefit:** Real outages described in plain words reach level 2. Tickets that only say "download" or "dropdown" stop jumping the queue.
- **Main risk:** Rating a real outage too low delays it. Check level-2 recall on its own on the labeled set.
- **Poor fit if:** priority should come from a contract or SLA tier that code can look up. None is visible here. If one appears, use it, possibly alongside this Score.
- **Why this rank:** It runs on every open ticket. The substring rule fails in both directions. A miss costs more than a misroute (a missed outage SLA) but can still be corrected. It sits just behind routing because its levels need a short agreement. No Footprints.
- **Effort:** S

### 3. Angry-customer flag (replace the YES/NO LLM call)
- **Where:** `helpdesk/sentiment.py:7` (`is_angry`), with the LLM call at `helpdesk/sentiment.py:8`. Called from `helpdesk/pipeline.py:14`.
- **Today:** One LLM call per open ticket. The system prompt is "Answer only YES or NO." and the user prompt is "Is this customer angry?" plus the body. The reply is parsed with `startswith("YES")` and sets `senior`. The call has no timeout and no error handling.
- **Jev decision:** Noul: "The customer who wrote this ticket is angry or strongly frustrated with the company or its service."
  - Yes means the text shows anger or strong frustration, such as angry venting, insults, or "this is unacceptable". Mild disappointment or a neutral bug report is no.
  - State: `ticket.body`
- **Confidence handling (starting point; tune on labeled data):**
  - p ≥ 0.8: set `senior`.
  - p ≤ 0.2: not senior.
  - In between, or on Jev errors: use the current LLM call. Wrap it with a timeout and try/except, so its own failure gives the safe default `senior = False` (the ticket stays in the normal queue) instead of crashing `handle_new_ticket`.
- **What Jev Sees:** personal (the ticket body). Send the body only, with signatures and contact details stripped. Middle-band tickets still go to the current LLM provider as well.
- **Precedent:** no precedent lookup available
- **Benefit:** A probability that code can apply a cutoff to replaces parsing a free-text YES/NO. The LLM runs only on the unsure middle band.
- **Main risk:** "Angry" is subjective. The cutoff decides how many tickets reach senior agents, so tune it against senior capacity.
- **Poor fit if:** the current LLM flag is already accurate enough and its cost doesn't matter at this volume, or senior agents need a written reason for each flag (Jev returns a probability, not reasons).
- **Why this rank:** It runs on every open ticket. Today's approach works but is an unguarded, paid call with fragile parsing. A mistake costs a medium amount: an angry customer gets a non-senior agent. The change is reversible and small. No Footprints.
- **Effort:** S

### 4. Abuse hold
- **Where:** `helpdesk/abuse.py:7` (`should_hold`), with the regex at `helpdesk/abuse.py:4`. It runs first, at `helpdesk/pipeline.py:6`.
- **Today:** A regex of 5 words (`idiot|stupid|moron|scam(mers)?|f*k`) runs on the body. A match sets `held_for_review` and skips everything else, including the refund check, routing and priority.
  - "This charge looks like a scam" or "stupid bug" gets held.
  - Abuse that avoids those words passes.
- **Jev decision:** Noul ×2
  - Noul A: "This message insults or harasses a support agent or another person." Yes means name-calling or abuse aimed at a person. A complaint about a product, charge or bug is no, even with rude words.
  - Noul B: "This message threatens violence or harm against a person." Yes means any stated or implied threat of harm.
  - State: `ticket.body`
- **Confidence handling (starting point; tune on labeled data):**
  - Hold when either Noul is ≥ 0.8. Any one triggers the hold.
  - Don't hold when both are ≤ 0.2.
  - Otherwise, or on errors: use the current regex.
  - A person already reviews every hold, so the default cutoffs for reversible actions apply. Noul B can get a lower hold cutoff if the policy wants threats caught more eagerly.
- **What Jev Sees:** personal (the ticket body). Strip signatures and contact details. Send it in the same request as ideas 1 to 3.
- **Precedent:** no precedent lookup available
- **Benefit:** Real complaints that say "scam" or "stupid" reach a queue, and the refund check, instead of the review pile. Abuse without the five words gets caught.
- **Main risk:** A missed threat reaches an agent.
- **Poor fit if:** the hold rate is tiny and reviewers clear holds quickly, or a hold ever leads to a ban or legal report. Today it doesn't; if it does, keep a person deciding.
- **Why this rank:** It runs on every new ticket (about 4,000 a day) and goes first. A 5-word regex misfires on billing complaints, and a false hold delays the ticket and skips the refund path. It needs an agreed abuse policy, so it is M. No Footprints.
- **Effort:** M

### 5. Auto-close on a "thanks" reply
- **Where:** `helpdesk/autoclose.py:7` (`should_close`), with the regex at `helpdesk/autoclose.py:4`. Called from `helpdesk/pipeline.py:20`.
- **Today:** The ticket closes when the whole reply matches a thanks-only regex ("thanks", "thank you", "thx", "ty", "cheers").
  - It closes on a "thanks" sent after a status update that fixed nothing.
  - It misses "Thanks, that fixed it!" and a thanks followed by a signature.
- **Jev decision:** Noul: "This reply says the customer's issue is resolved and they need nothing more."
  - Yes means the customer confirms the fix worked or says they're done. A thanks for an update, a thanks plus a new question, or "I'll try that" is no.
  - State: `reply`. Optionally add the agent's previous message if the app keeps it. That isn't visible here: the `ticket` argument at `pipeline.py:19` is unused.
- **Confidence handling (starting point; tune on labeled data):**
  - Closing a customer's ticket is costly, so close only at p ≥ 0.9.
  - No code check exists today. Add one if the app can confirm the reply came from the ticket's customer.
  - Anything else, or on errors: the ticket stays open for an agent, which is the manual flow today.
- **What Jev Sees:** personal (the reply text). Strip the quoted earlier thread and the signature before sending.
- **Precedent:** no precedent lookup available
- **Benefit:** Fewer unresolved tickets close on a polite "thanks". More real "that fixed it" replies close automatically.
- **Main risk:** Closing an open problem by mistake reaches the customer directly.
- **Poor fit if:** reply volume is low (it isn't visible) and agents already close tickets quickly by hand.
- **Why this rank:** Reply volume isn't visible. The regex fails in both directions. A wrong close reaches the customer, so it needs a high cutoff and a person as the fallback. No Footprints.
- **Effort:** M

### 6. Auto-refund claim check
- **Where:** `helpdesk/refunds.py:6` (`auto_refund`), with the keywords at `helpdesk/refunds.py:8-9` and the cap at `helpdesk/refunds.py:3`. Called from `helpdesk/pipeline.py:8`.
- **Today:** The ticket is marked `refunded` when all three hold:
  - the body contains "refund" or "money back"
  - the body contains "charged twice" or "double charge"
  - the order is $50 or less

  "I was not charged twice" matches; "billed twice" doesn't. Nothing checks payment records for a real duplicate charge.
- **Jev decision:** Noul ×2
  - Noul A: "The customer is asking for money back." Yes means an explicit request for a refund or for a payment to be returned.
  - Noul B: "The customer says they were charged more than once for the same purchase." Yes means they describe a duplicate or repeated charge for one order. A denial ("I was not charged twice") or a different billing problem is no.
  - State: `ticket.body` only. The order amount stays in code.
- **Confidence handling (starting point; tune on labeled data):**
  - Money moves, so this fails closed. Auto-refund only when both Nouls are ≥ 0.9 and the code checks pass. All conditions must hold.
  - Code checks that stay in plain code:
    - an order is linked (`pipeline.py:8`)
    - `order["amount_usd"] <= AUTO_REFUND_LIMIT_USD` (the $50 cap)
  - Strongly recommended extra code check: confirm the duplicate charge in payment records before refunding. No such lookup is visible today.
  - Anything else, or on errors and timeouts: no auto-refund. The ticket goes on through routing to the billing queue, which is the manual flow today.
- **What Jev Sees:** personal, close to sensitive (the message is about payments). Send only the body, with card numbers, account numbers and contact details masked. Never send the order record or payment data; compute "amount ≤ $50" and "duplicate charge confirmed" in code.
- **Precedent:** no precedent lookup available
- **Benefit:** Negations and paraphrases stop slipping through the keyword pair. Fewer real duplicate charges wait in the queue.
- **Main risk:** A confident wrong yes pays out up to $50 on a claim anyone can type. Jev reads the claim; it cannot verify it.
- **Poor fit if:** payment records can confirm duplicate charges directly (then that lookup should decide and Jev at most sorts the billing queue), or policy requires a person to approve every refund.
- **Why this rank:** It runs only on tickets with a linked order; that share isn't visible. The keyword pair both misses and over-matches. Money leaves on a wrong yes, so the risk is high, and the main fix (a payment-record check) is plain code, not Jev. No Footprints.
- **Effort:** M

### 7. Help-article suggestions
- **Where:** `helpdesk/kb.py:4` (`suggest_articles`), with the sort at `helpdesk/kb.py:10`. Called from `helpdesk/pipeline.py:15`.
- **Today:** The code counts the words each article title shares with the body and returns the top 3, even when no article shares a word.
- **Jev decision:** Noul (one per candidate article): "The help article titled `article.title` addresses the problem in this ticket."
  - Yes means an agent could send that article as all or part of the answer.
  - State: `ticket.body`, one `article.title` per question.
  - Code narrows the candidates to a short list first. The article count isn't visible.
- **Confidence handling (starting point; tune on labeled data):**
  - Show an article at p ≥ 0.8.
  - Drop it at p ≤ 0.2.
  - In between, keep today's word-overlap order.
  - On errors: use the current overlap ranking.
  - Code keeps the top 3 and can show none when nothing passes.
- **What Jev Sees:** personal (the ticket body) plus public (article titles). Strip the body as in idea 1.
- **Precedent:** no precedent lookup available
- **Benefit:** Suggestions stop being three arbitrary titles when nothing fits.
- **Main risk:** This is relevance reranking. A report on the awesome-jev list found that Jev reranking alone did not beat vector search. That report is unverified and was not fetched in this run. It also takes one question per article per ticket, which grows with the catalog.
- **Poor fit if:** agents already ignore suggestions cheaply, the catalog is large, or a search index or embeddings would do the job. Measure against the current ranking first.
- **Why this rank:** It runs on every open ticket and the word overlap is weak. But a bad suggestion costs little (agents ignore it), and reranking carries a known fit warning. No Footprints.
- **Effort:** M

## One request, several questions
- **Each new ticket (`ticket.body`, plus `ticket.subject`):** ideas 1, 2, 3, 4 and 6 can go in one Jev request (idea 6 only when an order is linked), plus Power Jewel 1. Each answer is independent, so code can use or ignore each one.
  - The pipeline stops early for held tickets (`pipeline.py:6-7`) and for auto-refunded ones (`pipeline.py:8-9`).
  - Start with one request for everything. It is simplest, and it only wastes the routing, priority and anger answers on held or refunded tickets. That share isn't visible.
  - If held and refunded tickets turn out to be a large share, switch to two stages: send the abuse and refund Nouls first, then routing, priority and anger only for tickets that stay open.
  - Idea 7 adds article titles to the state, so keep it in its own request.
- **Each customer reply (`reply`):** idea 5 and Power Jewel 2 can go in one request.

## Power Jewels
New things Jev could add, using data the app already has.
- **Cancel-intent flag on new tickets:**
  - Data: `ticket["body"]`, which `handle_new_ticket` already receives (`helpdesk/pipeline.py:5`).
  - Noul: "The customer says they intend to cancel, downgrade, or stop using the service." Yes means a stated plan or threat to cancel, leave or switch providers. General complaints are no.
  - What the app would do: add a `churn_risk` flag next to `senior` on open tickets, so agents or account managers see it. Flag at p ≥ 0.8. Below that, or on errors, no flag, as today.
  - What Jev Sees: personal (the body, stripped as in idea 1). It goes in the same request as ideas 1 to 4.
  - Precedent: no precedent lookup available.
- **Still-broken flag on replies:**
  - Data: the `reply` string at `helpdesk/pipeline.py:19`. Today it is only checked for "thanks". The `ticket` argument there is passed in but unused.
  - Noul: "This reply says the problem is still happening or the suggested fix did not work." Yes means the customer reports the issue persists, came back, or got worse.
  - What the app would do: keep the ticket open and raise its priority or flag it for the assigned agent. Flag at p ≥ 0.8. Below that, or on errors, no change.
  - What Jev Sees: personal (the reply, with the quoted thread and signature stripped). It goes in the same request as idea 5.
  - Precedent: no precedent lookup available.

## Not Jev's Job
- `helpdesk/pipeline.py:8` (`handle_new_ticket`): `if order` checks that a linked order record exists. That is an exact check, so plain code should keep it. What would change my mind: tickets arrive without a linked order and the order must be found from the email text. Then code would find candidate orders and a Jev Choice would pick one.
- `helpdesk/kb.py:4` (`suggest_articles`): `k=3`, the number of articles shown, is a display choice. What would change my mind: agents want a varying number depending on fit. That would still be a cutoff in code on idea 7's answers.

## Off the Map
- `.env` at the app root: a secret file, not opened.
- `helpdesk/settings.py`: I read variable names only; the values were never loaded because one line assigns a secret-looking value. It has no decision logic, and no module imports it.
- Payment processing, email intake and ticket storage: not in this folder. `pipeline.py` and `refunds.py` set a `refunded` status, but no payment call, inbox reader or database is visible. To cover them next: `/jev-where <path to that code>`.
- Nothing was skipped as dependencies or build output; none is present.

## Also noticed
- `helpdesk/settings.py:3`: a hardcoded secret-looking value is assigned to `SIGNING_SECRET`. The value is not shown, and no module imports it. Move it to a secret store or delete it.
- `helpdesk/sentiment.py:4`: the LLM client is created when the module loads. If its API key is missing, importing `pipeline` fails, which breaks both `handle_new_ticket` and `handle_reply`.
- `helpdesk/sentiment.py:8`: an unguarded API call with no timeout, retry or error handling. An API error or an empty reply crashes `handle_new_ticket` for every open ticket.
- `helpdesk/sentiment.py:12`: raw customer text goes straight into the prompt, so a customer can steer the YES/NO answer and the `senior` flag.
- `helpdesk/refunds.py:10`:
  - `order["amount_usd"]` raises an unhandled KeyError when the field is missing.
  - Refunds are approved with no payment-record check, no guard against repeat tickets for the same order, and no audit log.

## Start here
Start with idea 1, ticket routing. It runs on every open ticket, today's first-match regex is the weakest rule in the pipeline, a misroute is cheap to correct, and the regex stays as a fallback that can't fail. Ideas 2 and 3 read the same ticket, so the same request and the same labeled set can test them next.

Evaluate it on a small labeled set of real inputs: run the current approach and Jev side by side, then compare:
- overall accuracy
- accuracy on the cases Jev would handle automatically
- how often it falls back
- the cost and latency you measure yourself

Want me to draft a minimal starter integration for one of these ideas? Tell me which one. I'll read the current TypeSafe docs first (and tell you if I can't reach them), and show the code here without changing any files. I can also save this report as a Treasure Map (`jev-where-map.json`) so the next run can show what changed.
