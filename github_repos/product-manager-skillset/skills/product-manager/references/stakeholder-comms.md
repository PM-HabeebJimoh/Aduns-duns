# Stakeholder Communication

Match the format to the audience. Always lead with the headline.

## Format matrix

| Audience | Format | Length | Cadence |
|---|---|---|---|
| Exec / leadership | Situation → decision → recommendation → risks | 1 page | Monthly or on-demand |
| Cross-functional team | Weekly update | 200–400 words | Weekly |
| Eng team | PRD + standup | The PRD itself | Sprint |
| Sales / CS | Change brief + FAQ | Bulleted, ≤ 1 page | Per launch |
| Users / customers | Release notes / changelog | Feature-by-feature | Per release |
| Board / investors | Metrics + narrative | 3–5 slides | Quarterly |

---

## Exec review / one-pager

Structure:

```markdown
## [Topic]

**Decision needed:** [Yes / No / By when]
**Recommendation:** [One sentence]

### Situation
2–3 sentences on where things stand. Include the numbers.

### Options considered
1. [Option A] — pro / con
2. [Option B] — pro / con
3. [Option C] — pro / con

### Recommendation
Why this option. What we'll do next.

### Risks & mitigations
- Risk: [X] — Mitigation: [Y]

### Ask
What we need from the room (approval, budget, headcount, air cover).
```

**Rules:**
- No slide should have more than one message.
- Numbers over adjectives. "22% churn" not "concerning churn".
- If a decision isn't needed, don't call the meeting.

---

## Weekly update

```markdown
### Team [X] — week of [date]

**Headline:** [The one thing to know this week]

**Shipped**
- …

**Shipping this week**
- …

**Blocked / need help**
- [Blocker] — need [X] from [Y]

**Metrics**
- [Metric]: [current] (Δ vs. last week)
- …

**Next week**
- …
```

**Rules:**
- Headline first, always.
- Blockers get names and asks, not just a list of problems.
- Metrics with deltas — a number without a comparison is noise.
- If the update repeats last week's blocker, escalate.

---

## Change brief for Sales / CS

Structure:

```markdown
### What's changing
[One paragraph, plain English, no jargon]

### When
[Date, rollout shape]

### Who's affected
[Segments]

### What to say to a customer who asks
> "[Draft one-liner]"

### FAQ
**Q:** …
**A:** …

### Who to escalate to
[Name] for [type of question]
```

**Rules:**
- Give them the exact words. Sales will use whatever's on the page.
- Anticipate the awkward question (price change, feature removal, deprecation).
- Send it 2 weeks before, not 2 days before.

---

## Release notes / changelog

Structure (per release):

```markdown
### [Date] — [Version]

**New**
- [Feature] — [1-line benefit] · [link to docs]

**Improved**
- [Change] — [benefit]

**Fixed**
- [Bug] — [impact]

**Deprecated**
- [Thing] — [when it goes away, migration path]
```

**Rules:**
- Benefit, not feature. "Faster search" not "Rewrote search backend".
- Users read release notes to answer "what changed for me". Keep that lens.

---

## Escalation script

When to escalate: blocker persists > 5 days, or risk to the goal is > 30%.

Script:

```markdown
Hi [name],

I need to escalate [issue] because [impact] and [what I've tried].

**Ask:** [Specific — decision, resource, or air cover].
**Deadline:** [date, and what happens if we miss].
**Context:** [1 paragraph, link to details].

I'm free [times] to talk.
```

**Rules:**
- Lead with the ask.
- Name what you've already tried; don't make them ask.
- Give a deadline with consequences.

---

## Anti-patterns

- **Burying the ask** — decisions get made in the first 30 seconds. Front-load.
- **Passive voice on ownership** — "It was decided that…" hides accountability. Name names.
- **Status update as therapy** — listing everything you did ≠ update. Filter to what matters.
- **Same update every week** — if nothing changed, ask whether you're working on the right thing.
- **Slide theatre** — 30 slides for a 5-line decision. Cut.
