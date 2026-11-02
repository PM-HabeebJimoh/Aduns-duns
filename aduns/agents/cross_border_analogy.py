"""Cross-Border Analogy Agent — finds places that solved a similar problem differently.

Method (positive-deviance on real World Bank WDI data):
  1. Map the need's domain to outcome indicators (taxonomy).
  2. Peer set = countries with GDP per capita (PPP) within a factor of `income_band` of the target —
     i.e. places with similar resources.
  3. Analogs = peers with materially better outcome levels, ranked by
        deviance  = standardised outperformance vs the target, and
        momentum  = 10-year improvement (fast improvers usually have a transferable recent playbook).
  4. Evidence of *how*: World Bank projects in the analog country for that domain and research papers
     naming the analog country + the need — the concrete programme/business models to study.
"""
from __future__ import annotations

import json
import math
import statistics
import time
from collections import Counter

from .. import db, geo, http, taxonomy
from ..sources import capabilities as C
from ..sources import worldbank
from .base import Agent

GDP = "NY.GDP.PCAP.PP.KD"


class CrossBorderAnalogyAgent(Agent):
    name = "cross_border_analogy"

    def execute(self, hypothesis_id: int | None = None, country: str = "", domain: str = "",
                income_band: float = 2.0, top_k: int = 5, with_evidence: bool = True) -> dict:
        hyp = db.q1("SELECT * FROM hypotheses WHERE id=?", (hypothesis_id,)) if hypothesis_id else None
        iso3 = geo.resolve(country) if country else None
        if not iso3 and hyp:
            ranked = Counter(db.loads(hyp["countries"], {})).most_common()
            iso3 = next((c for c, _ in ranked if geo.country(c)), None)
        domain = domain or (hyp or {}).get("domain")
        if not iso3:
            raise ValueError("No target country: pass country= or use a hypothesis with geographic signals")
        if domain not in taxonomy.DOMAINS:
            raise ValueError(f"Unknown or missing domain '{domain}'. Options: {', '.join(taxonomy.DOMAINS)}")
        target = geo.country(iso3)
        cs = geo.countries()
        self.stats.update({"target": iso3, "domain": domain})

        gdp = self.safe("wdi:gdp", lambda: worldbank.latest(GDP), {})
        if iso3 not in gdp:
            raise ValueError(f"No GDP per capita data for {iso3}")
        g_t = gdp[iso3][0]
        peers = {i for i, (g, _) in gdp.items() if i in cs and i != iso3 and 1 / income_band <= g / g_t <= income_band}
        self.stats["peers"] = len(peers)
        this_year = time.gmtime().tm_year

        ids: list[int] = []
        for code, label, better in taxonomy.DOMAINS[domain]["indicators"]:
            lat = self.safe(f"wdi:{code}", lambda code=code: worldbank.latest(code), {})
            if iso3 not in lat:
                self.errors.append(f"{code}: no value for {iso3}")
                continue
            v_t, y_t = lat[iso3]
            peer_vals = [lat[p][0] for p in peers if p in lat]
            if len(peer_vals) < 4:
                continue
            sd = statistics.pstdev(peer_vals) or 1e-9
            ser = self.safe(f"wdi-series:{code}", lambda code=code: worldbank.series(code, this_year - 14, this_year), {})
            cands = []
            for p in peers:
                if p not in lat:
                    continue
                v_a, y_a = lat[p]
                gain = (v_a - v_t) if better == "higher" else (v_t - v_a)
                if gain <= 0.25 * sd:
                    continue
                dev = gain / sd
                change = None
                s = ser.get(p, {})
                if s:
                    yrs = sorted(s)
                    old = [y for y in yrs if y <= yrs[-1] - 8]
                    if old:
                        change = s[yrs[-1]] - s[old[-1]]
                        if better == "lower":
                            change = -change
                inc_sim = max(0.0, 1 - abs(math.log(gdp[p][0] / g_t)) / math.log(income_band))
                momentum = (change / sd) if change is not None else 0.0
                score = 0.5 * min(dev, 3) / 3 + 0.25 * inc_sim + 0.25 * max(0.0, min(momentum, 3)) / 3
                cands.append((score, p, v_a, y_a, change, inc_sim, dev))
            cands.sort(reverse=True)
            for rank, (score, p, v_a, y_a, change, inc_sim, dev) in enumerate(cands[:top_k]):
                # "how they did it" evidence for the strongest analogs (each costs 2 API calls)
                evidence = self._evidence(p, domain, hyp) if with_evidence and rank < 3 else []
                aid = db.insert("analogies", {
                    "hypothesis_id": hyp["id"] if hyp else None, "target_country": iso3, "analog_country": p,
                    "indicator_code": code, "indicator_name": label, "target_value": v_t, "analog_value": v_a,
                    "target_year": y_t, "analog_year": y_a, "analog_change_10y": change,
                    "income_similarity": round(inc_sim, 3), "deviance_score": round(score, 4),
                    "evidence": json.dumps(evidence), "retrieved_at": time.time(),
                }, ignore=True)
                if not aid:
                    row = db.q1("""SELECT id FROM analogies WHERE hypothesis_id IS ? AND target_country=? AND
                                   analog_country=? AND indicator_code=?""",
                                (hyp["id"] if hyp else None, iso3, p, code))
                    aid = row["id"] if row else None
                    if aid:
                        db.update("analogies", aid, {"analog_value": v_a, "target_value": v_t,
                                                     "deviance_score": round(score, 4), "evidence": json.dumps(evidence),
                                                     "retrieved_at": time.time()})
                if aid:
                    ids.append(aid)
                    self.bump("analogies")
        return {"analogy_ids": ids, "target": target["name"] if target else iso3}

    def _evidence(self, iso3: str, domain: str, hyp: dict | None) -> list[dict]:
        c = geo.country(iso3)
        if not c:
            return []
        kw = taxonomy.DOMAINS[domain]["keywords"]
        topic = " ".join(db.loads(hyp["key_terms"], [])[:2]) if hyp else kw[0]
        out: list[dict] = []
        projs = self.safe(f"wbproj:{iso3}", lambda: worldbank.projects(f"{kw[0]} {topic}".strip(), country=c["iso2"],
                                                                          limit=4), []) or []
        if not projs:
            projs = self.safe(f"wbproj:{iso3}", lambda: worldbank.projects(kw[0], country=c["iso2"], limit=4), []) or []
        for p in projs[:4]:
            out.append({"source": "worldbank_projects", "title": p.get("name"), "url": p.get("url"),
                        "status": p.get("status"), "approved": p.get("approved")})
        name = c["name"].split(",")[0]
        papers = self.safe(f"crossref:{iso3}", lambda: C.crossref(f"{name} {topic} access", limit=4), []) or []
        for p in papers[:3]:
            if name.lower() in (p["title"] + " " + (p.get("description") or "")).lower():
                out.append({"source": "crossref", "title": p["title"], "url": p["url"], "year": p.get("year")})
        return out
