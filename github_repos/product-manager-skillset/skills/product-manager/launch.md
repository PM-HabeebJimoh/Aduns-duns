# Launch

See [launch-safety.md](./rules/launch-safety.md) for enforced rules with Incorrect/Correct pairs.

## Contents

- Stages
- Pre-launch checklist
- Internal dogfood
- Closed beta
- Percentage rollout
- GA
- Post-launch review

---

## Stages

```
Internal dogfood → Closed beta → % rollout (5 → 25 → 50 → 100) → GA → Post-launch
```

Each stage has entry and exit criteria. No skipping.

---

## Pre-launch checklist (T-2 weeks)

### Product & spec
- [ ] PRD approved by eng, design, data
- [ ] Success metrics defined with baseline + target
- [ ] Guardrail metrics defined with regression thresholds
- [ ] Non-goals explicitly listed
- [ ] Edge cases in PRD reviewed against QA test plan

### Engineering
- [ ] Feature flag configured (`<flag-name>`)
- [ ] Kill switch tested end-to-end in staging
- [ ] Rollback tested — actually flipped off in staging while flag on
- [ ] Load/perf test passed at expected launch traffic × 3
- [ ] Alerting configured on p95 latency, error rate, key business metrics
- [ ] Runbook written for on-call

### Data
- [ ] Analytics events shipped and validated in staging
- [ ] Dashboard live with the metrics from the PRD
- [ ] Baseline captured (last 4 weeks, same day-of-week)
- [ ] A/B test (if applicable) configured, power-calculated, guardrails set

### Design & content
- [ ] All states designed: empty, loading, error, zero-data, max-data
- [ ] Copy reviewed for tone + localization (if applicable)
- [ ] Accessibility check passed (keyboard nav, screen reader, contrast)

### Legal / compliance / privacy
- [ ] Privacy review (if collecting new data)
- [ ] Terms updated (if applicable)
- [ ] Regional restrictions applied (if applicable)

### Comms
- [ ] Sales / CS change brief drafted
- [ ] Support macros / FAQ ready
- [ ] Docs written and reviewed
- [ ] Marketing / blog post drafted (if external)
- [ ] Exec / stakeholder heads-up sent

---

## Internal dogfood

**Entry:** all pre-launch boxes checked.

- Enable flag for company employees
- Slack channel for feedback (`#launch-<name>`)
- Daily triage of feedback for 3–5 days

**Exit criteria (advance when all true)**
- [ ] No P0/P1 bugs open
- [ ] Success metric shows expected direction or is neutral, not negative
- [ ] No guardrail regression
- [ ] Support / CS trained

---

## Closed beta

**Entry:** dogfood exit criteria met.

- Enable flag for N invited external users (target: 20–100)
- Weekly check-in with 3–5 beta users
- Weekly metrics review

**Exit criteria**
- [ ] ≥ X% of beta users completed the core flow
- [ ] Qualitative feedback net-positive (≥ 3 users would recommend)
- [ ] No unresolved P0/P1 bugs
- [ ] No guardrail regression at beta scale

---

## Percentage rollout

Advance one step at a time. Bake at least 3–7 days at each step.

- [ ] 5% — bake 3+ days
- [ ] 25% — bake 3+ days
- [ ] 50% — bake 3+ days
- [ ] 100%

**Advance criteria per step**
- [ ] Success metric neutral-or-positive vs. holdout
- [ ] No guardrail regression beyond threshold
- [ ] Error rate within tolerance
- [ ] No P0/P1 open

**Rollback triggers** (write these before launch, not after the incident)
- If `<primary metric>` regresses > X% for > Y hours → rollback
- If `<error rate>` > Z for > 10 min → rollback
- If `<support ticket rate>` × threshold → pause (not necessarily rollback)

---

## GA

**Entry:** 100% rollout stable for ≥ 1 week.

- Remove feature flag or leave as kill switch (per team convention)
- Publish blog post / release notes / changelog
- Update pricing pages / marketing site (if applicable)
- Sales enablement session

---

## Post-launch review

- Week 1: daily metrics review
- Week 2: weekly metrics review, first retro
- Week 4: outcome review — did we hit the PRD's success metric?
- Week 8: decision — double down, iterate, or sunset

**Retro questions**
- Did we hit the metric target? Why / why not?
- What surprised us in user behavior?
- What did we learn about the segment?
- What would we do differently next time?
- What follow-on work is worth doing?
