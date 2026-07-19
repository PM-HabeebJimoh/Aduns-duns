# Problem Framing

See [discovery.md](../discovery.md) for the underlying discovery loop and interview technique.

## Contents

- Problem before solution
- User + job + pain
- Quantify the pain
- No solution language in Problem
- No feature-request as truth

---

## Problem before solution

Never draft a spec whose first section is a feature description. The Problem section describes the world without this feature.

**Incorrect:**

```markdown
## Problem
Add a shared boards feature so multiple people can edit the same board.
```

**Correct:**

```markdown
## Problem
Small-team users (2–10 people) sign up intending to collaborate, but today
the product is single-player. In 12 discovery interviews (Q2 2026), 9 users
mentioned "I ended up sharing screenshots" or "we went back to WhatsApp"
within their first two weeks.
```

---

## User + job + pain

Every problem statement names the user, the job they're trying to do, and the pain today. Missing any of the three = not a problem statement.

**Incorrect:**

```markdown
## Problem
Onboarding is confusing.
```

**Correct:**

```markdown
## Problem
New signups on the free tier (persona: Ope, ops lead at a 5-person agency)
trying to set up their first client board cannot find the "invite teammate"
action. 68% of week-1 support tickets in this segment are variants of
"how do I add someone to my board".
```

---

## Quantify the pain

Use ticket counts, funnel drop-off, interview counts, revenue at risk — not adjectives like "significant" or "major".

**Incorrect:**

```markdown
Users struggle significantly with the current flow.
```

**Correct:**

```markdown
34% of new signups drop off at step 3 of onboarding (baseline: 12% at
step 2). Median time-on-step 3 is 4m 12s vs. 22s at step 2. 11/12
interviewed users named step 3 as the point of confusion.
```

---

## No solution language in Problem

Words like "add", "build", "integrate", "redesign" belong in Requirements or Proposed Solution. Their presence in Problem means the writer skipped framing.

**Incorrect:**

```markdown
## Problem
We need to build a bulk-edit feature so users can update many tasks at once.
```

**Correct:**

```markdown
## Problem
Users managing weekly sprint boards (median: 40 tasks/week) currently
edit tasks one at a time. In 8 interviews, users described the end-of-sprint
cleanup as "the worst part of the week" and 5 of 8 said they skip it.
Board hygiene degrades: stale-task rate on boards > 4 weeks old is 47%
vs. 12% on boards < 2 weeks old.
```

---

## No feature-request as truth

Users are excellent at describing problems and unreliable at prescribing solutions. Record the request, but frame the problem behind it.

**Incorrect:**

```markdown
## Problem
Enterprise customer X asked for a Gantt view.
```

**Correct:**

```markdown
## Problem
Program managers (persona: Chidi, running 6+ concurrent projects) cannot
see cross-project timeline conflicts without exporting to a spreadsheet.
3 enterprise accounts (including X) named this as their #1 workflow gap
in Q2 QBRs; combined ARR at risk = $180k. Requested solution ("Gantt")
is one of several options — Proposed Solution below evaluates three.
```
