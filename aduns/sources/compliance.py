"""Compliance & safety data for the Governance agents (real, free, keyless).

* US Consolidated Screening List (trade.gov; public domain) — OFAC SDN, BIS Entity/Denied Persons, ITAR debarred,
  sectoral sanctions, CMIC … ~26k entities with countries and programs. Ingested into SQLite daily and screened
  with normalised exact + token-set matching.
* openFDA enforcement reports (food / drug / device recalls) and CPSC SaferProducts recalls — known hazards of the
  product category.
* Country sanctions programs (OFAC country-based programs) — comprehensive vs sectoral, with source URLs.
* Regulated-domain licence rules and export-controlled HS chapters — explicit rule tables (verify nationally).
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone

import requests

from .. import config, db, http

CSL_URL = "https://data.trade.gov/downloadable_consolidated_screening_list/v1/consolidated.json"
OFAC_PROGRAMS_URL = "https://ofac.treasury.gov/sanctions-programs-and-country-information"

# OFAC country-based programs (comprehensive embargoes vs. sectoral/list-based programs).
COMPREHENSIVE = {"CUB": "Cuba", "IRN": "Iran", "PRK": "North Korea", "SYR": "Syria"}
BROAD_SECTORAL = {"RUS", "BLR", "VEN"}
SECTORAL = {"RUS": "Russia-related", "BLR": "Belarus", "VEN": "Venezuela-related", "MMR": "Burma (Myanmar)",
            "AFG": "Afghanistan-related (Taliban)", "IRQ": "Iraq-related", "LBY": "Libya", "SOM": "Somalia",
            "SDN": "Sudan", "SSD": "South Sudan", "YEM": "Yemen", "CAF": "Central African Republic",
            "COD": "Democratic Republic of the Congo", "MLI": "Mali", "NIC": "Nicaragua", "LBN": "Lebanon",
            "ZWE": "Zimbabwe (legacy)", "UKR": "Ukraine-/Russia-related (occupied regions)", "ETH": "Ethiopia-related",
            "BIH": "Western Balkans", "SRB": "Western Balkans", "MKD": "Western Balkans", "MNE": "Western Balkans",
            "XKX": "Western Balkans", "HTI": "Haiti-related"}

GDPR = {"AUT", "BEL", "BGR", "HRV", "CYP", "CZE", "DNK", "EST", "FIN", "FRA", "DEU", "GRC", "HUN", "IRL", "ITA", "LVA",
        "LTU", "LUX", "MLT", "NLD", "POL", "PRT", "ROU", "SVK", "SVN", "ESP", "SWE", "ISL", "LIE", "NOR"}

# What usually needs a licence / registration (generic; the exact national regime must be verified).
LICENSED_DOMAINS = {
    "medicines": ["Pharmaceutical import/wholesale licence", "Product registration with the national medicines regulator",
                  "Pharmacy licence for dispensing", "Good Distribution Practice (cold chain for biologics)"],
    "health": ["Health facility / professional licensing", "Medical device registration", "Patient-data protection"],
    "food": ["Food business registration / hygiene certification", "Import permit & phytosanitary/veterinary certificate",
             "Product labelling & standards (national bureau of standards)"],
    "agriculture": ["Phytosanitary / veterinary import permits", "Seed & fertiliser registration"],
    "fuel": ["Petroleum products import / storage / retail licence", "Fire safety & environmental permits",
             "Price-regulated product in many countries"],
    "energy": ["Electricity generation/distribution licence (mini-grids)", "Equipment standards certification"],
    "finance": ["Central-bank licence (payments, lending, deposits)", "KYC/AML obligations", "Consumer-credit rules"],
    "water_sanitation": ["Water-quality standards & utility permits"],
    "cold_chain": ["Food-safety cold-chain standards", "Refrigerant (F-gas) regulations"],
    "mobility": ["Transport operator licence", "Vehicle & driver regulations"],
    "public_services": ["Government contracting rules / public-procurement law"],
    "education_skills": ["Accreditation of training providers"],
    "care": ["Care-facility licensing & safeguarding checks"],
    "digital": ["Telecom / data-protection registration where applicable"],
}

# Export-controlled or dual-use HS headings (4-digit prefixes).
EXPORT_CONTROLLED = {"93": "arms & ammunition", "2844": "radioactive elements", "2845": "isotopes",
                     "3601": "propellant powders", "3602": "explosives", "3603": "detonators", "8806": "drones",
                     "8802": "aircraft", "8710": "military vehicles", "9013": "lasers", "2812": "chemical-weapon precursors",
                     "2853": "chemical precursors"}

# generic words that are never, on their own, evidence that a counterparty is a listed entity
GENERIC = {"gas", "oil", "world", "water", "milk", "bank", "energy", "power", "fuel", "food", "foods", "trade", "global",
           "star", "union", "national", "general", "new", "best", "first", "united", "service", "services", "market",
           "health", "pharmacy", "medical", "solar", "tech", "technology", "industries", "industry", "petroleum",
           "investment", "investments", "capital", "finance", "group", "agro", "dairy", "farm", "transport", "logistics",
           "center", "centre", "store", "shop", "mart", "supply", "import", "export", "oil gas", "rice", "sugar"}
_STOP = {"ltd", "limited", "llc", "inc", "co", "company", "corp", "corporation", "plc", "sa", "srl", "gmbh", "ag", "the",
         "group", "holding", "holdings", "international", "trading", "of", "and", "jsc", "ooo", "pjsc", "bv"}


def _norm(name: str) -> str:
    n = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", n)).strip()


def _tokens(name: str) -> frozenset[str]:
    return frozenset(t for t in _norm(name).split() if t not in _STOP and len(t) > 1)


def _ensure() -> None:
    with db.tx() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS screening_entities (id TEXT PRIMARY KEY, name TEXT, norm TEXT,
                     alt TEXT, source TEXT, programs TEXT, country TEXT, url TEXT)""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_screen_norm ON screening_entities(norm)")


def refresh_screening_list(max_age_s: int = 86400) -> int:
    """Download and ingest the US Consolidated Screening List (streamed; not kept in the HTTP cache)."""
    _ensure()
    st = db.q1("SELECT at FROM daemon_state WHERE key='screening_list'")
    if st and time.time() - st["at"] < max_age_s:
        return db.q1("SELECT COUNT(*) n FROM screening_entities")["n"]
    entities: list[tuple] = []
    r = requests.get(CSL_URL, timeout=180, headers={"User-Agent": config.USER_AGENT})
    r.raise_for_status()
    for e in r.json().get("results", []):
        entities.append((f"US:{e.get('id')}", e.get("name"), json.dumps(e.get("alt_names") or []), e.get("source"),
                         json.dumps(e.get("programs") or []), e.get("country"), e.get("source_information_url")))
    for name, fn in (("EU", _eu_list), ("UN", _un_list), ("UK", _uk_list)):
        try:
            got = fn()
            entities += got
            http._health(f"sanctions_{name.lower()}", True)
        except Exception as ex:  # noqa: BLE001 — one list failing must not drop the others
            http._health(f"sanctions_{name.lower()}", False, str(ex)[:300])
    with db.tx() as c:
        c.execute("DELETE FROM screening_entities")
        for (eid, name, alts, src, progs, country, url) in entities:
            if name:
                c.execute("INSERT OR REPLACE INTO screening_entities VALUES (?,?,?,?,?,?,?,?)",
                          (eid, name, _norm(name), alts, src, progs, country, url))
        c.execute("INSERT OR REPLACE INTO daemon_state (key, value, at) VALUES ('screening_list', ?, ?)",
                  (str(len(entities)), time.time()))
    http._health("screening_list", True)
    _index.clear()
    return len(entities)


EU_URL = "https://webgate.ec.europa.eu/fsd/fsf/public/files/csvFullSanctionsList_1_1/content?token=dG9rZW4tMjAxNw"
UN_URL = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"
UK_URL = "https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.csv"


def _eu_list() -> list[tuple]:
    import csv
    import io
    r = requests.get(EU_URL, timeout=180, headers={"User-Agent": config.USER_AGENT})
    r.raise_for_status()
    rows = csv.DictReader(io.StringIO(r.content.decode("utf-8-sig", "replace")), delimiter=";")
    by: dict[str, dict] = {}
    for row in rows:
        lid = row.get("Entity_LogicalId")
        nm = (row.get("NameAlias_WholeName") or "").strip()
        if not lid or not nm:
            continue
        d = by.setdefault(lid, {"names": [], "prog": row.get("Entity_Regulation_Programme"),
                                "country": row.get("Address_CountryIso2Code") or row.get("Citizenship_CountryIso2Code")})
        if nm not in d["names"]:
            d["names"].append(nm)
    return [(f"EU:{k}", v["names"][0], json.dumps(v["names"][1:6]), "EU Financial Sanctions (FSF)",
             json.dumps([v["prog"]] if v["prog"] else []), v["country"],
             "https://data.europa.eu/data/datasets/consolidated-list-of-persons-groups-and-entities-subject-to-eu-financial-sanctions")
            for k, v in by.items()]


def _un_list() -> list[tuple]:
    import xml.etree.ElementTree as ET
    r = requests.get(UN_URL, timeout=180, headers={"User-Agent": config.USER_AGENT})
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = []
    for tag in ("INDIVIDUAL", "ENTITY"):
        for e in root.iter(tag):
            parts = [e.findtext(k) or "" for k in ("FIRST_NAME", "SECOND_NAME", "THIRD_NAME", "FOURTH_NAME")]
            name = " ".join(p for p in parts if p).strip()
            aliases = [a.findtext("ALIAS_NAME") for a in e.iter(f"{tag}_ALIAS") if a.findtext("ALIAS_NAME")]
            out.append((f"UN:{e.findtext('REFERENCE_NUMBER') or e.findtext('DATAID')}", name, json.dumps(aliases[:6]),
                        "UN Security Council Consolidated List", json.dumps([e.findtext("UN_LIST_TYPE") or ""]),
                        (e.findtext("NATIONALITY/VALUE") or "")[:60], UN_URL))
    return out


def _uk_list() -> list[tuple]:
    import csv
    import io
    r = requests.get(UK_URL, timeout=180, headers={"User-Agent": config.USER_AGENT})
    r.raise_for_status()
    lines = r.content.decode("utf-8-sig", "replace").splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("Last Updated"))
    by: dict[str, dict] = {}
    for row in csv.DictReader(io.StringIO("\n".join(lines[start:]))):
        uid = row.get("Unique ID")
        parts = [row.get(f"Name {i}") or "" for i in (1, 2, 3, 4, 5)]
        nm = " ".join(p for p in parts + [row.get("Name 6") or ""] if p).strip()
        if not uid or not nm:
            continue
        d = by.setdefault(uid, {"names": [], "regime": row.get("Regime Name")})
        if nm not in d["names"]:
            d["names"].append(nm)
    return [(f"UK:{k}", v["names"][0], json.dumps(v["names"][1:6]), "UK Sanctions List (FCDO/OFSI)",
             json.dumps([v["regime"]] if v["regime"] else []), None, UK_URL) for k, v in by.items()]


_index: dict = {}


def _load_index():
    if not _index:
        for e in db.q("SELECT id, name, alt, source, programs, country, url FROM screening_entities"):
            for n in [e["name"]] + db.loads(e["alt"], []):
                toks = _tokens(n)
                if toks:
                    _index.setdefault(min(toks), []).append((toks, n, e))
    return _index


def screen(name: str) -> list[dict]:
    """Match a counterparty name against the screening list (exact normalised or ≥2-token token-set match)."""
    toks = _tokens(name)
    if not toks or not name:
        return []
    distinctive = {t for t in toks if t not in GENERIC and len(t) >= 3}
    if not distinctive:
        return []          # e.g. 'GAS', 'World', 'E.S. Gas and Gas' — no distinctive name to match on
    idx = _load_index()
    hits, seen = [], set()
    for t in toks:
        for etoks, ename, e in idx.get(t, []):
            if e["id"] in seen:
                continue
            inter = len(toks & etoks)
            if not (distinctive & etoks):
                continue
            if len(toks) == 1 and len(next(iter(toks))) < 5:
                continue      # single short token: too weak for a match
            if etoks == toks or (inter >= 2 and inter / max(len(toks), len(etoks)) >= 0.8):
                seen.add(e["id"])
                hits.append({"query": name, "matched": ename, "source": e["source"], "country": e["country"],
                             "programs": db.loads(e["programs"], []), "url": e["url"],
                             "match": "exact" if etoks == toks else "token-set"})
    return hits


# --------------------------------------------------------------------- recalls
def fda_recalls(term: str, kind: str = "food", days: int = 365, limit: int = 20) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y%m%d")
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    try:
        data = http.fetch(f"https://api.fda.gov/{kind}/enforcement.json",
                          {"search": f'product_description:"{term}" AND report_date:[{since} TO {today}]', "limit": limit},
                          source="openfda_recalls", ttl=24 * 3600, retries=1)
    except http.FetchError as e:
        if "404" in str(e):
            return []          # openFDA answers 404 for "no matches"
        raise
    return [{"product": r.get("product_description", "")[:200], "reason": r.get("reason_for_recall", "")[:300],
             "class": r.get("classification"), "date": r.get("report_date"), "firm": r.get("recalling_firm"),
             "country": r.get("country"), "source": f"openFDA {kind} enforcement",
             "url": "https://www.accessdata.fda.gov/scripts/ires/index.cfm"} for r in data.get("results", [])]


def cpsc_recalls(term: str, days: int = 365) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    data = http.fetch("https://www.saferproducts.gov/RestWebServices/Recall",
                      {"format": "json", "RecallDateStart": since, "ProductName": term}, source="cpsc", ttl=24 * 3600)
    return [{"product": r.get("Title"), "reason": "; ".join(h.get("Name", "") for h in (r.get("Hazards") or []))[:300],
             "date": (r.get("RecallDate") or "")[:10], "source": "CPSC", "url": r.get("URL")} for r in data or []]


def country_sanctions(iso3: str) -> dict | None:
    if iso3 in COMPREHENSIVE:
        return {"level": "comprehensive", "program": COMPREHENSIVE[iso3], "url": OFAC_PROGRAMS_URL}
    if iso3 in SECTORAL:
        return {"level": "sectoral" if iso3 in BROAD_SECTORAL else "list-based (named persons)",
                "program": SECTORAL[iso3], "url": OFAC_PROGRAMS_URL}
    return None


def export_controlled(hs: str | None) -> str | None:
    if not hs:
        return None
    for k, v in EXPORT_CONTROLLED.items():
        if hs.startswith(k):
            return v
    return None



def recall_channels(hs: str | None) -> list[str]:
    """Which recall databases are relevant for a product (by HS chapter)."""
    if not hs:
        return []
    ch = int(hs[:2])
    if 1 <= ch <= 24:
        return ["fda:food"]
    if ch == 30:
        return ["fda:drug"]
    if ch == 90:
        return ["fda:device", "cpsc"]
    if ch in (39, 40, 42, 61, 62, 63, 64, 73, 82, 83, 84, 85, 87, 94, 95, 96):
        return ["cpsc"]
    return []
