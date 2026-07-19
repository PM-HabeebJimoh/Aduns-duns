# Launch Safety

See [launch.md](../launch.md) for stage definitions and the full checklist.

## Contents

- Feature flag before code
- Rollback criteria written before launch
- Metrics instrumented before enabling
- No skipping rollout stages
- Kill switch tested
- Rollback is a first-class decision

---

## Feature flag before code

Every user-facing change ships behind a flag. Not "we'll add one if needed".

**Incorrect:**

```markdown
Rollout plan: Merge to main and deploy to all users.
```

**Correct:**

```markdown
Rollout plan:
- Feature flag: `shared-boards`
- Default off in prod; enabled per rollout stage below
- Kill switch tested in staging (see runbook link)
- Flag removed after 2 weeks stable at 100%
```

---

## Rollback criteria written before launch

Rollback criteria written at 2am during an incident are judgment calls. Rollback criteria written before launch are decisions.

**Incorrect:**

```markdown
Rollback plan: If things look bad, roll back.
```

**Correct:**

```markdown
Rollback triggers (if any true, kill switch fires immediately):
- p95 sync latency > 500ms for > 30 min
- Error rate on `POST /invites` > 2% for > 10 min
- Any P0 bug (data loss, auth bypass, cross-tenant leak)

Pause triggers (halt further rollout, do not roll back):
- Week-4 retention in treatment cohort < control by > 5pp for > 3 days
- Support ticket rate for `collaboration` > 1.5× baseline for > 48h

On-call: A. Okafor (primary), H. Jimoh (product decisions).
Runbook: [link]
```

---

## Metrics instrumented before enabling

No trusted baseline = uncontestable impact claims. Instrument, then enable.

**Incorrect:**

```markdown
Ship it Monday; we'll add tracking after we see how it goes.
```

**Correct:**

```markdown
Instrumentation gates (must be green before flag enable):
- [x] Events shipped and validated in staging (Jul 10)
- [x] Dashboard live, reviewed by data + PM (Jul 12)
- [x] Baseline captured for 4 prior weeks, same day-of-week (Jul 14)
- [x] Alerting configured on p95 latency + error rate (Jul 14)
- [x] Weekly retention cohorts running for 8+ weeks pre-launch
```

---

## No skipping rollout stages

The cost of a bad rollout > the cost of one more week baking. Every stage has entry and exit criteria.

**Incorrect:**

```markdown
- Aug 15: Enable flag for 100% of users.
```

**Correct:**

```markdown
Stage schedule (each advances only when exit criteria met):

- Aug  4: Internal dogfood — 3–5 days bake
    Exit: no P0/P1 open; metric neutral+; support/CS trained
- Aug 11: Closed beta, 50 SMB accounts — 7 days bake
    Exit: ≥ 60% completed core flow; ≥ 3 users would recommend
- Aug 25:  5% rollout — 3 days bake
    Exit: metric neutral-or-positive vs holdout; no guardrail regression
- Aug 29: 25% rollout — 3 days bake
- Sep  3: 50% rollout — 3 days bake
- Sep  8: 100% rollout — 1 week stable → GA
```

---

## Kill switch tested

An untested kill switch is not a kill switch. Test it in staging by actually flipping it off while traffic is on.

**Incorrect:**

```markdown
- [x] Feature flag configured.
```

**Correct:**

```markdown
- [x] Feature flag configured (`shared-boards`)
- [x] Kill switch drill run in staging Jul 15:
      - Flag on for 100% of staging traffic
      - Flag flipped off
      - Confirmed within 30s: new writes rejected, in-flight sync
        completes gracefully, no client errors surfaced to UI
      - Runbook updated with observed rollback time (28s p95)
```

---

## Rollback is a first-class decision

Rollback is not defeat. It's a normal part of a healthy rollout. Treat it as a decision the team is empowered to make, not an escalation.

**Incorrect:**

```markdown
Only VP Eng can approve a rollback.
```

**Correct:**

```markdown
Rollback authority:
- On-call engineer can trigger kill switch immediately on any hard
  trigger (see rollback triggers). Notify #launch-shared-boards.
- Pause decision (soft trigger) — PM + eng lead, in writing in
  #launch-shared-boards, within 4h of trigger firing.
- Resume decision after rollback — same PM + eng lead, requires
  written root cause in the incident doc.
- Post-mortem within 5 business days of any rollback, blameless.
```
