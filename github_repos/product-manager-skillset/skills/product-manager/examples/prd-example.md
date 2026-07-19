# Example PRD — "Shared Boards" for Aduns-duns

A worked example of the canonical PRD. Fictional product ("Aduns-duns" = a task-board SaaS for small teams).

---

# Shared Boards

**Author:** H. Jimoh (PM)  •  **Status:** In review  •  **Last updated:** 2026-07-15
**Reviewers:** A. Okafor (Eng lead) · L. Adeyemi (Design) · O. Bello (Data) · Legal N/A
**Related:** [Q3 strategy doc], [Discovery notes — 12 interviews], [Competitive teardown]

## 1. TL;DR

Let a board owner invite up to 10 collaborators to view and edit a single board in real time. Target: raise week-4 team retention for new signups from 28% → 40% by end of Q3, by removing the top-cited drop-off reason ("I couldn't get my teammate in").

## 2. Problem

Small-team users (2–10 people) sign up for Aduns-duns intending to collaborate, but today the product is single-player. In 12 discovery interviews (Q2 2026), 9 users mentioned "I ended up sharing screenshots" or "we went back to WhatsApp" within their first two weeks. Support tickets tagged `collaboration` have grown 3.4× since the SMB campaign launched in April. Week-4 retention for accounts that never invite a teammate: 12%. For accounts that manually shared boards via export: 41%.

## 3. Why now

- Q3 strategy pillar #2 is "Land the team, not the user." Shared Boards is the smallest unlock for that pillar.
- SMB acquisition channel is spending more per month than it returns; retention is the bottleneck, not acquisition.
- Competitor Trello Free removed real-time collab from the free tier in June — window is open.

## 4. Goals

- Week-4 team retention for new signups: 28% → 40% by 2026-09-30
- % of new signups inviting ≥ 1 teammate in first 7 days: 8% → 30% by 2026-09-30

## 5. Non-goals

- Not building granular per-column permissions this quarter (view/edit only).
- Not building comments or @-mentions (separate PRD, Q4).
- Not building SSO or SCIM (enterprise scope, not SMB).
- Not building notifications for board changes (Q4 candidate).

## 6. Target users & use cases

- **Primary persona:** Ope, ops lead at a 5-person agency. Runs client work through a single shared board.
- **Secondary persona:** Chidi, freelancer working with 2 clients. Wants each client to see their own board only.

**Top 3 use cases**
1. Ope creates a board, invites 4 teammates via email, all see updates live.
2. Chidi invites 1 client as "view-only" so the client can track progress without editing.
3. A collaborator leaves the agency; Ope removes them and their access ends immediately.

## 7. Proposed solution

Add a **Share** button on every board. Opens a modal:

- Input: email(s), comma or newline separated (up to 10)
- Toggle per invitee: **Can edit** / **Can view**
- Optional message
- Copy-link fallback (link inherits the modal's default permission)

Invitees receive an email with a magic link (24h expiry) → click → land in the board. If not signed up, sign-up flow runs first, then redirects back.

Real-time: cursors, selection highlights, optimistic updates via existing Yjs sync layer.

### Happy path

1. Ope clicks **Share** on board "Client Alpha"
2. Types 4 emails, leaves default (Can edit), clicks Send
3. Teammates get email, click, land on board
4. All 5 see each other's cursors and edits live

### Edge cases

- **Empty state:** no collaborators yet — modal shows "Only you" and the Share input
- **Error state:** invalid email — inline error, don't block valid ones
- **Loading:** invite send takes > 500ms — show inline spinner, don't block modal
- **Zero-data:** invitee lands on empty board — show onboarding tooltip
- **Max-data:** 11th invite attempted — inline error "Free plan supports up to 10 collaborators. Upgrade or remove one."
- **Offline:** collaborator loses connection — banner "Reconnecting…", local edits queue
- **Accessibility:** modal fully keyboard-navigable; cursors have text labels for screen readers
- **i18n:** email subject/body localized to invitee's account language

## 8. Requirements

- **[FR-1]** *As a board owner, I can invite up to 10 collaborators by email so we can work together.*
  - Given I am the owner of a board, when I open Share and submit valid emails, then each invitee receives an email within 60s.
- **[FR-2]** *As an invitee, I can accept an invite via email link so I can access the board.*
  - Given I click a valid invite link within 24h, when I sign in (or sign up), then I land on the shared board with the granted permission.
- **[FR-3]** *As a board owner, I can revoke access so a former collaborator loses access immediately.*
  - Given I remove a collaborator, when they attempt any board action, then they receive a 403 within 5s.
- **[FR-4]** *As a collaborator, I can see other collaborators' cursors and edits in real time.*
  - Given ≥ 2 users are on the same board, when one user edits, then others see the update within 300ms p95.

**Non-functional**
- p95 sync latency < 300ms at 10 concurrent editors per board
- No auth token in URL after the initial exchange (magic-link → session cookie)
- Rate limit: 20 invites per user per hour
- WCAG 2.1 AA compliance

## 9. Success metrics

- **Primary:** Week-4 team retention for new signups — baseline 28%, target 40%, measured 4 weeks after signup
- **Input:** % of new signups sending ≥ 1 invite in first 7 days — baseline 8%, target 30%
- **Guardrails:**
  - Support ticket rate per 100 signups must not increase > 10%
  - p95 sync latency must not exceed 300ms
  - Signup conversion (visitor → signup) must not regress > 5%
- **Diagnostics:** invite send rate, invite accept rate, time-to-first-invite, collaborators per board (distribution)
- **Instrumentation plan:** `board_shared`, `invite_sent`, `invite_accepted`, `collaborator_removed`, `collaborator_edit` — owner: O. Bello

## 10. Rollout plan

- Feature flag: `shared-boards`
- Stages:
  - Internal dogfood — week of Aug 4
  - Closed beta — 50 handpicked SMB accounts, week of Aug 11
  - 5% rollout — Aug 25 · bake 3 days
  - 25% rollout — Aug 29 · bake 3 days
  - 50% rollout — Sep 3 · bake 3 days
  - 100% rollout — Sep 8
- Rollback trigger: if week-4 retention shows a downward trend > 5pp in the treatment cohort at 25%, pause. If p95 sync latency > 500ms for > 30 min, kill.

## 11. Open questions

1. Do we count a "team" as ≥ 2 collaborators or ≥ 2 active editors? — owner: O. Bello, needed by Aug 1
2. Do we send an email to the owner when an invitee accepts? — owner: L. Adeyemi, needed by Aug 4
3. What happens to shared boards if the owner downgrades to a paid tier with a lower cap? — owner: PM, needed by Aug 8

## 12. Assumptions

- We assume SMB users prefer email invites over link-sharing — evidence: 8/12 interviews — risk if wrong: **low** (we support both)
- We assume 10 collaborators is enough for the free tier — evidence: median team size in signup survey = 4, p95 = 9 — risk if wrong: **low**
- We assume real-time sync latency is the bar users expect — evidence: comparison to Notion/Figma — risk if wrong: **medium** (if latency slips, "collaboration" feels broken)

## 13. Appendix

- [Discovery notes — 12 interviews (Google Doc)]
- [Competitive teardown — Trello, Notion, Linear]
- [Retention cohort analysis, Q2 2026]
