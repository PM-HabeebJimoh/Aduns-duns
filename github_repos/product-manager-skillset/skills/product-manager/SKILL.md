---
name: product-manager
description: Manages product-management work — writing PRDs, prioritizing backlogs, defining success metrics and OKRs, planning discovery and user research, drafting stakeholder communications, and running launches (beta → % rollout → GA). Provides canonical artifact structures, framework selection, and rule-based guidance for PM output. Applies when the user is drafting a PRD, one-pager, or spec; scoring a backlog with RICE / ICE / WSJF / Kano / MoSCoW; defining a North Star, AARRR, HEART, or OKR; planning a discovery study or user interview; writing an exec review, weekly update, or launch comms; or planning a rollout with feature flags. Also triggers for "write a PRD", "prioritize this", "what metric", "draft an OKR", "plan the launch", "run a discovery", or "frame this for leadership".
user-invocable: false
allowed-tools: Read, Write, Edit, Bash
---

# product-manager

A framework for producing high-quality product-management artifacts — PRDs, prioritization scores, metric definitions, OKRs, launch plans, and stakeholder updates. Artifacts are added to the user's project as source markdown, using canonical structures rather than free-form prose.

> **IMPORTANT:** Every artifact this skill produces must be traceable to (1) a user problem, (2) a measurable outcome, and (3) an owner. If any of the three is missing, ask before writing — do not fill in with plausible-sounding defaults.

## Current Project Context

```text
!`find . -type f \( -name "*.md" -path "*prd*" -o -name "roadmap*" -o -name "okr*" -o -name "metrics*" \) | head -20`
!`test -f components.json && echo "shadcn project detected" || echo "no shadcn project"`
```

The output above lists existing PM artifacts in the project. Read them before drafting new ones — reuse the project's naming, section order, and tone. Use `discovery.md` for research plans, `prd.md` for PRD structure, `prioritization.md` for scoring, `metrics.md` for metric and OKR definitions, and `launch.md` for rollout plans.

## Principles

1. **Use existing artifacts first.** Check `docs/prds/`, `docs/roadmap.md`, or the project wiki before drafting new. Reuse section order and tone.
2. **Compose, don't reinvent.** Feature launch = PRD + metrics tree + launch checklist + comms brief. Quarterly plan = OKRs + prioritized backlog + roadmap.
3. **Use canonical structures before custom formats.** `prd.md` for specs, `metrics.md` for KPIs, `launch.md` for rollouts.
4. **Use outcome language, not output.** "Increase week-4 retention 28% → 40%" — never "Ship v2 of onboarding".

## Critical Rules

These rules are **always enforced**. Each links to a file with Incorrect/Correct pairs.

### Problem Framing → [problem-framing.md](./rules/problem-framing.md)

- **Problem before solution.** Never draft a spec whose first section is a feature description.
- **User + job + pain.** Every problem statement names the user, the job they're trying to do, and the pain today.
- **Quantify the pain.** Use ticket counts, funnel drop-off %, or interview counts — not adjectives.
- **No solution language in the problem.** Words like "add", "build", "integrate" belong in Requirements, not Problem.

### PRD Structure → [prd-structure.md](./rules/prd-structure.md)

- **Canonical section order.** TL;DR → Problem → Why now → Goals → Non-goals → Users → Solution → Requirements → Metrics → Rollout → Open questions → Assumptions. Never reorder.
- **Explicit Non-goals.** Every PRD lists what it will **not** do. Missing Non-goals = missing PRD.
- **Acceptance criteria as Given/When/Then.** Not free-form prose.
- **Edge states listed.** Empty, loading, error, zero-data, max-data, offline, a11y, i18n — enumerated, not implied.

### Metrics Definition → [metrics-definition.md](./rules/metrics-definition.md)

- **Every target metric ships with a guardrail.** Activation ↑ paired with support-ticket rate as guardrail.
- **Numerator and denominator both defined.** For any ratio.
- **Population and time window explicit.** "All users last 28d, excluding internal accounts and bots."
- **No vanity metrics as targets.** Total signups, total pageviews, total downloads — only allowed as diagnostics, never as OKR key results.

### OKRs → [okrs.md](./rules/okrs.md)

- **KRs are outcomes, not outputs.** "Ship X" → "X% of segment adopts feature within 30 days".
- **Numbers live in KRs, not the Objective.** Objective is qualitative and inspirational.
- **Baseline + target + date on every KR.** All three or it's not a KR.
- **≤ 5 KRs per Objective.** More = no priorities.

### Prioritization → [prioritization.md](./rules/prioritization.md)

- **Framework matches the situation.** RICE for mixed sizes, ICE for quick sorts, WSJF for delivery-critical, Kano for delighters, MoSCoW for release scope.
- **Show the scoring table, not just the rank.** Reviewers audit the working.
- **Confidence < 50% = do discovery, don't guess lower.** Never score-around a validation gap.
- **Same time window for Reach across all items.** Otherwise scores aren't comparable.

### Stakeholder Communication → [stakeholder-comms.md](./rules/stakeholder-comms.md)

- **Headline first.** Never bury the decision, ask, or status in paragraph three.
- **Numbers with deltas.** A metric without a comparison is noise.
- **Blockers name people and dates.** "Waiting on legal" is not a blocker; "Bola, by Fri" is.
- **Match format to audience.** Exec = 1-pager, team = weekly, sales = change brief, users = release notes.

### Launch Safety → [launch-safety.md](./rules/launch-safety.md)

- **Feature flag before code.** Every user-facing change ships behind a flag.
- **Rollback criteria written before launch.** If-then rules ("if p95 latency > 500ms for 30 min, kill"), not judgment calls at 2am.
- **Metrics instrumented before enabling.** Baseline captured for at least 4 prior weeks.
- **No skipping rollout stages.** Internal → beta → 5% → 25% → 50% → 100%. Every stage has entry and exit criteria.

## Key Patterns

These are the most common patterns that differentiate correct PM artifacts. For edge cases, see the linked rule files above.

```markdown
<!-- Problem framing: user + job + pain, quantified, no solution language. -->

<!-- Incorrect -->
## Problem
Users need a better dashboard.

<!-- Correct -->
## Problem
Ops leads (persona: Ope) running weekly client reviews cannot see which
tasks are stalled without opening each board manually. 9 of 12 interviewed
mention this; support ticket rate for "how do I find stalled work" grew
3× QoQ.

<!-- OKR: outcome, not output. Baseline + target + date. -->

<!-- Incorrect -->
KR1: Ship Shared Boards by end of Q3.

<!-- Correct -->
KR1: Week-4 team retention for new signups from 28% → 40% by 2026-09-30.

<!-- Metric: guardrail always paired. -->

<!-- Incorrect -->
Target: activation rate up 20%.

<!-- Correct -->
Target:    Week-1 activation 34% → 50% by Sep 30.
Guardrail: Support tickets per 100 activated users must not increase.

<!-- Prioritization: show the working, not just the rank. -->

<!-- Incorrect -->
Top priority: Shared Boards.

<!-- Correct -->
| Item          | Reach | Impact | Conf | Effort | Score |
|---------------|------:|-------:|-----:|-------:|------:|
| Shared Boards | 12000 |    3   | 0.80 |   4.0  |  7200 |
| Templates     | 18000 |    1   | 0.80 |   1.5  |  9600 |
Recommend Shared Boards despite lower score — Templates' Impact=1
overstates retention effect; see discovery notes.
```

## Artifact Selection

| Need                                    | Use                                                                     |
| --------------------------------------- | ----------------------------------------------------------------------- |
| Spec a feature for eng + design         | PRD → [prd.md](./prd.md)                                                |
| Order candidate work                    | Prioritization framework → [prioritization.md](./prioritization.md)     |
| Define success for a feature or team    | Metrics tree + OKRs → [metrics.md](./metrics.md)                        |
| Validate an assumption before building  | Discovery plan → [discovery.md](./discovery.md)                         |
| Ship a change to users                  | Launch checklist → [launch.md](./launch.md)                             |
| Update leadership on progress           | Exec one-pager → `rules/stakeholder-comms.md`                           |
| Update the team weekly                  | Weekly update → `rules/stakeholder-comms.md`                            |
| Brief sales / CS on a change            | Change brief + FAQ → `rules/stakeholder-comms.md`                       |
| Announce a change to users              | Release notes → `rules/stakeholder-comms.md`                            |
| Score an idea's demand before building  | Fake-door / smoke test → [discovery.md](./discovery.md)                 |
| Score an idea's value before building   | Concierge / Wizard-of-Oz → [discovery.md](./discovery.md)               |
| Compare 2 solutions with live users     | A/B test → [metrics.md](./metrics.md#experimentation)                   |

## Anti-patterns

Refuse (politely, with a reframe) if the user asks for any of these:

- **PRD for a solution with no stated problem** → ask for the problem first.
- **Output-only OKR** ("Launch v2 by Q3") → convert to an outcome KR.
- **Vanity metric as target** (total signups without engagement cut) → propose a paired activation/retention metric.
- **Prioritization by loudest voice** → score the ask against the alternatives, show the trade-off.
- **Launch with no rollback criterion** → block until if-then rules are written.
- **Discovery skipped under time pressure** → offer the 3-user, 90-minute version instead of blocking.
