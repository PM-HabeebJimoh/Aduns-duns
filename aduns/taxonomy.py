"""Need-domain taxonomy.

Maps each problem domain to:
  * keywords used to tag signals and expand queries,
  * real World Bank WDI indicators that measure the *structural* version of the
    need (used by the invisible-need detector and the Cross-Border Analogy Agent),
  * capability search hints (which capability sources are most useful).

`better` = "higher" means a higher indicator value is a better outcome.
"""
from __future__ import annotations

DOMAINS: dict[str, dict] = {
    "energy": {
        "keywords": ["electricity", "power", "outage", "blackout", "generator", "solar", "inverter", "battery",
                     "grid", "diesel", "fuel", "load shedding", "kerosene", "mini-grid", "off-grid", "cooking gas", "lpg"],
        "indicators": [("EG.ELC.ACCS.ZS", "Access to electricity (% of population)", "higher"),
                       ("EG.ELC.ACCS.RU.ZS", "Access to electricity, rural (% of rural population)", "higher"),
                       ("EG.CFT.ACCS.ZS", "Access to clean fuels and technologies for cooking (% of population)", "higher")],
        "capability_sources": ["patents", "github", "papers", "worldbank_projects", "wikidata"],
    },
    "cold_chain": {
        "keywords": ["refrigeration", "cold storage", "cold room", "freezer", "fridge", "cold chain", "spoil", "spoilage",
                     "perishable", "post-harvest", "harvest loss", "preservation", "ice", "chiller", "vaccine storage"],
        "indicators": [("EG.ELC.ACCS.RU.ZS", "Access to electricity, rural (% of rural population)", "higher"),
                       ("LP.LPI.INFR.XQ", "LPI: quality of trade and transport infrastructure (1-5)", "higher")],
        "capability_sources": ["patents", "github", "papers", "worldbank_projects", "wikidata"],
    },
    "water_sanitation": {
        "keywords": ["water", "drinking water", "borehole", "well", "sanitation", "toilet", "sewage", "water filter",
                     "purification", "desalination", "irrigation water", "water tanker", "latrine"],
        "indicators": [("SH.H2O.BASW.ZS", "People using at least basic drinking water services (% of population)", "higher"),
                       ("SH.STA.BASS.ZS", "People using at least basic sanitation services (% of population)", "higher")],
        "capability_sources": ["patents", "github", "papers", "worldbank_projects"],
    },
    "health": {
        "keywords": ["clinic", "hospital", "doctor", "nurse", "diagnosis", "diagnostic", "treatment", "surgery", "dialysis",
                     "specialist", "health", "patient", "medical device", "oxygen", "x-ray", "ultrasound", "lab test", "ambulance"],
        "indicators": [("SH.MED.PHYS.ZS", "Physicians (per 1,000 people)", "higher"),
                       ("SH.XPD.OOPC.CH.ZS", "Out-of-pocket expenditure (% of current health expenditure)", "lower"),
                       ("SH.MED.BEDS.ZS", "Hospital beds (per 1,000 people)", "higher")],
        "capability_sources": ["papers", "clinicaltrials", "patents", "worldbank_projects", "github"],
    },
    "medicines": {
        "keywords": ["drug", "medicine", "medication", "pharmacy", "prescription", "insulin", "antibiotic", "vaccine",
                     "generic", "drug shortage", "injection", "tablet", "api supply"],
        "indicators": [("SH.XPD.OOPC.CH.ZS", "Out-of-pocket expenditure (% of current health expenditure)", "lower"),
                       ("SH.IMM.MEAS", "Immunization, measles (% of children ages 12-23 months)", "higher")],
        "capability_sources": ["papers", "clinicaltrials", "patents", "wikidata"],
    },
    "agriculture": {
        "keywords": ["farm", "farmer", "crop", "harvest", "seed", "fertilizer", "tractor", "irrigation", "pest", "livestock",
                     "feed", "yield", "smallholder", "agro", "processing", "mill", "dryer", "grain", "cassava", "maize"],
        "indicators": [("AG.YLD.CREL.KG", "Cereal yield (kg per hectare)", "higher"),
                       ("AG.CON.FERT.ZS", "Fertilizer consumption (kg per hectare of arable land)", "higher")],
        "capability_sources": ["patents", "github", "papers", "worldbank_projects", "wikidata"],
    },
    "finance": {
        "keywords": ["loan", "credit", "bank account", "payment", "remittance", "insurance", "microfinance", "interest rate",
                     "collateral", "financing", "savings", "mobile money", "invoice", "working capital"],
        "indicators": [("FX.OWN.TOTL.ZS", "Account ownership at a financial institution or mobile-money provider (% of 15+)", "higher"),
                       ("FS.AST.PRVT.GD.ZS", "Domestic credit to private sector (% of GDP)", "higher")],
        "capability_sources": ["papers", "github", "worldbank_projects", "wikidata"],
    },
    "digital": {
        "keywords": ["internet", "broadband", "connectivity", "network", "data cost", "mobile data", "software", "app",
                     "website", "online", "digital", "cloud", "laptop", "phone repair"],
        "indicators": [("IT.NET.USER.ZS", "Individuals using the Internet (% of population)", "higher"),
                       ("IT.NET.BBND.P2", "Fixed broadband subscriptions (per 100 people)", "higher")],
        "capability_sources": ["github", "papers", "worldbank_projects", "wikidata"],
    },
    "logistics": {
        "keywords": ["shipping", "delivery", "freight", "transport", "truck", "logistics", "warehouse", "customs", "port",
                     "courier", "last mile", "road", "import", "export", "clearing", "lead time"],
        "indicators": [("LP.LPI.OVRL.XQ", "Logistics performance index: overall (1-5)", "higher"),
                       ("LP.LPI.CUST.XQ", "LPI: efficiency of customs clearance (1-5)", "higher")],
        "capability_sources": ["github", "papers", "worldbank_projects", "wikidata"],
    },
    "manufacturing": {
        "keywords": ["manufacturer", "factory", "machine", "machinery", "spare part", "spare parts", "component", "supplier",
                     "fabrication", "tooling", "mould", "mold", "cnc", "equipment", "repair", "maintenance", "technician"],
        "indicators": [("NV.IND.MANF.ZS", "Manufacturing, value added (% of GDP)", "higher"),
                       ("TX.VAL.TECH.MF.ZS", "High-technology exports (% of manufactured exports)", "higher")],
        "capability_sources": ["patents", "github", "papers", "usaspending", "wikidata"],
    },
    "education_skills": {
        "keywords": ["school", "teacher", "training", "course", "skill", "skills", "apprentice", "certification", "tutor",
                     "university", "vocational", "learning"],
        "indicators": [("SE.PRM.CMPT.ZS", "Primary completion rate (% of relevant age group)", "higher"),
                       ("SE.TER.ENRR", "School enrollment, tertiary (% gross)", "higher")],
        "capability_sources": ["papers", "github", "worldbank_projects"],
    },
    "housing_construction": {
        "keywords": ["housing", "rent", "construction", "cement", "building material", "contractor", "roofing", "brick",
                     "mortgage", "slum", "affordable housing", "plumber", "electrician"],
        "indicators": [("EN.POP.SLUM.UR.ZS", "Population living in slums (% of urban population)", "lower")],
        "capability_sources": ["patents", "papers", "worldbank_projects", "wikidata"],
    },
    "business_services": {
        "keywords": ["accountant", "lawyer", "permit", "license", "registration", "compliance", "bureaucracy", "paperwork",
                     "certification", "standards", "testing lab", "audit", "contract"],
        "indicators": [("IC.REG.DURS", "Time required to start a business (days)", "lower"),
                       ("IC.FRM.CORR.ZS", "Informal payments to public officials (% of firms)", "lower")],
        "capability_sources": ["github", "papers", "worldbank_projects"],
    },
}

# Universal coverage: additional need domains (no official indicators — sensed from ground signals only).
DOMAINS.update({
    "food": {"keywords": ["food", "bread", "rice", "flour", "sugar", "cooking oil", "maize", "beans", "milk", "meat",
                          "vegetable", "food price", "hunger", "groceries", "baby formula", "eggs", "onion", "tomato"],
             "indicators": [], "capability_sources": ["papers", "github", "patents", "worldbank_projects"]},
    "fuel": {"keywords": ["fuel", "petrol", "gasoline", "diesel", "kerosene", "cooking gas", "lpg", "filling station",
                          "fuel queue", "gas cylinder", "cng"],
             "indicators": [], "capability_sources": ["patents", "papers", "github", "wikidata"]},
    "mobility": {"keywords": ["bus", "taxi", "train", "commute", "traffic", "transport fare", "ride", "metro", "ferry",
                              "motorbike", "public transport", "parking", "visa", "flight", "airline"],
                 "indicators": [], "capability_sources": ["github", "papers", "worldbank_projects"]},
    "jobs_income": {"keywords": ["job", "jobs", "unemployment", "salary", "wage", "hiring", "workers", "labour shortage",
                                 "labor shortage", "skilled workers", "freelance", "pension"],
                    "indicators": [], "capability_sources": ["github", "papers", "worldbank_projects"]},
    "public_services": {"keywords": ["passport", "id card", "birth certificate", "government office", "permit", "court",
                                     "police", "registry", "public service", "tax office", "license renewal", "garbage",
                                     "waste collection", "street light"],
                        "indicators": [], "capability_sources": ["github", "papers", "worldbank_projects"]},
    "safety_security": {"keywords": ["crime", "theft", "robbery", "kidnapping", "security", "fraud", "scam", "violence"],
                        "indicators": [], "capability_sources": ["github", "papers"]},
    "disaster_climate": {"keywords": ["flood", "drought", "earthquake", "cyclone", "heatwave", "wildfire", "landslide",
                                      "storm", "displaced", "evacuation", "relief"],
                         "indicators": [], "capability_sources": ["papers", "github", "worldbank_projects"]},
    "consumer_goods": {"keywords": ["phone", "laptop", "clothes", "shoes", "furniture", "appliance", "spare parts",
                                    "car parts", "tyres", "cosmetics", "electronics"],
                       "indicators": [], "capability_sources": ["patents", "github", "wikidata"]},
    "care": {"keywords": ["childcare", "daycare", "elderly care", "nursing home", "caregiver", "disability", "nanny"],
             "indicators": [], "capability_sources": ["papers", "github"]},
})

GENERAL_INDICATORS = [
    ("NY.GDP.PCAP.PP.KD", "GDP per capita, PPP (constant international $)"),
    ("SP.POP.TOTL", "Population, total"),
]


def classify_domain(text: str) -> tuple[str | None, dict[str, int]]:
    """Return (best_domain, hit_counts) by keyword hits."""
    t = f" {text.lower()} "
    hits: dict[str, int] = {}
    spec_len: dict[str, int] = {}
    for dom, spec in DOMAINS.items():
        n = 0
        for kw in spec["keywords"]:
            if f" {kw}" in t:
                n += 1
                spec_len[dom] = spec_len.get(dom, 0) + len(kw)
        if n:
            hits[dom] = n
    if not hits:
        return None, {}
    # most hits; ties broken by more specific (longer) matched keywords
    best = max(hits, key=lambda d: (hits[d], spec_len.get(d, 0)))
    return best, hits
