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
| **Structural** (measured / institutional) | WFP measured market-price spikes (~90 countries) · World Bank procurement notices · failed and cancelled tenders (Prozorro UA, SECOP CO, SAM.gov US) | GDACS disaster alerts · openFDA drug shortages |

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

## Run

```bash
pip install -r requirements.txt
python -m aduns selftest                  # live check of all 31 data sources
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
| `ADUNS_TELEGRAM_TOKEN` | Enables Telegram bot replies for scouts (`/webhooks/telegram`) |
| `GITHUB_TOKEN`, `STACKEXCHANGE_KEY` | Higher rate limits (optional) |
| `ANTHROPIC_API_KEY` | Optional Claude synthesis of hypotheses from their evidence |

## Roadmap (next layers)
2. Opportunity design: solution composition, localization, delivery routes, economics, market structure, defensibility.
3. Governance: verification, legal & safety, red team, impact, audit.
4. Execution: experiments, partnerships, operations, customers, finance, expansion.
5. Learning from real outcomes.
