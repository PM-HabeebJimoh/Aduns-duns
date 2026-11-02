# Aduns — Global Opportunity-to-Reality Engine

> A system that discovers unmet or poorly served needs anywhere, finds hidden or underused solutions anywhere
> else (including offline), and builds the most profitable, scalable way to connect them.

**Layer 1, the Discovery agents, is built here.** It is universal: no fixed industry, country or region.
It runs **24/7** across **every country on every continent, with equal coverage**, and reads each country's
**own platforms in its own languages**. It uses **free sources only** and **recent data only**: anything
older than `ADUNS_MAX_AGE_DAYS` (default 90) is rejected.

```
     ┌──────────────── 24/7 scheduler: one country per continent per cycle, round-robin ───────────────┐
     │                                                                                                  │
 Need Sensing ──▶ translation (MinT) ──▶ Signal Fusion ──▶ Capability Discovery ──▶ Cross-Border Analogy
 (69 languages,                         (cross-language,     (patents, research,      (ground evidence:
  25+ platforms)                         cross-country)       open designs, local       solution activity vs
                                                              apps, OSM providers,      need pressure, every
                                                              know-how, idle assets)    continent)
                                                                     │
                                                         Offline Scout Coordinator ◀──┘
                                       (missions in the local language, web / SMS / WhatsApp / Telegram intake,
                                        consent, corroboration, human validation, compensation ledger)
```

## Where the signals come from (all free; crawled politely where no API exists)

| Layer | Per-country sources (local language) | Global sources |
|---|---|---|
| **Invisible** (latent / normalized) | Google Trends daily rising searches · Google autocomplete in the local language and storefront ("where to buy…", "why is … so expensive", "shortage of…") | |
| **Scattered** (social) | Bluesky (language-filtered) · YouTube search crawl (uploaded this month) · Reddit country communities · Telegram public channels (auto-discovered) · Mastodon · Lemmy · Google Play reviews of essential-service apps (banking, power, water, health, transport…) | Hacker News · Stack Exchange · CFPB complaints |
| **Visible** (press) | Google News country edition in the local language (last 30 days) · GDELT local press (translingual) | |
| **Structural** (measured / institutional) | WFP measured market-price spikes (~90 countries) · World Bank procurement notices · public tenders that failed: TED lots closed with no winner (all EU/EEA countries), Brazil PNCP revoked or suspended procurements, UK Find a Tender cancellations, Prozorro UA, SECOP CO, SAM.gov US | GDACS disaster alerts · openFDA drug shortages |
| **Local media** (seeded per country) | Wikidata lists each country's own media, agencies and municipalities with their Telegram usernames, YouTube channels and subreddits. These are seeded automatically and crawled (YouTube via official channel RSS). | |

**Snowball discovery:** every Telegram channel (`t.me/…`) and subreddit (`r/…`) mentioned in collected text is
added to `source_registry` and crawled on later sweeps. The source map grows by itself.

**Not used:** X/Twitter, Facebook, Instagram, TikTok and WhatsApp groups. They are login-walled, they have no free
legal access, and their terms forbid crawling. Their content is still reached indirectly through news, YouTube,
Bluesky, Telegram, and field scouts who can report what they see.

**Official statistics** (World Bank WDI) are not treated as ground truth. They are optional, labelled
"secondary", and limited to recent years.

## The five agents

| Agent | Universal behaviour |
|---|---|
| **Need Sensing** | `sweep_country(iso3)` covers the country's languages (69-language lexicon of shortage, price, unmet, normalized and broken-service cues) across the sources above, in parallel and rate-limited per host. Each candidate is date-checked, need-detected in its own language, translated to English with Wikimedia MinT, geo-tagged, and stored with full provenance. `focused_worldwide(focus)` searches one need across 10 languages. |
| **Signal Fusion** | Clusters recent signals by domain (22 open domains plus "general"), using English translations so needs merge across languages and borders. Scores volume, source diversity, layer diversity, intensity, engagement, recency (30-day half-life), latent/normalized share and multi-country spread. Assigns a scope of local, multi-country or global. Writes falsification tests. Keeps a stable identity for each hypothesis and supersedes stale ones. |
| **Capability Discovery** | Searches for functional equivalents: patents (flagging designs not active in the target country), recent research, open hardware and software, programme models, proven vendors, organisations, apps already serving the need in the target country and in reference markets on every continent, mapped local providers (OpenStreetMap), YouTube know-how and skills, and idle or unused assets in the news. |
| **Cross-Border Analogy** | Samples peer countries from every continent. In each one, in its language and over the last 90 days, it measures solution activity (local news of launches and solutions, local apps) against need pressure (local shortage and price news plus sensed signals). Countries with high solutions and low pressure are returned with their headlines and apps as evidence. |
| **Offline Scout Coordinator** | Drafts missions with real OSM venues, local languages, an interview guide and consent script translated into the local language, and a compensation amount. Takes reports through the web form, API, SMS/WhatsApp (Twilio) and Telegram bot. Runs consent checks, auto-corroboration and human validation, and records payments in a ledger. |

## Scale, learning and alerts

* **Distributed workers (free horizontal scale).** Run `ADUNS_WORKER_TOKEN=… python -m aduns serve --daemon` on a
  central machine. Then run `python -m aduns worker --server https://central:8000 --token …` on as many other
  machines as you like (free VMs, laptops, a Raspberry Pi). Countries are leased exclusively, one per continent at a
  time, so coverage stays equal and nothing is swept twice. Each worker uses its own IP and rate-limit budget, so N
  workers make a full world rotation roughly N× faster and get past per-IP blocks. Use `daemon --no-sense` to make
  the central machine only fuse and run the downstream agents.
* **Review loop.** In the Hypotheses tab, or via `POST /api/hypotheses/{id}/review`, a reviewer marks a hypothesis
  as confirmed, rejected, duplicate or noise. The engine learns how reliable each source, language and need type is
  (Beta-smoothed) and scales every hypothesis score by its evidence's learned reliability. Rejected needs stay
  rejected even when the same evidence re-clusters.
* **Emerging needs.** Momentum compares evidence from the last 7 days with the 7 days before. A need is flagged
  `emerging` when momentum is 2× or more with at least 3 recent signals (dashboard filter: "Emerging only").
* **Alerts.** Strong or emerging needs are sent once each to `ADUNS_ALERT_WEBHOOK` (Slack, Discord or any JSON
  endpoint) and/or a Telegram chat (`ADUNS_TELEGRAM_TOKEN` + `ADUNS_ALERT_CHAT_ID`).

## Run

```bash
pip install -r requirements.txt
python -m aduns selftest                  # live check of all 36 data sources
python -m aduns worker --server URL       # extra sweep worker on another machine/IP
python -m aduns serve --daemon            # dashboard + API at :8000 and the 24/7 worldwide loop
python -m aduns daemon                    # the loop alone (Ctrl-C or touch data/STOP to stop)
python -m aduns sweep --country Kenya     # one country, its own languages
python -m aduns discover --focus insulin  # one need, worldwide
python -m aduns coverage                  # signals per continent
docker compose up -d                      # always-on deployment (see also deploy/aduns.service)
```

Dashboard tabs: **World coverage** (every continent and country: signals, sources working or failing, last sweep,
daemon status with start/stop), Hypotheses, Signals (original text plus English), Capabilities, Field network,
and Runs & audit.

| Env var | Effect |
|---|---|
| `ADUNS_MAX_AGE_DAYS` | Recency window (default 90) |
| `ADUNS_CONTACT_EMAIL` | Polite-pool identification; raises the MyMemory fallback translation quota |
| `ADUNS_TELEGRAM_TOKEN` | Enables Telegram bot replies for scouts (`/webhooks/telegram`) and Telegram alerts |
| `ADUNS_WORKER_TOKEN` | Shared secret that enables remote workers (`/api/worker/*`) |
| `ADUNS_ALERT_WEBHOOK`, `ADUNS_ALERT_CHAT_ID` | Where alerts for strong or emerging needs are sent |
| `GITHUB_TOKEN`, `STACKEXCHANGE_KEY` | Higher rate limits (optional) |
| `ANTHROPIC_API_KEY` | Optional Claude synthesis of hypotheses from their evidence |

## Layer 2 — Opportunity design (`aduns/agents/opportunity.py`)

For each strong hypothesis and target country, six agents design how to deliver the solution:

| Agent | What it produces (real inputs) |
|---|---|
| **Market Structure** | Maps the need object to an HS product code, using a curated table for everyday goods and then choosing the code the country actually trades most. Reports market size, volume, landed unit value, supplier countries and supply concentration (HHI) from **UN Comtrade** (the latest year available, 2025 for many countries). Classifies the market (import-dependent, two-way, service, informal). Lists incumbents (local apps, mapped providers, organisations) and barriers (regulation mentions, failed public tenders, patents active in the country). |
| **Localization** | Languages, currency (Wikidata) and live exchange rate. **Local consumer prices** extracted from the country's own news in its language: unit-normalised (for example "¥4,200 per 5kg"), outlier-filtered, and with financial, salary and stock-price contexts rejected. Also infrastructure limits from recent signals (outages, connectivity, fuel), mobile-money and wallet apps, local channels, and the value proposition translated into the local language. |
| **Solution Composition** | Builds concrete offerings from discovered capabilities and lists any gaps: sourced supply (manufacturer FOB listings from Made-in-China, current supplier countries), local make (open or inactive-patent designs, fabricators, know-how), idle capacity, service or platform, and knowledge transfer. |
| **Delivery-Route** | Scores all **14 routes** on 10 criteria (affordability, speed, upfront capital, margin, regulatory, operational simplicity, reliability, defensibility, local impact, scalability). Routes without supporting evidence are marked infeasible, with the reason. |
| **Economics** | Monte Carlo (4,000 runs) of gross and net margin, year-1 revenue and profit, capital, payback and P(profitable), across the top 3 routes, after customer acquisition, field operations, support, fraud, overhead, freight, duty, financing and tax. **Every input is tagged real, official or assumption, with its source.** Sensitivity analysis names the inputs that drive the result; assumptions among them become the validation priorities. **Evidence confidence** (the share of price, cost and market-size inputs that are real) discounts assumption-driven results. If there is no price and no cost, the agent refuses to model and asks for field data. |
| **Defensibility** | Exclusivity potential, network effects, switching costs, local relationships, data advantage, regulatory moat and scale economies, plus imitation risk with notes. |

The 24/7 loop designs up to two opportunities per cycle (validated hypotheses first) and refreshes them every 3 days.
They appear in the dashboard's **Opportunities** tab and at `/api/opportunities`.

## Layer 3 — Governance (`aduns/agents/governance.py`)

Before any money or reputation is committed, every designed opportunity faces a deliberately adversarial board:

| Agent | What it checks (real data) |
|---|---|
| **Verification** | Sorts each key claim (need exists, market size, local price, unit cost, profitability, analogies) into confirmed, corroborated, single-source, claim, assumption or missing. Counts *independent* evidence by merging syndicated or near-identical copies and counting distinct publishing domains, authors and layers. Checks a sample of evidence links for dead pages, and counts validated field observations. |
| **Legal & Safety** | Screens every counterparty (suppliers, holders, incumbents, organisations) against the **US Consolidated Screening List**: 26k entities from OFAC SDN, BIS Entity and Denied Persons lists, ITAR and CMIC, refreshed daily. Matching uses normalised exact and token-set rules, and generic words like "gas" or "world" never match on their own. Also checks the target and supplier countries against OFAC country programs (comprehensive, sectoral or list-based), export-controlled HS codes, the licences a domain needs, and **product recalls** in the last year (openFDA food/drug/device, CPSC), plus privacy jurisdiction (GDPR) and competition-law notes. |
| **Red Team** | Tries to prove the business fails. It **searches for counter-evidence** (surplus, glut, prices falling) in the country's own news, in its language and translated, and keeps only items from that country's edition or naming the country. It **stress-tests** the economics with every assumption at its unfavourable end, and flags unverified tariffs, supply concentration, incumbent strength, single-source or search-only demand, assumption-driven economics, unverified claims, legal issues and rejected field observations. Writes explicit **kill criteria**. Verdict: kill, pilot only with conditions, or proceed to pilot. |
| **Impact** | Beneficiary groups named in the evidence; potential harms (displacing incumbents, undercutting local producers, environmental risk by HS chapter, profiteering optics) with mitigations; local value capture by route; SDG mapping. |
| **Audit** | A **hash-chained, tamper-evident ledger** (any edit breaks verification at the edited entry), a sealed SHA-256 evidence **dossier** per review (every signal, capability, input provenance, agent run, human review and field observation), and the **human approval gate**: Execution requires a named person's approve, approve-with-conditions or reject decision, recorded in the chain. Overriding a "reject" recommendation is recorded as an override. |

The **Governance Board** issues the most cautious recommendation the evidence supports (reject, conditional pilot or
approve pilot), with a numbered list of conditions. The 24/7 loop reviews new or updated opportunities each cycle.
Dashboard: **Governance** tab. API: `/api/governance`, `/api/governance/{id}`, `/api/governance/{id}/approve`,
`/api/ledger/verify`.

## Layer 4 — Execution (`aduns/agents/execution.py`) and the learning loop

| Agent | What it does |
|---|---|
| **Experiment** | Turns governance kill criteria and Economics validation priorities into tests, each with a sample size and decision rule: problem interviews (field mission), verified local price (≥10 quotes), supplier quotes, **tariff verification** (WTO TTD / MacMap / national tariff), smoke test (landing-page or SMS conversion > 2%), and a ≤50-customer pilot (net margin). Evaluates with **Bayesian Beta updates** on real events. Pass or fail is recorded in the ledger. **Measured values replace assumptions in Economics** (kind `measured`), and interview outcomes confirm or reject the hypothesis, so the discovery scoring learns. |
| **Partnership** | Shortlists real counterparties from discovered capabilities and suppliers. Uses **publicly published contacts only**: the app developer's own domain, official websites, OSM contact tags and supplier pages. Every partner is sanctions-screened. Writes outreach drafts in English and the local language. Pipeline stages are set by humans, and moving to "contacted" requires approval. |
| **Operations** | A workflow for the chosen route; a lead-time estimate (great-circle distance from the main supplier country, with explicit assumptions); an inventory policy (reorder point, safety stock); infrastructure adaptations, payment rails, compliance tasks and KPIs. |
| **Customer** | A landing page in English and the local language (waitlist or pre-order, consent required, **no payment taken**) served at `/x/{slug}` **only after approval**. Real visits and sign-ups feed the smoke test. SMS, WhatsApp and Telegram commands: `WAIT <code>`, `ORDER <code> <qty>`, `FEEDBACK <code> <text>`, `STOP`. |
| **Finance** | Actuals from entries a named person records with a reference (revenue, refunds, COGS, CAC, opex, capex) in any currency, converted at live rates. Compares them with the model's p10–p90, flags variances, and writes the measured gross margin back. |
| **Expansion** | Next countries where the same need appears (same cluster or related hypotheses), ranked by real import market size (Comtrade), shared language, continent and sanctions. |

**Safety gates:** the Execution Coordinator plans for any governed opportunity; it skips a "reject" unless a human
has overridden it. Outward actions (publishing a page, contacting a partner, recording money) raise `403` until a
named human approves the opportunity in Governance. Nothing is synthesised: customers, quotes, interviews and money
come only from real people and evidence links.

## Money, tariffs and sanctions (real data)

* **Payments in automatically:** `POST /webhooks/payments/{paystack|flutterwave|stripe|mpesa}`. Each provider's
  signature is verified (Paystack HMAC-SHA512, Flutterwave verif-hash, Stripe signed timestamp with 5-minute replay
  window, M-Pesa Daraja secret URL token). The payment reference must name the opportunity (`AD<id>` or
  `AD<id>-…`). Revenue is recorded only for **human-approved** opportunities, de-duplicated by transaction id,
  zero-decimal currencies are handled, and every payment goes into the audit ledger. Configure
  `ADUNS_PAYSTACK_SECRET`, `ADUNS_FLW_HASH`, `ADUNS_STRIPE_WHSEC`, `ADUNS_MPESA_TOKEN` with your own accounts.
* **Tariffs:** product-line duties from the **USITC HTS** (US) and the **UK Trade Tariff API**. Per-weight duties
  such as "£121/1000 kg" are converted to ad-valorem using the Comtrade unit value. Elsewhere, the World Bank
  country-average applied tariff is used and labelled as an average; the Red Team keeps "verify the product
  tariff" as a condition until an official product-line rate or a measured rate exists.
* **Sanctions screening:** about 40k entities across the **US Consolidated Screening List, EU Financial
  Sanctions, the UN Security Council Consolidated List and the UK Sanctions List**, refreshed daily. A hit on any
  asset-freeze list is a blocker.

## Free 24/7 operation (GitHub Actions)

`.github/workflows/aduns-24x7.yml` runs a 45-minute slice of the worldwide loop every 3 hours
(`daemon --max-minutes 45` stops cleanly). The evidence database persists between runs in the Actions cache, and
a coverage and top-needs report is uploaded as an artifact. Actions minutes are unlimited for **public**
repositories; for a private repository, reduce the schedule as noted in the file. Scheduled workflows run from
the default branch. For real-time operation (dashboard, webhooks, scouts), deploy `docker compose up -d` on any
server.

## Roadmap
- Country-specific licence look-ups (currently a per-sector checklist to verify).
- EU product-level tariffs (TARIC needs a JavaScript renderer; the free API access is not reachable here).
