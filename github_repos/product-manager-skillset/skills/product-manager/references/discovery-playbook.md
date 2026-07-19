# Discovery Playbook

Continuous discovery, not one-off research sprints. The rule: talk to ≥ 3 users a week, every week.

## The core loop (Teresa Torres, Opportunity Solution Tree)

```
Outcome (what we want to move)
  └── Opportunities (unmet needs / pains, from customer interviews)
        └── Solutions (bets — features, changes, experiments)
              └── Assumption tests (cheapest way to invalidate)
```

Every solution in your backlog must trace up to an opportunity, which traces up to an outcome. If the chain breaks, the solution shouldn't ship.

---

## Method selection

Match the method to the question:

| Question | Method | Sample size |
|---|---|---|
| What problems do users have? | Semi-structured interview | 5–7 per segment |
| How do they do it today? | Diary study or observation | 5–10 |
| Will they use this solution? | Prototype test | 5 |
| Will they pay for it? | Fake-door / smoke test | Traffic-dependent |
| Which of A/B works better? | A/B test | Power-calculated |
| How satisfied are they? | Survey (NPS/CSAT) | 100+ |

**5-user rule (Nielsen):** ~85% of usability issues surface with 5 users per segment. More users ≠ better data; more segments = better data.

---

## Interview rules (from *The Mom Test*)

1. **Ask about their life, not your idea.** *"Walk me through the last time you did X"* beats *"Would you use a tool that does X?"*
2. **Ask about specifics in the past, not opinions about the future.**
3. **Talk less, listen more.** Target a 30/70 split.
4. **Follow-up on emotions.** *"You said 'annoying' — tell me more."*
5. **Never pitch.** The moment you pitch, you can't trust the answer.
6. **Ask for commitments and referrals.** Time, money, or intros — real signal of interest.

**Kill signals (positive):** users curse, users cry, users compare it to a competitor unprompted, users ask when they can have it.

**Fake signals (ignore):** "sounds cool", "I might use it", "great idea".

---

## Interview script skeleton

```
Warm-up (2 min)
- Tell me a bit about your role and how [related area] fits in.

Context (5 min)
- Walk me through the last time you did [job / task].
- What tools / people / steps were involved?

Pain (10 min)
- What was the most frustrating part?
- What did you do about it?
- What did you try that didn't work?

Workaround (5 min)
- Are you using anything to make this easier today?
- What made you pick that?

Close (3 min)
- If we could magically fix one thing, what would matter most?
- Who else should I talk to about this?
- Can I follow up if I have more questions?
```

Total: ~30 min. Longer than 45 min = diminishing returns.

---

## Assumption mapping

Before building, list the assumptions the solution rests on. Rate each on two axes:

- **Importance** — if wrong, does the solution fail?
- **Evidence** — how much do we know?

Test the **high importance + low evidence** ones first, with the cheapest possible test.

| Test type | Cost | Time | Best for |
|---|---|---|---|
| Landing-page / fake-door | Low | 1 day | Demand |
| Concierge (do it manually for one user) | Low | 1 week | Value |
| Wizard-of-Oz (fake it behind the scenes) | Med | 1–2 weeks | Value + UX |
| Prototype test | Low | 1 week | Usability |
| Painted-door (functional dead-end button) | Low | 2 days | Interest |
| Beta with N users | Med | 2–4 weeks | Value + retention |
| A/B test | Varies | Depends on traffic | Optimization |

---

## Synthesis

After 5+ interviews, look for:

- **Repeated pains** — 3+ mentions = signal
- **Repeated workarounds** — someone hacked a solution = strong signal
- **Repeated language** — the words users use for the problem (adopt these in your PRD and marketing)
- **Segments that behave differently** — split them; don't average

Output: an updated opportunity tree, not a slide deck.

---

## Anti-patterns

- **Talking only to customers who love you** — survivor bias. Talk to churned users, prospects, and non-buyers.
- **Leading questions** — *"Wouldn't it be great if…"* Never.
- **Feature-request as truth** — users are great at problems, unreliable at solutions.
- **Discovery as a phase, not a habit** — one-off research decays fast. Keep the weekly cadence.
- **Skipping synthesis** — raw notes ≠ insight. Budget synthesis time equal to interview time.
