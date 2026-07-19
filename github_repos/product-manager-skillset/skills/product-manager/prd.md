# PRD

See [prd-structure.md](./rules/prd-structure.md) for enforced structural rules with Incorrect/Correct pairs.

## Contents

- Canonical section order
- Field-by-field guidance
- Length targets
- Reviewer routing
- Statuses and lifecycle

---

## Canonical section order

Never reorder. Reviewers pattern-match on structure; reordering costs comprehension.

1. **TL;DR** — 3 sentences: what, for whom, expected outcome
2. **Problem** — user + job + pain, quantified
3. **Why now** — strategic fit + trigger
4. **Goals** — outcome-based, measurable, ≤ 3
5. **Non-goals** — explicit exclusions
6. **Target users & use cases** — primary + secondary persona, top 3 use cases
7. **Proposed solution** — experience, not implementation; happy path + edge cases
8. **Requirements** — user stories with Given/When/Then; NFRs at the bottom
9. **Success metrics** — primary + input + guardrail + diagnostics + instrumentation plan
10. **Rollout plan** — flag, stages, rollback criteria
11. **Open questions** — numbered, each with owner + needed-by date
12. **Assumptions** — with evidence link and risk-if-wrong rating
13. **Appendix** — discovery notes, teardowns, data cuts

## Field-by-field guidance

### TL;DR

Three sentences. What are we building, for whom, what outcome. If it takes more, the PRD isn't clear yet.

### Problem

Describes the **world without this feature**, not the feature itself. Must name:
- the user (persona or segment)
- the job they're trying to do
- what's broken today
- a quantification (interviews, tickets, funnel, revenue)

### Why now

Answers: which strategic bet does this ladder up to, and what changed that makes this quarter the right one? (New data, new segment, competitor move, platform change.)

### Goals

Outcome-based only. Format: `<metric> from <baseline> to <target> by <date>`. Cap at 3.

### Non-goals

The most-skipped section, and the highest-value one. Prevents scope creep in review. Format: bulleted list of what this PRD is **not** solving.

### Target users & use cases

- Primary persona: name + JTBD
- Secondary persona: name + JTBD (optional)
- Top 3 use cases: written as narratives, not features

### Proposed solution

Experience, not implementation. Wireframes/mocks linked. Happy path first, edge cases second.

**Edge cases to enumerate** (every PRD, every time):
- Empty state
- Loading state
- Error state (network / permission / validation)
- Zero-data (new user, no history)
- Max-data (10k+ items)
- Offline / degraded connectivity
- Accessibility (keyboard, screen reader)
- Internationalization

### Requirements

- Functional: user stories with `As a … I can … so that …` + Given/When/Then acceptance criteria
- Non-functional: performance, security, privacy, accessibility, compliance

### Success metrics

Follows `metrics.md` conventions. Must include: primary, input, guardrail(s), diagnostics, instrumentation plan (event names + owner).

### Rollout plan

Follows `launch.md`. Feature flag name, stage sequence with exit criteria per stage, rollback trigger as if-then rules.

### Open questions

Numbered. Each has an owner and a needed-by date. No unowned questions.

### Assumptions

Each has: statement, evidence (link or "unvalidated"), risk-if-wrong (low/med/high). Flag high-risk assumptions in the TL;DR.

## Length targets

| Audience         | Length         |
| ---------------- | -------------- |
| Small feature    | 1–2 pages      |
| Medium feature   | 3–5 pages      |
| Major initiative | 5–10 pages     |
| Anything longer  | Split the PRD  |

## Reviewer routing

| Reviewer     | Looks for                                                             |
| ------------ | --------------------------------------------------------------------- |
| Eng lead     | Requirements, NFRs, rollout, edge cases                               |
| Design lead  | Solution, use cases, edge states                                      |
| Data         | Metrics, instrumentation plan, baseline                               |
| Legal        | Privacy, terms changes, regional restrictions                         |
| Support / CS | Comms plan, FAQ, edge cases users will hit                            |

## Statuses and lifecycle

`Draft → In review → Approved → In build → Shipped → Archived`

- **Draft:** PM writing; not yet circulated
- **In review:** circulated for named reviewers, open questions have owners
- **Approved:** all open questions closed or explicitly deferred; eng starts
- **In build:** implementation in progress; changes go in an addendum, not the PRD body
- **Shipped:** post-launch; retro appended
- **Archived:** superseded or killed; keep for reference
