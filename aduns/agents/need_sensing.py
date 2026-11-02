"""Need Sensing Agent — detects unmet, latent and normalized needs across four layers.

Layers sensed (all real, free sources):
  visible     GDELT global news, Google News
  scattered   Hacker News, Stack Exchange (18 sites), Reddit, Lemmy, Mastodon
  invisible   Google autocomplete search demand ("where can I get X in <city>", "why is X so expensive in …")
              and normalized-need language ("always takes", "only available abroad", …) in any text
  structural  openFDA current drug shortages, SAM.gov sources-sought notices, World Bank procurement notices,
              World Bank WDI structural access gaps vs income peers

Every stored signal keeps provenance (source, url, retrieved_at, content hash).
"""
from __future__ import annotations

import json
import statistics
import time

from .. import db, geo, http, nlp, taxonomy
from ..sources import needs as S
from ..sources import worldbank
from .base import Agent

# Need cues used to build queries for social/news sources.
SOCIAL_CUES = ['"can\'t find"', '"no one sells"', '"too expensive"', '"shortage"', '"have to import"',
               '"only available"', '"no spare parts"', '"nobody repairs"', '"waiting list"', '"hard to find"']
NEWS_CUES = ['"shortage of"', '"scarcity of"', '"lack of access to"', '"long queues"', '"price of"']

STRUCTURAL_SOURCES = {"openfda", "samgov", "worldbank_procurement", "worldbank_wdi"}
ALL_SOURCES = ["hackernews", "stackexchange", "reddit", "lemmy", "mastodon", "gdelt", "googlenews",
               "googlesuggest", "openfda", "samgov", "worldbank_procurement", "worldbank_wdi"]

SUGGEST_NEED_TYPE = {
    "where to buy": "unmet", "where can i get": "unmet", "how to get": "unmet", "not available": "unmet",
    "supplier in": "unmet", "who repairs": "inefficient", "why is": "unaffordable", "price in": "unaffordable",
    "cheap": "unaffordable", "shortage": "scarcity", "for rent": "unaffordable", "near me": "unmet",
}


class NeedSensingAgent(Agent):
    name = "need_sensing"

    def execute(self, focus: str = "", country: str = "", sources: list[str] | None = None,
                depth: int = 1, min_need_score: float = 0.35, se_sites: list[str] | None = None) -> dict:
        focus = (focus or "").strip()
        iso3 = geo.resolve(country) if country else None
        crec = geo.country(iso3) if iso3 else None
        sources = sources or ALL_SOURCES
        domain = taxonomy.classify_domain(focus)[0] if focus else None
        self.stats.update({"focus": focus, "country": iso3, "domain": domain})

        raw: list[dict] = []
        cues = SOCIAL_CUES[: 3 + 3 * depth]
        place = crec["name"].split(",")[0] if crec else ""

        def q(cue: str) -> str:
            return f"{cue} {focus}".strip() if focus else cue

        if "hackernews" in sources:
            for c in cues:
                raw += self.safe("hackernews", lambda c=c: S.hackernews(q(c), limit=25 * depth), [])
        if "stackexchange" in sources:
            sites = se_sites or self._se_sites(domain)
            for site in sites:
                for c in cues[:3 + depth]:
                    raw += self.safe(f"stackexchange:{site}",
                                     lambda c=c, site=site: S.stackexchange(q(c).replace('"', ""), site, 20), [])
        if "reddit" in sources:
            # Reddit search supports OR — batch cues to stay under the anonymous rate limit.
            for i in range(0, len(cues), 4):
                qq = f"({' OR '.join(cues[i:i + 4])}) {focus} {place}".strip()
                raw += self.safe("reddit", lambda qq=qq: S.reddit(qq, limit=50), [])
        if "lemmy" in sources:
            for c in cues[:4]:
                raw += self.safe("lemmy", lambda c=c: S.lemmy(q(c).replace('"', ""), limit=20), [])
        if "mastodon" in sources:
            tags = ["shortage", "supplychain"] + ([focus.replace(" ", "")] if focus else [])
            for t in tags:
                raw += self.safe("mastodon", lambda t=t: S.mastodon_tag(t, limit=40), [])
        if "gdelt" in sources:
            # one OR-query (GDELT allows 1 request / 5 s)
            ors = f"({' OR '.join(NEWS_CUES[: 2 + depth])})"
            ftxt = f'"{focus}"' if " " in focus else focus
            gq = f"{ors} {ftxt}".strip()
            raw += self.safe("gdelt", lambda: S.gdelt(gq, limit=75 * depth, timespan="6m",
                                                      country=place.lower().replace(" ", "") if place else None), [])
            if place:  # also global coverage that mentions the place
                raw += self.safe("gdelt", lambda: S.gdelt(f"{gq} {place}", limit=50 * depth, timespan="6m"), [])
        if "googlenews" in sources:
            gl = crec["iso2"] if crec else "US"
            for c in NEWS_CUES[: 2 + depth]:
                nq = f"{c} {focus} {place}".strip()
                raw += self.safe("googlenews", lambda nq=nq: S.google_news(nq, gl=gl, limit=40), [])
        if "googlesuggest" in sources and focus:
            raw += self._search_demand(focus, crec)
        if "openfda" in sources and (domain in ("medicines", "health") or not focus):
            raw += self.safe("openfda", lambda: S.fda_drug_shortages(None, limit=100 * depth), [])
        if "samgov" in sources and focus:
            raw += self.safe("samgov", lambda: S.sam_sources_sought(focus, limit=25 * depth), [])
        if "worldbank_procurement" in sources and focus:
            raw += self.safe("worldbank_procurement",
                             lambda: S.worldbank_procurement(f"{focus} {place}".strip(), limit=40 * depth), [])

        self.stats["raw_fetched"] = len(raw)
        stored = self._process(raw, focus, domain, iso3, min_need_score)

        if "worldbank_wdi" in sources:
            gaps = self.structural_gaps(domain_list=[domain] if domain else None, country=iso3)
            stored += gaps

        self.stats["signals_stored"] = len(stored)
        return {"signal_ids": stored}

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _stem(t: str) -> str:
        for suf in ("ies", "es", "s"):
            if t.endswith(suf) and len(t) > len(suf) + 3:
                return t[: -len(suf)] + ("y" if suf == "ies" else "")
        return t

    @staticmethod
    def _se_sites(domain: str | None) -> list[str]:
        by_domain = {
            "energy": ["diy", "electronics", "sustainability"], "cold_chain": ["diy", "engineering", "cooking"],
            "water_sanitation": ["diy", "sustainability", "engineering"], "health": ["health", "medicalsciences"],
            "medicines": ["health", "medicalsciences"], "agriculture": ["gardening", "sustainability"],
            "finance": ["money", "expatriates"], "digital": ["softwarerecs", "hardwarerecs"],
            "logistics": ["expatriates", "travel"], "manufacturing": ["engineering", "electronics", "mechanics"],
            "education_skills": ["workplace"], "housing_construction": ["diy"], "business_services": ["law", "money"],
        }
        return by_domain.get(domain or "", ["diy", "engineering", "money", "expatriates"])

    def _search_demand(self, focus: str, crec: dict | None) -> list[dict]:
        out: list[dict] = []
        places = [None]
        if crec:
            places = [crec["name"].split(",")[0]] + [c["name"] for c in crec["cities"][:3]]
        for p in places:
            out += self.safe("googlesuggest", lambda p=p: S.search_demand(
                focus, p, gl=crec["iso2"] if crec else None), [])
        return out

    def _process(self, raw: list[dict], focus: str, domain: str | None, iso3: str | None,
                 min_need_score: float) -> list[int]:
        focus_toks = {self._stem(t) for t in nlp.tokens(focus)}
        stored: list[int] = []
        seen: set[str] = set()
        for r in raw:
            text = nlp.clean(r.get("text") or r.get("title"))
            if not text or len(text) < 8:
                continue
            h = http.content_hash(r["source"], r.get("external_id"), text[:500])
            if h in seen:
                continue
            seen.add(h)
            toks = {self._stem(t) for t in nlp.tokens(f"{r.get('title') or ''} {text}")}
            # Relevance gate: search engines return loose matches, so require every focus term
            # (or all but one for 3+ term foci) to appear.
            need_overlap = len(focus_toks) if len(focus_toks) < 3 else len(focus_toks) - 1
            if focus_toks and len(focus_toks & toks) < need_overlap and r["source"] not in ("openfda",):
                self.bump("dropped_off_topic")
                continue
            det = nlp.detect_need(text)
            need_types = list(det["need_types"])
            need_score = det["need_score"]
            layer = r["layer"]
            if r["source"] == "googlesuggest":
                tpl = (r.get("extra") or {}).get("template", "")
                t = next((v for k, v in SUGGEST_NEED_TYPE.items() if k in tpl), "unmet")
                need_types = ["latent_search", t] + [x for x in need_types if x not in (t, "latent_search")]
                need_score = max(need_score, 0.55)
            elif r["source"] in STRUCTURAL_SOURCES:
                need_types = ["institutional"] + [x for x in need_types if x != "institutional"]
                need_score = max(need_score, 0.7)
            if "normalized" in need_types and layer in ("scattered", "visible"):
                layer = "invisible"   # normalized needs are the invisible layer even if found online
            if need_score < min_need_score:
                self.bump("dropped_low_need")
                continue
            countries = geo.find_countries(f"{r.get('title') or ''} {text}")
            sc = (r.get("extra") or {}).get("sourcecountry")
            if sc:
                iso_sc = geo.resolve(sc)
                if iso_sc and iso_sc not in countries:
                    countries.append(iso_sc)
            if iso3 and iso3 not in countries and r["source"] in ("googlesuggest", "googlenews", "gdelt", "worldbank_procurement"):
                # query was geo-scoped; record the scope country as the signal's geography
                countries.append(iso3)
            sig_domain = taxonomy.classify_domain(text)[0] or domain
            sid = db.insert("signals", {
                "source": r["source"], "layer": layer, "external_id": str(r.get("external_id") or "")[:500],
                "url": r.get("url"), "title": (r.get("title") or "")[:500], "text": text[:4000],
                "author": r.get("author"), "published_at": r.get("published_at"), "retrieved_at": time.time(),
                "content_hash": h, "query": focus, "domain": sig_domain,
                "need_types": json.dumps(need_types), "gap_causes": json.dumps(det["gap_causes"]),
                "intensity": det["intensity"], "need_score": need_score, "countries": json.dumps(countries),
                "entities": json.dumps(det["objects"]), "engagement": r.get("engagement") or 0.0,
                "run_id": self.run_id,
                "extra": json.dumps({**(r.get("extra") or {}), "cues": det["cues"]}),
            }, ignore=True)
            if sid:
                stored.append(sid)
                self.bump(f"stored:{r['source'].split(':')[0]}")
            else:
                self.bump("duplicates")
        return stored

    # --------------------------------------------- structural (invisible) gaps
    def structural_gaps(self, domain_list: list[str] | None = None, country: str | None = None,
                        z_threshold: float = 0.75) -> list[int]:
        """Find countries far worse than their income peers on WDI access indicators.

        A large gap vs similar-income countries signals a need that is *solvable at that income level*
        but locally normalized — exactly the 'why is this accepted here?' question.
        """
        stored: list[int] = []
        try:
            cs = geo.countries()
        except http.FetchError as e:
            self.errors.append(f"geo: {e}")
            return stored
        domains = domain_list or list(taxonomy.DOMAINS)
        for dom in domains:
            for code, label, better in taxonomy.DOMAINS[dom]["indicators"]:
                data = self.safe(f"wdi:{code}", lambda code=code: worldbank.latest(code), {})
                if not data:
                    continue
                by_income: dict[str, list[float]] = {}
                for iso, (v, _) in data.items():
                    if iso in cs:
                        by_income.setdefault(cs[iso]["income_id"], []).append(v)
                targets = [country] if country else [i for i in data if i in cs]
                for iso in targets:
                    if iso not in data or iso not in cs:
                        continue
                    v, year = data[iso]
                    peers = by_income.get(cs[iso]["income_id"], [])
                    if len(peers) < 5:
                        continue
                    med = statistics.median(peers)
                    sd = statistics.pstdev(peers) or 1e-9
                    z = (v - med) / sd if better == "higher" else (med - v) / sd
                    if z > -z_threshold and not country:
                        continue
                    worse = z <= -z_threshold
                    if not worse and country:
                        # still record the measured position for the requested country (context, not a gap)
                        self.bump("structural_no_gap")
                        continue
                    name = cs[iso]["name"]
                    text = (f"Structural access gap in {name}: {label} = {v:.1f} ({year}) versus a median of {med:.1f} "
                            f"among {cs[iso]['income']} economies (z = {z:.2f}). Peers at similar income levels achieve "
                            f"materially better outcomes, so the gap is likely solvable rather than inevitable.")
                    h = http.content_hash("worldbank_wdi", code, iso, year)
                    sid = db.insert("signals", {
                        "source": "worldbank_wdi", "layer": "structural", "external_id": f"{code}:{iso}:{year}",
                        "url": f"https://data.worldbank.org/indicator/{code}?locations={cs[iso]['iso2']}",
                        "title": f"{label}: {name} lags income peers", "text": text, "author": "World Bank WDI",
                        "published_at": str(year), "retrieved_at": time.time(), "content_hash": h,
                        "query": dom, "domain": dom, "need_types": json.dumps(["institutional", "normalized"]),
                        "gap_causes": json.dumps([]), "intensity": round(min(1.0, abs(z) / 3), 3),
                        "need_score": round(min(0.95, 0.5 + abs(z) / 6), 3), "countries": json.dumps([iso]),
                        "entities": json.dumps([label]), "engagement": 0.0, "run_id": self.run_id,
                        "extra": json.dumps({"indicator": code, "value": v, "peer_median": med, "z": z,
                                             "income": cs[iso]["income"], "better": better}),
                    }, ignore=True)
                    if sid:
                        stored.append(sid)
                        self.bump("stored:worldbank_wdi")
        return stored
