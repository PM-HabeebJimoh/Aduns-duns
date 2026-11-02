"""Opportunity-design layer: six agents that turn a discovered need into designed, costed delivery options.

    Market Structure  – market size (real imports), suppliers, incumbents, concentration, barriers
    Localization      – language, currency, real local prices, infrastructure limits, payment rails, channels
    Solution Composition – combines discovered capabilities into concrete offerings (with gaps listed)
    Delivery-Route    – scores the 14 delivery routes on 10 criteria from evidence; infeasible routes explained
    Economics         – Monte Carlo unit economics + capital + sensitivity; every input tagged real / official / assumption
    Defensibility     – sustainable advantages and imitation risk

Provenance rule: numbers from the world carry `kind: real|official` and a source URL. Where no free data exists
(e.g. customer-acquisition cost) the value is an explicit `assumption` range, and the sensitivity analysis turns the
assumptions that matter most into validation priorities for the Experiment agent. Nothing is presented as fact
that is not.
"""
from __future__ import annotations

import json
import math
import time
from collections import Counter

import numpy as np

from .. import db, geo, nlp, translate
from ..sources import market as MK
from ..sources import social as S
from .base import Agent

ROUTES = {
    "import_and_resell": "Import and resell",
    "local_distribution_partnership": "Local distribution partnership",
    "license_and_localize": "License and localize",
    "manufacture_locally": "Manufacture locally",
    "use_idle_capacity": "Use existing idle capacity",
    "subscription": "Deliver as a subscription",
    "service_instead_of_product": "Offer it as a service",
    "bundle": "Bundle with something customers already buy",
    "local_agents_retail": "Use local agents / retail networks",
    "software_layer": "Software layer over existing providers",
    "demand_aggregation": "Aggregate demand and negotiate supply",
    "cooperative_model": "Shared-access / cooperative model",
    "enable_existing_operator": "Enable an existing operator",
    "policy_pathway": "Policy / regulatory pathway",
}
CRITERIA = ["affordability", "speed", "upfront_capital", "margin", "regulatory", "operational_simplicity",
            "reliability", "defensibility", "local_impact", "scalability"]
# Structural priors per route archetype (0..1, higher = better). Judgement, not data — labelled as such in output.
ROUTE_PRIOR = {
    "import_and_resell":              {"speed": .8, "upfront_capital": .5, "operational_simplicity": .6},
    "local_distribution_partnership": {"speed": .8, "upfront_capital": .8, "operational_simplicity": .7},
    "license_and_localize":           {"speed": .4, "upfront_capital": .5, "operational_simplicity": .5},
    "manufacture_locally":            {"speed": .2, "upfront_capital": .2, "operational_simplicity": .3},
    "use_idle_capacity":              {"speed": .6, "upfront_capital": .7, "operational_simplicity": .5},
    "subscription":                   {"speed": .6, "upfront_capital": .4, "operational_simplicity": .5},
    "service_instead_of_product":     {"speed": .6, "upfront_capital": .5, "operational_simplicity": .4},
    "bundle":                         {"speed": .7, "upfront_capital": .7, "operational_simplicity": .7},
    "local_agents_retail":            {"speed": .7, "upfront_capital": .7, "operational_simplicity": .5},
    "software_layer":                 {"speed": .6, "upfront_capital": .7, "operational_simplicity": .6},
    "demand_aggregation":             {"speed": .6, "upfront_capital": .6, "operational_simplicity": .5},
    "cooperative_model":              {"speed": .4, "upfront_capital": .6, "operational_simplicity": .4},
    "enable_existing_operator":       {"speed": .7, "upfront_capital": .8, "operational_simplicity": .7},
    "policy_pathway":                 {"speed": .1, "upfront_capital": .9, "operational_simplicity": .3},
}
# Cost structure assumption ranges by archetype (% of revenue) — explicit assumptions to be validated.
COST_ASSUMPTIONS = {
    "product":  {"cac": (0.04, 0.15), "field_ops": (0.04, 0.12), "support": (0.01, 0.04), "fraud_loss": (0.005, 0.03),
                 "overhead": (0.05, 0.12)},
    "service":  {"cac": (0.08, 0.25), "field_ops": (0.10, 0.30), "support": (0.03, 0.08), "fraud_loss": (0.005, 0.03),
                 "overhead": (0.08, 0.15)},
    "platform": {"cac": (0.15, 0.40), "field_ops": (0.03, 0.10), "support": (0.04, 0.10), "fraud_loss": (0.01, 0.05),
                 "overhead": (0.10, 0.25)},
}
ROUTE_ARCHETYPE = {"software_layer": "platform", "demand_aggregation": "platform", "subscription": "service",
                   "service_instead_of_product": "service", "cooperative_model": "service", "policy_pathway": "service"}


# =============================================================================== context
def build_context(hypothesis_id: int, country: str = "") -> dict:
    hyp = db.q1("SELECT * FROM hypotheses WHERE id=?", (hypothesis_id,))
    if not hyp:
        raise ValueError(f"hypothesis {hypothesis_id} not found")
    ranked = Counter(db.loads(hyp["countries"], {})).most_common()
    iso3 = geo.resolve(country) if country else next((c for c, _ in ranked if geo.country(c)), None)
    if not iso3:
        raise ValueError("no target country for this hypothesis; pass country=")
    obj = nlp.need_object(geo.strip_places((hyp["title"] or "").split(" — ")[0])) or \
        " ".join(db.loads(hyp["key_terms"], [])[:1])
    sigs = db.q("""SELECT s.* FROM signals s JOIN hypothesis_signals hs ON hs.signal_id=s.id
                   WHERE hs.hypothesis_id=?""", (hypothesis_id,))
    caps = db.q("""SELECT c.*, hc.relevance FROM capabilities c JOIN hypothesis_capabilities hc ON hc.capability_id=c.id
                   WHERE hc.hypothesis_id=? ORDER BY hc.relevance DESC""", (hypothesis_id,))
    for c in caps:
        c["extra"] = db.loads(c["extra"], {})
        c["countries"] = db.loads(c["countries"], [])
        c["transferability"] = db.loads(c["transferability"], [])
    analogies = db.q("SELECT * FROM analogies WHERE hypothesis_id=? ORDER BY deviance_score DESC", (hypothesis_id,))
    # all recent signals about the object in the target country (beyond the hypothesis cluster)
    first = (obj.split() or [""])[0]
    local = db.q("""SELECT * FROM signals WHERE scope_country=? AND (text_en LIKE ? OR text LIKE ?)
                    AND COALESCE(published_ts, retrieved_at) >= ? LIMIT 500""",
                 (iso3, f"%{first}%", f"%{first}%", time.time() - 120 * 86400)) if first else []
    return {"hyp": hyp, "iso3": iso3, "country": geo.country(iso3), "object": obj, "signals": sigs, "caps": caps,
            "analogies": analogies, "local_signals": local}


def _iso2(iso3: str) -> str:
    c = geo.country(iso3)
    return c["iso2"] if c else ""


# ============================================================================ agents
class MarketStructureAgent(Agent):
    name = "market_structure"

    def execute(self, ctx: dict) -> dict:
        iso3, obj = ctx["iso3"], ctx["object"]
        hs, imports = self.safe("comtrade", lambda: MK.best_hs_for_market(obj, iso3), (None, None)) or (None, None)
        exports = self.safe("comtrade_x", lambda: MK.comtrade_flows(iso3, hs["hs"], "X"), None) if hs else None
        caps = ctx["caps"]
        iso2 = _iso2(iso3)
        incumbents = [c for c in caps if c["capability_type"] in ("local_digital_solution", "local_provider")
                      and (iso2 in c["countries"] or iso3 in c["countries"])]
        orgs_in_country = [c for c in caps if c["capability_type"] == "organization"
                           and (ctx["country"]["name"] in c["countries"])]
        sigs = ctx["signals"] + ctx["local_signals"]
        causes = Counter(cs for s in sigs for cs in db.loads(s["gap_causes"], []))
        institutional = sum(1 for s in sigs if s["source"] in ("ted", "pncp", "findatender", "prozorro", "secop",
                                                               "samgov", "worldbank_procurement"))
        active_patents = [c for c in caps if c["capability_type"] == "ip_patent" and iso2 in (c["extra"].get("active_in") or [])]
        if imports and (not exports or (exports.get("value_usd") or 0) < 0.2 * (imports.get("value_usd") or 0)):
            structure = "import-dependent"
        elif imports and exports:
            structure = "two-way trade (local production exists)"
        elif not hs:
            structure = "service market (no traded good)"
        else:
            structure = "no recorded imports (local or informal supply)"
        out = {
            "object": obj, "hs": hs, "imports": imports, "exports": exports and {k: exports[k] for k in
                                                                                  ("year", "value_usd", "net_kg", "source_url")},
            "structure": structure,
            "supply_concentration_hhi": (imports or {}).get("hhi"),
            "demand_evidence": {"hypothesis_signals": len(ctx["signals"]), "local_signals_120d": len(ctx["local_signals"]),
                                "sources": sorted({s["source"] for s in sigs})},
            "incumbents": [{"title": c["title"], "type": c["capability_type"], "url": c["url"],
                            "installs": c["extra"].get("installs")} for c in incumbents[:12]],
            "organizations_in_country": [{"title": c["title"], "url": c["url"]} for c in orgs_in_country[:10]],
            "barriers": {"regulation_mentions": causes.get("regulation", 0), "trust_mentions": causes.get("trust", 0),
                         "failed_public_tenders": institutional,
                         "active_patents_in_country": [{"title": c["title"], "holder": c["holder"], "url": c["url"]}
                                                       for c in active_patents[:5]]},
            "gap_causes": dict(causes.most_common()),
        }
        self.stats.update({"hs": (hs or {}).get("hs"), "imports_usd": (imports or {}).get("value_usd"),
                           "structure": structure, "incumbents": len(incumbents)})
        return out


class LocalizationAgent(Agent):
    name = "localization"

    def execute(self, ctx: dict, value_proposition: str = "", market_hs: str | None = None) -> dict:
        c, iso3 = ctx["country"], ctx["iso3"]
        cur = self.safe("currency", lambda: MK.currency_of(iso3), "USD") or "USD"
        fx = self.safe("fx", MK.fx_usd, {}) or {}
        texts = [s.get("text_en") or s["text"] for s in ctx["signals"] + ctx["local_signals"]] + \
                [s["text"] for s in ctx["signals"] + ctx["local_signals"] if s.get("text_en")]
        # Active local price discovery: the country's own news, in its language and in English (last 30 days)
        lang = next((l for l in (c.get("langs") or []) if l != "en"), "en")
        cname = c["name"].split(",")[0]
        queries = [(f'"{ctx["object"]}" price {cname}', "en")]
        if lang != "en":
            queries.append((f'"{translate.from_english(ctx["object"], lang)}" '
                            f'{translate.from_english("price", lang)} {cname}', lang))
        for q, ql in queries:
            for n in self.safe(f"price_news:{ql}", lambda q=q, ql=ql: S.google_news(q, c["iso2"], ql, 40), []) or []:
                texts.append(n["text"])
                en = translate.to_english(n["text"], ql) if ql != "en" else None
                if en:
                    texts.append(en)
        words = ctx["object"].split() + ([translate.from_english(ctx["object"], lang)] if lang != "en" else [])
        mentions = self.safe("prices", lambda: MK.price_mentions(texts, cur, words), []) or []
        mentions = MK.clean_price_mentions(mentions, MK.is_bulk(market_hs)) if mentions else []
        cutoff = time.time() - 90 * 86400
        infra = {}
        for label, words in {"power_outages": ["outage", "blackout", "load shedding", "power cut", "no electricity"],
                             "connectivity": ["internet", "network down", "no signal", "data cost"],
                             "fuel": ["fuel shortage", "fuel queue", "petrol", "diesel shortage"],
                             "roads_logistics": ["road", "transport cost", "delivery delay", "port congestion"]}.items():
            n = db.q1(f"""SELECT COUNT(*) n FROM signals WHERE scope_country=? AND COALESCE(published_ts, retrieved_at)>=?
                          AND ({' OR '.join(['LOWER(COALESCE(text_en,text)) LIKE ?'] * len(words))})""",
                      (iso3, cutoff, *[f"%{w}%" for w in words]))["n"]
            infra[label] = n
        pay = self.safe("payments", lambda: S.play_search("mobile money wallet", c["iso2"], "en", 6), []) or []
        reg = db.q("SELECT kind, COUNT(*) n FROM source_registry WHERE country=? GROUP BY kind", (iso3,))
        langs = c.get("langs") or ["en"]
        local_lang = next((l for l in langs if l != "en"), None)
        vp = value_proposition or f"Reliable, affordable {ctx['object']} where and when you need it."
        out = {
            "country": c["name"], "iso3": iso3, "languages": langs, "official_languages": c.get("languages"),
            "currency": cur, "usd_rate": fx.get(cur), "fx_source": "https://open.er-api.com/v6/latest/USD",
            "local_price_evidence": {"mentions": mentions[:15],
                                     "usd_summary": MK.consistent_price([m for m in mentions if m["currency"] in (cur, "USD")]),
                                     "kind": "real (consumer prices quoted in local news/signals; ≥2 consistent quotes "
                                             "required, else inconclusive)"},
            "infrastructure_constraints_90d": infra,
            "payment_rails_apps": pay,
            "local_channels": {r["kind"]: r["n"] for r in reg},
            "value_proposition": {"en": vp, local_lang: translate.from_english(vp, local_lang)} if local_lang else {"en": vp},
            "design_implications": self._implications(infra, pay, mentions),
        }
        self.stats.update({"price_mentions": len(mentions), "currency": cur})
        return out

    @staticmethod
    def _implications(infra: dict, pay: list, mentions: list) -> list[str]:
        out = []
        if infra.get("power_outages", 0) >= 3:
            out.append("Frequent power-outage signals: design for off-grid / battery / solar operation.")
        if infra.get("connectivity", 0) >= 3:
            out.append("Connectivity complaints: offline-first app, USSD/SMS fallback.")
        if infra.get("fuel", 0) >= 3:
            out.append("Fuel shortages: minimise fuel-dependent logistics, consolidate deliveries.")
        if pay:
            out.append("Mobile-money / wallet apps present: accept them as primary payment rail.")
        if not mentions:
            out.append("No local price quotes found yet: collect prices via field scouts before launch.")
        return out


class SolutionCompositionAgent(Agent):
    name = "solution_composition"

    def execute(self, ctx: dict, market: dict) -> dict:
        caps = ctx["caps"]
        by = {}
        for c in caps:
            by.setdefault(c["capability_type"], []).append(c)
        wholesale = self.safe("wholesale", lambda: MK.wholesale_prices(ctx["object"], 15), []) if market.get("hs") else []
        ow = [w[:4] for w in nlp.tokens(ctx["object"]) if len(w) > 2]
        wholesale = [w for w in wholesale or [] if any(o in w["name"].lower() for o in ow)]

        def comp(role, c):
            return {"role": role, "title": c["title"], "type": c["capability_type"], "url": c["url"],
                    "holder": c.get("holder"), "capability_id": c.get("id")}
        local_partners = by.get("local_provider", []) + by.get("local_digital_solution", [])
        designs = by.get("open_design", []) + [p for p in by.get("ip_patent", [])
                                               if _iso2(ctx["iso3"]) not in (p["extra"].get("active_in") or [])]
        offerings = []
        sourcing = [{"role": "supply", "title": w["name"], "type": "wholesale_listing", "url": w["url"],
                     "holder": w["supplier"], "price_usd": [w["price_min_usd"], w["price_max_usd"]]} for w in wholesale[:3]]
        imp = (market.get("imports") or {}).get("partners") or []
        sourcing += [{"role": "supply_country", "title": f"Current supplier country {p['iso3']} "
                      f"({(p['share'] or 0):.0%} of imports)", "type": "trade_flow", "url": market["imports"]["source_url"]}
                     for p in imp[:2] if p.get("iso3")]
        if sourcing:
            offerings.append({"name": f"Sourced {ctx['object']} with local distribution",
                              "components": sourcing + [comp("distribution", c) for c in local_partners[:3]],
                              "routes": ["import_and_resell", "local_distribution_partnership", "local_agents_retail"],
                              "gaps": [] if local_partners else ["no local distribution partner identified yet"]})
        if designs:
            offerings.append({"name": f"Locally made {ctx['object']} from proven designs",
                              "components": [comp("design", c) for c in designs[:3]] +
                                            [comp("fabrication_partner", c) for c in by.get("local_provider", [])[:2]] +
                                            [comp("know_how", c) for c in by.get("skill_knowhow", [])[:2]],
                              "routes": ["manufacture_locally", "license_and_localize"],
                              "gaps": [] if by.get("local_provider") else ["no local fabricator identified yet"]})
        if by.get("unused_asset"):
            offerings.append({"name": f"{ctx['object'].capitalize()} using idle / surplus capacity",
                              "components": [comp("idle_asset", c) for c in by["unused_asset"][:3]] +
                                            [comp("distribution", c) for c in local_partners[:2]],
                              "routes": ["use_idle_capacity", "enable_existing_operator"], "gaps": []})
        if local_partners or by.get("program_model"):
            offerings.append({"name": f"{ctx['object'].capitalize()} access as a service / platform",
                              "components": [comp("operator", c) for c in local_partners[:4]] +
                                            [comp("proven_model", c) for c in by.get("program_model", [])[:2]],
                              "routes": ["software_layer", "demand_aggregation", "service_instead_of_product",
                                         "subscription", "enable_existing_operator", "cooperative_model"],
                              "gaps": [] if len(local_partners) >= 2 else ["few existing operators to aggregate"]})
        if by.get("research") or by.get("organization"):
            offerings.append({"name": f"Transfer of a proven {ctx['object']} solution",
                              "components": [comp("knowledge", c) for c in by.get("research", [])[:2]] +
                                            [comp("holder", c) for c in by.get("organization", [])[:3]],
                              "routes": ["license_and_localize", "local_distribution_partnership"], "gaps": []})
        self.stats.update({"offerings": len(offerings), "wholesale_listings": len(wholesale)})
        return {"offerings": offerings, "wholesale": wholesale[:10],
                "capability_mix": {k: len(v) for k, v in by.items()}}


class DefensibilityAgent(Agent):
    name = "defensibility"

    def execute(self, ctx: dict, market: dict, composition: dict) -> dict:
        mix = composition.get("capability_mix", {})
        holders = {c.get("holder") for c in ctx["caps"] if c["capability_type"] in ("ip_patent", "organization") and c.get("holder")}
        active = market["barriers"]["active_patents_in_country"]
        n_inc = len(market["incumbents"])
        missions = db.q1("SELECT COUNT(*) n FROM scout_missions WHERE hypothesis_id=?", (ctx["hyp"]["id"],))["n"]
        factors = {
            "exclusivity_potential": min(1.0, (0.5 if active else 0.2) + (0.3 if 0 < len(holders) <= 5 else 0)),
            "network_effects": 0.7 if n_inc >= 3 else 0.4,
            "switching_costs": 0.5,
            "local_relationships": min(1.0, 0.2 + 0.2 * missions + 0.05 * n_inc),
            "data_advantage": min(1.0, len(ctx["signals"]) / 50),
            "regulatory_moat": min(1.0, market["barriers"]["regulation_mentions"] / 10 + market["barriers"]["failed_public_tenders"] / 20),
            "scale_economies": min(1.0, math.log1p(((market.get("imports") or {}).get("value_usd") or 0) / 1e6) / 6),
        }
        imitation = min(1.0, 0.2 + 0.1 * mix.get("open_design", 0) / 3 + 0.08 * n_inc + (0.2 if not active else 0))
        score = round(float(np.mean(list(factors.values()))) * (1 - 0.5 * imitation), 3)
        notes = []
        if active:
            notes.append(f"{len(active)} patent(s) active in the country: license for exclusivity or design around.")
        if n_inc >= 3:
            notes.append(f"{n_inc} incumbents found: a layer that coordinates them gains network effects; competing head-on does not.")
        if mix.get("open_design"):
            notes.append("Open designs exist: easy to copy — defensibility must come from distribution, brand and relationships.")
        if (market.get("supply_concentration_hhi") or 0) > 0.5:
            notes.append("Imports come from very few countries: diversified sourcing is an advantage and a resilience pitch.")
        self.stats.update({"score": score, "imitation_risk": round(imitation, 3)})
        return {"factors": {k: round(v, 3) for k, v in factors.items()}, "imitation_risk": round(imitation, 3),
                "score": score, "notes": notes, "kind": "heuristic scoring from evidence"}


class DeliveryRouteAgent(Agent):
    name = "delivery_route"

    def execute(self, ctx: dict, market: dict, loc: dict, composition: dict, defens: dict) -> dict:
        mix = composition["capability_mix"]
        offered = {r for o in composition["offerings"] for r in o["routes"]}
        sigs = ctx["signals"]
        types = Counter(t for s in sigs for t in db.loads(s["need_types"], []))
        n_countries = len(db.loads(ctx["hyp"]["countries"], {}))
        local_price = (loc["local_price_evidence"]["usd_summary"] or {}).get("median")
        unit_cost = self._unit_cost(market, composition)
        margin_ev = (local_price - unit_cost) / local_price if local_price and unit_cost and local_price > 0 else None
        reg = market["barriers"]["regulation_mentions"]
        feas = {
            "import_and_resell": (bool(composition["wholesale"]) or bool(market.get("imports")), "needs a supplier (wholesale listing or trade flow)"),
            "local_distribution_partnership": (bool(market["incumbents"]) or bool(market["organizations_in_country"]), "needs a local partner"),
            "license_and_localize": (bool(market["barriers"]["active_patents_in_country"]) or mix.get("research", 0) + mix.get("organization", 0) > 0, "needs an IP/know-how holder"),
            "manufacture_locally": (mix.get("open_design", 0) + mix.get("ip_patent", 0) > 0 and bool(market.get("hs")), "needs a design and a physical product"),
            "use_idle_capacity": (mix.get("unused_asset", 0) > 0, "needs evidence of idle/surplus capacity"),
            "subscription": (bool(market.get("hs")) or types.get("unaffordable", 0) > 0, "needs a recurring or costly good"),
            "service_instead_of_product": (True, ""),
            "bundle": (len(loc["payment_rails_apps"]) > 0 or bool(market["incumbents"]), "needs an existing purchase channel"),
            "local_agents_retail": (loc["local_channels"].get("telegram", 0) + len(market["incumbents"]) > 0, "needs a local agent/retail network"),
            "software_layer": (len(market["incumbents"]) >= 2, "needs ≥2 existing providers to coordinate"),
            "demand_aggregation": (types.get("latent_search", 0) + types.get("unmet", 0) + types.get("scarcity", 0) >= 5, "needs many small buyers"),
            "cooperative_model": (mix.get("program_model", 0) > 0 or ctx["hyp"].get("domain") in ("agriculture", "food", "energy", "water_sanitation"), "needs a shared-asset domain"),
            "enable_existing_operator": (bool(market["incumbents"]) or bool(market["organizations_in_country"]), "needs an existing operator"),
            "policy_pathway": (market["barriers"]["failed_public_tenders"] > 0 or reg >= 2 or mix.get("program_model", 0) > 0, "needs an institutional/regulatory lever"),
        }
        routes = []
        for key, label in ROUTES.items():
            ok, why = feas[key]
            prior = ROUTE_PRIOR[key]
            crit = {
                "affordability": 0.5 if local_price is None or unit_cost is None else max(0.0, min(1.0, 1 - unit_cost / max(local_price, 1e-9) + 0.3)),
                "speed": prior["speed"], "upfront_capital": prior["upfront_capital"],
                "margin": 0.5 if margin_ev is None else max(0.0, min(1.0, margin_ev + 0.2)),
                "regulatory": max(0.1, 1 - reg / 10) if key != "policy_pathway" else 0.6,
                "operational_simplicity": prior["operational_simplicity"],
                "reliability": 1 - 0.5 * ((market.get("supply_concentration_hhi") or 0.5) if key == "import_and_resell" else 0.3),
                "defensibility": defens["score"] + (0.15 if key in ("software_layer", "demand_aggregation", "license_and_localize") else 0),
                "local_impact": min(1.0, 0.3 + float(ctx["hyp"]["score"] or 0)),
                "scalability": min(1.0, 0.2 + n_countries / 10 + (0.2 if key in ("software_layer", "license_and_localize", "demand_aggregation") else 0)),
            }
            score = round(float(np.mean(list(crit.values()))) * (1.0 if ok else 0.0) * (1.1 if key in offered else 1.0), 4)
            routes.append({"route": key, "label": label, "feasible": ok, "why_not": None if ok else why,
                           "criteria": {k: round(v, 3) for k, v in crit.items()}, "score": score,
                           "supported_by_offering": key in offered})
        routes.sort(key=lambda r: -r["score"])
        self.stats.update({"feasible": sum(r["feasible"] for r in routes), "best": routes[0]["route"]})
        return {"routes": routes, "inputs": {"local_price_usd": local_price, "unit_cost_usd": unit_cost,
                                             "unit_cost_source": ("Comtrade import unit value (USD/kg, bulk good)"
                                                                  if MK.is_bulk((market.get("hs") or {}).get("hs"))
                                                                  else "manufacturer FOB listings (Made-in-China)"),
                                             "margin_evidence": margin_ev},
                "note": "speed/capital/simplicity are route-archetype priors (judgement); other criteria are computed from evidence"}

    @staticmethod
    def _unit_cost(market: dict, composition: dict) -> float | None:
        """Per-unit wholesale price for manufactured goods; per-kg import unit value only for bulk commodities
        (so it is comparable with local per-kg/per-litre prices)."""
        w = composition.get("wholesale") or []
        hs = (market.get("hs") or {}).get("hs")
        if w and not MK.is_bulk(hs):
            return float(np.median([(x["price_min_usd"] + x["price_max_usd"]) / 2 for x in w]))
        uv = (market.get("imports") or {}).get("unit_value_usd_per_kg")
        return float(uv) if uv and MK.is_bulk(hs) else None


class EconomicsAgent(Agent):
    name = "economics"

    def execute(self, ctx: dict, market: dict, loc: dict, routes: dict, n: int = 4000, seed: int = 7) -> dict:
        rng = np.random.default_rng(seed)
        price_sum = loc["local_price_evidence"]["usd_summary"]
        unit_cost = routes["inputs"]["unit_cost_usd"]
        inputs: dict[str, dict] = {}
        if price_sum:
            lo, hi = price_sum["p25"], max(price_sum["p75"], price_sum["p25"] * 1.01)
            if price_sum.get("weak"):
                lo, hi = price_sum["median"] * 0.8, price_sum["median"] * 1.2
            inputs["price_usd"] = {"range": [lo, hi], "kind": "real", "weak": bool(price_sum.get("weak")),
                                   "source": f"local consumer price quotes (n={price_sum['n']})"}
        if unit_cost:
            inputs["unit_cost_usd"] = {"range": [unit_cost * 0.85, unit_cost * 1.15], "kind": "real",
                                       "source": routes["inputs"].get("unit_cost_source") or "trade data"}
        if "price_usd" not in inputs and unit_cost:
            inputs["price_usd"] = {"range": [unit_cost * 1.6, unit_cost * 2.5], "kind": "assumption",
                                   "source": "retail markup 1.6–2.5× over landed cost — verify with local price scouting"}
        if "unit_cost_usd" not in inputs and price_sum:
            inputs["unit_cost_usd"] = {"range": [price_sum["median"] * 0.45, price_sum["median"] * 0.7], "kind": "assumption",
                                       "source": "COGS 45–70% of local price — verify with suppliers"}
        if "price_usd" not in inputs:
            return {"econ_status": "insufficient_data", "missing": ["local price", "unit cost"],
                    "next_step": "Collect ≥10 local price quotes and ≥3 supplier quotes via the field mission."}
        lend = MK.lending_rate(ctx["iso3"])
        inputs["lending_rate"] = ({"range": [lend[0] / 100 * 0.9, lend[0] / 100 * 1.1], "kind": "official",
                                   "source": f"World Bank FR.INR.LEND {lend[1]}"} if lend else
                                  {"range": [0.08, 0.25], "kind": "assumption", "source": "no recent official rate"})
        imports_usd = (market.get("imports") or {}).get("value_usd")
        if imports_usd:
            inputs["market_usd"] = {"range": [imports_usd * 0.9, imports_usd * 1.1], "kind": "real",
                                    "source": f"Comtrade imports {market['imports']['year']} (HS {market['hs']['hs']})"}
        else:
            inputs["market_usd"] = {"range": [2e5, 5e6], "kind": "assumption", "source": "no trade data — size via field test"}
        inputs["capture_share"] = {"range": [0.003, 0.03], "kind": "assumption", "source": "year-1 share 0.3–3% — validate with pilot"}
        is_goods = bool(market.get("hs"))
        landed = {"freight_insurance": (0.08, 0.20), "import_duty": (0.0, 0.35), "local_logistics": (0.05, 0.12)} if is_goods else {}
        for k, (a, b) in landed.items():
            inputs[k] = {"range": [a, b], "kind": "assumption", "source": "verify tariff schedule & freight quotes"}
        inputs["income_tax"] = {"range": [0.15, 0.35], "kind": "assumption", "source": "verify national corporate tax rate"}
        inputs["working_capital_days"] = {"range": [30, 90], "kind": "assumption", "source": "supplier/customer terms"}
        results = []
        top = [r for r in routes["routes"] if r["feasible"]][:3]
        for r in top:
            arche = ROUTE_ARCHETYPE.get(r["route"], "product")
            costs = COST_ASSUMPTIONS[arche]
            draws = {k: rng.uniform(*v["range"], n) for k, v in inputs.items()}
            opex = {k: rng.uniform(*v, n) for k, v in costs.items()}
            price, cost = draws["price_usd"], draws["unit_cost_usd"]
            if is_goods and r["route"] in ("import_and_resell", "local_distribution_partnership", "local_agents_retail", "bundle"):
                landed_cost = cost * (1 + draws["freight_insurance"]) * (1 + draws["import_duty"]) * (1 + draws["local_logistics"])
            elif r["route"] in ("manufacture_locally", "license_and_localize"):
                landed_cost = cost * rng.uniform(0.7, 1.1, n)   # assumption: local make 70–110% of import cost
            else:
                landed_cost = cost * (1 + draws.get("local_logistics", np.zeros(n)))
            gross = (price - landed_cost) / price
            opex_pct = sum(opex.values())
            revenue = draws["market_usd"] * draws["capture_share"]
            fin = draws["lending_rate"] * draws["working_capital_days"] / 365 * (landed_cost / price)
            ebt = gross - opex_pct - fin
            net = np.where(ebt > 0, ebt * (1 - draws["income_tax"]), ebt)
            units = revenue / price
            capital = revenue * (draws["working_capital_days"] / 365) * (landed_cost / price) + \
                {"product": 25000, "service": 40000, "platform": 60000}[arche] * rng.uniform(0.6, 1.6, n)
            profit = net * revenue
            payback = np.where(profit > 0, capital / np.maximum(profit / 12, 1e-9), np.inf)
            sens = {}
            all_in = {**draws, **opex}
            nr = np.argsort(np.argsort(net))
            for k, v in all_in.items():
                vr = np.argsort(np.argsort(v))
                c = float(np.corrcoef(vr, nr)[0, 1]) if np.std(v) > 0 else 0.0
                sens[k] = round(c, 3)
            drivers = sorted(sens.items(), key=lambda kv: -abs(kv[1]))[:5]
            q = lambda a: {"p10": float(np.percentile(a, 10)), "p50": float(np.percentile(a, 50)), "p90": float(np.percentile(a, 90))}
            fin_payback = payback[np.isfinite(payback)]
            results.append({
                "route": r["route"], "label": r["label"], "archetype": arche,
                "gross_margin": q(gross), "net_margin": q(net), "revenue_year1_usd": q(revenue),
                "net_profit_year1_usd": q(profit), "capital_needed_usd": q(capital), "units_year1": q(units),
                "payback_months_p50": float(np.median(fin_payback)) if len(fin_payback) else None,
                "p_profitable": round(float((net > 0).mean()), 3),
                "top_drivers": [{"input": k, "spearman": v, "kind": (inputs.get(k) or {}).get("kind", "assumption")}
                                for k, v in drivers],
                "opex_assumptions": {k: list(v) for k, v in costs.items()},
            })
        key = ["price_usd", "unit_cost_usd", "market_usd"]
        confidence = round(sum((0.5 if inputs.get(k, {}).get("weak") else 1.0) for k in key
                               if inputs.get(k, {}).get("kind") in ("real", "official")) / len(key), 3)
        # results whose top-2 drivers include unverified assumptions (e.g. import duty) deserve less confidence
        if results:
            n_assume = sum(1 for d in results[0]["top_drivers"][:2] if d["kind"] == "assumption")
            confidence = round(confidence * (1 - 0.25 * n_assume), 3)
        validate = []
        for res in results[:1]:
            for d in res["top_drivers"]:
                if d["kind"] == "assumption":
                    validate.append(d["input"])
        self.stats.update({"routes_modelled": len(results),
                           "best_p_profitable": max((x["p_profitable"] for x in results), default=None)})
        return {"econ_status": "modelled", "simulations": n, "inputs": inputs, "routes": results,
                "evidence_confidence": confidence,
                "validation_priorities": validate,
                "method": "Monte Carlo over input ranges; real/official inputs from sources, assumptions explicit"}


# ============================================================================ designer
class OpportunityDesigner(Agent):
    """Runs the six design agents for one hypothesis and stores an `opportunities` record."""
    name = "opportunity_designer"

    def execute(self, hypothesis_id: int, country: str = "") -> dict:
        _ensure_table()
        ctx = build_context(hypothesis_id, country)
        market = MarketStructureAgent().run(ctx=ctx)
        loc = LocalizationAgent().run(ctx=ctx, market_hs=((_clean(market).get("hs") or {}).get("hs")))
        comp = SolutionCompositionAgent().run(ctx=ctx, market=_clean(market))
        defens = DefensibilityAgent().run(ctx=ctx, market=_clean(market), composition=_clean(comp))
        routes = DeliveryRouteAgent().run(ctx=ctx, market=_clean(market), loc=_clean(loc), composition=_clean(comp),
                                          defens=_clean(defens))
        econ = EconomicsAgent().run(ctx=ctx, market=_clean(market), loc=_clean(loc), routes=_clean(routes))
        parts = [market, loc, comp, defens, routes, econ]
        failed = [p for p in parts if p.get("status") == "error"]
        best = (_clean(routes).get("routes") or [{}])[0]
        e = _clean(econ)
        p_prof = max((x["p_profitable"] for x in e.get("routes", [])), default=None)
        conf = e.get("evidence_confidence", 0.0)
        # profitability only counts as far as it rests on real inputs (assumption-driven results pulled to 0.5)
        p_eff = 0.5 + ((p_prof if p_prof is not None else 0.5) - 0.5) * conf
        opp_score = round((best.get("score") or 0) * (0.5 + 0.5 * p_eff)
                          * (0.5 + float(ctx["hyp"]["score"] or 0)), 4)
        row = {"hypothesis_id": hypothesis_id, "country": ctx["iso3"], "object": ctx["object"],
               "market": json.dumps(_clean(market), default=str), "localization": json.dumps(_clean(loc), default=str),
               "composition": json.dumps(_clean(comp), default=str), "defensibility": json.dumps(_clean(defens), default=str),
               "routes": json.dumps(_clean(routes), default=str), "economics": json.dumps(e, default=str),
               "best_route": best.get("route"), "p_profitable": p_prof, "opportunity_score": opp_score,
               "evidence_confidence": conf,
               "status": "designed" if not failed else "partial", "updated_at": time.time()}
        ex = db.q1("SELECT id FROM opportunities WHERE hypothesis_id=? AND country=?", (hypothesis_id, ctx["iso3"]))
        if ex:
            db.update("opportunities", ex["id"], row)
            oid = ex["id"]
        else:
            oid = db.insert("opportunities", {**row, "created_at": time.time()})
        db.audit(self.name, "opportunity_designed", "opportunity", oid, {"best_route": best.get("route"),
                                                                         "score": opp_score})
        self.stats.update({"opportunity_id": oid, "best_route": best.get("route"), "p_profitable": p_prof,
                           "score": opp_score, "failed_parts": [p.get("run_id") for p in failed]})
        return {"opportunity_id": oid}


def _clean(res: dict) -> dict:
    """Strip run bookkeeping from an agent result."""
    return {k: v for k, v in res.items() if k not in ("run_id", "status", "stats")} if res.get("status") != "error" else {}


def _ensure_table() -> None:
    with db.tx() as c:
        try:
            c.execute("ALTER TABLE opportunities ADD COLUMN evidence_confidence REAL")
        except Exception:  # noqa: BLE001 — table missing (created below) or column exists
            pass
        c.execute("""CREATE TABLE IF NOT EXISTS opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT, hypothesis_id INTEGER, country TEXT, object TEXT,
            market TEXT, localization TEXT, composition TEXT, defensibility TEXT, routes TEXT, economics TEXT,
            best_route TEXT, p_profitable REAL, opportunity_score REAL, evidence_confidence REAL, status TEXT,
            created_at REAL, updated_at REAL,
            UNIQUE(hypothesis_id, country))""")
