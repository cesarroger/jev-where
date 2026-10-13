# Example: `/jev-where` on the helpdesk fixture

A real run of JEV WHERE? v0.4 on [`evals/helpdesk-report/app`](../evals/helpdesk-report/app), a fake
support-ticket service built to test the plugin, on 2026-10-12. It used the Jev Sightings copy
bundled with the skill (the live copy wasn't reachable yet), rechecked each cited sighting on
GitHub, and fetched awesome-jev live for projects not read yet. Every cited sighting was checked
against `sightings.jsonl` and every live-list entry against the category files downloaded in that
run. Figures quoted from list entries are the entries' own claims, unverified.

---

**Scope:** I analyzed the helpdesk app in this folder: `README.md` and the 8 Python files under `helpdesk/`. I skipped `.env` (a secret file, not opened) and read `helpdesk/settings.py` by variable name only. The app does not call Jev today. Footprints: none (no rule was edited 2+ times or touched by fix commits).
**Precedents:** run date 2026-10-12. Jev Sightings: 75 verified (bundled copy, generated 2026-10-12; the live copy returned HTTP 404). I cited 9 sightings and rechecked all 9 live today. awesome-jev categories fetched: Classification & Routing (68 entries), Content Moderation (11), Verification & Guardrails (53), Scoring & Ranking (43). I skipped 2 listed projects that matched my searches because Jev Sightings found they don't call Jev. Sightings and awesome-jev listings are not endorsements.

Choice picks one option from a list. Score places something on ordered levels. Noul is the probability that a yes/no statement is true. A Jev sighting is a project where Jev was found in the code, linked to the exact lines.

| Rank | Idea | Shape | Effort | Value | Risk |
| --- | --- | --- | --- | --- | --- |
| 1 | Route each ticket to a team | Choice | S | High | Low |
| 2 | Set ticket priority | Score | S | High | Low |
| 3 | Flag angry customers for a senior agent | Noul | S | Medium | Low |
| 4 | Hold abusive tickets for review | Noul ×2 | M | Medium | Medium |
| 5 | Auto-close a ticket when the reply says it's solved | Noul | M | Medium | Medium |
| 6 | Auto-refund duplicate charges | Noul ×2 | M | Medium | High |
| 7 | Suggest help articles | Noul per article | M | Low | Low |

### 1. Route each ticket to a team
- **Where:** `helpdesk/router.py:14` (`route`), rules at `helpdesk/router.py:4-9`
- **Today:** The code joins subject and body, then tries four regexes in a fixed order: billing, technical, account, sales. The first match wins, and no match means `general`. Because order decides, "payment page shows error 500" goes to billing, not technical. The word "card" in any sense also sends a ticket to billing.
- **Jev decision:** Choice: "Which team should handle the request in this ticket?"
  - `billing`: charges, invoices, refunds, payment methods
  - `technical`: errors, bugs, crashes, API or integration problems
  - `account`: login, password, 2FA, locked accounts, username changes
  - `sales`: pricing, quotes, upgrades, enterprise plans, discounts
  - `general` (no match): none of these, or no clear owner
  - State: `ticket.subject`, `ticket.body`
- **Confidence handling (starting point; tune on labeled data):** Routing is reversible.
  - Confidence ≥ 0.8: use Jev's queue.
  - 0.5 to 0.8: use it, and tag the ticket for a quick triage check.
  - Below 0.5, or on any error or timeout: use today's `route()` regexes.
- **What Jev Sees:** personal (customer email text). Send the subject and body only. First strip signatures, quoted earlier emails, email addresses and phone numbers, and mask long digit runs such as card numbers.
- **Precedent:**
  - Jev sighting, [Jevidence](https://github.com/peakevergreen/jevidence): a Choice (asked with a Noul and a Score) at [runner.py:55](https://github.com/peakevergreen/jevidence/blob/6450a7820fec9dc9210dbea7982b6ae330d427e7/jevidence/runner.py#L55-L62), Python, a demo with tests. It sends a bug report to an investigation area, and a provider error keeps the current queue. Why it's similar: same queue Choice, and its error fallback matches the one above. (verified 2026-10-12, live today)
  - Jev sighting, [typeful-triage](https://github.com/cephalization/jev-triage): a Choice and Score at [typesafe.ts:14](https://github.com/cephalization/jev-triage/blob/adb509425d3f3d75c4053184501505c3a810509a/apps/api/src/worker/typesafe.ts#L14-L25), TypeScript. It asks category and severity for GitHub issues in one batched call and retries once on transient failures. Why it's similar: the same pairing as ideas 1 and 2. (verified 2026-10-12, live today)
- **Benefit:** Fewer misrouted tickets where keywords from two teams collide, plus a confidence value to send uncertain ones for a check.
- **Main risk:** A confident wrong queue on unusual wording. The 0.5 to 0.8 band and the regex fallback limit this.
- **Poor fit if:** tickets start arriving with a reliable category field (a form dropdown). Then route on the field.
- **Why this rank:** Nearly every one of about 4,000 tickets a day (README.md:6) × a first-match regex with known collisions × a misroute costs re-triage and delay but is easy to undo. No Footprints.
- **Effort:** S

### 2. Set ticket priority
- **Where:** `helpdesk/router.py:22` (`priority`), word list at `helpdesk/router.py:11`, branch at `helpdesk/router.py:26`
- **Today:** The code counts substrings of the body only: "urgent", "asap", "immediately", "down", "outage", "can't work". Two or more hits, or "!!!", gives 2; one hit gives 1; none gives 0. "down" matches "download" and "downgrade". "cannot work" and a curly apostrophe are missed. The subject is ignored.
- **Jev decision:** Score: "How urgent is the problem in this ticket?"
  - `0`: a routine question or request, with no deadline or impact mentioned (also covers "nothing urgent applies")
  - `1`: a problem that slows the customer down but has a workaround, or a deadline in the next few days
  - `2`: the customer cannot work right now, a service is down, or many users or payments are affected
  - State: `ticket.subject`, `ticket.body`
- **Confidence handling (starting point; tune on labeled data):** Priority is reversible.
  - Round the position to the nearest level. Confidence ≥ 0.8: use it. 0.5 to 0.8: use it and tag for a check.
  - Below 0.5, or on error: today's keyword `priority()`.
  - The 0/1/2 scale itself stays in code (`router.py:23-30`). Keep the unrounded position to sort tickets within a level.
- **What Jev Sees:** personal. The same trimmed subject and body as idea 1, in the same request.
- **Precedent:**
  - Jev sighting, [jev-oncall](https://github.com/mingleiw/jev-oncall): a severity question at [triage.py:455](https://github.com/mingleiw/jev-oncall/blob/e6b02aed03976f71b6ef4fe67f3d71247ca512c8/triage.py#L455-L469), Python. It judges how severe and actionable each production alert is. A Jev error makes the alert fall back to its configured severity. Why it's similar: an urgency judgment with the old rule as the fallback. (verified 2026-10-12, live today)
  - Jev sighting, typeful-triage (see idea 1): it asks severity as a Score in the same request as category.
- **Benefit:** Real outages stop landing at low priority because of missing keywords, and "download" stops counting as "down".
- **Main risk:** Customers who overstate urgency. The levels describe impact, not tone, to limit this.
- **Poor fit if:** priority should come from contract or SLA tiers that code can look up. Then use those tiers and let Jev only break ties.
- **Why this rank:** The same volume as idea 1 × a very weak substring rule × a buried outage is costly, but a wrong level is easy to fix. No Footprints.
- **Effort:** S

### 3. Flag angry customers for a senior agent
- **Where:** `helpdesk/sentiment.py:7` (`is_angry`), LLM call at `helpdesk/sentiment.py:8-15`, used at `helpdesk/pipeline.py:14`
- **Today:** A `gpt-4o-mini` call is told "Answer only YES or NO" about "Is this customer angry?" with the raw body. A reply starting with "YES" sets `senior`. There is no error handling, so a failed call breaks the whole new-ticket request.
- **Jev decision:** Noul: "The customer who wrote this ticket is angry with the company or its service."
  - Yes means: a hostile or exasperated tone, complaints about repeated failures or being ignored, or threats to cancel or complain publicly. A calm or polite report counts as no, even when it is urgent.
  - State: `ticket.body`
- **Confidence handling (starting point; tune on labeled data):** The senior flag is reversible.
  - p ≥ 0.8: `senior = True`. p ≤ 0.2: `senior = False`.
  - In between, or on error: today's LLM call. Wrap that call in a try/except with a timeout so its own failure gives `senior = False`. The ticket is still routed and prioritized, so nothing is lost.
- **What Jev Sees:** personal. The body only, with signatures and contact details stripped. Today the full body already goes to a third-party LLM.
- **Precedent:**
  - Jev sighting, [jevcal](https://github.com/abhixhek/jevcal): Choice, Noul and Score questions at [typesafe.py:45](https://github.com/abhixhek/jevcal/blob/ae8f3144d69c9cb0e5e0a2c17f70b9d14714cb9f/src/jevcal/providers/typesafe.py#L45-L59), Python. It asks typed questions per row, such as a support ticket's department, urgency or frustration, and trusts an answer only above a locked per-question cutoff, else leaves it for fallback. Why it's similar: a frustration Noul with the same fallback design, and a tool for picking these cutoffs. (verified 2026-10-12, live today)
  - Jev sighting, [jev-ood-calibration](https://github.com/scienthoon/jev-ood-calibration): Choice, Score and Noul at [jev_eval.mjs:77](https://github.com/scienthoon/jev-ood-calibration/blob/48572305b384b53072bfc869de4420c5d9a6acf1/scripts/jev_eval.mjs#L77-L91), JavaScript, a benchmark. It asks a synthetic ticket's queue, its priority, and whether the customer sounds angry, and stores the probabilities to study calibration (no cutoff). Why it's similar: the same three questions as ideas 1 to 3. (verified 2026-10-12, live today)
- **Benefit:** A probability instead of a parsed "YES" string, so the senior threshold can be tuned. It also removes free-text reply parsing. Adding the missing error handling here closes a crash path.
- **Main risk:** Sarcasm or very polite anger read wrongly. The middle band hands those to today's LLM.
- **Poor fit if:** the senior team wants a written reason for each flag. Jev returns probabilities, not explanations.
- **Why this rank:** One LLM call on nearly every ticket × the current judgment is probably fair but unguarded and unscored × a wrong flag only shifts who handles a ticket. Ranked below 1 and 2 because today's approach is weaker there. No Footprints.
- **Effort:** S

### 4. Hold abusive tickets for review
- **Where:** `helpdesk/abuse.py:7` (`should_hold`), regex at `helpdesk/abuse.py:4`, used at `helpdesk/pipeline.py:6-7`
- **Today:** One word-boundary regex (`idiot`, `stupid`, `moron`, `scam`/`scammers`, a starred profanity). Any match holds the ticket and skips everything else. "I think this is a scam charge" holds a customer reporting fraud. Disguised spellings slip through.
- **Jev decision:** Noul ×2. Any one triggers a hold.
  - Noul: "The ticket insults or uses abusive language aimed at the support staff." Yes means: name-calling, slurs, or profanity aimed at people, including disguised spellings. Frustration with the product, or the word "scam" used to report fraud, counts as no.
  - Noul: "The ticket threatens violence or harm to a person." Yes means: any threat to hurt staff or others.
  - State: `ticket.body`
- **Confidence handling (starting point; tune on labeled data):** These are the reversible-Noul cutoffs, because a hold goes to a person, not to the customer.
  - Hold if either p ≥ 0.8. No hold if both are ≤ 0.2.
  - In between, or on error: today's regex. Drop `scam(mers)?` from that regex, since it holds fraud reports (see Power Jewels).
  - A short regex of unmistakable slurs can stay as a fast first pass in front of Jev.
- **What Jev Sees:** personal. The body only, with signatures and contact details stripped.
- **Precedent:**
  - Jev sighting, [Jev Moderation Bot](https://github.com/brainstormity/Jev-Moderation-Bot): a Choice and Noul at [\_\_init\_\_.py:260](https://github.com/brainstormity/Jev-Moderation-Bot/blob/325ea7f4ae889b666ca6133ddac0efcf2f1e7afc/typesafe/__init__.py#L260-L274), Python, with tests. It decides whether a Discord message is legitimate, spam or a scam link, and whether it warrants a ban. After repeated failures it lets messages through and posts an outage alert. Why it's similar: moderation Nouls in front of a hold or ban action. (verified 2026-10-12, live today)
  - [mastra-jev-moderation](https://github.com/CodeAlive-AI/mastra-jev-moderation) (Content Moderation, listed on awesome-jev, not yet verified): asks a yes/no "must this message be blocked?" plus a category Choice in one request, behind a deadline and circuit breaker. Its entry reports production use; its figures are unverified.
- **Benefit:** Fraud reporters and frustrated customers stop being held, and disguised insults get caught.
- **Main risk:** Under-holding real abuse, so agents see it. The middle band falls back to the regex.
- **Poor fit if:** holds turn into automatic bans or legal reports. Keep a person in that loop.
- **Why this rank:** Runs on every ticket × a crude regex with a known false-positive word × a wrong hold delays a real customer. M effort, because the abuse policy needs agreeing first. No Footprints.
- **Effort:** M

### 5. Auto-close a ticket when the reply says it's solved
- **Where:** `helpdesk/autoclose.py:7` (`should_close`), regex at `helpdesk/autoclose.py:4`, used at `helpdesk/pipeline.py:20-21`
- **Today:** The ticket closes only when the whole reply is a bare thank-you ("thanks", "thx", "cheers"…). "Thanks, that fixed it" stays open. A bare "Thanks." closes even when it's sarcastic. Quoted email history in the reply blocks the match.
- **Jev decision:** Noul: "The customer's reply says their problem is solved and they need nothing more."
  - Yes means: thanks along with confirmation that it works ("all sorted", "that fixed it, you can close this"). A new question, "thanks, but it's still broken", sarcasm, or thanks for an update while still waiting counts as no.
  - State: `reply` (the latest reply text only)
- **Confidence handling (starting point; tune on labeled data):** Closing a customer's ticket counts as costly.
  - Close only at p ≥ 0.9. Everything else stays open, which is today's default. Errors also leave it open.
  - No code check is visible in this app to add on top.
  - `THANKS_ONLY` can stay as today's fast path for bare thank-yous. Send those through Jev too if your data shows sarcastic "Thanks." closes.
- **What Jev Sees:** personal. The reply text only, with quoted history and signature stripped (this also fixes the regex's quoted-history miss).
- **Precedent:** Jev sighting, [jevgrep (allebee)](https://github.com/allebee/jevgrep): a Noul at [judge.py:120](https://github.com/allebee/jevgrep/blob/5cebf4c046ac30704aba7a901e5f0c85b931e1d2/src/jevgrep/judge.py#L120-L122), Python, with tests and a benchmark. It answers whether each line satisfies a plain-English yes/no question, instead of a regex, and a missing answer raises rather than defaulting. Why it's similar: it replaces a regex with one yes/no statement over short text. (verified 2026-10-12, live today)
- **Benefit:** More solved tickets close without an agent touching them.
- **Main risk:** Closing a ticket that isn't solved, which the customer sees. The high cutoff and stay-open default limit this.
- **Poor fit if:** reply volume is small. The current conservative regex may be good enough.
- **Why this rank:** Reply volume is not visible × today's rule is safe but misses common "it's fixed" replies × a wrong close reaches the customer. M effort, because it acts on customers directly. No Footprints.
- **Effort:** M

### 6. Auto-refund duplicate charges
- **Where:** `helpdesk/refunds.py:6` (`auto_refund`), keyword checks at `helpdesk/refunds.py:8-9`, used at `helpdesk/pipeline.py:8-9`
- **Today:** The code refunds when the body contains "refund" or "money back", AND contains "charged twice" or "double charge", AND the order is at most $50. Negation is ignored ("I don't want a refund" still counts). "Billed twice" and "duplicate charge" are missed. No payment record is checked, and no person reviews the refund.
- **Jev decision:** Noul ×2. All must pass, along with the code checks.
  - Noul: "The customer asks for their money back." Yes means: an explicit request for a refund, reversal, or credit of a charge. Refund-policy questions, or "I don't want a refund", count as no.
  - Noul: "The customer says they were charged more than once for the same purchase." Yes means: a double, duplicate, or repeated charge for one order, in any wording. Two separate purchases, or one disputed charge, count as no.
  - State: `ticket.body`
- **Confidence handling (starting point; tune on labeled data):** This moves money, so it fails closed.
  - Auto-refund only when both Nouls are p ≥ 0.9, AND `order["amount_usd"] <= AUTO_REFUND_LIMIT_USD` (kept in code, `refunds.py:10`).
  - Also require payment records to show two charges for the order. That check is code, not Jev, and doesn't exist today.
  - Everything else, including errors: no auto-refund. The ticket continues through the normal flow to a person in the billing queue.
- **What Jev Sees:** personal, sensitive if customers paste card details. Send the body only, with card-like numbers masked. The order amount and payment records stay in your code.
- **Precedent:** Jev sighting, [jev-auto-approve](https://github.com/BasmaAbouzied0/jev-auto-approve): a Noul at [jev_auto_approve.py:63](https://github.com/BasmaAbouzied0/jev-auto-approve/blob/d8e636635d00dd7b201522a6b3fe0d36efca4982/jev_auto_approve.py#L63-L74), Python. It auto-approves only at 0.95 or more. Any error, missing key, or hard-no rule falls back to the normal human prompt. Why it's similar: an automatic action only at high probability, with code rules and a person as the default. (verified 2026-10-12, live today)
- **Benefit:** Catches negation and varied wording before money moves.
- **Main risk:** A wrong refund of up to $50. Most of this risk comes from never checking payment records, which Jev can't fix.
- **Poor fit if:** payment records can confirm duplicates directly. Then the "charged twice" Noul matters little, and code plus the "asks for money back" Noul decide.
- **Why this rank:** Only tickets with an order (volume not visible) × weak substring logic × money leaves with no review. High stakes keep it below the reversible ideas. M effort; L if payment records aren't reachable yet. No Footprints.
- **Effort:** M

### 7. Suggest help articles
- **Where:** `helpdesk/kb.py:4` (`suggest_articles`), ranking at `helpdesk/kb.py:7-10`
- **Today:** Each article scores by the word overlap between the body and the article title, with no stopword removal, so "the", "my" and "to" count. The top 3 are returned even when nothing matches.
- **Jev decision:** Noul per shortlisted article: "This article would help resolve the problem in the ticket."
  - Yes means: the article covers the customer's specific problem or question. When nothing fits, every probability stays low.
  - State: `ticket.body` (or subject plus first paragraph), `article.title` for each shortlisted candidate
- **Confidence handling (starting point; tune on labeled data):** Suggestions are advisory and reversible.
  - Code shortlists about 10 candidates with today's overlap (stopwords removed).
  - Show articles at p ≥ 0.8, sorted by p, up to 3. If none clear 0.8, or on error, show today's overlap list.
  - The sort and top-k slice stay in code.
- **What Jev Sees:** personal (ticket text) plus public (article titles). Send a trimmed excerpt and the shortlisted titles only.
- **Precedent:**
  - Jev sighting, [jev-reranker](https://github.com/hotchpotch/jev-reranker): a Noul at [reranker.py:771](https://github.com/hotchpotch/jev-reranker/blob/d58594b393b29b7ee6398cc9337dc5e9d6c6691e/src/jev_reranker/reranker.py#L771-L785), Python, a library with tests. It judges how useful each retrieved document is, sorts by probability, and drops those under a cutoff, so an empty list means nothing qualified. Why it's similar: a relevance Noul with a cutoff that can return nothing. (verified 2026-10-12, live today)
  - [jevsearch](https://github.com/kylemclaren/jevsearch) (Scoring & Ranking, listed on awesome-jev, not yet verified): docs-site search that sends keyword hits to Jev with a Noul per page, plus a Noul on whether any page answers at all. Its entry cites its own benchmark (unverified).
- **Benefit:** Agents stop seeing articles that match only on filler words.
- **Main risk:** Extra cost per ticket for a low-stakes, advisory feature.
- **Poor fit if:**
  - Better plain retrieval would be enough. Removing stopwords, or using embeddings, may close most of the gap. Measure that first.
  - Fit warning: a report on the awesome-jev list found Jev reranking alone did not beat vector search. It is not in the categories fetched this run, so it is unlinked and unverified.
- **Why this rank:** High volume × a very weak overlap score × mistakes are cheap, since agents can ignore suggestions. M effort for the shortlist step. No Footprints.
- **Effort:** M

## One request, several questions
- **Each new ticket:** ideas 1, 2, 3, 4 and 6 (refund Nouls only when an order is attached), plus Power Jewels 1 and 3, can go in one Jev request. Each answer is independent, so code can use or ignore each one.
  - Holds and auto-refunds stop the pipeline early (`pipeline.py:6-9`), so the routing, priority and anger answers on those tickets go unused.
  - One request is still better here. It is simplest, and if a reviewer releases a held ticket, its queue and priority answers are already there.
  - Switch to two stages (abuse and refund Nouls first, triage only when they pass) if your data shows holds and refunds are a large share of tickets.
- **Idea 7** is a second request after the article shortlist, only for open tickets.
- **Each customer reply:** idea 5 and Power Jewel 2 can go in one request.

## Power Jewels
New things Jev could add, using data the app already has.
- **Churn-risk tag:**
  - Data: `ticket["body"]`, passed in at `helpdesk/pipeline.py:5`.
  - Noul: "The customer says they plan to cancel, not renew, or move to another provider."
  - Use: at p ≥ 0.8, add a `churn_risk` flag beside `senior` so retention or the account owner sees it. Otherwise do nothing.
  - What Jev Sees: personal; the same trimmed body as idea 1.
  - Precedent: none found.
- **"Still broken" reply signal:**
  - Data: `reply` at `helpdesk/pipeline.py:19`. Today it is only checked for a bare thank-you, and every other reply just returns `open`.
  - Noul: "The customer's reply says the problem is still happening or has come back."
  - Use: at p ≥ 0.8, raise the ticket's priority or notify the assigned agent.
  - What Jev Sees: personal; the reply text only.
  - Precedent: none found.
- **Fraud-report fast lane:**
  - Data: `ticket["body"]`. Today `scam(mers)?` at `helpdesk/abuse.py:4` holds these tickets.
  - Noul: "The customer reports a charge they did not make, or a scam using the company's name."
  - Use: at p ≥ 0.8, set queue `billing` and priority 2. The hold check still runs on its own Nouls.
  - What Jev Sees: personal, sensitive if card details are pasted; mask card-like numbers.
  - Precedent: none found.

## Not Jev's Job
- `helpdesk/pipeline.py:8` (`handle_new_ticket`): `if order` is a plain None check on whether an order is attached. What would change my mind: tickets arriving without a linked order, so the order has to be picked from numbers in the email. Then use a Choice over the candidate order IDs that code extracts.
- `helpdesk/pipeline.py:6-9` (`handle_new_ticket`): the gate order (hold first, refund second, early returns) is control flow. Jev's answers feed it; they don't replace it. What would change my mind: nothing likely; this stays code.

## Off the Map
- `.env` (app root): a secret file, skipped without opening. It holds no decisions to scan.
- `helpdesk/settings.py`: read by variable name only, with the value masked. It holds two constants and no decisions.
- Code outside this folder: the email intake that builds tickets, the review queue behind `held_for_review`, the code that actually issues refunds, and whatever stores tickets and replies. To cover it next: `/jev-where <path to that code>`.

## Also noticed
- `helpdesk/settings.py:3`: `SIGNING_SECRET` is assigned a hardcoded literal (value not shown). The file's docstring calls it a fake fixture value. Still, load it from the environment or a secret store, since it is never referenced elsewhere.
- `helpdesk/sentiment.py:8-15`: an unguarded OpenAI call, with no try/except, timeout or retry, and none at `pipeline.py:14` either. An API error or empty content fails the whole new-ticket request, so the ticket gets no queue or priority.
- `helpdesk/sentiment.py:4`: the OpenAI client is built at import time, so importing `pipeline` fails when the key isn't set.
- `helpdesk/sentiment.py:12`: the raw customer body is put into the prompt. A customer can write text that steers the YES/NO answer.
- `helpdesk/sentiment.py:12`: full ticket bodies, which are personal data, go to a third-party LLM.
- `helpdesk/refunds.py:6-10`: money moves on keyword text alone, with no payment-record check and no human review.

## Start here
Start with idea 1 (team routing), and ask idea 2's priority Score in the same request. Both run on nearly every ticket, both replace weak keyword rules, a wrong answer is easy to undo, and today's regexes are a ready fallback. Evaluate it on a small labeled set of real inputs: run the current approach and Jev side by side, then compare accuracy, accuracy on the cases Jev would handle automatically, how often it falls back, and the cost and latency you measure yourself.

Want me to draft a minimal starter integration for one of these ideas? Tell me which one. I'll read the current TypeSafe docs first (and tell you if I can't reach them), and show the code here without changing any files. I can also save this report as a Treasure Map (`jev-where-map.json`) so the next run can show what changed.
