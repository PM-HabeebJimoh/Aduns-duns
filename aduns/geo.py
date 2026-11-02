"""Real-world gazetteer built at runtime from free open data.

* World Bank country API — ISO3/ISO2, name, region, income group, capital, coordinates.
* Wikidata SPARQL      — demonyms, official languages, cities with >1M inhabitants.

Used to geo-tag need signals ("…in Lagos" → NGA) and to plan field missions.
Results are cached in the HTTP cache for 30 days.
"""
from __future__ import annotations

import re
import threading
from functools import lru_cache

from . import http

_WB_COUNTRIES = "https://api.worldbank.org/v2/country"
_SPARQL = "https://query.wikidata.org/sparql"
_TTL = 30 * 24 * 3600
_lock = threading.Lock()

_Q_META = """SELECT ?iso3 (GROUP_CONCAT(DISTINCT ?dem; separator="|") AS ?dems)
 (GROUP_CONCAT(DISTINCT ?langLabel; separator="|") AS ?langs) WHERE {
 ?c wdt:P298 ?iso3; wdt:P31 wd:Q3624078.
 OPTIONAL{?c wdt:P1549 ?dem FILTER(lang(?dem)="en")}
 OPTIONAL{?c wdt:P37 ?lang. ?lang rdfs:label ?langLabel FILTER(lang(?langLabel)="en")}
} GROUP BY ?iso3"""

_Q_CITIES = """SELECT ?iso3 ?cityLabel ?pop ?lat ?lon WHERE {
 ?city wdt:P1082 ?pop. FILTER(?pop > 1000000)
 ?city wdt:P31/wdt:P279? wd:Q515; wdt:P17 ?c. ?c wdt:P298 ?iso3.
 OPTIONAL { ?city p:P625/psv:P625 [ wikibase:geoLatitude ?lat; wikibase:geoLongitude ?lon ] }
 SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }"""

# Names that are also common English words / ambiguous as standalone tokens.
_AMBIGUOUS = {"chad", "georgia", "jordan", "turkey", "guinea", "niger", "china", "india", "jersey", "mali", "togo",
              "aba", "kota", "nice", "reading", "mobile", "victoria", "georgetown", "santiago"}


def _sparql(query: str) -> list[dict]:
    data = http.fetch(_SPARQL, {"query": query, "format": "json"}, source="wikidata", ttl=_TTL,
                      headers={"Accept": "application/sparql-results+json"})
    return [{k: v["value"] for k, v in b.items()} for b in data["results"]["bindings"]]


@lru_cache(maxsize=1)
def countries() -> dict[str, dict]:
    """ISO3 → country record (real countries only, aggregates removed)."""
    with _lock:
        data = http.fetch(_WB_COUNTRIES, {"format": "json", "per_page": 400}, source="worldbank", ttl=_TTL)
        out: dict[str, dict] = {}
        for c in data[1]:
            if c["region"]["value"].strip() == "Aggregates":
                continue
            out[c["id"]] = {
                "iso3": c["id"],
                "iso2": c["iso2Code"],
                "name": c["name"],
                "region": c["region"]["value"].strip(),
                "income": c["incomeLevel"]["value"].strip(),
                "income_id": c["incomeLevel"]["id"],
                "capital": c.get("capitalCity") or "",
                "lat": float(c["latitude"]) if c.get("latitude") else None,
                "lon": float(c["longitude"]) if c.get("longitude") else None,
                "demonyms": [],
                "languages": [],
                "cities": [],
            }
        try:
            for r in _sparql(_Q_META):
                rec = out.get(r["iso3"])
                if rec:
                    rec["demonyms"] = [d for d in r.get("dems", "").split("|") if d]
                    rec["languages"] = [l for l in r.get("langs", "").split("|") if l]
            seen = set()
            for r in _sparql(_Q_CITIES):
                rec = out.get(r["iso3"])
                name = r.get("cityLabel", "")
                if not rec or not name or name.startswith("Q") and name[1:].isdigit():
                    continue
                if (r["iso3"], name) in seen:
                    continue
                seen.add((r["iso3"], name))
                rec["cities"].append({
                    "name": name,
                    "population": int(float(r.get("pop", 0) or 0)),
                    "lat": float(r["lat"]) if r.get("lat") else None,
                    "lon": float(r["lon"]) if r.get("lon") else None,
                })
            for rec in out.values():
                rec["cities"].sort(key=lambda c: -c["population"])
        except http.FetchError:
            pass  # gazetteer still works with World Bank names only
        return out


_SHORT_NAMES = {
    "USA": ["United States", "USA", "U.S.", "America"], "GBR": ["United Kingdom", "UK", "Britain", "England", "Scotland", "Wales"],
    "RUS": ["Russia"], "KOR": ["South Korea", "Korea"], "PRK": ["North Korea"], "IRN": ["Iran"], "EGY": ["Egypt"],
    "VEN": ["Venezuela"], "COD": ["DR Congo", "DRC", "Democratic Republic of the Congo"], "COG": ["Republic of the Congo"],
    "SYR": ["Syria"], "YEM": ["Yemen"], "LAO": ["Laos"], "VNM": ["Vietnam"], "TUR": ["Turkey", "Türkiye"],
    "CIV": ["Ivory Coast", "Côte d'Ivoire", "Cote d'Ivoire"], "GMB": ["Gambia"], "BHS": ["Bahamas"], "KGZ": ["Kyrgyzstan"],
    "SVK": ["Slovakia"], "CZE": ["Czech Republic", "Czechia"], "MKD": ["North Macedonia"], "FSM": ["Micronesia"],
    "HKG": ["Hong Kong"], "MAC": ["Macau", "Macao"], "PSE": ["Palestine", "Gaza", "West Bank"], "BRN": ["Brunei"],
}


@lru_cache(maxsize=1)
def _matcher() -> tuple[re.Pattern, dict[str, str]]:
    alias_to_iso: dict[str, str] = {}
    for iso, rec in countries().items():
        names = {rec["name"], *(_SHORT_NAMES.get(iso, []))}
        # World Bank long forms: "Egypt, Arab Rep." → "Egypt"
        base = rec["name"].split(",")[0].strip()
        names.add(base)
        names.update(rec["demonyms"])
        if rec["capital"]:
            names.add(rec["capital"])
        for c in rec["cities"][:15]:
            names.add(c["name"])
        for n in names:
            n = n.strip()
            if len(n) < 3 and n not in ("UK",):
                continue
            if n.lower() in _AMBIGUOUS and n not in ("India", "China", "Niger", "Mali", "Togo", "Chad", "Jordan", "Turkey"):
                continue
            alias_to_iso.setdefault(n.lower(), iso)
    aliases = sorted(alias_to_iso, key=len, reverse=True)
    pat = re.compile(r"(?<![\w-])(" + "|".join(re.escape(a) for a in aliases) + r")(?![\w-])", re.IGNORECASE)
    return pat, alias_to_iso


def find_countries(text: str) -> list[str]:
    """Return ISO3 codes mentioned in text (by name, demonym, capital or major city)."""
    if not text:
        return []
    try:
        pat, m = _matcher()
    except http.FetchError:
        return []
    found: list[str] = []
    for hit in pat.finditer(text):
        token = hit.group(1)
        # case-sensitive guard for ambiguous capitalised words ("Turkey" the bird, "Chad" the name)
        if token.lower() in _AMBIGUOUS and not token[0].isupper():
            continue
        iso = m.get(token.lower())
        if iso and iso not in found:
            found.append(iso)
    return found


def country(iso3: str) -> dict | None:
    try:
        return countries().get((iso3 or "").upper())
    except http.FetchError:
        return None


def resolve(name_or_code: str) -> str | None:
    """Resolve free text like 'Nigeria', 'NG', 'NGA', 'Lagos' to ISO3."""
    if not name_or_code:
        return None
    s = name_or_code.strip()
    cs = countries()
    if s.upper() in cs:
        return s.upper()
    for iso, rec in cs.items():
        if rec["iso2"].upper() == s.upper():
            return iso
    hits = find_countries(s)
    return hits[0] if hits else None


def strip_places(text: str) -> str:
    """Remove country/city/demonym mentions (geography is tracked separately from the need itself)."""
    if not text:
        return ""
    try:
        pat, _ = _matcher()
    except http.FetchError:
        return text
    return pat.sub(" ", text)
