# Example — Weekly update

A well-written weekly stakeholder update. Headline-first, numbers not adjectives, blockers with named owners.

---

### Team Aduns-duns — week of 2026-07-14

**Headline:** Shared Boards beta opens Monday with 50 SMB accounts. On track for 25% rollout Aug 25.

**Shipped**
- Invite modal (send + resend + revoke) — behind `shared-boards` flag, dogfood-enabled
- Real-time cursor + selection sync — p95 latency 220ms at 10 concurrent editors (target < 300ms ✅)
- Analytics events (`board_shared`, `invite_sent`, `invite_accepted`) validated end-to-end in staging

**Shipping this week**
- Magic-link email template + 24h expiry logic (A. Okafor, by Fri)
- Rate limit: 20 invites/user/hour (A. Okafor, by Fri)
- Support macros + FAQ (M. Adekola, by Thu)

**Blocked / need help**
- Legal review of the invite email copy — need sign-off by **Fri Jul 18** or beta slips one week. Ping: **@bola-legal** (I've followed up twice).
- Design bandwidth for the "invitee-not-signed-up" state — need **4h of L. Adeyemi's time** this week. Requesting via **@leke-adeyemi**.

**Metrics (baseline, pre-launch)**
- Week-4 team retention (new signups): **28%** (Δ 0 vs last week — as expected, no treatment yet)
- % new signups inviting a teammate: **8%** (Δ 0)
- p95 board load time: **1.1s** (Δ −0.2s — improvement from unrelated caching change)
- Support tickets tagged `collaboration`: **34 this week** (Δ +5 vs prior week — SMB campaign continues)

**Next week**
- Open closed beta Mon Jul 21 (50 accounts, invite emails go out Sun evening)
- Daily beta triage stand-up (10 min, 9am)
- Instrument invite-accept-time-to-first-edit for cohort analysis

**Risks**
- Legal review is the only path to beta; if it slips past Fri, beta slips to Jul 28 (still leaves 4 weeks to 25% rollout)
- Sync latency is under target now, but we haven't tested with 10+ boards active per pod — load test scheduled Wed

---

## Why this update works

- **Headline first** — reader knows the state in one line.
- **Metrics have deltas** — every number has a comparison and an interpretation.
- **Blockers name people and dates** — no "waiting on legal" without a name and a deadline.
- **Risks are pre-stated** — reader doesn't discover them in a fire-drill next week.
- **Under 400 words** — actually gets read.
