# Metrics & OKRs

See [metrics-definition.md](./rules/metrics-definition.md) and [okrs.md](./rules/okrs.md) for enforced rules with Incorrect/Correct pairs.

## Contents

- Metric types
- North Star
- AARRR (Pirate Metrics)
- HEART
- OKR shape
- Writing a good Objective
- Writing a good Key Result
- Grading and cadence
- Experimentation

---

## Metric types

| Type              | Purpose                                             | Example                                    |
| ----------------- | --------------------------------------------------- | ------------------------------------------ |
| **North Star**    | The one metric the team optimizes over quarters    | Weekly active teams                        |
| **Input**         | Levers the team can move this quarter              | Activation rate, invite-send rate          |
| **Output**        | Result of moving inputs                            | Retention, revenue                         |
| **Guardrail**     | Must not regress while chasing target              | Support ticket rate, p95 latency           |
| **Diagnostic**    | For debugging, not target-setting                  | Funnel step-by-step conversion             |
| **Vanity**        | Looks good, drives nothing                         | Total signups, total pageviews             |

Every target metric ships with at least one guardrail. This is a hard rule; see `rules/metrics-definition.md`.

---

## North Star

One metric that captures the core value the product delivers. Properties:

1. Reflects user value — moves when users get value, not when marketing spends
2. Leading indicator of revenue — precedes it by weeks/months
3. Actionable — the team can move it through product changes
4. Measurable — clear definition, no ambiguity

Reference North Stars: Airbnb — nights booked. Slack — weekly active teams sending 2,000+ messages. Spotify — time spent listening. Stripe — payment volume processed.

---

## AARRR

Lifecycle funnel view.

| Stage           | Question                     | Example metric                         |
| --------------- | ---------------------------- | -------------------------------------- |
| **Acquisition** | Where do users come from?    | Signups by channel, CAC                |
| **Activation**  | Did they get first value?    | % reaching "aha" event in 24h          |
| **Retention**   | Do they come back?           | Week-4 retention, DAU/MAU              |
| **Referral**    | Do they bring others?        | K-factor, invites sent                 |
| **Revenue**     | Do they pay?                 | ARPU, LTV, conversion to paid          |

Diagnose full funnel. Set OKRs on the weakest stage; don't spread across all five.

---

## HEART

UX quality (not funnel performance).

| Dimension       | Question                     | Example metric                     |
| --------------- | ---------------------------- | ---------------------------------- |
| **Happiness**   | Do users like it?            | NPS, CSAT                          |
| **Engagement**  | How intensely used?          | Sessions/user, time in app         |
| **Adoption**    | Are new users trying it?     | % of MAU using feature             |
| **Retention**   | Do they keep using it?       | Feature retention curve            |
| **Task success**| Can they complete goals?     | Task completion rate, time-on-task |

Pair with a Goals-Signals-Metrics table so every metric traces back to a user goal.

---

## OKR shape

- **Objective** — qualitative, inspirational, time-bound. What we want to achieve and why it matters.
- **Key Results (2–5)** — measurable outcomes that prove the Objective was achieved.
- **Initiatives** (not KRs) — the projects/features you'll ship to move the KRs.

**Critical distinction:** KRs are outcomes, not outputs. See `rules/okrs.md` for enforced examples.

---

## Writing a good Objective

- Inspirational — the team should want to work on it
- Qualitative — no numbers (those live in the KRs)
- Time-bound — one quarter
- Aligned — traces up to a company-level Objective

Examples:
- *Make new teams successful in their first week.*
- *Become the fastest way to publish a report.*
- *Turn casual users into daily habits.*

---

## Writing a good Key Result

Each KR:

1. Measurable — a number, not an adjective
2. Outcome-focused — changes user or business behavior
3. Time-bound — by end of quarter
4. Ambitious — 70% attainment = success
5. Owned — one name

Format: `<metric> from <baseline> to <target> by <date>`.

Example set:

> **Objective:** Make new teams successful in their first week.
> - **KR1:** Week-1 activation from 34% → 50% by 2026-09-30
> - **KR2:** % of activated teams inviting a second user from 22% → 40% by 2026-09-30
> - **KR3:** Median time to first "aha" event from 3h 40m → under 60 min by 2026-09-30
> - **Guardrail:** Support ticket rate per 100 new teams must not increase

---

## Grading and cadence

Score each KR 0.0–1.0:

| Score      | Meaning                                          |
| ---------- | ------------------------------------------------ |
| 0.0–0.3    | Missed — debug target, plan, or execution        |
| 0.4–0.6    | Progress — real motion, didn't fully land        |
| 0.7–1.0    | Delivered — on target                            |
| 1.0+       | Overshoot — was the target too low?              |

Consistent 1.0s means the target was too safe. Aim team average at 0.7.

Cadence: draft week 0, publish week 1, weekly check-in per KR, mid-quarter review, end-of-quarter grade + retro.

---

## Experimentation

For A/B tests:

- Define the null hypothesis and the minimum detectable effect **before** running
- Compute sample size and duration; commit to running the full duration (no peeking)
- Register guardrails alongside the primary metric
- Pre-declare segments of interest; treat post-hoc segment cuts as directional only
- Sanity-check for network effects, novelty effects, and Simpson's paradox before rolling out

If sample size for a proper A/B is out of reach, prefer a phased rollout with holdout, or a pre/post analysis with clear caveats.
