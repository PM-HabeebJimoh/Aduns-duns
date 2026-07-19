# OKRs

See [metrics.md](../metrics.md) for framework definitions and cadence.

## Contents

- KRs are outcomes, not outputs
- Numbers live in KRs, not the Objective
- Baseline + target + date on every KR
- ≤ 5 KRs per Objective
- Guardrails paired with target KRs
- One named owner per KR

---

## KRs are outcomes, not outputs

If a KR can be marked done by shipping something regardless of whether users behave differently, it's an output.

**Incorrect:**

```markdown
Objective: Make new teams successful in their first week.
- KR1: Launch v2 of onboarding by Aug 15.
- KR2: Ship 3 new email templates.
- KR3: Publish revised getting-started docs.
```

**Correct:**

```markdown
Objective: Make new teams successful in their first week.
- KR1: Week-1 activation rate for new signups from 34% → 50% by 2026-09-30
- KR2: % of new signups inviting a second user in 7d from 22% → 40% by 2026-09-30
- KR3: Median time to first "aha" event from 3h 40m → under 60 min by 2026-09-30
```

---

## Numbers live in KRs, not the Objective

The Objective is qualitative and inspirational. The KRs carry the numbers.

**Incorrect:**

```markdown
Objective: Get to 50% week-1 activation by Q3 end.
```

**Correct:**

```markdown
Objective: Make new teams successful in their first week.
- KR1: Week-1 activation from 34% → 50% by 2026-09-30
```

---

## Baseline + target + date on every KR

All three or it's not a KR.

**Incorrect:**

```markdown
- KR1: Improve activation.
- KR2: Reduce time-to-value.
- KR3: More teams should invite a second user.
```

**Correct:**

```markdown
- KR1: Week-1 activation from 34% → 50% by 2026-09-30
- KR2: Median time-to-first-aha from 3h 40m → under 60 min by 2026-09-30
- KR3: % of new signups inviting a second user in 7d from 22% → 40% by 2026-09-30
```

---

## ≤ 5 KRs per Objective

More = no priorities. If you can't cut, split the Objective.

**Incorrect:**

```markdown
Objective: Make new teams successful.
- KR1..KR9 (nine KRs across activation, retention, revenue, support, NPS)
```

**Correct:**

```markdown
Objective: Make new teams successful in their first week.
- KR1: Week-1 activation from 34% → 50% by 2026-09-30
- KR2: % of new signups inviting a second user in 7d from 22% → 40%
- KR3: Median time-to-first-aha from 3h 40m → under 60 min

Objective: Keep support cost per new team flat while activation grows.
- KR1: Support tickets per 100 new teams from 22 → ≤ 22 by 2026-09-30
- KR2: Median first-response time from 4h → 2h
```

---

## Guardrails paired with target KRs

Chasing a KR without a guardrail is how you accidentally break another team's KR.

**Incorrect:**

```markdown
- KR1: Signups from 8k/week → 20k/week by 2026-09-30
```

**Correct:**

```markdown
- KR1: Signups from 8k/week → 20k/week by 2026-09-30
- Guardrail: Week-4 retention for new signups must not drop below 26%
- Guardrail: Cost per acquired activated user must not exceed $18
```

---

## One named owner per KR

Team-owned = no-one owned.

**Incorrect:**

```markdown
- KR1: Week-1 activation from 34% → 50% (Owner: Growth team)
```

**Correct:**

```markdown
- KR1: Week-1 activation from 34% → 50% (Owner: H. Jimoh, PM)
- KR2: Median time-to-first-aha under 60 min (Owner: L. Adeyemi, Design)
- KR3: Second-user invite rate 22% → 40% (Owner: A. Okafor, Eng)
```
