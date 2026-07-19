# 4. Analytics & Data

Modern PMs are expected to be **data-literate operators**: define the right metrics, pull their own data, run experiments, and reason about causality.

## Sub-skills

- **Metrics frameworks** — North Star Metric, AARRR (Pirate Metrics), HEART, input vs. output metrics.
- **Instrumentation** — event taxonomies, naming conventions, tracking plans, working with data engineering.
- **SQL** — SELECT, JOIN, GROUP BY, window functions, CTEs; enough to self-serve.
- **Product analytics tools** — Amplitude, Mixpanel, Heap, PostHog, GA4.
- **Cohort & funnel analysis** — retention curves, conversion funnels, activation definitions.
- **Experimentation** — A/B testing, sample size, statistical significance, novelty & network effects, guardrail metrics.
- **Dashboards & BI** — Looker, Tableau, Metabase; building trustworthy dashboards.
- **Causal reasoning** — difference between correlation and causation, quasi-experiments, holdouts.
- **Reading data critically** — spotting Simpson's paradox, survivorship bias, vanity metrics.

## Why it matters

Data turns opinions into decisions. PMs who can pull their own numbers ship faster and are trusted more by execs.

## What great looks like

- Defines success metrics *before* building, not after.
- Writes their own SQL for 80% of routine questions.
- Knows the current value of every key metric they own.
- Distinguishes signal from noise; doesn't over-react to a single week's data.

## Common pitfalls

- Vanity metrics (total signups) without engagement/retention context.
- Running A/B tests underpowered → false negatives.
- Peeking at experiments and stopping early.
- Instrumentation as an afterthought (untrustworthy data forever).

## Learning resources

- 📘 *Lean Analytics* — Alistair Croll & Benjamin Yoskovitz
- 📘 *Trustworthy Online Controlled Experiments* — Kohavi, Tang, Xu
- 📘 *Storytelling with Data* — Cole Nussbaumer Knaflic
- 🌐 [Mode SQL tutorial](https://mode.com/sql-tutorial/) (free)
- 🌐 [Amplitude Academy](https://academy.amplitude.com/)
- 🌐 [Reforge — Experimentation & Analytics for PMs](https://www.reforge.com/)
- 🎧 *Data-Informed Product Building* — Andrew Chen essays on retention
