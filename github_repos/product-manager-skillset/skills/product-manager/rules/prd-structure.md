# PRD Structure

See [prd.md](../prd.md) for the full canonical structure and field-by-field guidance.

## Contents

- Canonical section order
- Explicit Non-goals
- Acceptance criteria as Given/When/Then
- Edge states enumerated
- Open questions have owners and dates
- Assumptions rated for risk

---

## Canonical section order

Never reorder. Reviewers scan structure before content.

**Incorrect:**

```markdown
# Feature X

## Solution
[wireframes and description]

## Why we should build it
...

## Metrics
...

## Problem
...
```

**Correct:**

```markdown
# Feature X

## TL;DR
## Problem
## Why now
## Goals
## Non-goals
## Target users & use cases
## Proposed solution
## Requirements
## Success metrics
## Rollout plan
## Open questions
## Assumptions
## Appendix
```

---

## Explicit Non-goals

The most-skipped section, and the highest-leverage one. Absence causes scope creep in review.

**Incorrect:**

```markdown
## Goals
- Increase week-4 retention from 28% → 40%

## Target users & use cases
[skips straight to solution]
```

**Correct:**

```markdown
## Goals
- Increase week-4 retention from 28% → 40% by 2026-09-30

## Non-goals
- Not building granular per-column permissions (view/edit only)
- Not building comments or @-mentions (separate PRD, Q4)
- Not building SSO or SCIM (enterprise scope, not SMB)
- Not building change notifications (Q4 candidate)
```

---

## Acceptance criteria as Given/When/Then

Free-form prose is untestable. Given/When/Then is unambiguous for eng and QA.

**Incorrect:**

```markdown
- Users should be able to invite teammates and they should get an email.
- If the invite is old it shouldn't work anymore.
```

**Correct:**

```markdown
- **[FR-1]** *As a board owner, I can invite up to 10 collaborators by email.*
  - Given I am the owner of a board, when I open Share and submit valid
    emails, then each invitee receives an email within 60s.
  - Given an invite email older than 24h, when the invitee clicks the
    link, then they see "This invite has expired" and no board access
    is granted.
```

---

## Edge states enumerated

Every PRD lists all edge states. Missing edge states = design and QA fill them in silently, badly.

**Incorrect:**

```markdown
## Proposed solution
Click Share, type emails, click Send. Teammates get an email.
```

**Correct:**

```markdown
## Proposed solution
[Happy path]
1. Owner clicks Share on the board.
2. Types emails in a comma/newline-separated input, up to 10.
3. Clicks Send.

### Edge cases
- **Empty state:** no collaborators yet — modal shows "Only you".
- **Error:** invalid email — inline error per email, valid ones still send.
- **Loading:** send > 500ms — inline spinner, don't block modal.
- **Zero-data:** invitee lands on empty board — show onboarding tooltip.
- **Max-data:** 11th invite — error "Free plan supports up to 10".
- **Offline:** collaborator loses connection — banner + queue local edits.
- **A11y:** modal keyboard-navigable; cursors have text labels for SR.
- **i18n:** email subject/body localized to invitee's account language.
```

---

## Open questions have owners and dates

An unowned question is a hole in the plan.

**Incorrect:**

```markdown
## Open questions
- What happens on downgrade?
- Should we send a notification email?
- How do we count "team"?
```

**Correct:**

```markdown
## Open questions
1. Do we count a "team" as ≥ 2 collaborators or ≥ 2 active editors?
   — owner: O. Bello (data), needed by: 2026-08-01
2. Do we send an email to the owner when an invitee accepts?
   — owner: L. Adeyemi (design), needed by: 2026-08-04
3. What happens to shared boards on downgrade to a lower-cap tier?
   — owner: PM, needed by: 2026-08-08
```

---

## Assumptions rated for risk

Every assumption has evidence and a risk-if-wrong rating. High-risk assumptions get called out in the TL;DR.

**Incorrect:**

```markdown
## Assumptions
- Users want this.
- 10 collaborators is enough for free tier.
- Real-time will feel fast.
```

**Correct:**

```markdown
## Assumptions
- We assume SMB users prefer email invites over link-sharing —
  evidence: 8/12 interviews — risk if wrong: **low** (we support both).
- We assume 10 collaborators is enough for the free tier —
  evidence: median team size in signup survey = 4, p95 = 9 —
  risk if wrong: **low**.
- We assume sync latency < 300ms is the bar users expect —
  evidence: comparison to Notion/Figma — risk if wrong: **medium**
  (if latency slips, "collaboration" feels broken).
```
