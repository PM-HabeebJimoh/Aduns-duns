# Metrics Definition

See [metrics.md](../metrics.md) for framework selection and definitions.

## Contents

- Every target has a guardrail
- Numerator and denominator defined
- Population and time window explicit
- No vanity metrics as targets
- Deltas, not raw numbers
- Instrumented before shipped

---

## Every target has a guardrail

A metric moving in isolation is meaningless. Pair every target with what must not regress.

**Incorrect:**

```markdown
## Success metrics
- Increase activation rate by 20%.
```

**Correct:**

```markdown
## Success metrics
- **Primary:** Week-1 activation 34% → 50% by 2026-09-30
- **Guardrail:** Support tickets per 100 activated users must not increase
- **Guardrail:** p95 signup-to-activation latency must not exceed 2 min
```

---

## Numerator and denominator defined

Ratios without both sides are un-auditable.

**Incorrect:**

```markdown
- Activation rate
- Conversion
- Engagement
```

**Correct:**

```markdown
- **Activation rate** =
  (# new signups reaching first "aha" event within 24h of signup) /
  (# new signups in the same day, excluding internal accounts and bots)

- **Free-to-paid conversion** =
  (# free-tier users starting a paid plan within 30 days of signup) /
  (# free-tier signups 30+ days ago, excluding refunded)
```

---

## Population and time window explicit

"Users" and "recently" mean nothing.

**Incorrect:**

```markdown
- Weekly active users last week: 12,400
```

**Correct:**

```markdown
- **Weekly Active Users (WAU)** =
  distinct user_id with ≥ 1 session_start event
  in the last 7 rolling days, excluding internal accounts
  (email @company.com) and bots (UA in bot_list).
  - Last complete week (Mon–Sun): 12,400
```

---

## No vanity metrics as targets

Total signups, total pageviews, total downloads — allowed as diagnostics only, never as OKR key results.

**Incorrect:**

```markdown
KR1: 50,000 new signups this quarter.
KR2: 1M pageviews on the pricing page.
```

**Correct:**

```markdown
KR1: 15,000 activated new signups (reaching first "aha" event) this quarter.
KR2: Pricing-page → signup conversion 3.2% → 5.0% by end of quarter.
```

---

## Deltas, not raw numbers

A number without a comparison is noise.

**Incorrect:**

```markdown
- WAU: 12,400
- Activation: 38%
- Support tickets: 220
```

**Correct:**

```markdown
- WAU: 12,400 (Δ +4.2% WoW, Δ +18% vs. same week last quarter)
- Activation: 38% (Δ +2pp WoW, baseline 34%, target 50%)
- Support tickets: 220 (Δ −8% WoW, guardrail: not > 250/week)
```

---

## Instrumented before shipped

Without instrumentation before launch, the pre-launch baseline is unknowable and impact is uncontestable.

**Incorrect:**

```markdown
Ship the feature; add analytics in a follow-up if we have time.
```

**Correct:**

```markdown
Instrumentation plan (must land before flag enable):
- Event: `board_shared` — props: board_id, owner_id, collaborator_count
- Event: `invite_sent` — props: board_id, invitee_email_hash, permission
- Event: `invite_accepted` — props: invite_id, delta_hours_from_send
- Event: `collaborator_removed` — props: board_id, removed_by_id
- Baseline captured for 4 weeks before flag enable
- Dashboard live and reviewed with data before dogfood
- Owner: O. Bello (data)
```
