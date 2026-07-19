# Metrics Frameworks

Choose the framework that matches the decision. Then wire up the guardrails.

## Metric types

| Type | Purpose | Example |
|---|---|---|
| **North Star** | The one metric the team optimizes over quarters | Weekly active teams |
| **Input / leading** | Levers the team can move this quarter | Activation rate, invite-send rate |
| **Output / lagging** | Result of moving inputs | Retention, revenue |
| **Guardrail** | Must not regress while chasing target | Support ticket rate, p95 latency |
| **Diagnostic** | For debugging, not target-setting | Funnel step-by-step conversion |
| **Vanity** | Looks good, drives nothing | Total signups, total pageviews |

**Rule:** Every target metric ships with at least one guardrail.

---

## Framework: North Star Metric

One metric that captures the core value the product delivers. Properties:

1. **Reflects user value** — moves when users get value, not just when marketing spends
2. **Leading indicator of revenue** — precedes it by weeks/months
3. **Actionable** — the team can move it through product changes
4. **Measurable** — clear definition, no ambiguity

Examples:
- Airbnb: nights booked
- Slack: weekly active teams sending 2,000+ messages
- Spotify: time spent listening
- Stripe: total payment volume processed

**Failure mode:** picking a metric that moves with marketing spend (signups) instead of product value (activated users).

---

## Framework: AARRR (Pirate Metrics)

Funnel view for lifecycle products.

| Stage | Question | Example metric |
|---|---|---|
| **Acquisition** | Where do users come from? | Signups by channel, CAC |
| **Activation** | Did they get first value? | % reaching "aha" event in 24h |
| **Retention** | Do they come back? | Week-4 retention, DAU/MAU |
| **Referral** | Do they bring others? | K-factor, invites sent |
| **Revenue** | Do they pay? | ARPU, LTV, conversion to paid |

Use for full-funnel diagnosis. Don't set OKRs on all five — pick the weakest and focus.

---

## Framework: HEART (Google's UX metrics)

For UX quality, not funnel performance.

| Dimension | Question | Example metric |
|---|---|---|
| **Happiness** | Do users like it? | NPS, CSAT, survey score |
| **Engagement** | How intensely used? | Sessions/user, time in app |
| **Adoption** | Are new users trying it? | % of MAU using feature |
| **Retention** | Do they keep using it? | Feature retention curve |
| **Task success** | Can they complete goals? | Task completion rate, time-on-task |

Best paired with a Goals-Signals-Metrics table so every metric traces back to a user goal.

---

## Defining a metric — the checklist

Before shipping a metric to a dashboard, answer:

1. **Definition** — precise event/query. No "roughly speaking".
2. **Numerator & denominator** — for ratios, both must be defined.
3. **Time window** — daily, weekly, rolling 28-day?
4. **Population** — all users? Paid only? Excluding internal accounts and bots?
5. **Baseline** — current value with confidence interval.
6. **Target** — with a date and rationale for the number.
7. **Guardrail(s)** — what must not regress.
8. **Owner** — one name, not a team.

If any field is blank, the metric isn't ready.

---

## Anti-patterns

- **Averaging bimodal data** — average session length hides that half the users bounce. Use medians or distributions.
- **Chasing a metric that regresses another** — activation ↑ while retention ↓ = you're onboarding worse users faster.
- **Instrumenting after launch** — you'll never trust the pre-launch baseline. Instrument first.
- **Metric proliferation** — >7 top-line metrics = no priorities.
- **Simpson's paradox** — segment-level truth can invert at aggregate. Always cut by cohort.
