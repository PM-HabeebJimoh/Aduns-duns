# PRD Template

Canonical Product Requirements Document. Fill top-to-bottom; do not reorder — reviewers pattern-match on structure.

---

# [Feature name]

**Author:** [PM name]  •  **Status:** Draft | In review | Approved | Shipped  •  **Last updated:** YYYY-MM-DD
**Reviewers:** [Eng lead] [Design lead] [Data] [Legal/Compliance if applicable]
**Related:** [Link to strategy doc, discovery notes, competitive teardown]

## 1. TL;DR

Three sentences max. What are we building, for whom, and what outcome do we expect?

## 2. Problem

Who is the user? What are they trying to do? What's broken today? Quantify the pain if possible (support tickets, churn cohort, funnel drop-off).

**Not:** a description of the feature. **Yes:** a description of the world without this feature.

## 3. Why now

Strategic fit — which company/product bet does this ladder up to? What changed that makes this the right quarter to build it? (New data, new segment unlocked, competitive move, platform change.)

## 4. Goals

Outcome-based, measurable. 1–3 max.

- Increase [metric] from X to Y by [date]
- Reduce [metric] from X to Y by [date]

## 5. Non-goals

Explicit list of what this is **not** solving. Prevents scope creep in review.

- We are not addressing [adjacent problem].
- We are not changing [adjacent surface].

## 6. Target users & use cases

- **Primary persona:** [name, JTBD]
- **Secondary persona:** [name, JTBD]
- **Top 3 use cases** in narrative form (User → does → gets outcome).

## 7. Proposed solution

Describe the experience, not the implementation. Sketches / wireframes go here (link to Figma). Walk through the happy path first, then edge cases.

### Happy path

1. …
2. …
3. …

### Edge cases

- Empty state
- Error state (network, permission, validation)
- Loading state
- Zero-data state (new user, no history)
- Max-data state (10k+ items)
- Offline / degraded connectivity
- Accessibility (keyboard, screen reader)
- Internationalization

## 8. Requirements

Functional requirements as user stories with acceptance criteria (Given / When / Then).

- **[FR-1]** *As a [persona], I can [action] so that [outcome].*
  - Given [context], when [event], then [result].
- **[FR-2]** …

Non-functional requirements: performance, security, privacy, accessibility, compliance.

## 9. Success metrics

- **North Star / primary metric:** [definition, current baseline, target, measurement window]
- **Input / leading metric:** [what will move first]
- **Guardrail metric(s):** [must not regress]
- **Diagnostic metrics:** [for debugging, not target-setting]
- **Instrumentation plan:** event names, properties, owner

## 10. Rollout plan

- Feature flag: `[flag-name]`
- Stages: internal dogfood → closed beta (N users) → % rollout (5% → 25% → 50% → 100%)
- Exit criteria per stage
- Rollback trigger: if [metric] regresses by [%] or [error rate] > [threshold]

## 11. Open questions

Numbered list. Each has an owner and a needed-by date.

1. [Question] — owner: [name], needed by: [date]

## 12. Assumptions

Things we believe but have not validated. Flag which ones would kill the project if wrong.

- We assume [X] — evidence: [link or "unvalidated"] — risk if wrong: [low / med / high]

## 13. Appendix

- Discovery notes
- Competitive teardown
- Data cuts
- Prior versions of this doc
