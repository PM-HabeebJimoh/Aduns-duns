"""Capability-side connectors (Network B): hidden or underused solutions anywhere.

Returned record shape:
    {source, capability_type, external_id, url, title, description, holder, countries, year,
     maturity (0..1), transferability [routes], extra}

capability_type ∈
    ip_patent        – patented invention (active → licence route; expired → free-to-use design)
    research         – peer-reviewed / preprint research (tech transfer, localisation)
    open_design      – open-source hardware/software (manufacture or deploy locally)
    program_model    – an implemented development programme (institutional / delivery model)
    proven_vendor    – firm that has already delivered this to a public buyer (supplier / partner)
    clinical         – clinical intervention under study (health)
    organization     – company / institution holding the capability (Wikidata)
"""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from urllib.parse import quote

from .. import config, http
from ..nlp import clean

_TTL = 3 * 24 * 3600


def _year(s) -> int | None:
    try:
        return int(str(s)[:4])
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ Google Patents
def google_patents(query: str, limit: int = 15) -> list[dict]:
    q = f"q=({quote(query)})&num={min(limit, 100)}&sort=new"
    data = http.fetch("https://patents.google.com/xhr/query", {"url": q, "exp": ""}, source="googlepatents", ttl=_TTL)
    out = []
    for cl in (data.get("results") or {}).get("cluster", []):
        for r in cl.get("result", []):
            p = r.get("patent", {})
            num = p.get("publication_number")
            if not num:
                continue
            states = [(cs.get("country_code"), (cs.get("best_patent_stage") or {}).get("state"))
                      for cs in ((p.get("family_metadata") or {}).get("aggregated") or {}).get("country_status", [])]
            active = [c for c, s in states if s == "ACTIVE"]
            expired = [c for c, s in states if s in ("EXPIRED", "NOT_ACTIVE", "WITHDRAWN", "LAPSED")]
            granted = bool(p.get("grant_date"))
            # Expired/lapsed family = design is free to use where not active: hidden capability.
            routes = ["license_and_localize"] if active else ["manufacture_locally", "open_design_adaptation"]
            maturity = 0.6 if granted else 0.35
            out.append({
                "source": "googlepatents", "capability_type": "ip_patent", "external_id": num,
                "url": f"https://patents.google.com/patent/{num}/en",
                "title": clean(p.get("title")), "description": clean(p.get("snippet")),
                "holder": clean(p.get("assignee")) or clean(p.get("inventor")),
                "countries": [c for c, _ in states], "year": _year(p.get("priority_date")),
                "maturity": maturity, "transferability": routes,
                "extra": {"active_in": active, "inactive_in": expired, "granted": granted,
                          "filing_date": p.get("filing_date"), "grant_date": p.get("grant_date")},
            })
    return out[:limit]


# ----------------------------------------------------------------------- Crossref
def crossref(query: str, limit: int = 15) -> list[dict]:
    params = {"query": query, "rows": min(limit, 50),
              "select": "DOI,title,published,container-title,abstract,URL,author,type,is-referenced-by-count",
              "filter": "type:journal-article"}
    if config.CONTACT_EMAIL:
        params["mailto"] = config.CONTACT_EMAIL
    data = http.fetch("https://api.crossref.org/works", params, source="crossref", ttl=_TTL)
    out = []
    for it in (data.get("message") or {}).get("items", []):
        title = clean((it.get("title") or [""])[0])
        if not title:
            continue
        year = None
        dp = (it.get("published") or {}).get("date-parts")
        if dp and dp[0]:
            year = dp[0][0]
        cites = it.get("is-referenced-by-count") or 0
        authors = it.get("author") or []
        aff = [a.get("name") for au in authors for a in (au.get("affiliation") or []) if a.get("name")]
        out.append({
            "source": "crossref", "capability_type": "research", "external_id": it.get("DOI"),
            "url": it.get("URL") or f"https://doi.org/{it.get('DOI')}", "title": title,
            "description": clean(it.get("abstract"))[:1500],
            "holder": "; ".join(dict.fromkeys(aff))[:300] or ", ".join(
                f"{a.get('family', '')}" for a in authors[:3]),
            "countries": [], "year": year,
            "maturity": round(min(0.6, 0.2 + math.log1p(cites) / 15), 3),
            "transferability": ["license_and_localize", "expert_transfer"],
            "extra": {"journal": (it.get("container-title") or [""])[0], "citations": cites},
        })
    return out


# ---------------------------------------------------------------------- EuropePMC
def europepmc(query: str, limit: int = 15) -> list[dict]:
    data = http.fetch("https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                      {"query": query, "format": "json", "pageSize": min(limit, 100), "resultType": "core"},
                      source="europepmc", ttl=_TTL)
    out = []
    for r in (data.get("resultList") or {}).get("result", []):
        affs = r.get("affiliation") or ""
        out.append({
            "source": "europepmc", "capability_type": "research", "external_id": r.get("id"),
            "url": f"https://europepmc.org/article/{r.get('source')}/{r.get('id')}",
            "title": clean(r.get("title")), "description": clean(r.get("abstractText"))[:1500],
            "holder": affs[:300], "countries": [], "year": _year(r.get("pubYear")),
            "maturity": round(min(0.6, 0.2 + math.log1p(r.get("citedByCount") or 0) / 15), 3),
            "transferability": ["license_and_localize", "expert_transfer"],
            "extra": {"journal": r.get("journalTitle"), "citations": r.get("citedByCount"), "doi": r.get("doi")},
        })
    return out


# -------------------------------------------------------------------------- arXiv
_A = {"a": "http://www.w3.org/2005/Atom"}


def arxiv(query: str, limit: int = 10) -> list[dict]:
    terms = " AND ".join(f"all:{w}" for w in query.split()[:6])
    body = http.fetch("https://export.arxiv.org/api/query",
                      {"search_query": terms, "max_results": min(limit, 50), "sortBy": "relevance"},
                      source="arxiv", ttl=_TTL, expect="text")
    root = ET.fromstring(body)
    out = []
    for e in root.findall("a:entry", _A):
        aid = e.findtext("a:id", default="", namespaces=_A)
        out.append({
            "source": "arxiv", "capability_type": "research", "external_id": aid, "url": aid,
            "title": clean(e.findtext("a:title", default="", namespaces=_A)),
            "description": clean(e.findtext("a:summary", default="", namespaces=_A))[:1500],
            "holder": ", ".join(a.findtext("a:name", default="", namespaces=_A) for a in e.findall("a:author", _A)[:4]),
            "countries": [], "year": _year(e.findtext("a:published", default="", namespaces=_A)),
            "maturity": 0.2, "transferability": ["expert_transfer", "license_and_localize"], "extra": {},
        })
    return out


# ------------------------------------------------------------------ GitHub (open designs)
def github_repos(query: str, limit: int = 15) -> list[dict]:
    data = http.fetch("https://api.github.com/search/repositories",
                      {"q": query, "sort": "stars", "order": "desc", "per_page": min(limit, 50)},
                      source="github", ttl=_TTL, headers={"Accept": "application/vnd.github+json"})
    out = []
    for r in data.get("items", []):
        lic = (r.get("license") or {}).get("spdx_id")
        stars = r.get("stargazers_count") or 0
        out.append({
            "source": "github", "capability_type": "open_design", "external_id": r.get("full_name"),
            "url": r.get("html_url"), "title": r.get("full_name"),
            "description": clean(r.get("description")), "holder": (r.get("owner") or {}).get("login"),
            "countries": [], "year": _year(r.get("created_at")),
            "maturity": round(min(0.8, 0.15 + math.log1p(stars) / 12 + (0.1 if lic and lic != "NOASSERTION" else 0)), 3),
            "transferability": ["manufacture_locally", "software_layer", "open_design_adaptation"],
            "extra": {"stars": stars, "license": lic, "topics": r.get("topics", []),
                      "pushed_at": r.get("pushed_at"), "archived": r.get("archived")},
        })
    return out


# ------------------------------------------------------- World Bank programme models
def worldbank_programs(query: str, limit: int = 15) -> list[dict]:
    from . import worldbank
    out = []
    for p in worldbank.projects(query, limit=limit):
        closed = (p.get("status") or "").lower() == "closed"
        out.append({
            "source": "worldbank_projects", "capability_type": "program_model", "external_id": p["id"],
            "url": p.get("url"), "title": p.get("name") or p["id"], "description": clean(p.get("abstract"))[:1500],
            "holder": p.get("country"), "countries": p.get("countrycode") if isinstance(p.get("countrycode"), list) else
            ([p["countrycode"]] if p.get("countrycode") else []),
            "year": _year(p.get("approved")),
            "maturity": 0.7 if closed else 0.45,
            "transferability": ["policy_pathway", "cooperative_model", "enable_existing_operator", "demand_aggregation"],
            "extra": {"status": p.get("status"), "amount": p.get("amount"), "country": p.get("country")},
        })
    return out


# ----------------------------------------------------- USAspending (proven vendors)
def usaspending_vendors(keywords: list[str], limit: int = 15) -> list[dict]:
    body = {
        "filters": {"keywords": keywords[:5], "award_type_codes": ["A", "B", "C", "D"],
                    "time_period": [{"start_date": "2018-10-01", "end_date": "2026-09-30"}]},
        "fields": ["Award ID", "Recipient Name", "Award Amount", "Description", "Awarding Agency", "Start Date",
                   "generated_internal_id"],
        "limit": min(limit, 100), "page": 1, "sort": "Award Amount", "order": "desc",
    }
    data = http.fetch("https://api.usaspending.gov/api/v2/search/spending_by_award/", method="POST",
                      json_body=body, source="usaspending", ttl=_TTL)
    out = []
    for r in data.get("results", []):
        amt = r.get("Award Amount") or 0
        out.append({
            "source": "usaspending", "capability_type": "proven_vendor",
            "external_id": r.get("generated_internal_id") or r.get("Award ID"),
            "url": f"https://www.usaspending.gov/award/{r.get('generated_internal_id')}",
            "title": f"{r.get('Recipient Name')} — {clean(r.get('Description'))[:120]}",
            "description": clean(r.get("Description")), "holder": r.get("Recipient Name"), "countries": ["USA"],
            "year": _year(r.get("Start Date")),
            "maturity": round(min(0.9, 0.5 + math.log1p(amt) / 60), 3),
            "transferability": ["import_and_resell", "local_distribution_partnership", "license_and_localize"],
            "extra": {"amount_usd": amt, "agency": r.get("Awarding Agency")},
        })
    return out


# ----------------------------------------------------------- ClinicalTrials.gov
def clinical_trials(query: str, limit: int = 10) -> list[dict]:
    data = http.fetch("https://clinicaltrials.gov/api/v2/studies",
                      {"query.term": query, "pageSize": min(limit, 50),
                       "fields": "NCTId,BriefTitle,OverallStatus,LeadSponsorName,LocationCountry,BriefSummary,StartDate,Phase"},
                      source="clinicaltrials", ttl=_TTL)
    out = []
    for s in data.get("studies", []):
        ps = s.get("protocolSection", {})
        nct = ps.get("identificationModule", {}).get("nctId")
        status = ps.get("statusModule", {}).get("overallStatus")
        countries = sorted({l.get("country") for l in (ps.get("contactsLocationsModule") or {}).get("locations", [])
                            if l.get("country")})
        out.append({
            "source": "clinicaltrials", "capability_type": "clinical", "external_id": nct,
            "url": f"https://clinicaltrials.gov/study/{nct}",
            "title": ps.get("identificationModule", {}).get("briefTitle"),
            "description": clean(ps.get("descriptionModule", {}).get("briefSummary"))[:1500],
            "holder": ps.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name"),
            "countries": countries, "year": _year(ps.get("statusModule", {}).get("startDateStruct", {}).get("date")),
            "maturity": 0.6 if status == "COMPLETED" else 0.3,
            "transferability": ["expert_transfer", "service_instead_of_product"],
            "extra": {"status": status, "phases": ps.get("designModule", {}).get("phases")},
        })
    return out


# --------------------------------------------------------- Wikidata organisations
def wikidata_orgs(query: str, limit: int = 15) -> list[dict]:
    """Businesses/organisations whose Wikidata description or label matches the capability."""
    sparql = f"""SELECT ?item ?itemLabel ?itemDescription ?countryLabel ?website ?inception WHERE {{
      SERVICE wikibase:mwapi {{
        bd:serviceParam wikibase:endpoint "www.wikidata.org"; wikibase:api "Search";
                        mwapi:srsearch "{query.replace('"', '')} haswbstatement:P31=Q4830453"; mwapi:srlimit "{min(limit, 50)}".
        ?item wikibase:apiOutputItem mwapi:title. }}
      OPTIONAL {{ ?item wdt:P17 ?country. }}
      OPTIONAL {{ ?item wdt:P856 ?website. }}
      OPTIONAL {{ ?item wdt:P571 ?inception. }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }}"""
    data = http.fetch("https://query.wikidata.org/sparql", {"query": sparql, "format": "json"},
                      source="wikidata", ttl=_TTL, headers={"Accept": "application/sparql-results+json"})
    seen: dict[str, dict] = {}
    for b in data["results"]["bindings"]:
        qid = b["item"]["value"].rsplit("/", 1)[-1]
        rec = seen.setdefault(qid, {
            "source": "wikidata", "capability_type": "organization", "external_id": qid,
            "url": b.get("website", {}).get("value") or f"https://www.wikidata.org/wiki/{qid}",
            "title": b.get("itemLabel", {}).get("value", qid),
            "description": b.get("itemDescription", {}).get("value", ""), "holder": b.get("itemLabel", {}).get("value"),
            "countries": [], "year": _year(b.get("inception", {}).get("value")), "maturity": 0.6,
            "transferability": ["import_and_resell", "local_distribution_partnership", "license_and_localize"],
            "extra": {"wikidata": f"https://www.wikidata.org/wiki/{qid}"},
        })
        c = b.get("countryLabel", {}).get("value")
        if c and c not in rec["countries"]:
            rec["countries"].append(c)
    return list(seen.values())


CAPABILITY_SOURCES = {
    "patents": google_patents,
    "papers": crossref,
    "europepmc": europepmc,
    "arxiv": arxiv,
    "github": github_repos,
    "worldbank_projects": worldbank_programs,
    "clinicaltrials": clinical_trials,
    "wikidata": wikidata_orgs,
}
