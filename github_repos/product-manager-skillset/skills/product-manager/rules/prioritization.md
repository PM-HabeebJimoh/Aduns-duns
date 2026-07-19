# Prioritization

See [prioritization.md](../prioritization.md) for framework details and selection.

## Contents

- Framework matches situation
- Show the scoring table
- Confidence < 50% = go discover
- Same time window for Reach
- Impact requires evidence
- Recommendation over ranking

---

## Framework matches situation

Don't apply RICE to everything. Different situations, different tools.

**Incorrect:**

```markdown
[Team scoring 30 bug fixes with RICE, filling in Reach = "some users"
and Impact = 2 for every one.]
```

**Correct:**

```markdown
[Team uses MoSCoW for the release scope decision (fixed date), and a
simple severity × frequency 2×2 for bug fixes. RICE is used only for
the 6 quarterly feature bets.]
```

---

## Show the scoring table

Reviewers audit the working, not the ranking.

**Incorrect:**

```markdown
Q3 priorities:
1. Shared Boards
2. Templates gallery
3. Slack integration
```

**Correct:**

```markdown
Q3 candidates (RICE, Reach = users/quarter):

| Item          | Reach | Impact | Conf | Effort | Score |
|---------------|------:|-------:|-----:|-------:|------:|
| Templates     | 18000 |   1    | 0.80 |  1.5   | 9600  |
| Shared Boards | 12000 |   3    | 0.80 |  4.0   | 7200  |
| AI breakdown  | 12000 |   2    | 0.50 |  3.5   | 3429  |
| Slack         |  3500 |   2    | 0.80 |  2.0   | 2800  |
| Mobile web    |  8000 |   2    | 0.50 |  3.0   | 2667  |
| CSV import    |  1200 |   1    | 1.00 |  0.5   | 2400  |

Recommend: Shared Boards → Templates → AI breakdown (after concept test).
See Recommendation section below for reasoning.
```

---

## Confidence < 50% = go discover

Never score-around a validation gap. If Confidence is < 50%, the answer is discovery, not a lower score.

**Incorrect:**

```markdown
| AI task breakdown | 12000 | 2 | 0.25 | 3.5 | 1714 |
```

**Correct:**

```markdown
| AI task breakdown | — | — | — | — | Do 1-week concept test first |

Committing to a 1-week concept test in week 1 of Q3:
- Prompt: 10 users generate task breakdowns from real briefs
- Kill signal: < 50% rate output as "usable without editing"
- If validated, re-score with Confidence = 0.8; if killed, drop
```

---

## Same time window for Reach

Different windows across items make scores non-comparable.

**Incorrect:**

```markdown
| Item          | Reach                          | ... |
|---------------|--------------------------------|-----|
| Templates     | 18000/quarter                  | ... |
| Shared Boards | 4000/month                     | ... |
| CSV import    | 200/week                       | ... |
```

**Correct:**

```markdown
Reach window: users affected per quarter (13 weeks).

| Item          | Reach   | ... |
|---------------|--------:|-----|
| Templates     | 18000   | ... |
| Shared Boards | 12000   | ... |
| CSV import    | 2600    | ... |
```

---

## Impact requires evidence

Impact filled in without a data point or user quote is fiction.

**Incorrect:**

```markdown
| Shared Boards | 12000 | 3 (feels right) | 0.8 | 4.0 | 7200 |
```

**Correct:**

```markdown
| Shared Boards | 12000 | 3 | 0.8 | 4.0 | 7200 |

Impact = 3 evidence:
- 9/12 discovery interviews named collaboration as #1 blocker
- Accounts that manually shared boards (workaround) show 41% week-4
  retention vs. 12% for solo accounts (Q2 cohort analysis)
- Support ticket rate tagged "collaboration" grew 3.4× since April
```

---

## Recommendation over ranking

Rankings hide judgment. Explicit recommendations expose it and invite challenge.

**Incorrect:**

```markdown
Top pick: Templates (highest RICE score).
```

**Correct:**

```markdown
Recommend Shared Boards first, not Templates, despite Templates' higher
RICE score.

Rationale:
- Templates' Reach counts every signup, but its Impact on the actual
  outcome KR (week-4 team retention) is unproven. If we score against
  the KR, Impact drops from 1 → 0.5 and the score falls to 4,800.
- Shared Boards traces directly to the Q3 strategic pillar ("Land the
  team, not the user"); Templates does not.
- Ship Templates second as a fill-in for the tail of the quarter.

Skipped, with reasoning:
- AI breakdown: 50% confidence → concept test in week 1, revisit for Q4.
- Slack: real value but small addressable audience for the quarter.
- Mobile web: pull mobile-session % from analytics before re-scoring.
- CSV: fill-in only, do only with slack capacity.
```
