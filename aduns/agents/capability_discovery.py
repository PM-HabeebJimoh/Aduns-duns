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


# Functional synonyms used for concept coverage (kept small and auditable).
SYNONYMS = {
    "solar": ["photovoltaic", "pv", "sun"], "freezer": ["refrigerator", "fridge", "refrigeration", "cold"],
    "fridge": ["refrigerator", "freezer", "refrigeration"], "dialysis": ["hemodialysis", "haemodialysis", "renal"],
    "generator": ["genset"], "tractor": ["tillage", "mechanization"], "loan": ["credit", "microfinance", "lending"],
    "water": ["potable", "drinking"], "dryer": ["drier", "drying", "dehydrator"], "internet": ["connectivity", "broadband"],
    "insulin": ["diabetes"], "oxygen": ["o2", "concentrator"], "battery": ["batteries", "storage"],
}


class CapabilityDiscoveryAgent(Agent):
    name = "capability_discovery"

    def execute(self, hypothesis_id: int | None = None, query: str = "", sources: list[str] | None = None,
                limit_per_source: int = 12, min_relevance: float = 0.6) -> dict:
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

        q_main = query or self._query_from_hypothesis(hyp, terms)
        srcs = sources or (taxonomy.DOMAINS.get(domain, {}).get("capability_sources")
                           or ["patents", "papers", "github", "worldbank_projects", "wikidata"])
        self.stats.update({"query": q_main, "sources": srcs, "domain": domain})

        found: list[dict] = []
        queries = [q_main]
        # Functional equivalents: also search the generic function within the domain
        # (e.g. "solar freezer" → "solar refrigeration" / "cold storage").
        generic = self._generic_query(q_main, domain)
        if generic and generic != q_main:
            queries.append(generic)
        self.stats["queries"] = queries
        for qi, q_main in enumerate(queries):
            found += self._search(srcs, q_main, domain, limit_per_source if qi == 0 else max(4, limit_per_source // 2))
        q_main = queries[0]
        self.stats["fetched"] = len(found)
        if not found:
            return {"capability_ids": []}
        self._concepts = self._concept_groups(q_main, domain)
        return self._link(found, hyp, hyp_text, target_countries, min_relevance)

    @staticmethod
    def _stem(w: str) -> str:
        """Crude but robust: drop plural 's', keep a 7-char prefix (refrigerator ≈ refrigeration)."""
        if w.endswith("s") and len(w) > 4:
            w = w[:-1]
        return w[:7]

    def _concept_groups(self, q: str, domain: str | None) -> list[set[str]]:
        """Each query word is a concept; domain vocabulary words are interchangeable functional equivalents."""
        dom_kw = set()
        for kw in taxonomy.DOMAINS.get(domain or "", {}).get("keywords", []):
            dom_kw.update(self._stem(w) for w in kw.split())
        groups = []
        for w in nlp.tokens(q):
            st = self._stem(w)
            syn = {self._stem(x) for x in SYNONYMS.get(w, [])}
            groups.append({st} | syn | (dom_kw if st in dom_kw else set()))
        return groups

    def relevance(self, text: str, qv, tf) -> float:
        stems = {self._stem(w) for w in nlp.tokens(text)}
        groups = getattr(self, "_concepts", [])
        coverage = (sum(1 for g in groups if g & stems) / len(groups)) if groups else 0.0
        cos = float(qv @ tf.transform(text))
        return round(0.75 * coverage + 0.25 * min(1.0, cos * 6), 4)

    def _search(self, srcs: list[str], q_main: str, domain: str | None, limit_per_source: int) -> list[dict]:
        found: list[dict] = []
        for s in srcs:
            fn = C.CAPABILITY_SOURCES.get(s)
            if s == "usaspending":
                found += self.safe("usaspending", lambda: C.usaspending_vendors(q_main.split()[:3], limit_per_source), [])
            elif fn:
                found += self.safe(s, lambda fn=fn: fn(q_main, limit_per_source), [])
            if s == "papers" and domain in ("health", "medicines", "agriculture", "water_sanitation", "cold_chain"):
                found += self.safe("europepmc", lambda: C.europepmc(q_main, limit_per_source), [])
        return found

    def _link(self, found: list[dict], hyp: dict | None, hyp_text: str, target_countries: list[str],
              min_relevance: float) -> dict:
        # de-duplicate across queries
        uniq: dict[tuple, dict] = {}
        for c in found:
            uniq.setdefault((c["source"], str(c["external_id"])), c)
        found = list(uniq.values())
        # Relevance = cosine(hypothesis, capability) in a shared TF-IDF space.
        docs = [hyp_text] + [f"{c['title']} {c.get('description') or ''}" for c in found]
        tf = nlp.TfIdf(docs)
        hv = tf.transform(hyp_text)
        qv = tf.transform(" ".join(" ".join(sorted(g)) for g in getattr(self, "_concepts", [])) or hyp_text)
        ids: list[int] = []
        if hyp:  # links are recomputed from scratch each run
            with db.tx() as conn:
                conn.execute("DELETE FROM hypothesis_capabilities WHERE hypothesis_id=?", (hyp["id"],))
        for c in found:
            ctext = f"{c['title']} {c.get('description') or ''}"
            cv = tf.transform(ctext)
            rel = self.relevance(ctext, qv, tf)
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

    NOISE = {"price", "prices", "sale", "buy", "cost", "cheap", "cheapest", "best", "near", "shop", "jumia", "konga",
             "amazon", "alibaba", "online", "new", "used", "brand", "review", "reviews", "much", "how", "deep"}

    def _query_from_hypothesis(self, hyp: dict | None, terms: list[str]) -> str:
        """The thing that is needed: the hypothesis object (title before ' — '), minus commerce noise."""
        base = (hyp or {}).get("title", "").split(" — ")[0] if hyp else ""
        words = [w for w in nlp.tokens(geo.strip_places(base)) if w not in self.NOISE]
        if len(words) < 2:
            words = [w for w in nlp.tokens(geo.strip_places(self._query_from_terms(terms))) if w not in self.NOISE]
        return " ".join(dict.fromkeys(words))[:80] or " ".join(terms[:2])

    @staticmethod
    def _generic_query(q: str, domain: str | None) -> str | None:
        generic = {
            "cold_chain": "refrigeration", "energy": "off-grid power", "water_sanitation": "water treatment",
            "health": "low-cost medical device", "medicines": "drug supply", "agriculture": "smallholder",
            "finance": "microfinance", "digital": "connectivity", "logistics": "last mile delivery",
            "manufacturing": "local manufacturing", "education_skills": "vocational training",
            "housing_construction": "low-cost housing", "business_services": "small business",
        }.get(domain or "")
        if not generic:
            return None
        head = q.split()[0] if q else ""
        return f"{head} {generic}".strip() if head and head not in generic else generic

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
