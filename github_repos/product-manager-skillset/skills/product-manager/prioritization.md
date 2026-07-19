# Prioritization

See [prioritization.md](./rules/prioritization.md) for enforced scoring rules with Incorrect/Correct pairs.

## Contents

- Framework selection
- RICE
- ICE
- WSJF
- Kano
- MoSCoW
- 2×2 matrix
- Sensitivity checks

---

## Framework selection

Match the framework to the situation. Don't apply RICE to everything.

| Situation                                              | Framework    |
| ------------------------------------------------------ | ------------ |
| Mixed sizes, need defensible scoring                   | **RICE**     |
| Roughly equal-sized ideas, need a quick sort           | **ICE**      |
| Regulated / delivery-critical / cost of delay matters  | **WSJF**     |
| Distinguishing must-haves from delighters              | **Kano**     |
| Scoping a fixed-date release                           | **MoSCoW**   |
| Workshop / stakeholder alignment                       | **2×2**      |

---

## RICE

`Score = (Reach × Impact × Confidence) / Effort`

| Field       | Definition                                | Scale                                        |
| ----------- | ----------------------------------------- | -------------------------------------------- |
| Reach       | # users or events affected per time window | Absolute number (e.g. 5,000/quarter)         |
| Impact      | Effect per user when reached              | 3 massive, 2 high, 1 medium, 0.5 low, 0.25 minimal |
| Confidence  | How sure of the above                     | 100% / 80% / 50% (< 50% → discover first)    |
| Effort      | Person-months, rounded to halves          | 0.5, 1, 2, 3…                                |

**Rules**
- Same time window for Reach across every item; otherwise scores aren't comparable.
- Confidence < 50% means "go validate", not "guess lower".
- Impact never filled in without at least one data point or one user quote.

---

## ICE

`Score = Impact × Confidence × Ease` (each 1–10)

Use when items are similar in size and you need a 15-minute answer. Not appropriate when reach varies widely.

---

## WSJF

`Score = Cost of Delay / Job Size`

Cost of Delay = User/Business Value + Time Criticality + Risk Reduction/Opportunity Enablement. Each 1, 2, 3, 5, 8, 13. Job Size same scale.

Use in SAFe environments, hardware, regulated products, or anywhere delay itself is expensive.

---

## Kano

Classify each feature via user survey:

| Category    | Meaning                                         | Investment rule                       |
| ----------- | ----------------------------------------------- | ------------------------------------- |
| Must-be     | Absence dissatisfies; presence doesn't delight  | Ship, don't over-invest               |
| Performance | More is linearly better                         | Invest proportional to competitiveness |
| Delighter   | Unexpected joy; absence is fine                 | Invest sparingly for differentiation  |
| Indifferent | Users don't care                                | Don't build                           |
| Reverse     | Users dislike it                                | Remove                                |

For feature-set decisions, not sprint prioritization.

---

## MoSCoW

Scope-cutting for a fixed-date release:

- **Must** — release fails without it
- **Should** — important but release can go without
- **Could** — nice, if time permits
- **Won't** — explicitly out (write it down; prevents re-litigation)

Musts should be ≤ 60% of estimated capacity. If Musts > 100%, the release is at risk before it starts.

---

## 2×2 matrix

Impact vs. Effort quadrants. Fast workshop tool:

- High impact, low effort → do now
- High impact, high effort → plan, break down
- Low impact, low effort → fill-in
- Low impact, high effort → don't do

Loses precision at scale. Good for stakeholder alignment, bad for a 50-item backlog.

---

## Sensitivity checks

After scoring, sanity-check:

1. Would a ±1 point change on Impact or ±0.2 on Confidence flip the ranking? If yes, the top pick isn't robust — discover to firm up Confidence.
2. Are the top 3 items strategically aligned? If the top-scored item doesn't ladder up to a strategic pillar, either the strategy or the score is wrong.
3. What did the framework ignore? Dependencies, sequencing, team morale, learning value — apply judgment on top of the score, don't defer to the number.
