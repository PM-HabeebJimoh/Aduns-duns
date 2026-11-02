# Aduns — Global Opportunity-to-Reality Engine

> A system that discovers unmet or poorly served needs anywhere, finds hidden or underused solutions
> anywhere else (including offline), and builds the most profitable, scalable way to connect them.

This repository is being built layer by layer. **Layer 1, the Discovery agents, is built here.** It runs
on **real, free, public data only**. Nothing is simulated or synthetic. Field observations exist only
when a real person submits them.

```
 Sense ─▶ Detect ─▶ Explain ─▶ Match ─────────────▶ (Layer 2: invent delivery routes, economics …)
   │         │          │        ├─ Capability map
   │         │          │        └─ Cross-border analogies
   └─ offline scouts ◀──┴────────── field missions (validate / falsify)
```

## The five Discovery agents

| Agent | What it does | Real data sources |
|---|---|---|
| **Need Sensing** (`aduns/agents/need_sensing.py`) | Detects unmet, unaffordable, scarce, inefficient, *normalized* ("always takes two days", "only available abroad") and *latent* needs across four layers. It also finds **structural access gaps**: countries that do far worse than their income peers on a World Bank indicator. | GDELT (global news), Google News RSS, Hacker News, Stack Exchange (18 sites), Reddit RSS, Lemmy, Mastodon, Google Autocomplete (search demand by city), openFDA drug shortages, SAM.gov "sources sought", World Bank procurement notices, World Bank WDI |
| **Signal Fusion** (`signal_fusion.py`) | Clusters weak signals (TF-IDF + average-linkage) into testable hypotheses. Each hypothesis is scored on volume, source diversity, layer diversity, intensity, engagement, recency, latent/normalized share and geographic focus. It explains *why* the gap exists (affordability, distribution, regulation, infrastructure, awareness, trust, capability, supply, finance) and writes **falsification tests**. | all stored signals |
| **Capability Discovery** (`capability_discovery.py`) | Finds functional equivalents: patents (it flags families **not active** in the target country, whose designs may be free to make there), research, open-source designs, implemented programme models, proven public-sector vendors, clinical interventions and organisations. Results are ranked by relevance and tagged with the delivery routes they suggest. | Google Patents, Crossref, Europe PMC, arXiv, GitHub, World Bank projects, USAspending, ClinicalTrials.gov, Wikidata |
| **Cross-Border Analogy** (`cross_border_analogy.py`) | **Positive deviance.** Among countries within 2× of the target's GDP per capita (PPP), it finds those with much better outcomes and strong 10-year improvement. It then attaches evidence of *how* they did it: World Bank projects in that country and papers. | World Bank WDI, World Bank projects, Crossref |
| **Offline Scout Coordinator** (`offline_scout.py`) | Designs field missions with real OSM venues near major cities, official languages, target respondents, a consent script and a non-leading interview guide (normalized-need, analogy and capability probes, plus Van Westendorp pricing questions). It registers scouts only with consent and takes observations from the web, the API, or SMS/WhatsApp (Twilio webhook). Observations are corroborated against other scouts and online signals, then go to human validation and a **compensation ledger**. | OpenStreetMap Nominatim, Wikidata, the people in the field |

Every record keeps its provenance (source, URL, retrieval time, content hash). Every agent run and
decision is written to `agent_runs` and `audit_log`. Evidence levels move from
`claim` (one source) to `corroborated` (two or more independent sources) to `field_verified`
(two or more validated field observations).

## Run it

```bash
pip install -r requirements.txt
python -m aduns serve                 # dashboard at http://localhost:8000, scout form at /scout, API docs at /docs

# or from the CLI
python -m aduns discover --focus "solar freezer" --country Nigeria --top 5
python -m aduns gaps --country NGA              # structural gaps vs income peers, all domains
python -m aduns analogies --country NGA --domain energy
python -m aduns show
python -m pytest -q
```

Optional environment variables (the system works without any of them):

| Variable | Effect |
|---|---|
| `ADUNS_CONTACT_EMAIL` | Sent to polite-pool APIs (Crossref, Nominatim) |
| `GITHUB_TOKEN`, `STACKEXCHANGE_KEY` | Higher rate limits |
| `ANTHROPIC_API_KEY` | Turns on optional Claude synthesis of hypotheses. It is stored separately from the evidence and is told to use only that evidence. |
| `ADUNS_DB` | SQLite path (default `data/aduns.db`) |
| `ADUNS_SCOUT_REWARD_SUBMITTED` / `_VALIDATED` | Scout compensation |

### SMS / WhatsApp field intake
Point a Twilio number (SMS or WhatsApp) to `POST /webhooks/sms`. The commands are:
`JOIN name | role | country | town`, `MISSIONS`, `OBS <code> <text>`,
`PRICE <code> <amount> <CUR> <item> @ <place>`, and `STOP`.

## Roadmap (next layers)
2. **Opportunity design.** Solution Composition, Localization, Delivery-Route (14 routes), Economics (net margin after customer acquisition, field operations, fraud, tax and financing), Market Structure, Defensibility.
3. **Execution.** Experiment, Partnership, Operations, Customer, Finance, Expansion.
4. **Governance.** Verification, Legal & Safety, Red-Team, Impact, Audit. The provenance and audit tables they need already exist.
5. **Learning loop.** Real outcomes feed back into scoring.
