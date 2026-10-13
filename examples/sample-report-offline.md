# Example: `/jev-where` with no network

A real run of JEV WHERE? v0.4 on [`evals/helpdesk-offline/app`](../evals/helpdesk-offline/app), a fake
support-ticket service built to test the plugin, with every network tool blocked. The live lookups
can't run, so precedents come only from the Jev Sightings copy bundled with the skill, each
labelled "not rechecked today", and nothing is filled in from memory. The fake app's secrets are
flagged by location only.

---

**Scope:** I analyzed the whole `helpdesk` app in the current folder: `pipeline.py`, `router.py`, `abuse.py`, `refunds.py`, `sentiment.py`, `autoclose.py`, `kb.py`, `settings.py` and `README.md`. I did not open `.env`, and I did not load line 3 of `settings.py` because it holds a secret-looking value. This is one app. It does not call Jev yet.

**Run details:**
- Run date: 2026-10-12.
- Jev Sightings: 75 verified, from the bundled copy dated 2026-10-12. I couldn't fetch the live copy because this session has no network access. Every sighting below is labelled "not rechecked today".
- awesome-jev lookup failed: no network access in this session. I fetched no categories and skipped the fallback folder listing.
- Footprints: the radar ran and found no hot rules.

Sightings and awesome-jev listings are not endorsements.

Choice picks one option from a list. Score places something on ordered levels. Noul is the probability that a yes/no statement is true. A Jev sighting is a project where Jev was found in the code, linked to the exact lines.

| Rank | Idea | Shape | Effort | Value | Risk |
| --- | --- | --- | --- | --- | --- |
| 1 | Route each ticket to a team | Choice | S | High | Low |
| 2 | Ticket priority | Score | S | High | Low |
| 3 | Angry-customer flag (replace the label-only LLM call) | Noul | S | Medium | Low |
| 4 | Abuse hold that doesn't catch scam victims | Noul ×2 | M | Medium | Medium |
| 5 | Auto-close on "thanks, solved" replies | Noul | S | Low to medium | Medium |
| 6 | Auto-refund gate | Noul ×2 | M | Medium | High |
| 7 | Help-article suggestions | Noul per article | M | Low | Low (poor fit) |

### 1. Route each ticket to a team
- **Where:** `helpdesk/router.py:14` (`route`). The keyword regexes are at `router.py:5-8`.
- **Today:**
  - The code joins subject and body, then returns the first matching keyword regex, checked in this order:
    - `billing`: invoice, charge, refund, payment, card
    - `technical`: error, bug, crash, 500, api, broken
    - `account`: password, login, locked, 2fa
    - `sales`: pricing, quote, upgrade, discount
  - Anything else goes to `general`.
  - First match wins. "Card error at checkout" goes to billing, and tickets that use none of the words land in `general`.
- **Jev decision:** Choice: "Which team should handle the request in this ticket?"
  - `billing`: charges, invoices, refunds, payment methods
  - `technical`: errors, bugs, crashes, API or integration problems
  - `account`: login, password, 2FA, locked account, username or profile
  - `sales`: pricing, quotes, plan upgrades, discounts, enterprise deals
  - `other`: none of these (maps to today's `general` queue)
  - State: `ticket.subject`, `ticket.body`
- **Confidence handling (starting point; tune on labeled data):**
  - Confidence ≥ 0.8: use Jev's queue.
  - 0.5 to 0.8: use Jev's queue and tag the ticket for a quick check by the receiving team.
  - Below 0.5, or on any error or timeout: use today's `route()` regexes, which stay in code as the fallback.
  - `other` goes to `general`, as today. Routing is reversible, so these are the default reversible cutoffs.
- **What Jev Sees:** personal. Ticket subject and body (customer email text). Send-less tip:
  - Send only subject and body.
  - Strip signatures, email addresses, phone numbers, and order or card numbers.
  - Never send the order record or customer ID.
- **Precedent:**
  - Jev sighting, [jevcal](https://github.com/abhixhek/jevcal): Choice, Noul and Score questions at [typesafe.py:45](https://github.com/abhixhek/jevcal/blob/ae8f3144d69c9cb0e5e0a2c17f70b9d14714cb9f/src/jevcal/providers/typesafe.py#L45-L59), Python.
    - It asks user-defined questions per labeled row, such as a support ticket's department, urgency or frustration.
    - At runtime it trusts an answer only above a per-question cutoff and leaves the rest for fallback.
    - Why it's similar: it routes tickets to departments with a cutoff and a fallback, and it can tune those cutoffs on your own labeled tickets.
    - (verified 2026-10-12, not rechecked today)
  - Jev sighting, [Jevidence](https://github.com/peakevergreen/jevidence): a Choice route (asked with a Noul and a Score) at [runner.py:55](https://github.com/peakevergreen/jevidence/blob/6450a7820fec9dc9210dbea7982b6ae330d427e7/jevidence/runner.py#L55-L62), Python.
    - It sends a bug report to an investigation area, and a provider error keeps the current queue.
    - It is a demo with tests.
    - Why it's similar: Choice queue routing where an error falls back to the existing route.
    - (verified 2026-10-12, not rechecked today)
- **Benefit:** routing reads what the customer means instead of which keyword appears first. Fewer tickets land in `general` or the wrong queue, so there are fewer hand-offs.
- **Main risk:** confident misroutes on tickets that span two teams. Those are caught only by the receiving team.
- **Poor fit if:** tickets start arriving through a form with a reliable category field. Then route on the field.
- **Why this rank:** every open ticket (the README says roughly 4,000 a day) × first-match keyword rules that misfire on mixed or keyword-free tickets × a reversible cost (delay and hand-off). The regex is already there as a fallback.
- **Effort:** S

### 2. Ticket priority
- **Where:** `helpdesk/router.py:22` (`priority`), with `URGENT_WORDS` at `router.py:11` and the cutoffs at `router.py:26-30`
- **Today:**
  - The code counts substring hits from "urgent", "asap", "immediately", "down", "outage" and "can't work".
  - Two or more hits, or "!!!", gives priority 2. One hit gives 1. No hits gives 0.
  - "down" also matches "download" and "downgrade".
  - A curly apostrophe in "can’t work" doesn't match.
  - The subject is ignored.
- **Jev decision:** Score: "How urgent is the issue in this ticket?"
  - `0`: a question or request with no deadline and nothing blocked (also covers "nothing applies")
  - `1`: something is wrong for this customer but they can still work, or there's a workaround
  - `2`: the customer can't work, a service they rely on is down or in an outage, or they give a deadline within a day
  - State: `ticket.subject`, `ticket.body`
- **Confidence handling (starting point; tune on labeled data):**
  - Round the position to the nearest level, and keep the unrounded position for sorting within a level.
  - Confidence ≥ 0.8: use Jev's level.
  - 0.5 to 0.8: use the higher of Jev's level and today's keyword level, and flag the ticket. This differs from the default "act and flag" band so an urgent ticket is never demoted on an unsure answer.
  - Below 0.5, or on error: today's `priority()`, which stays in code as the fallback.
- **What Jev Sees:** personal. The same masked subject and body as idea 1. Send it once (see "One request, several questions").
- **Precedent:**
  - Jev sighting, [jev-oncall](https://github.com/mingleiw/jev-oncall): a severity question at [triage.py:455](https://github.com/mingleiw/jev-oncall/blob/e6b02aed03976f71b6ef4fe67f3d71247ca512c8/triage.py#L455-L469), Python. The sighting doesn't record the shape.
    - It judges how severe and actionable each production alert is.
    - A Jev error falls back to the alert's configured severity.
    - Why it's similar: urgency on incoming work, with the existing rule kept as the fallback.
    - (verified 2026-10-12, not rechecked today)
  - Jev sighting, [typeful-triage](https://github.com/cephalization/jev-triage): Choice and Score at [typesafe.ts:14](https://github.com/cephalization/jev-triage/blob/adb509425d3f3d75c4053184501505c3a810509a/apps/api/src/worker/typesafe.ts#L14-L25), TypeScript.
    - It asks category and severity for each GitHub issue in one batch, and retries once on transient failures.
    - Why it's similar: category plus severity on the same item in one request, like ideas 1 and 2 together.
    - (verified 2026-10-12, not rechecked today)
- **Benefit:** fixes the substring false alarms ("download"). It also catches urgency written without the magic words, so SLA queues sort on what the ticket says.
- **Main risk:** under-ranking a truly urgent ticket. The middle-band max rule above limits this.
- **Poor fit if:** priority should really come from the customer's plan or SLA tier, which code can look up. Then use the lookup and keep Jev only for "is this an outage".
- **Why this rank:** the same ~4,000/day as idea 1 × a word count that misfires both ways × missed SLAs. The cost is slightly lower than misrouting because an agent can re-prioritize in place.
- **Effort:** S

### 3. Angry-customer flag (replace the label-only LLM call)
- **Where:** `helpdesk/sentiment.py:7` (`is_angry`); the LLM call is at `sentiment.py:8`
- **Today:**
  - The code sends the full ticket body to `gpt-4o-mini` with "Answer only YES or NO." and "Is this customer angry?".
  - It treats any reply that doesn't start with YES as no. The result sets `senior` (`pipeline.py:14`).
  - The call runs once per open ticket, with no timeout or error handling.
- **Jev decision:** Noul: "The customer who wrote this ticket is angry."
  - Yes means clear anger or strong frustration aimed at the company, its product or its staff. A calm report of a problem counts as no.
  - State: `ticket.body`
- **Confidence handling (starting point; tune on labeled data):**
  - p ≥ 0.8: `senior = True`.
  - p ≤ 0.2: `senior = False`.
  - Between, or on a Jev error: today's LLM call, wrapped in a timeout and try/except. If that also fails, take today's default for an unclear answer (`senior = False`) and log it, so a failure no longer crashes `handle_new_ticket`.
  - Once tuned, you may be able to send the middle band to `False` and drop the LLM call. Measure first.
- **What Jev Sees:** personal. The ticket body. Today the full body already goes to a third-party LLM, so this moves that exposure rather than adding one. Check your data policy and TypeSafe's terms. Send-less tip: the same masked body as idea 1, and no other ticket fields.
- **Precedent:**
  - Jev sighting, [jev-ood-calibration](https://github.com/scienthoon/jev-ood-calibration): Choice, Score and Noul questions at [jev_eval.mjs:77](https://github.com/scienthoon/jev-ood-calibration/blob/48572305b384b53072bfc869de4420c5d9a6acf1/scripts/jev_eval.mjs#L77-L91), JavaScript.
    - One of its questions is whether a synthetic ticket's customer sounds angry.
    - It keeps the full probabilities to check calibration and applies no cutoff.
    - It is a benchmark, not an app.
    - Why it's similar: the same anger question on support tickets.
    - (verified 2026-10-12, not rechecked today)
  - Also see jevcal under idea 1, which covers ticket frustration.
- **Benefit:** you get a probability instead of a bare YES/NO string, so you can set and tune a cutoff. Guarding the fallback also removes a crash path.
- **Main risk:** sarcasm or polite-but-furious wording scoring low, so some angry customers miss a senior agent. That is reversible.
- **Poor fit if:** you also want the model to explain why the customer is upset or draft a reply. Jev returns probabilities, not text.
- **Why this rank:** one LLM call per open ticket (~4,000/day) × a yes/no that gives no confidence and can crash the pipeline × a moderate, reversible cost (the wrong agent tier).
- **Effort:** S

### 4. Abuse hold that doesn't catch scam victims
- **Where:** `helpdesk/abuse.py:7` (`should_hold`), with the `BANNED` regex at `abuse.py:4`. Called first at `pipeline.py:6`.
- **Today:**
  - A regex over a short insult list plus "scam" and "scammers" holds the ticket for review.
  - A hold skips refund, routing, priority and suggestions.
  - "My stupid printer" is held, and so is a customer reporting that scammers targeted them.
- **Jev decision:** Noul ×2
  - (a) "This ticket insults, threatens or harasses the support staff or people at the company." Yes means insults, slurs, threats or harassment aimed at people. Swearing about a product or a situation counts as no.
  - (b) "This ticket reports that the customer was targeted by, or fell for, a scam, phishing or fraud attempt." Yes means the customer describes being targeted or defrauded.
  - State: `ticket.body`
- **Confidence handling (starting point; tune on labeled data):**
  - A hold sends the ticket to a person, so it is reversible. Use the reversible Noul cutoffs on (a):
    - p ≥ 0.8: hold.
    - p ≤ 0.2: don't hold.
    - Between, or on error: today's `BANNED` regex, which stays in code as the fallback.
  - (b) is a veto on the fallback only: when (b) p ≥ 0.8, a regex match on "scam" or "scammers" alone doesn't hold the ticket.
  - A threat of violence should still reach a person. The hold already does that.
- **What Jev Sees:** personal. The ticket body, which for scam reports can include account details. Send-less tip: the same masked body, with digit runs (account, card, order numbers) masked.
- **Precedent:**
  - Jev sighting, [Jev Moderation Bot](https://github.com/brainstormity/Jev-Moderation-Bot): Choice and Noul at [\_\_init\_\_.py:260](https://github.com/brainstormity/Jev-Moderation-Bot/blob/325ea7f4ae889b666ca6133ddac0efcf2f1e7afc/typesafe/__init__.py#L260-L274), Python.
    - It asks whether each incoming message is legitimate, spam or a scam link, and whether it warrants a ban.
    - Repeated failures let messages through and post an outage alert.
    - It has tests.
    - Why it's similar: screening every incoming message with Noul policy questions, with a deliberate failure mode.
    - (verified 2026-10-12, not rechecked today)
  - Jev sighting, [Dub](https://github.com/dubinc/dub): a Noul check at [malicious-link-check.ts:25](https://github.com/dubinc/dub/blob/b003f93d488a36bd1f8ecf24689be9612545a084/apps/web/lib/api/links/malicious-link-check.ts#L25-L39), TypeScript.
    - It asks whether a submitted URL leads to phishing, malware or other abuse.
    - Over 0.5 the link counts as malicious; over 0.8 its domain is also blocklisted.
    - The sighting lists production evidence.
    - Why it's similar: a policy Noul on user input, with a stricter cutoff for the stronger action.
    - (verified 2026-10-12, not rechecked today)
- **Benefit:** customers who vent about a thing, or who report fraud, are no longer silently delayed. Abuse aimed at staff is still held.
- **Main risk:** a Jev "no" letting real abuse reach agents.
- **Poor fit if:** the hold queue is tiny and reviewers clear it fast. Then the regex's false holds cost little.
- **Why this rank:** every new ticket × a word list that can't tell venting or victims from abuse × a customer-facing delay on a held ticket. It ranks below 1-3 because "what counts as abuse" needs a written policy first.
- **Effort:** M

### 5. Auto-close on "thanks, solved" replies
- **Where:** `helpdesk/autoclose.py:7` (`should_close`), with the `THANKS_ONLY` regex at `autoclose.py:4`. Called from `pipeline.py:20`.
- **Today:**
  - A strict regex closes the ticket only when the whole reply is "thanks", "thank you", "thx", "ty" or "cheers".
  - "Thank you so much, all working now!" stays open. Closes are rare, and resolved tickets pile up.
- **Jev decision:** Noul: "This reply only thanks the agent or confirms the problem is solved, with no new question, problem or request."
  - Yes means a closing reply. Any follow-up, "but…", or new issue counts as no.
  - State: `reply` (the latest customer reply only)
- **Confidence handling (starting point; tune on labeled data):**
  - Closing a customer's ticket counts as costly, so this uses the costly Noul row:
    - Keep `THANKS_ONLY` as the exact first pass. A match closes as today, with no Jev call.
    - For other replies, close only when p ≥ 0.9 and a code check passes: the reply has no question mark.
    - Everything else, including errors, stays open, which is today's normal manual flow.
- **What Jev Sees:** personal. The reply text. Send-less tip: strip the quoted earlier thread and the signature, and send only the new text.
- **Precedent:**
  - Jev sighting, [jevgrep (allebee)](https://github.com/allebee/jevgrep): a Noul check at [judge.py:120](https://github.com/allebee/jevgrep/blob/5cebf4c046ac30704aba7a901e5f0c85b931e1d2/src/jevgrep/judge.py#L120-L122), Python.
    - For each input line it asks whether the line satisfies a plain-English yes/no question, in place of a regex.
    - A missing answer raises an error instead of defaulting.
    - It has tests and a benchmark.
    - Why it's similar: swapping a hand-written regex for a plain-English yes/no question.
    - (verified 2026-10-12, not rechecked today)
  - Jev sighting, [Reflex](https://github.com/kaustav1996/reflex): a Noul check at [index.ts:125](https://github.com/kaustav1996/reflex/blob/05f0f80254c0796cec928802222d57f2e2720e26/src/extensions/hooks/index.ts#L125-L132), TypeScript.
    - It decides whether a configured hook should fire for an event. It fires at its minimum (default 0.6), and on any error it doesn't fire.
    - Why it's similar: an action that happens only on a confident yes, with "do nothing" as the safe default.
    - (verified 2026-10-12, not rechecked today)
- **Benefit:** clearly resolved tickets close without an agent, and the open queue reflects real work.
- **Main risk:** closing a ticket where the customer added a small follow-up. The customer then has to reopen.
- **Poor fit if:** reply volume is low, or agents already close tickets as part of their normal flow. Then leave the regex as is.
- **Why this rank:** reply volume isn't visible × a regex that is safe but misses most real thank-yous × a customer-facing cost on a false close.
- **Effort:** S

### 6. Auto-refund gate
- **Where:** `helpdesk/refunds.py:6` (`auto_refund`), with the limit at `refunds.py:3`. Called at `pipeline.py:8` when an order exists.
- **Today:**
  - The ticket is refunded with no review when three things all hold:
    - the lowercased body contains "refund" or "money back";
    - it contains "charged twice" or "double charge";
    - the order amount is $50 or less.
  - "I don't want a refund, but I was charged twice" passes the text test.
  - Nothing checks that a duplicate charge actually exists, or that the order wasn't already refunded.
- **Jev decision:** Noul ×2
  - (a) "This ticket asks for money back for a charge." Yes means a current request for a refund or reversal. Negated or hypothetical mentions count as no.
  - (b) "This ticket says the customer was charged more than once for the same purchase." Yes means it describes a duplicate charge on one order.
  - State: `ticket.body`
- **Confidence handling (starting point; tune on labeled data):**
  - Money movement is irreversible, so this fails closed.
  - Auto-refund only when all of these hold:
    - (a) p ≥ 0.9 and (b) p ≥ 0.9;
    - `amount_usd ≤ 50` (code, unchanged);
    - a new code check against your payment records confirms two charges for the order and no earlier refund.
  - Everything else, including errors, gets no auto-refund. The ticket continues as open to the billing queue, which is the normal manual flow.
  - If you can't add the payment-record check, keep a person on every refund and use the two Nouls only to sort the billing queue.
- **What Jev Sees:** sensitive (payment context). Send only the masked body. The amount, order ID and payment records stay in code. Mask any card or account digits before sending.
- **Precedent:**
  - Jev sighting, [jev-auto-approve](https://github.com/BasmaAbouzied0/jev-auto-approve): a Noul check at [jev_auto_approve.py:63](https://github.com/BasmaAbouzied0/jev-auto-approve/blob/d8e636635d00dd7b201522a6b3fe0d36efca4982/jev_auto_approve.py#L63-L74), Python.
    - It judges whether a terminal command only inspects and changes nothing.
    - It approves at 0.95 or more. Any error, a missing key, or a hard-no pattern in code sends the command to the normal prompt.
    - This is a different domain, not refunds.
    - Why it's similar: an auto-approval that fails closed to the normal manual flow, with a code rule that can veto.
    - (verified 2026-10-12, not rechecked today)
- **Benefit:** stops refunds triggered by negated or offhand wording, and catches real duplicate-charge requests phrased without the exact words.
- **Main risk:** money paid out on a wrong yes. Treat the payment-record check as the real safeguard, not Jev.
- **Poor fit if:** the payment system can detect duplicate charges directly. Then refund on that signal and keep at most question (a).
- **Why this rank:** volume not visible × keyword matching that is unsafe for money × direct financial loss. It needs a policy agreed and new data plumbing, so it sits below the quick wins.
- **Effort:** M

### 7. Help-article suggestions
- **Where:** `helpdesk/kb.py:4` (`suggest_articles`); the sort is at `kb.py:10`
- **Today:**
  - The code scores each article by how many raw words the body shares with the article title, then returns the top 3.
  - It doesn't strip punctuation, so "password?" doesn't match "password".
  - Articles with no overlap are still suggested.
- **Jev decision:** Noul per candidate: "The help article titled `article.title` would help solve the problem in this ticket."
  - Yes means the article addresses the customer's issue.
  - State: `ticket.body`, `article.title`
- **Confidence handling (starting point; tune on labeled data):**
  - Code narrows candidates first: today's overlap with punctuation stripped, top ~10.
  - p ≥ 0.8: show, sorted by p.
  - p ≤ 0.2: drop.
  - Between: show after the confident ones, in today's overlap order.
  - If nothing qualifies, show no suggestions. On error: today's top 3.
- **What Jev Sees:** personal plus internal. The masked body and the article titles. Article bodies aren't needed.
- **Precedent:**
  - Jev sighting, [jev-reranker](https://github.com/hotchpotch/jev-reranker): a Noul check at [reranker.py:771](https://github.com/hotchpotch/jev-reranker/blob/d58594b393b29b7ee6398cc9337dc5e9d6c6691e/src/jev_reranker/reranker.py#L771-L785), Python. It is a library, not an app.
    - It judges how useful each retrieved document is for a query and orders by probability.
    - Documents under a cutoff are dropped, and an empty list tells the caller nothing qualified.
    - It has tests and CI.
    - Why it's similar: a Noul per candidate, with an honest empty result.
    - (verified 2026-10-12, not rechecked today)
- **Benefit:** agents stop seeing irrelevant suggestions.
- **Main risk:** paying per article for a low-stakes, agent-facing hint.
- **Poor fit if:** the article list is long, or a punctuation fix plus a minimum-overlap rule in code is good enough. Try that code fix first.
  - Fit warning: a report on the awesome-jev list found Jev reranking alone did not beat vector search. This is unverified, and it isn't linked because no awesome-jev category was fetched this run.
- **Why this rank:** every open ticket × weak word overlap × a low cost (a wrong hint the agent ignores), plus a reranking fit warning.
- **Effort:** M

## One request, several questions
- **Each new ticket:** ideas 1, 2, 3, 4 and 6, plus the "bank dispute" Power Jewel, read the same ticket body (idea 1 also reads the subject). They can go in one Jev request. Each answer is independent, so code can use or ignore each one, and code adds the refund questions only when an order exists.
  - **One request or two stages:** the abuse hold (`pipeline.py:6`) and the refund (`pipeline.py:8`) stop the pipeline early. The share of tickets that are held or refunded isn't visible.
    - One request for everything is simplest: one round trip per ticket, and the routing, priority and anger answers for held or refunded tickets are wasted.
    - Two stages ask the hold and refund questions first, and the rest only when the ticket stays open. That is better if holds and refunds turn out to be a large share.
    - Start with one request and measure.
- **Each customer reply:** idea 5 and the "churn risk" Power Jewel read the same reply and can share one request.
- Idea 7 asks one question per candidate article, after code narrows the list. Keep it as its own request.

## Power Jewels
New things Jev could add, using data the app already has.
- **Churn risk on customer replies:**
  - **Data:** every reply already passes through `handle_reply` (`helpdesk/pipeline.py:19`), but only the thank-you regex reads it.
  - **Question:** Noul "This reply says the customer plans to cancel, switch to a competitor, or close their account."
  - **What the app does:** at p ≥ 0.8 it flags the ticket for a senior agent or retention follow-up. The status doesn't change, so a wrong flag costs only attention.
  - **What Jev Sees:** personal (reply text, quoted thread and signature stripped).
  - **Precedent:**
    - Jev sighting, [jev-eval](https://github.com/Shogo-nfrealmusic/jev-eval): Choice, Score and Noul questions at [jev.ts:10](https://github.com/Shogo-nfrealmusic/jev-eval/blob/6963f03101c4c144cae170b9a23899a339a7c23e/src/jev.ts#L10-L23), TypeScript. It is a benchmark.
      - It asks a customer inquiry's category and urgency, plus a Noul on whether staff must handle it.
      - Why it's similar: only in shape, a Noul flag on a customer message that pulls in a person.
      - (verified 2026-10-12, not rechecked today)
- **Bank-dispute flag on new tickets:**
  - **Data:** the ticket body already read at `helpdesk/pipeline.py:6-15`.
  - **Question:** Noul "This ticket says the customer has disputed, or will dispute, the charge with their bank or card issuer."
  - **What the app does:** at p ≥ 0.8 it skips auto-refund, to avoid paying twice (refund plus chargeback), and raises the ticket to priority 2 in the billing queue. It fits in the same request as ideas 1-4 and 6.
  - **What Jev Sees:** personal (masked body).
  - **Precedent:** none found in Jev Sightings (bundled copy). The awesome-jev list couldn't be searched (no network access in this session).

## Not Jev's Job
- `helpdesk/refunds.py:3` and `:10` (`auto_refund`), the $50 cap: a hard money limit must stay exact and auditable. What would change my mind: nothing. Even a per-customer limit should be a lookup.
- `helpdesk/pipeline.py:8` (`handle_new_ticket`), `if order`: a presence check on a record. What would change my mind: nothing; it's exact.
- `helpdesk/pipeline.py:6-9` (`handle_new_ticket`), the gate order (hold, then refund, then open): control flow that should stay explicit and reviewable. What would change my mind: nothing. Jev's answers feed these gates; they don't reorder them.
- `helpdesk/router.py:19` (`route`), the fixed queue set and the `general` default: an enum and a fallback. What would change my mind: queues added often enough that code can't keep the list current.
- `helpdesk/kb.py:10` (`suggest_articles`), sort and top-k: mechanical once each article has a score. What would change my mind: nothing.

## Off the Map
- `.env`: a secret file, not opened.
- `helpdesk/settings.py:3`: a secret-looking value, not loaded. The rest of the file was read.
- The code that actually pays refunds, closes tickets, ingests email, and stores tickets, orders and articles is not in this folder. `auto_refund` and `should_close` only return a bool. To cover it next: `/jev-where <path to that service>`.
- Per-step volumes (holds, refunds, replies) aren't visible. The only figure is the README's "Roughly 4,000 tickets a day".

## Also noticed
- `helpdesk/settings.py:3`: a hardcoded secret-looking value (`SIGNING_SECRET`). I didn't read the value. Move it to the environment or a secret store, even if it is a placeholder.
- `helpdesk/sentiment.py:4`: the OpenAI client is created at import time, so importing the pipeline fails without API credentials in the environment.
- `helpdesk/sentiment.py:8-15`: an unguarded network call with no timeout, retry or try/except.
  - A failure crashes `handle_new_ticket` at `pipeline.py:14` after routing and priority have run.
  - An empty message content raises at line 15.
- `helpdesk/sentiment.py:12`: the raw customer body goes into the LLM prompt. A ticket can steer the YES/NO answer (prompt injection), and the full body leaves your system.
- `helpdesk/refunds.py:10`: an irreversible money action from keywords alone.
  - It has no negation handling and no duplicate-charge or repeat-refund check.
  - It raises a KeyError if `amount_usd` is missing.
- `helpdesk/abuse.py:4`: "scam" and "scammers" silently hold customers who are reporting fraud.
- `helpdesk/router.py:11` and `:25`: substring matching makes "down" fire on "download" or "downgrade". "can't work" misses a curly apostrophe.
- `helpdesk/kb.py:7-10`: punctuation isn't stripped, and articles with no overlap are still suggested. This is a code fix.
- `helpdesk/pipeline.py:6` and `helpdesk/router.py:15`: a KeyError if a ticket arrives without `body` or `subject`.

## Start here
Start with idea 1, ticket routing as a Choice. It runs on every open ticket, today's first-match keyword rules are the weakest part of the open-ticket path, a misroute is reversible, and the existing regexes stay as the fallback. True labels are easy to collect, because each time an agent moves a ticket to another queue that records the right team. Run it in shadow mode first: call Jev on each ticket but keep routing with the regex.

Evaluate it on a small labeled set of real inputs. Run the current approach and Jev side by side, then compare:
- overall accuracy;
- accuracy on the cases Jev would handle automatically;
- how often it falls back;
- the cost and latency you measure yourself.

Adding the priority Score and the anger Noul to the same request then costs little, so measure them in the same run.

Want me to draft a minimal starter integration for one of these ideas? Tell me which one. I'll read the current TypeSafe docs first (and tell you if I can't reach them), and show the code here without changing any files. I can also save this report as a Treasure Map (`jev-where-map.json`) so the next run can show what changed.
