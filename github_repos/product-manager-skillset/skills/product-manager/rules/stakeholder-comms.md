# Stakeholder Communication

## Contents

- Headline first
- Numbers with deltas
- Blockers name people and dates
- Match format to audience
- Lead with the ask on escalation
- Feature → benefit in release notes

---

## Headline first

Decisions get made in the first 30 seconds of a doc. Front-load the state, not the background.

**Incorrect:**

```markdown
### Team update — week of Jul 14

Over the last few weeks we've been working on several things across the
board. There's been a lot of good progress and also some blockers. Below
is a summary. First, some context on what shipped last quarter…
```

**Correct:**

```markdown
### Team update — week of Jul 14

**Headline:** Shared Boards beta opens Monday with 50 SMB accounts.
On track for 25% rollout Aug 25.

**Shipped**
- …
```

---

## Numbers with deltas

A metric without a comparison is noise.

**Incorrect:**

```markdown
**Metrics**
- WAU: 12,400
- Activation: 38%
- Tickets: 220
```

**Correct:**

```markdown
**Metrics**
- WAU: 12,400 (Δ +4.2% WoW; baseline 11,900)
- Activation: 38% (Δ +2pp WoW; target 50% by Sep 30)
- Tickets: 220 (Δ −8% WoW; guardrail ≤ 250/week)
```

---

## Blockers name people and dates

"Waiting on X" is not a blocker. A blocker names the person, the ask, and the deadline.

**Incorrect:**

```markdown
**Blocked**
- Waiting on legal review
- Design bandwidth
- Need clarity from sales
```

**Correct:**

```markdown
**Blocked / need help**
- Legal review of invite email copy — need sign-off by **Fri Jul 18**
  or beta slips one week. Ping: **@bola-legal** (2nd follow-up).
- Design bandwidth for "invitee-not-signed-up" state — need **4h of
  L. Adeyemi's time** this week. Requesting via **@leke-adeyemi**.
- Enterprise-tier pricing for shared boards — need decision from
  **T. Adigun (sales)** by **Wed Jul 23** or GA launch slips.
```

---

## Match format to audience

One format doesn't serve every audience.

**Incorrect:**

```markdown
[Same 12-page PRD sent to eng, sales, exec team, and customer support.]
```

**Correct:**

```markdown
Eng team:   PRD + Given/When/Then acceptance criteria + edge cases
Design:     PRD Solution section + use cases + edge states
Data:       PRD Metrics section + instrumentation plan
Sales/CS:   Change brief (1 page) + FAQ + suggested talking script
Exec:       One-pager: situation → decision needed → recommendation → risks
Users:      Release notes: benefit-led, feature-by-feature
```

---

## Lead with the ask on escalation

Escalations get read for the ask, not the story. Ask first, context second.

**Incorrect:**

```markdown
Hi,

I wanted to loop you in on a situation we've been dealing with. Over the
past few weeks the team has been working on X, and we've hit some
interesting challenges. There's a lot to unpack here so I'll try to walk
through the background…
```

**Correct:**

```markdown
Hi K.,

**Ask:** Approve pushing the Shared Boards GA date from Aug 25 → Sep 8.
**Deadline:** Need decision by Fri Jul 25; sales collateral goes to
print Monday.

**Why:** Legal review of the invite email copy is 2 weeks behind
schedule; without approved copy we can't run the closed beta, and
without beta data we shouldn't rollout to 25%+.

**What I've tried:** 3 follow-ups with legal, escalation to their
manager Wed, offered to draft alternate copy myself.

**Alternative if not approved:** Launch on Aug 25 with a placeholder
non-transactional invite email; accept the risk of ~10pp lower
invite-accept rate for the first 2 weeks.

Free 3–4pm today or 10–11am tomorrow to talk.
```

---

## Feature → benefit in release notes

Release notes are read to answer "what changed for me". Lead with the benefit.

**Incorrect:**

```markdown
### v2.14 release notes

- Rewrote the search backend using OpenSearch 2.11 with new relevance
  scoring based on BM25+ and vector embeddings from the fine-tuned
  MiniLM-L6-v2 model.
- Migrated the invite service from synchronous SMTP to async queue
  backed by SQS with 3 retries and DLQ.
- Refactored the board-load path to use React Server Components.
```

**Correct:**

```markdown
### v2.14 — Jul 19, 2026

**Improved**
- **Search is now ~5× faster** and finds tasks by intent, not just
  keywords. Search "overdue payment" finds tasks about invoices even
  if the word "payment" isn't in the title.
- **Invites arrive within 60s**, down from ~5 min at peak. Failed
  invites now auto-retry instead of vanishing.
- **Boards load ~40% faster** on first open, especially for boards
  with 500+ tasks.

**Fixed**
- Dark mode toggle no longer flashes light theme on page load.
```
