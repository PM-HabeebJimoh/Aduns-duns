# Eval: PRD Quality

Regression tests for the `product-manager` skill. Each case defines an input prompt, the rules the response must satisfy, and the failure modes to watch for.

## Case 1: PRD from feature-first prompt

**Input**
> "Write me a PRD for a chatbot on the pricing page."

**Must satisfy**
- Response asks for the underlying user problem before drafting anything (per `rules/problem-framing.md`).
- If the user answers, the resulting PRD opens with Problem, not Solution.
- Non-goals section is present and non-empty.
- Success metrics include at least one guardrail.

**Failure modes**
- Skill drafts a PRD whose Problem section reads "Users want a chatbot" — fails `rules/problem-framing.md`.
- Skill omits Non-goals — fails `rules/prd-structure.md`.

---

## Case 2: Output-flavored OKR

**Input**
> "Draft an OKR for us to launch the new onboarding by end of Q3."

**Must satisfy**
- Response points out that "launch the new onboarding" is an output, not an outcome.
- Proposed KRs use `<metric> from <baseline> to <target> by <date>` format.
- Baseline is either provided by the user or explicitly marked as `TBD — need from data team`.

**Failure modes**
- Skill accepts "Ship v2 of onboarding by Sep 30" as a KR — fails `rules/okrs.md`.
- Skill invents a plausible-sounding baseline instead of asking or flagging.

---

## Case 3: RICE on 30 items

**Input**
> "Here's our Q3 backlog of 30 items. Score them all with RICE and give me the top 3."

**Must satisfy**
- Response asks whether the situation actually needs RICE, or whether MoSCoW (release scope) or 2×2 (workshop) fits better.
- If RICE is used, table declares a single Reach time window.
- Any item with Confidence < 50% is marked "discover first" rather than scored down.
- Final answer includes a Recommendation section with reasoning, not just a ranking.

**Failure modes**
- Skill fills in Impact = 2 for every item to make the exercise finish — fails `rules/prioritization.md`.
- Skill mixes per-week and per-quarter Reach — fails `rules/prioritization.md`.

---

## Case 4: Launch with no rollback plan

**Input**
> "We're launching Feature X tomorrow. Give me a launch plan."

**Must satisfy**
- Response refuses to advance to 100% until rollback triggers are written as if-then rules.
- Response asks whether kill switch has been tested in staging; if not, flags as blocker.
- Response requires instrumentation + baseline captured before flag enable.
- Response proposes a stage sequence (dogfood → beta → % rollout → GA), not a same-day 100% launch.

**Failure modes**
- Skill produces a same-day 100% rollout plan — fails `rules/launch-safety.md`.
- Skill lists "roll back if things look bad" as the rollback plan — fails `rules/launch-safety.md`.

---

## Case 5: Weekly update with buried headline

**Input**
> "Write our weekly update. Beta opens Monday; legal review is late; activation up 2pp week-over-week; we're on track for 25% rollout Aug 25."

**Must satisfy**
- Update opens with a headline that names the state (beta opens Monday, on track for 25% Aug 25).
- Metrics carry deltas and comparisons, not raw numbers.
- Legal-review blocker names a person and a date.
- Total length ≤ 400 words.

**Failure modes**
- Update opens with paragraph of context before the headline — fails `rules/stakeholder-comms.md`.
- Blocker reads "waiting on legal" with no name or deadline — fails `rules/stakeholder-comms.md`.
