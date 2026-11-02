"""Governance layer: five agents that must challenge an opportunity before money or reputation is committed.

    Verification   – separates claims from confirmed evidence (independence, syndication, liveness, consistency)
    Legal & Safety – sanctions & export-control screening of every counterparty and country, licences for the
                     domain, known product hazards (recalls), privacy jurisdiction, competition/contract notes
    Red-Team       – tries to prove the business will fail: actively searches for counter-evidence, stress-tests
                     the economics, lists failure modes and explicit kill criteria
    Impact         – who benefits, who could be harmed, local value capture, environmental and affordability risk
    Audit          – tamper-evident (hash-chained) ledger, a hashed evidence dossier per opportunity, and the
                     human approval gate that Execution requires

The agents are deliberately adversarial: the Board's recommendation is the *most cautious* that the evidence
supports, and nothing proceeds to Execution without a named human's approval recorded in the chain.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter
from urllib.parse import urlparse

import numpy as np
import requests

from .. import config, db, geo, nlp, translate
from ..sources import compliance as CP
from ..sources import social as S
from .base import Agent
from .opportunity import COST_ASSUMPTIONS, ROUTE_ARCHETYPE, build_context

SEVERITY = {"blocker": 3, "high": 2, "medium": 1, "info": 0}


def _opp(oid: int) -> dict:
    o = db.q1("SELECT * FROM opportunities WHERE id=?", (oid,))
    if not o:
        raise ValueError(f"opportunity {oid} not found")
    for k in ("market", "localization", "composition", "defensibility", "routes", "economics"):
        o[k] = db.loads(o[k], {})
    return o


def _domain(url: str | None) -> str:
    try:
        d = urlparse(url or "").netloc.lower()
    except ValueError:
        return ""
    return d[4:] if d.startswith("www.") else d


# ============================================================================ Verification
class VerificationAgent(Agent):
    name = "verification"

    def execute(self, opportunity_id: int, check_links: int = 8) -> dict:
        o = _opp(opportunity_id)
        ctx = build_context(o["hypothesis_id"], o["country"])
        sigs = ctx["signals"]
        # independence: distinct publishing domains/authors; syndication: near-identical texts count once
        groups: list[set] = []
        reps: list[frozenset] = []
        for s in sigs:
            toks = frozenset(nlp.tokens(s.get("text_en") or s["text"]))
            for i, r in enumerate(reps):
                if toks and r and len(toks & r) / max(1, len(toks | r)) >= 0.8:
                    groups[i].add(s["id"])
                    break
            else:
                reps.append(toks)
                groups.append({s["id"]})
        domains = {_domain(s["url"]) or s["source"] for s in sigs}
        authors = {s.get("author") for s in sigs if s.get("author")}
        layers = {s["layer"] for s in sigs}
        field_ok = db.q1("""SELECT COUNT(*) n FROM scout_observations o JOIN scout_missions m ON m.id=o.mission_id
                            WHERE m.hypothesis_id=? AND o.status='validated'""", (o["hypothesis_id"],))["n"]
        indep = len(groups)
        need_status = ("confirmed" if field_ok >= 2 or (indep >= 5 and len(domains) >= 3 and len(layers) >= 2)
                       else "corroborated" if indep >= 2 and len(domains) >= 2 else "claim")
        # liveness of a sample of evidence links
        links = [s["url"] for s in sigs if s.get("url") and s["url"].startswith("http")][:check_links]
        dead = []
        for u in links:
            try:
                r = requests.head(u, timeout=10, allow_redirects=True, headers={"User-Agent": config.USER_AGENT})
                if r.status_code >= 400 and r.status_code not in (403, 405, 429):
                    dead.append(u)
            except requests.RequestException:
                dead.append(u)
        loc, econ, mk = o["localization"], o["economics"], o["market"]
        price = (loc.get("local_price_evidence") or {}).get("usd_summary")
        claims = [
            {"claim": f"The need for {o['object']} exists in {o['country']}", "status": need_status,
             "basis": f"{indep} independent items (syndicated copies merged) from {len(domains)} domains, "
                      f"{len(authors)} authors, {len(layers)} layers; {field_ok} validated field observations"},
            {"claim": "Market size (imports)", "status": "confirmed" if mk.get("imports") else "unverified",
             "basis": "UN Comtrade official trade record" if mk.get("imports") else "no trade record"},
            {"claim": "Local consumer price", "status": ("confirmed" if price and not price.get("weak") and price["n"] >= 2
                                                         else "single-source" if price else "missing"),
             "basis": f"{price['n']} consistent quote(s)" if price else "no consistent local quotes"},
            {"claim": "Unit cost", "status": "confirmed" if (econ.get("inputs", {}).get("unit_cost_usd") or {}).get("kind") == "real"
             else "assumption", "basis": (econ.get("inputs", {}).get("unit_cost_usd") or {}).get("source", "—")},
            {"claim": "Profitability", "status": "modelled" if econ.get("econ_status") == "modelled" else "not modelled",
             "basis": f"evidence confidence {o.get('evidence_confidence')}; assumptions: "
                      f"{[k for k, v in (econ.get('inputs') or {}).items() if v.get('kind') == 'assumption']}"},
            {"claim": "Others solved it elsewhere (analogies)",
             "status": "corroborated" if sum(len(db.loads(a["evidence"], [])) >= 2 for a in ctx["analogies"]) else "claim",
             "basis": f"{len(ctx['analogies'])} analog countries with local solution reports"},
        ]
        weights = {"confirmed": 1.0, "corroborated": 0.7, "modelled": 0.6, "single-source": 0.4, "claim": 0.25,
                   "assumption": 0.2, "unverified": 0.1, "missing": 0.0, "not modelled": 0.0}
        score = round(float(np.mean([weights[c["status"]] for c in claims])) * (1 - 0.5 * (len(dead) / max(1, len(links)))), 3)
        self.stats.update({"score": score, "independent": indep, "dead_links": len(dead)})
        return {"claims": claims, "score": score, "independent_evidence": indep, "syndicated_merged": len(sigs) - indep,
                "domains": len(domains), "links_checked": len(links), "dead_links": dead}


# ========================================================================== Legal & Safety
class LegalSafetyAgent(Agent):
    name = "legal_safety"

    def execute(self, opportunity_id: int) -> dict:
        o = _opp(opportunity_id)
        iso3, mk, comp = o["country"], o["market"], o["composition"]
        flags: list[dict] = []

        def flag(sev, area, text, url=None):
            flags.append({"severity": sev, "area": area, "finding": text, "source": url})

        sanc = CP.country_sanctions(iso3)
        if sanc:
            flag({"comprehensive": "blocker", "sectoral": "high"}.get(sanc["level"], "medium"), "sanctions",
                 f"Target country {iso3} is under the OFAC {sanc['program']} program ({sanc['level']}).", sanc["url"])
        for p in ((mk.get("imports") or {}).get("partners") or [])[:5]:
            s2 = CP.country_sanctions(p.get("iso3") or "")
            if s2:
                flag("high" if s2["level"] == "comprehensive" else "medium" if s2["level"] == "sectoral" else "info", "sanctions",
                     f"Supplier country {p['iso3']} ({(p.get('share') or 0):.0%} of imports) is under OFAC "
                     f"{s2['program']} ({s2['level']}).", s2["url"])
        self.safe("screening_list", CP.refresh_screening_list, 0)
        parties = set()
        for of in comp.get("offerings", []):
            for c in of.get("components", []):
                for n in (c.get("holder"), c.get("title") if c.get("type") in ("organization", "local_provider") else None):
                    if n and len(n) > 3:
                        parties.add(n[:120])
        for i in mk.get("incumbents", []) + mk.get("organizations_in_country", []):
            parties.add(i["title"][:120])
        hits = []
        for p in parties:
            for h in CP.screen(p):
                hits.append(h)
                freeze = any(k in h["source"] for k in ("SDN", "EU Financial", "UN Security", "UK Sanctions"))
                flag("blocker" if freeze else "high", "sanctions",
                     f"Counterparty '{p}' matches '{h['matched']}' on {h['source']} ({h['match']} match).", h["url"])
        hs = (mk.get("hs") or {}).get("hs")
        ec = CP.export_controlled(hs)
        if ec:
            flag("high", "export_control", f"HS {hs} is export-controlled / dual-use ({ec}).")
        hyp = db.q1("SELECT domain FROM hypotheses WHERE id=?", (o["hypothesis_id"],))
        domain = (hyp or {}).get("domain")
        for lic in CP.LICENSED_DOMAINS.get(domain, []):
            flag("medium", "licensing", f"{lic} — verify the {geo.country(iso3)['name']} regime before launch.")
        recalls = []
        for ch in CP.recall_channels(hs):
            if ch.startswith("fda:"):
                recalls += self.safe(ch, lambda k=ch[4:]: CP.fda_recalls(o["object"], k), []) or []
            else:
                recalls += self.safe("cpsc", lambda: CP.cpsc_recalls(o["object"]), []) or []
        if recalls:
            classes = Counter(r.get("class") for r in recalls if r.get("class"))
            flag("medium", "product_safety",
                 f"{len(recalls)} recalls of '{o['object']}' products in the last year ({classes.get('Class I', 0)} Class I; "
                 f"e.g. {recalls[0]['reason'][:140]}). Build these hazards into supplier QA and labelling.",
                 recalls[0].get("url"))
        if iso3 in CP.GDPR:
            flag("medium", "privacy", "GDPR applies: customer and scout personal data need a lawful basis, DPA and records.")
        flag("info", "privacy", "Scout network stores phone numbers: consent is recorded per scout and per observation; "
                                "honour withdrawal (STOP) and minimise retention.")
        best = o.get("best_route")
        if best in ("license_and_localize", "local_distribution_partnership", "demand_aggregation"):
            flag("info", "competition", "Exclusive territories or buyer cartels can breach competition law — use "
                                        "non-exclusive terms unless cleared.")
        worst = max((SEVERITY[f["severity"]] for f in flags), default=0)
        self.stats.update({"flags": len(flags), "worst": worst, "screen_hits": len(hits), "parties_screened": len(parties)})
        return {"flags": sorted(flags, key=lambda f: -SEVERITY[f["severity"]]),
                "worst_severity": next(k for k, v in SEVERITY.items() if v == worst),
                "parties_screened": sorted(parties)[:50], "screening_hits": hits, "recalls": recalls[:10]}


# ============================================================================== Red Team
COUNTER = ["surplus", "glut", "oversupply", "prices fall", "prices drop", "price cut", "abundant", "no shortage",
           "shortage over", "stocks restored"]


class RedTeamAgent(Agent):
    name = "red_team"

    def execute(self, opportunity_id: int, verification: dict | None = None, legal: dict | None = None,
                n: int = 3000, seed: int = 11) -> dict:
        o = _opp(opportunity_id)
        c = geo.country(o["country"])
        modes: list[dict] = []

        def fail(kind, text, evidence=None, severity="medium"):
            modes.append({"failure_mode": kind, "argument": text, "evidence": evidence or [], "severity": severity})

        # 1) Counter-evidence: actively look for reports that the need is NOT real or is ending
        name = c["name"].split(",")[0]
        lang = next((l for l in c.get("langs", []) if l != "en"), "en")
        q_en = f'"{o["object"]}" ({" OR ".join(chr(34) + w + chr(34) for w in COUNTER[:7])}) {name}'
        counter = self.safe("counter_en", lambda: S.google_news(q_en, c["iso2"], "en", 30), []) or []
        if lang != "en":
            lo = translate.from_english(o["object"], lang)
            lw = [translate.from_english(w, lang) for w in COUNTER[:4]]
            q_l = f'"{lo}" ({" OR ".join(chr(34) + w + chr(34) for w in lw)})'
            counter += self.safe("counter_local", lambda: S.google_news(q_l, c["iso2"], lang, 30), []) or []
        obj_rx = re.compile(rf"(?<!\w){re.escape(o['object'].split()[0][:6])}", re.I)
        cw = re.compile(r"\b(surplus|glut|oversupply|over-supply|abundan\w*|prices? (fall|fell|drop|dropped|ease|eased|"
                        r"decline|declined|down)|price cut|no shortage|shortage (is )?over|stocks? (restored|recover\w*)|"
                        r"cheaper)\b", re.I)
        kept = []
        for x in counter:
            t = x["text"]
            hl = (x.get("extra") or {}).get("hl", "en")
            en = t if hl.startswith("en") else (translate.to_english(t, hl.split("-")[0]) or "")
            # Google News may silently serve another edition: trust the edition only for the country's own language
            hl_lang = hl.split("-")[0]
            local_edition = (((x.get("extra") or {}).get("gl") or "").upper() == c["iso2"].upper()
                             and hl_lang in (c.get("langs") or [])[:2])
            mentioned = geo.find_countries(f"{t} {en}")
            about_country = o["country"] in mentioned
            about_elsewhere = (bool(mentioned) and not about_country) or bool(re.search(
                r"\b(EU|E\.U\.|Europe|European|U\.S\.|US|USA|American|global|world|Asia|Africa|Latin America)\b", en))
            if obj_rx.search(en) and cw.search(en) and (about_country or (local_edition and not about_elsewhere)):
                x["text_en"] = en
                kept.append(x)
        counter = kept
        hyp_n = db.q1("SELECT signal_count FROM hypotheses WHERE id=?", (o["hypothesis_id"],))["signal_count"]
        if counter:
            ratio = len(counter) / max(1, hyp_n)
            fail("counter_evidence", f"{len(counter)} recent reports suggest the shortage/price pressure is easing "
                                     f"(vs {hyp_n} need signals).",
                 [{"title": x["title"], "title_en": x.get("text_en"), "url": x["url"], "date": (x["published_at"] or "")[:10]}
                  for x in counter[:6]],
                 "high" if ratio >= 0.5 else "medium")
        # 2) Stress test: every assumption at its unfavourable end
        econ = o["economics"]
        stress = self._stress(econ, o.get("best_route"), n, seed) if econ.get("econ_status") == "modelled" else None
        if stress is not None:
            if stress["p_profitable"] < 0.2:
                fail("economics_fragile", f"Under pessimistic assumptions P(profitable) falls to {stress['p_profitable']:.0%} "
                                          f"(net margin p50 {stress['net_margin_p50']:.0%}).", severity="high")
        else:
            fail("economics_unknown", "Economics not modelled (no reliable local price or cost) — the business case is unproven.",
                 severity="high")
        # tariff: import-based economics resting on an assumed duty must be verified before any pilot
        duty = (econ.get("inputs") or {}).get("import_duty")
        if duty and duty.get("kind") not in ("official", "measured") and o.get("best_route") in (
                "import_and_resell", "local_agents_retail", "bundle", "local_distribution_partnership"):
            fail("tariff_unverified", f"Import duty for HS {(o['market'].get('hs') or {}).get('hs')} into {o['country']} is "
                                      f"{'a country average' if duty.get('kind') == 'official_average' else 'an assumption'} "
                                      f"({duty['range'][0]:.0%}–{duty['range'][1]:.0%}); real product tariffs (and "
                                      f"quotas/state-trading) can exceed this and erase the margin. Verify the national "
                                      f"tariff schedule before piloting.", severity="high")
        # 3) Structural risks from the evidence
        mk = o["market"]
        hhi = (mk.get("imports") or {}).get("hhi")
        if hhi and hhi > 0.6:
            top = (mk["imports"]["partners"] or [{}])[0]
            fail("supply_dependency", f"Imports are concentrated (HHI {hhi}); {top.get('iso3')} supplies "
                                      f"{(top.get('share') or 0):.0%}. A border closure or price move there breaks the model.")
        inc = mk.get("incumbents", [])
        big = [i for i in inc if i.get("installs") and re.search(r"(\d+)\s*(M|B)\+", i["installs"] or "")]
        if big:
            fail("incumbent_response", f"{len(big)} incumbents with millions of installs can copy or undercut: "
                                       + ", ".join(i["title"] for i in big[:3]))
        sigs = db.q("""SELECT s.source, s.published_ts FROM signals s JOIN hypothesis_signals hs ON hs.signal_id=s.id
                       WHERE hs.hypothesis_id=?""", (o["hypothesis_id"],))
        src = Counter(s["source"] for s in sigs)
        if sigs and src.most_common(1)[0][1] / len(sigs) > 0.7:
            fail("thin_evidence", f"{src.most_common(1)[0][1]}/{len(sigs)} signals come from one source "
                                  f"({src.most_common(1)[0][0]}); demand may be an artefact of that channel.")
        if sigs and src.get("googlesuggest", 0) / len(sigs) > 0.5:
            fail("search_not_purchase", "Demand rests mainly on search autocomplete — searching is not paying.")
        if (o.get("evidence_confidence") or 0) < 0.5:
            fail("assumption_driven", f"Evidence confidence {o.get('evidence_confidence')}: results are driven by assumptions "
                                      f"({', '.join(econ.get('validation_priorities') or econ.get('missing') or [])}).",
                 severity="high")
        if verification and verification.get("score", 1) < 0.4:
            fail("unverified_claims", f"Verification score {verification['score']}: key claims are not confirmed.", severity="high")
        if legal and legal.get("worst_severity") in ("blocker", "high"):
            fail("legal", f"Legal & Safety raised {legal['worst_severity']} issues.", severity=legal["worst_severity"]
                 if legal["worst_severity"] != "blocker" else "high")
        rej = db.q1("""SELECT COUNT(*) n FROM scout_observations ob JOIN scout_missions m ON m.id=ob.mission_id
                       WHERE m.hypothesis_id=? AND ob.status='rejected'""", (o["hypothesis_id"],))["n"]
        if rej:
            fail("field_contradiction", f"{rej} field observations were rejected on review.", severity="high")
        kills = self._kill_criteria(o, econ)
        highs = sum(1 for m in modes if m["severity"] == "high")
        blocker = legal and legal.get("worst_severity") == "blocker"
        verdict = ("kill" if blocker or (stress and stress["p_profitable"] < 0.05 and (o.get("evidence_confidence") or 0) >= 0.66)
                   else "pilot_only_with_conditions" if highs else "proceed_to_pilot")
        self.stats.update({"failure_modes": len(modes), "high": highs, "verdict": verdict})
        return {"verdict": verdict, "failure_modes": modes, "stress_test": stress, "kill_criteria": kills,
                "counter_evidence_found": len(counter)}

    @staticmethod
    def _stress(econ: dict, route: str | None, n: int, seed: int) -> dict:
        rng = np.random.default_rng(seed)
        inp = econ.get("inputs") or {}

        def bad(k, high_is_bad=True):
            v = inp.get(k)
            if not v:
                return np.zeros(n)
            lo, hi = v["range"]
            mid = (lo + hi) / 2
            return rng.uniform(mid, hi, n) if high_is_bad else rng.uniform(lo, mid, n)
        price = bad("price_usd", high_is_bad=False)
        cost = bad("unit_cost_usd")
        landed = cost * (1 + bad("freight_insurance")) * (1 + bad("import_duty")) * (1 + bad("local_logistics"))
        arche = ROUTE_ARCHETYPE.get(route or "", "product")
        opex = sum(rng.uniform((a + b) / 2, b, n) for a, b in COST_ASSUMPTIONS[arche].values())
        with np.errstate(divide="ignore", invalid="ignore"):
            gross = np.where(price > 0, (price - landed) / price, -1)
        net = gross - opex
        return {"net_margin_p50": float(np.median(net)), "net_margin_p10": float(np.percentile(net, 10)),
                "p_profitable": float((net > 0).mean()),
                "method": "every assumption drawn from its unfavourable half; real inputs at their pessimistic half"}

    @staticmethod
    def _kill_criteria(o: dict, econ: dict) -> list[str]:
        out = [f"Kill if fewer than 30% of ≥15 interviewed target customers in {o['country']} confirm the problem "
               f"(field mission)."]
        price = ((o["localization"].get("local_price_evidence") or {}).get("usd_summary") or {}).get("median")
        if price:
            out.append(f"Kill if ≥10 verified local quotes put the price below ${price * 0.8:.2f} (20% under today's median).")
        for v in (econ.get("validation_priorities") or [])[:3]:
            out.append(f"Kill or redesign if validated '{v}' lands in the unfavourable half of its assumed range.")
        out.append("Kill if a pilot of ≤50 customers shows net margin < 0 after 3 months.")
        return out


# ================================================================================ Impact
SDG = {"food": [2], "agriculture": [2, 8], "medicines": [3], "health": [3], "water_sanitation": [6], "energy": [7],
       "fuel": [7], "cold_chain": [2, 12], "jobs_income": [8], "finance": [1, 8, 10], "digital": [9],
       "education_skills": [4], "housing_construction": [11], "mobility": [11], "disaster_climate": [13, 11],
       "public_services": [16], "safety_security": [16], "care": [3, 5], "consumer_goods": [12], "manufacturing": [9]}
BENEFICIARY_WORDS = {"farmers": ["farmer", "farmers", "smallholder"], "patients": ["patient", "patients", "sick"],
                     "households": ["household", "families", "family", "residents"], "workers": ["worker", "workers", "jobs"],
                     "small businesses": ["traders", "shop", "sme", "vendors", "business"],
                     "students": ["student", "students", "school"], "women": ["women", "mothers", "girls"],
                     "children": ["children", "child", "infant", "baby"], "elderly": ["elderly", "pensioners", "older"]}
ENV_RISK_HS = {"27": "fossil fuels — emissions", "39": "plastics — waste", "85": "electronics/batteries — e-waste",
               "31": "fertiliser — runoff", "38": "chemicals — pollution", "84": "machinery — energy use"}


class ImpactAgent(Agent):
    name = "impact"

    def execute(self, opportunity_id: int) -> dict:
        o = _opp(opportunity_id)
        hyp = db.q1("SELECT * FROM hypotheses WHERE id=?", (o["hypothesis_id"],))
        texts = " ".join((s.get("text_en") or s["text"]).lower() for s in db.q(
            """SELECT s.text, s.text_en FROM signals s JOIN hypothesis_signals hs ON hs.signal_id=s.id
               WHERE hs.hypothesis_id=?""", (o["hypothesis_id"],)))
        ben = {g: sum(texts.count(w) for w in ws) for g, ws in BENEFICIARY_WORDS.items()}
        ben = {g: n for g, n in sorted(ben.items(), key=lambda kv: -kv[1]) if n}
        harms = []
        mk, route = o["market"], o.get("best_route")
        n_inc = len(mk.get("incumbents", []))
        if route in ("import_and_resell",) and n_inc:
            harms.append({"harm": f"May displace {n_inc} existing local providers instead of strengthening them.",
                          "mitigation": "Prefer partnership/enable-existing-operator routes; source via local SMEs."})
        if route == "import_and_resell" and (mk.get("structure") or "").startswith("two-way"):
            harms.append({"harm": "Imports could undercut local producers in a market that already produces locally.",
                          "mitigation": "Target supply gaps/seasons; buy from local producers first."})
        hs = (mk.get("hs") or {}).get("hs") or ""
        for pre, txt in ENV_RISK_HS.items():
            if hs.startswith(pre):
                harms.append({"harm": f"Environmental: {txt}.", "mitigation": "Take-back/recycling, efficiency standards, "
                                                                             "cleaner alternatives in the offer."})
        price = ((o["localization"].get("local_price_evidence") or {}).get("usd_summary") or {}).get("median")
        if (o["economics"].get("routes") or [{}])[0].get("gross_margin", {}).get("p50", 0) > 0.5:
            harms.append({"harm": "High gross margin on an essential need risks being perceived as profiteering.",
                          "mitigation": "Transparent pricing; tiered/social pricing for low-income users."})
        local_value = {"import_and_resell": 0.3, "local_distribution_partnership": 0.6, "manufacture_locally": 0.9,
                       "license_and_localize": 0.7, "use_idle_capacity": 0.8, "cooperative_model": 0.9,
                       "enable_existing_operator": 0.8, "local_agents_retail": 0.7, "software_layer": 0.5,
                       "demand_aggregation": 0.6, "subscription": 0.5, "service_instead_of_product": 0.6,
                       "bundle": 0.5, "policy_pathway": 0.7}.get(route or "", 0.5)
        need_severity = min(1.0, float(hyp["score"] or 0) + (0.2 if (hyp["domain"] in ("medicines", "health", "food",
                                                                                         "water_sanitation", "fuel")) else 0))
        score = round(0.5 * need_severity + 0.3 * local_value + 0.2 * min(1, len(ben) / 3) - 0.08 * len(harms), 3)
        self.stats.update({"score": score, "harms": len(harms)})
        return {"beneficiaries": ben, "potential_harms": harms, "local_value_capture": local_value,
                "sdgs": SDG.get(hyp["domain"], []), "need_severity": round(need_severity, 3), "score": score,
                "price_reference_usd": price}


# ================================================================================= Audit
def _chain_tables() -> None:
    with db.tx() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS ledger_chain (id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL, actor TEXT,
                     action TEXT, object_type TEXT, object_id INTEGER, payload_hash TEXT, prev_hash TEXT, hash TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS dossiers (id INTEGER PRIMARY KEY AUTOINCREMENT, opportunity_id INTEGER,
                     at REAL, sha256 TEXT, body TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS governance_reviews (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     opportunity_id INTEGER, at REAL, verification TEXT, legal TEXT, red_team TEXT, impact TEXT,
                     recommendation TEXT, conditions TEXT, dossier_sha256 TEXT, ledger_id INTEGER)""")
        c.execute("""CREATE TABLE IF NOT EXISTS approvals (id INTEGER PRIMARY KEY AUTOINCREMENT, opportunity_id INTEGER,
                     review_id INTEGER, approver TEXT, decision TEXT, conditions TEXT, at REAL, ledger_id INTEGER)""")


def ledger_append(actor: str, action: str, object_type: str, object_id: int | None, payload) -> dict:
    """Append a tamper-evident entry: hash = sha256(prev_hash | at | actor | action | object | payload_hash)."""
    _chain_tables()
    ph = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    with db.tx() as c:
        prev = c.execute("SELECT hash FROM ledger_chain ORDER BY id DESC LIMIT 1").fetchone()
        prev_h = prev[0] if prev else "GENESIS"
        at = time.time()
        h = hashlib.sha256(f"{prev_h}|{at:.6f}|{actor}|{action}|{object_type}|{object_id}|{ph}".encode()).hexdigest()
        cur = c.execute("""INSERT INTO ledger_chain (at, actor, action, object_type, object_id, payload_hash, prev_hash, hash)
                           VALUES (?,?,?,?,?,?,?,?)""", (at, actor, action, object_type, object_id, ph, prev_h, h))
        return {"id": cur.lastrowid, "hash": h, "payload_hash": ph}


def verify_chain() -> dict:
    _chain_tables()
    prev = "GENESIS"
    rows = db.q("SELECT * FROM ledger_chain ORDER BY id")
    for r in rows:
        h = hashlib.sha256(f"{prev}|{r['at']:.6f}|{r['actor']}|{r['action']}|{r['object_type']}|{r['object_id']}|"
                           f"{r['payload_hash']}".encode()).hexdigest()
        if r["prev_hash"] != prev or r["hash"] != h:
            return {"intact": False, "broken_at": r["id"], "entries": len(rows)}
        prev = r["hash"]
    return {"intact": True, "entries": len(rows), "head": prev}


class AuditAgent(Agent):
    name = "audit"

    def execute(self, opportunity_id: int, reviews: dict | None = None) -> dict:
        _chain_tables()
        o = _opp(opportunity_id)
        sigs = db.q("""SELECT s.id, s.source, s.url, s.retrieved_at, s.published_at, s.content_hash FROM signals s
                       JOIN hypothesis_signals hs ON hs.signal_id=s.id WHERE hs.hypothesis_id=?""", (o["hypothesis_id"],))
        caps = db.q("""SELECT c.id, c.source, c.url, c.content_hash FROM capabilities c JOIN hypothesis_capabilities hc
                       ON hc.capability_id=c.id WHERE hc.hypothesis_id=?""", (o["hypothesis_id"],))
        runs = db.q("""SELECT id, agent, status, started_at FROM agent_runs WHERE params LIKE ? OR params LIKE ?
                       ORDER BY id""", (f'%"hypothesis_id": {o["hypothesis_id"]}%', f'%"opportunity_id": {opportunity_id}%'))
        dossier = {
            "opportunity": {k: o[k] for k in ("id", "hypothesis_id", "country", "object", "best_route", "opportunity_score",
                                              "evidence_confidence", "updated_at")},
            "evidence": sigs, "capabilities": caps,
            "inputs_provenance": (o["economics"] or {}).get("inputs"),
            "agent_runs": runs,
            "human_reviews": db.q("SELECT * FROM hypothesis_reviews WHERE hypothesis_id=?", (o["hypothesis_id"],)),
            "field_observations": db.q("""SELECT ob.id, ob.status, ob.submitted_at FROM scout_observations ob
                                          JOIN scout_missions m ON m.id=ob.mission_id WHERE m.hypothesis_id=?""",
                                       (o["hypothesis_id"],)),
            "governance": reviews or {},
        }
        body = json.dumps(dossier, sort_keys=True, default=str)
        sha = hashlib.sha256(body.encode()).hexdigest()
        db.insert("dossiers", {"opportunity_id": opportunity_id, "at": time.time(), "sha256": sha, "body": body})
        led = ledger_append(self.name, "dossier_sealed", "opportunity", opportunity_id, {"sha256": sha})
        self.stats.update({"evidence_items": len(sigs), "sha256": sha[:16]})
        return {"dossier_sha256": sha, "ledger_id": led["id"], "evidence_items": len(sigs),
                "capabilities": len(caps), "agent_runs": len(runs), "chain": verify_chain()}


# ================================================================================= Board
class GovernanceBoard(Agent):
    """Runs Verification → Legal & Safety → Red-Team → Impact → Audit, and issues the most cautious recommendation."""
    name = "governance_board"

    def execute(self, opportunity_id: int) -> dict:
        _chain_tables()
        strip = lambda r: {k: v for k, v in r.items() if k not in ("run_id", "status", "stats")}   # noqa: E731
        ver = strip(VerificationAgent().run(opportunity_id=opportunity_id))
        leg = strip(LegalSafetyAgent().run(opportunity_id=opportunity_id))
        red = strip(RedTeamAgent().run(opportunity_id=opportunity_id, verification=ver, legal=leg))
        imp = strip(ImpactAgent().run(opportunity_id=opportunity_id))
        conditions = []
        for f in leg.get("flags", []):
            if f["severity"] in ("blocker", "high", "medium"):
                conditions.append(f"[{f['severity']}] {f['area']}: {f['finding']}")
        conditions += [f"[red-team] {m['argument']}" for m in red.get("failure_modes", []) if m["severity"] == "high"]
        conditions += [f"[kill criterion] {k}" for k in red.get("kill_criteria", [])]
        conditions += [f"[impact] mitigate: {h['harm']} → {h['mitigation']}" for h in imp.get("potential_harms", [])]
        if leg.get("worst_severity") == "blocker" or red.get("verdict") == "kill":
            rec = "reject"
        elif red.get("verdict") == "pilot_only_with_conditions" or (ver.get("score") or 0) < 0.5:
            rec = "conditional_pilot"
        else:
            rec = "approve_pilot"
        aud = strip(AuditAgent().run(opportunity_id=opportunity_id, reviews={
            "verification_score": ver.get("score"), "legal_worst": leg.get("worst_severity"),
            "red_team_verdict": red.get("verdict"), "impact_score": imp.get("score"), "recommendation": rec}))
        led = ledger_append(self.name, f"recommendation:{rec}", "opportunity", opportunity_id,
                            {"recommendation": rec, "dossier": aud.get("dossier_sha256"), "conditions": conditions})
        rid = db.insert("governance_reviews", {
            "opportunity_id": opportunity_id, "at": time.time(), "verification": json.dumps(ver, default=str),
            "legal": json.dumps(leg, default=str), "red_team": json.dumps(red, default=str),
            "impact": json.dumps(imp, default=str), "recommendation": rec, "conditions": json.dumps(conditions),
            "dossier_sha256": aud.get("dossier_sha256"), "ledger_id": led["id"]})
        db.update("opportunities", opportunity_id, {"status": f"governance:{rec}", "updated_at": time.time()})
        self.stats.update({"review_id": rid, "recommendation": rec, "verification": ver.get("score"),
                           "legal_worst": leg.get("worst_severity"), "red_team": red.get("verdict"),
                           "impact": imp.get("score"), "chain_intact": (aud.get("chain") or {}).get("intact")})
        return {"review_id": rid, "recommendation": rec}


def approve(opportunity_id: int, approver: str, decision: str, conditions: str = "") -> dict:
    """Human gate: Execution requires a named human's decision on the latest governance review."""
    if decision not in ("approved", "rejected", "approved_with_conditions"):
        raise ValueError("decision must be approved | approved_with_conditions | rejected")
    if not approver.strip():
        raise ValueError("approver name required")
    _chain_tables()
    rev = db.q1("SELECT * FROM governance_reviews WHERE opportunity_id=? ORDER BY id DESC LIMIT 1", (opportunity_id,))
    if not rev:
        raise ValueError("no governance review yet — run the Governance Board first")
    if rev["recommendation"] == "reject" and decision != "rejected":
        conditions = (conditions + " | OVERRIDE of a governance 'reject' recommendation").strip(" |")
    led = ledger_append(f"human:{approver}", f"approval:{decision}", "opportunity", opportunity_id,
                        {"review_id": rev["id"], "dossier": rev["dossier_sha256"], "conditions": conditions})
    aid = db.insert("approvals", {"opportunity_id": opportunity_id, "review_id": rev["id"], "approver": approver,
                                  "decision": decision, "conditions": conditions, "at": time.time(), "ledger_id": led["id"]})
    db.update("opportunities", opportunity_id, {"status": f"human:{decision}", "updated_at": time.time()})
    return {"approval_id": aid, "ledger_id": led["id"], "decision": decision}
