"""Capability Discovery Agent — finds suppliers, IP, research, open designs, programme models and
organisations that could serve a hypothesised need (functional equivalents, not just identical items).

Hidden-capability heuristics:
  * Patent families inactive in the target country → design is free to make there (manufacture locally).
  * Active patents → licence-and-localise route with the named holder.
  * Permissively licensed open hardware/software → local fabrication / deployment.
  * Closed World Bank projects → a delivery/institutional model already executed somewhere.
  * Firms that already delivered it to a public buyer (USAspending) → proven vendors / partners.
"""
from __future__ import annotations

import json
import time

from .. import db, geo, http, nlp, taxonomy
from ..sources import capabilities as C
from .base import Agent

ROUTE_LABELS = {
    "import_and_resell": "Import and resell", "local_distribution_partnership": "Local distribution partnership",
    "license_and_localize": "License and localize", "manufacture_locally": "Manufacture locally",
    "open_design_adaptation": "Adapt an open/expired design", "software_layer": "Software layer over providers",
    "expert_transfer": "Bring in expertise / train local teams", "service_instead_of_product": "Offer as a service",
    "policy_pathway": "Policy / regulatory pathway", "cooperative_model": "Cooperative / shared-access model",
    "enable_existing_operator": "Enable an existing operator", "demand_aggregation": "Aggregate demand",
}


class CapabilityDiscoveryAgent(Agent):
    name = "capability_discovery"

    def execute(self, hypothesis_id: int | None = None, query: str = "", sources: list[str] | None = None,
                limit_per_source: int = 12, min_relevance: float = 0.04) -> dict:
        hyp = db.q1("SELECT * FROM hypotheses WHERE id=?", (hypothesis_id,)) if hypothesis_id else None
        if not hyp and not query:
            raise ValueError("hypothesis_id or query required")
        terms = db.loads(hyp["key_terms"], []) if hyp else nlp.tokens(query)
        domain = (hyp or {}).get("domain") or taxonomy.classify_domain(query)[0]
        target_countries = list(db.loads(hyp["countries"], {}).keys()) if hyp else []
        # Hypothesis text = its statement + the strongest member signals
        hyp_text = query
        if hyp:
            sig = db.q("""SELECT s.text FROM signals s JOIN hypothesis_signals hs ON hs.signal_id=s.id
                          WHERE hs.hypothesis_id=? ORDER BY hs.similarity DESC LIMIT 15""", (hyp["id"],))
            hyp_text = hyp["need_statement"] + " " + " ".join(s["text"][:400] for s in sig)

        q_main = query or self._query_from_terms(terms)
        srcs = sources or (taxonomy.DOMAINS.get(domain, {}).get("capability_sources")
                           or ["patents", "papers", "github", "worldbank_projects", "wikidata"])
        self.stats.update({"query": q_main, "sources": srcs, "domain": domain})

        found: list[dict] = []
        for s in srcs:
            fn = C.CAPABILITY_SOURCES.get(s)
            if s == "usaspending":
                found += self.safe("usaspending", lambda: C.usaspending_vendors(q_main.split()[:3], limit_per_source), [])
            elif fn:
                found += self.safe(s, lambda fn=fn: fn(q_main, limit_per_source), [])
            if s == "papers" and domain in ("health", "medicines", "agriculture", "water_sanitation", "cold_chain"):
                found += self.safe("europepmc", lambda: C.europepmc(q_main, limit_per_source), [])
        self.stats["fetched"] = len(found)
        if not found:
            return {"capability_ids": []}

        # Relevance = cosine(hypothesis, capability) in a shared TF-IDF space.
        docs = [hyp_text] + [f"{c['title']} {c.get('description') or ''}" for c in found]
        tf = nlp.TfIdf(docs)
        hv = tf.transform(hyp_text)
        ids: list[int] = []
        for c in found:
            cv = tf.transform(f"{c['title']} {c.get('description') or ''}")
            rel = float(hv @ cv)
            if rel < min_relevance:
                self.bump("dropped_irrelevant")
                continue
            routes = list(c.get("transferability") or [])
            rationale = self._rationale(c, target_countries, tf, hv, cv)
            if c["capability_type"] == "ip_patent":
                active = set((c.get("extra") or {}).get("active_in") or [])
                tgt2 = {geo.country(t)["iso2"] for t in target_countries if geo.country(t)}
                if tgt2 and not (tgt2 & active):
                    routes = ["manufacture_locally", "open_design_adaptation"] + [r for r in routes if r not in (
                        "manufacture_locally", "open_design_adaptation")]
            h = http.content_hash(c["source"], c["external_id"])
            cid = db.insert("capabilities", {
                "source": c["source"], "capability_type": c["capability_type"], "external_id": str(c["external_id"]),
                "url": c.get("url"), "title": (c.get("title") or "")[:400], "description": (c.get("description") or "")[:3000],
                "holder": (c.get("holder") or "")[:300], "countries": json.dumps(c.get("countries") or []),
                "year": c.get("year"), "maturity": c.get("maturity"), "transferability": json.dumps(routes),
                "retrieved_at": time.time(), "content_hash": h, "extra": json.dumps(c.get("extra") or {}),
            }, ignore=True)
            if not cid:
                cid = db.q1("SELECT id FROM capabilities WHERE content_hash=?", (h,))["id"]
                db.update("capabilities", cid, {"transferability": json.dumps(routes), "maturity": c.get("maturity")})
            ids.append(cid)
            self.bump(f"cap:{c['capability_type']}")
            if hyp:
                with db.tx() as conn:
                    conn.execute("""INSERT OR REPLACE INTO hypothesis_capabilities
                                    (hypothesis_id, capability_id, relevance, rationale) VALUES (?,?,?,?)""",
                                 (hyp["id"], cid, round(rel, 4), rationale))
        self.stats["linked"] = len(ids)
        return {"capability_ids": ids}

    @staticmethod
    def _query_from_terms(terms: list[str]) -> str:
        words: list[str] = []
        for t in terms:
            for w in t.split():
                if w not in words:
                    words.append(w)
            if len(words) >= 4:
                break
        return " ".join(words[:4])

    @staticmethod
    def _rationale(c: dict, targets: list[str], tf: nlp.TfIdf, hv, cv) -> str:
        shared = [t for t in tf.top_terms(hv * cv, k=5)]
        extra = c.get("extra") or {}
        bits = [f"shares: {', '.join(shared)}" if shared else "lexical match"]
        if c["capability_type"] == "ip_patent":
            act = extra.get("active_in") or []
            tgt2 = [geo.country(t)["iso2"] for t in targets if geo.country(t)]
            if tgt2 and not set(tgt2) & set(act):
                bits.append(f"patent not active in {', '.join(tgt2)} → design may be free to practise there (verify with counsel)")
            elif act:
                bits.append(f"active in {', '.join(act[:6])} → licensing route via {c.get('holder') or 'holder'}")
        if c["capability_type"] == "open_design" and extra.get("license"):
            bits.append(f"open licence {extra['license']}, {extra.get('stars', 0)} stars")
        if c["capability_type"] == "program_model":
            bits.append(f"{extra.get('status', '')} World Bank programme in {extra.get('country', '')}")
        if c["capability_type"] == "proven_vendor":
            bits.append(f"delivered US${extra.get('amount_usd', 0):,.0f} to {extra.get('agency', 'a public buyer')}")
        if c["capability_type"] == "research" and extra.get("citations"):
            bits.append(f"{extra['citations']} citations")
        routes = [ROUTE_LABELS.get(r, r) for r in (c.get("transferability") or [])[:3]]
        if routes:
            bits.append("routes: " + "; ".join(routes))
        return " | ".join(bits)
