# Launch Checklist

Every user-facing change moves through stages. No skipping. Every unchecked item is a launch blocker.

## Stages

```
Internal dogfood → Closed beta → % rollout (5→25→50→100) → GA → Post-launch
```

Each stage has entry criteria (before) and exit criteria (before advancing).

---

## Pre-launch (T-2 weeks)

**Product & spec**
- [ ] PRD approved by eng, design, data
- [ ] Success metrics defined with baseline + target
- [ ] Guardrail metrics defined with regression thresholds
- [ ] Non-goals explicitly listed
- [ ] Edge cases in PRD reviewed against QA test plan

**Engineering**
- [ ] Feature flag configured (`[flag-name]`)
- [ ] Kill switch tested end-to-end in staging
- [ ] Rollback tested — actually flipped off in staging while flag on
- [ ] Load / perf test passed at expected launch traffic × 3
- [ ] Alerting configured on p95 latency, error rate, key business metrics
- [ ] Runbook written for on-call

**Data**
- [ ] Analytics events shipped and validated in staging
- [ ] Dashboard live with the metrics from the PRD
- [ ] Baseline captured (last 4 weeks, same day-of-week)
- [ ] A/B test (if applicable) configured, power-calculated, guardrails set

**Design & content**
- [ ] All states designed: empty, loading, error, zero-data, max-data
- [ ] Copy reviewed for tone + localization (if applicable)
- [ ] Accessibility check passed (keyboard nav, screen reader, contrast)

**Legal / compliance / privacy**
- [ ] Privacy review (if collecting new data)
- [ ] Terms updated (if applicable)
- [ ] Regional restrictions applied (if applicable)

**Comms**
- [ ] Sales / CS change brief drafted (see `stakeholder-comms.md`)
- [ ] Support macros / FAQ ready
- [ ] Docs written and reviewed
- [ ] Marketing / blog post drafted (if external)
- [ ] Exec / stakeholder heads-up sent

---

## Stage: Internal dogfood (T-1 week)

**Entry:** all pre-launch boxes checked.

**Actions**
- Enable flag for company employees
- Slack channel for feedback (`#launch-[name]`)
- Daily triage of feedback for 3–5 days

**Exit criteria** (all must be true to advance):
- [ ] No P0/P1 bugs open
- [ ] Success metric shows expected direction (or is neutral, not negative)
- [ ] No guardrail regression
- [ ] Support / CS trained

---

## Stage: Closed beta

**Entry:** dogfood exit criteria met.

**Actions**
- Enable flag for N invited external users (target: 20–100)
- Weekly check-in with 3–5 beta users
- Weekly metrics review

**Exit criteria**:
- [ ] ≥ [X]% of beta users completed the core flow
- [ ] Qualitative feedback net-positive (≥ 3 users would recommend)
- [ ] No unresolved P0/P1 bugs
- [ ] No guardrail regression at beta scale

---

## Stage: Percentage rollout

Advance one step at a time. Bake at least 3–7 days at each step.

- [ ] 5% rollout — bake 3+ days
- [ ] 25% rollout — bake 3+ days
- [ ] 50% rollout — bake 3+ days
- [ ] 100% rollout

**Advance criteria per step:**
- [ ] Success metric neutral-or-positive vs. holdout
- [ ] No guardrail regression beyond threshold
- [ ] Error rate within tolerance
- [ ] No P0/P1 open

**Rollback trigger** (write these down, don't improvise):
- If [primary metric] regresses > [X]% for > [Y] hours → rollback
- If [error rate] > [Z] for > 10 min → rollback
- If [support ticket rate] × [threshold] → pause, don't necessarily rollback

---

## Stage: GA (General Availability)

**Entry:** 100% rollout stable for ≥ 1 week.

**Actions**
- Remove feature flag (or leave as kill switch, per team convention)
- Publish blog post / release notes / changelog
- Update pricing pages / marketing site (if applicable)
- Sales enablement session

---

## Post-launch (T+2 to T+8 weeks)

- [ ] Week 1: daily metrics review
- [ ] Week 2: weekly metrics review, first retro
- [ ] Week 4: outcome review — did we hit the PRD's success metric?
- [ ] Week 8: decision — double down, iterate, or sunset

**Retro questions**
- Did we hit the metric target? Why / why not?
- What surprised us in user behavior?
- What did we learn about the segment?
- What would we do differently next time?
- What follow-on work is worth doing?

---

## Anti-patterns

- **Skipping stages under time pressure** — the cost of a bad rollout > the cost of one more week baking
- **No rollback plan** — every launch has one, written down before launch, not after the incident
- **Metrics instrumented after launch** — no trusted baseline, can't measure impact
- **Silent launches** — sales / support hear from customers before they hear from PM
- **Declaring victory at 100% rollout** — launch is the *start* of measurement, not the end
- **No post-launch review** — the team learns nothing, ships the same mistakes next time
