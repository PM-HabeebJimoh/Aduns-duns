# Prioritization Frameworks

Pick the framework that matches the situation. Don't apply RICE to everything.

## Decision matrix

| Situation | Framework | Why |
|---|---|---|
| Roughly equal-sized ideas, need quick sort | **ICE** | Fast, no reach data needed |
| Mixed sizes, need defensible scoring | **RICE** | Adds reach; harder to game |
| Regulated / delivery-critical / cost-of-delay matters | **WSJF** | Weights urgency and business value |
| Distinguishing must-haves from delighters | **Kano** | Categorical, not numeric |
| Scoping a fixed-date release | **MoSCoW** | Cuts scope, not ranks ideas |
| Two axes matter most (e.g. impact vs. effort) | **2x2 matrix** | Visual, fast, works in a workshop |

---

## RICE

**Score = (Reach × Impact × Confidence) / Effort**

| Field | Definition | Typical scale |
|---|---|---|
| Reach | # users / events affected per time window | Absolute number (e.g. 5,000/quarter) |
| Impact | Effect per user when reached | 3 = massive, 2 = high, 1 = medium, 0.5 = low, 0.25 = minimal |
| Confidence | How sure are we of the above? | 100% / 80% / 50% (below 50% → do discovery first) |
| Effort | Person-months (round to halves) | 0.5, 1, 2, 3… |

**Rules:**
- Reach must use the same time window for every item.
- Confidence below 50% means "go validate", not "guess lower".
- Never fill in Impact without at least one data point or one user quote.

**Common failure:** Everyone scores their own item Impact=3 and Confidence=100%. Force a group calibration on the first 3 items.

---

## ICE

**Score = Impact × Confidence × Ease** (each 1–10)

Use when items are similar in size and you need a 15-minute answer. Skip when reach varies wildly (RICE handles that).

---

## WSJF (Weighted Shortest Job First)

**Score = Cost of Delay / Job Size**

Cost of Delay = User/Business Value + Time Criticality + Risk Reduction / Opportunity Enablement.

Each component scored 1, 2, 3, 5, 8, 13 (Fibonacci). Job size same scale.

Use in SAFe environments, hardware, regulated products, or anywhere delay itself is expensive.

---

## Kano Model

Classify each feature into one of five categories based on user survey:

| Category | Meaning | Investment rule |
|---|---|---|
| Must-be | Absence causes dissatisfaction; presence doesn't delight | Ship, don't over-invest |
| Performance | More is linearly better | Invest proportional to competitiveness |
| Delighter | Unexpected joy; absence is fine | Invest sparingly, for differentiation |
| Indifferent | Users don't care | Don't build |
| Reverse | Users actively dislike it | Remove |

Use for feature-set decisions, not sprint prioritization.

---

## MoSCoW

Scope-cutting for a fixed-date release. Every item gets one label:

- **Must** — release fails without it
- **Should** — important but release can go without
- **Could** — nice, if time permits
- **Won't** — explicitly out of this release (write it down; prevents re-litigation)

**Rule:** Musts should be ≤ 60% of estimated capacity. If Musts > 100%, the release is already at risk.

---

## 2×2 matrix (Impact vs. Effort)

Fast workshop tool. Draw quadrants:

- **High impact, low effort** → do now
- **High impact, high effort** → plan, break down
- **Low impact, low effort** → fill-ins between big work
- **Low impact, high effort** → don't do

Loses precision at scale. Good for stakeholder alignment, bad for a 50-item backlog.

---

## Anti-patterns

- **Framework theatre** — scoring 30 items to justify a decision already made. Score fewer, faster.
- **Precision over accuracy** — RICE score of 1,247.3 implies certainty you don't have. Round.
- **Ignoring dependencies** — the #1 item can't ship without the #7 item. Track and resolve.
- **No re-scoring** — re-score at least once a quarter; the world changed.
