# Example — RICE scoring for Q3 backlog

Worked example of RICE applied to 6 candidate initiatives for Aduns-duns Q3.

## Inputs

- Time window for Reach: one quarter (13 weeks)
- Impact scale: 3 = massive, 2 = high, 1 = medium, 0.5 = low, 0.25 = minimal
- Confidence: 100% (strong data), 80% (some data), 50% (mostly opinion — should discover first)
- Effort: person-months, rounded to halves

## Scoring table

| # | Item | Reach (users/qtr) | Impact | Confidence | Effort (pm) | Score | Notes |
|---|---|---:|---:|---:|---:|---:|---|
| 1 | Shared Boards (invite + real-time) | 12,000 | 3 | 0.80 | 4.0 | **7,200** | Reach = all new SMB signups. Impact = fixes top retention driver. |
| 2 | Templates gallery | 18,000 | 1 | 0.80 | 1.5 | **9,600** | Big reach, small per-user impact, low effort. |
| 3 | Mobile web parity | 8,000 | 2 | 0.50 | 3.0 | **2,667** | Confidence low — need mobile usage data first. |
| 4 | Slack integration | 3,500 | 2 | 0.80 | 2.0 | **2,800** | Small reach (paid tier only) but high value per user. |
| 5 | Bulk import from CSV | 1,200 | 1 | 1.00 | 0.5 | **2,400** | Tiny reach, cheap. Fill-in work. |
| 6 | AI-generated task breakdown | 12,000 | 2 | 0.50 | 3.5 | **3,429** | Confidence low — need concept test. |

## Ranking

1. Templates gallery — 9,600
2. Shared Boards — 7,200
3. AI task breakdown — 3,429
4. Slack integration — 2,800
5. Mobile web parity — 2,667
6. Bulk CSV import — 2,400

## Recommendation

**Ship Shared Boards first, not Templates**, despite Templates ranking higher on RICE. Rationale:

- Templates' Reach is inflated — it counts every signup, but the *retention* delta from templates alone is unproven. If we score Templates against the actual Q3 outcome KR (week-4 team retention), Impact drops to 0.5 and the score falls to 4,800.
- Shared Boards traces directly to the strategic pillar ("Land the team, not the user"). Templates doesn't.
- Shared Boards' 4-pm cost is 2 engineers × 2 months — fits the quarter.

**Ship Templates second** as a fill-in for the tail of the quarter — it's cheap and additive.

## Skipped, with reasoning

- **AI task breakdown**: 50% confidence = go validate. Run a 1-week concept test with 10 users before committing engineering. If validated, promote to Q4 top of backlog.
- **Mobile web parity**: 50% confidence — pull the mobile usage numbers from analytics before scoring again. If mobile % is > 30% of sessions, this jumps.
- **Slack integration**: real value but small addressable audience — revisit once we're monetizing more of the base.
- **Bulk CSV**: fill-in only. Do only if we have < 0.5 pm slack in the quarter.

## Sensitivity check

If Shared Boards Confidence drops from 0.8 → 0.5 (say discovery reveals SMB owners are wary of inviting), score falls to 4,500 — still #3, still worth doing but re-evaluate scope.

If Templates Impact is really 0.5 not 1 (my suspicion), score is 4,800 — Shared Boards clearly wins.

## Assumptions to validate before committing

- [ ] Shared Boards Impact = 3 rests on retention interview cohort of 12. Widen to 30 before Q3 kickoff.
- [ ] Templates Reach = 18,000 assumes gallery is shown to every signup. Confirm with growth team.
- [ ] AI task breakdown Confidence = 0.5 — commit to a 1-week concept test in week 1 of Q3.
