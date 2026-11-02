"""Signal Fusion Agent — turns weak, scattered signals into testable need hypotheses.

One complaint is noise; many related signals across unrelated sources, layers and places reveal a
missing market. Method:
  1. TF-IDF vectors (unigrams+bigrams, need objects up-weighted) over stored signals.
  2. Average-linkage agglomerative clustering on cosine similarity.
  3. Score each cluster on volume, source diversity, layer diversity, intensity, engagement,
     recency, latent/normalized share and geographic focus.
  4. Explain the gap (dominant causes), state the hypothesis, and generate falsification tests.
"""
from __future__ import annotations

import json
import math
import time
from collections import Counter
from datetime import datetime, timezone

import numpy as np

from .. import db, geo, http, llm, nlp, taxonomy
from .base import Agent

TEST_TEMPLATES = {
    "unmet": "Interview ≥15 likely buyers{where}: if fewer than 30% say they searched for '{obj}' in the last 6 months and failed to obtain it, reject.",
    "unaffordable": "Collect ≥10 real price quotes for '{obj}'{where} and compare with the landed cost from the cheapest verified foreign supplier: if the local price premium is <25%, reject the affordability gap.",
    "normalized": "Ask ≥15 affected people{where} how they cope today; if fewer than 40% describe a recurring loss/delay they accept as normal, reject.",
    "scarcity": "Check stock at ≥10 distributors/retailers{where} over 2 weeks: if '{obj}' is in stock at ≥70%, reject the scarcity claim.",
    "inefficient": "Document ≥10 current workarounds{where}; if the workaround costs <10% of a proper solution's price over a year, reject.",
    "unaware": "Show ≥15 respondents{where} an existing solution for '{obj}': if <30% were unaware it exists, reject the awareness gap.",
    "latent_search": "Run a 7-day landing page / WhatsApp number for '{obj}'{where} with a small ad budget: if conversion to a contact is <2%, reject.",
    "institutional": "Confirm with ≥3 institutional buyers (procurement officers, clinics, cooperatives){where} that '{obj}' requirements went unfilled or under-supplied in the past 12 months; otherwise reject.",
}

WEIGHTS = {"volume": 0.22, "source_diversity": 0.18, "layer_diversity": 0.10, "intensity": 0.14,
           "engagement": 0.08, "recency": 0.10, "latent_normalized": 0.10, "geo_focus": 0.08}


def _parse_date(s: str | None) -> float | None:
    if not s:
        return None
    for fmt in (None, "%m/%d/%Y", "%Y"):
        try:
            if fmt is None:
                return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc).timestamp()
        except (ValueError, TypeError):
            continue
    return None


class SignalFusionAgent(Agent):
    name = "signal_fusion"

    def execute(self, query: str = "", domain: str = "", country: str = "", min_need_score: float = 0.35,
                threshold: float = 0.22, min_cluster_size: int = 2, max_signals: int = 4000,
                allow_structural_singletons: bool = True) -> dict:
        where, params = ["need_score >= ?"], [min_need_score]
        if query:
            where.append("(query = ? OR text LIKE ?)")
            params += [query, f"%{query}%"]
        if domain:
            where.append("domain = ?")
            params.append(domain)
        iso3 = geo.resolve(country) if country else None
        if iso3:
            where.append("countries LIKE ?")
            params.append(f'%"{iso3}"%')
        rows = db.q(f"SELECT * FROM signals WHERE {' AND '.join(where)} ORDER BY id DESC LIMIT ?",
                    (*params, max_signals))
        self.stats["signals_considered"] = len(rows)
        if not rows:
            return {"hypothesis_ids": []}

        docs = []
        for r in rows:
            objs = " ".join(db.loads(r["entities"], []))
            title = r["title"] if r["title"] and r["title"] not in r["text"] else ""
            # Geography is tracked separately: strip place names so "X in Lagos" and "X in Kano" cluster together.
            doc = geo.strip_places(f"{title} {r['text']} {objs} {objs}")
            docs.append(nlp.QUERY_TEMPLATE_WORDS.sub(" ", doc))
        tf = nlp.TfIdf(docs, min_df=1)
        M = tf.matrix()
        sim = nlp.cosine_sim_matrix(M)
        clusters = nlp.agglomerative(sim, threshold=threshold)
        self.stats["clusters"] = len(clusters)

        hyp_ids: list[int] = []
        for cl in clusters:
            members = [rows[i] for i in cl]
            structural_single = (len(cl) == 1 and allow_structural_singletons
                                 and members[0]["layer"] == "structural" and members[0]["need_score"] >= 0.7)
            if len(cl) < min_cluster_size and not structural_single:
                continue
            centroid = M[cl].mean(axis=0)
            hid = self._upsert(members, centroid, tf, [float(centroid @ M[i]) for i in cl])
            if hid:
                hyp_ids.append(hid)
        self.stats["hypotheses"] = len(hyp_ids)
        return {"hypothesis_ids": hyp_ids}

    # ---------------------------------------------------------------- scoring
    @staticmethod
    def score(members: list[dict]) -> tuple[float, dict]:
        n = len(members)
        sources = {m["source"].split(":")[0] for m in members}
        layers = {m["layer"] for m in members}
        now = time.time()
        recent = 0
        dated = 0
        for m in members:
            ts = _parse_date(m.get("published_at"))
            if ts:
                dated += 1
                recent += ts > now - 365 * 86400
        countries = Counter(c for m in members for c in db.loads(m["countries"], []))
        latent = sum(1 for m in members if {"normalized", "latent_search"} & set(db.loads(m["need_types"], [])))
        geo_focus = (countries.most_common(1)[0][1] / n) if countries else 0.0
        parts = {
            "volume": min(1.0, math.log1p(n) / math.log1p(40)),
            "source_diversity": min(1.0, len(sources) / 4),
            "layer_diversity": min(1.0, len(layers) / 3),
            "intensity": float(np.mean([m["intensity"] or 0 for m in members])),
            "engagement": float(np.mean([m["engagement"] or 0 for m in members])),
            "recency": (recent / dated) if dated else 0.5,
            "latent_normalized": latent / n,
            "geo_focus": geo_focus,
        }
        total = sum(WEIGHTS[k] * v for k, v in parts.items())
        # Single-source clusters are claims, not corroborated markets: dampen them.
        total *= 0.6 + 0.4 * min(1.0, (len(sources) - 1) / 2)
        return round(total, 4), {k: round(v, 3) for k, v in parts.items()}

    @staticmethod
    def _label(terms: list[str]) -> str:
        """Readable 1–3 word label from top terms without repeated words."""
        words: list[str] = []
        for t in terms[:3]:
            for w in t.split():
                if w not in words:
                    words.append(w)
            if len(words) >= 2:
                break
        return " ".join(words[:3])

    def _upsert(self, members: list[dict], centroid: np.ndarray, tf: nlp.TfIdf, sims: list[float]) -> int | None:
        terms = tf.top_terms(centroid, k=8)
        if not terms:
            return None
        doms = Counter(m["domain"] for m in members if m["domain"])
        domain = doms.most_common(1)[0][0] if doms else taxonomy.classify_domain(" ".join(terms))[0]
        types = Counter(t for m in members for t in db.loads(m["need_types"], []))
        causes = Counter(c for m in members for c in db.loads(m["gap_causes"], []))
        countries = Counter(c for m in members for c in db.loads(m["countries"], []))
        objs = Counter(o for m in members for o in db.loads(m["entities"], []))
        score, breakdown = self.score(members)
        sources = {m["source"].split(":")[0] for m in members}
        layers = {m["layer"] for m in members}

        top_obj = objs.most_common(1)[0][0] if objs and objs.most_common(1)[0][1] >= 2 else self._label(terms)
        top_c = [geo.country(c)["name"] if geo.country(c) else c for c, _ in countries.most_common(3)]
        where = f" in {', '.join(top_c)}" if top_c else ""
        dom_type = types.most_common(1)[0][0] if types else "unmet"
        cause_txt = ", ".join(c for c, _ in causes.most_common(3)) or "not yet evident"
        title = f"{top_obj.capitalize()} — {dom_type.replace('_', ' ')} need{where}"
        statement = (
            f"{len(members)} independent signals from {len(sources)} source(s) across {len(layers)} layer(s) "
            f"indicate a {dom_type.replace('_', ' ')} need around '{top_obj}' ({', '.join(terms[:5])}){where}. "
            f"Dominant need types: {', '.join(f'{t} ({c})' for t, c in types.most_common(4))}. "
            f"Likely gap causes: {cause_txt}."
        )
        tests = []
        for t, _ in types.most_common(3):
            if t in TEST_TEMPLATES:
                tests.append(TEST_TEMPLATES[t].format(obj=top_obj, where=where))
        if not tests:
            tests.append(TEST_TEMPLATES["unmet"].format(obj=top_obj, where=where))

        validated_field = any(m["source"].startswith("field") for m in members) and db.q1(
            "SELECT COUNT(*) n FROM scout_observations WHERE status='validated' AND signal_id IN (%s)"
            % ",".join(str(m["id"]) for m in members))["n"] >= 2
        evidence = "field_verified" if validated_field else ("corroborated" if len(sources) >= 2 else "claim")

        fp = http.content_hash(domain, *sorted(terms[:4]))
        existing = db.q1("SELECT id FROM hypotheses WHERE fingerprint=?", (fp,))
        row = {
            "title": title[:200], "need_statement": statement, "domain": domain,
            "key_terms": json.dumps(terms), "countries": json.dumps(dict(countries.most_common(10))),
            "need_types": json.dumps(dict(types)), "gap_causes": json.dumps(dict(causes)),
            "signal_count": len(members), "source_count": len(sources), "layer_count": len(layers),
            "score": score, "score_breakdown": json.dumps(breakdown), "evidence_level": evidence,
            "tests": json.dumps(tests), "updated_at": time.time(),
        }
        if llm.enabled():
            summ = llm.summarize_hypothesis(terms, [dict(m) for m in members])
            if summ:
                row["llm_summary"] = json.dumps(summ)
        if existing:
            hid = existing["id"]
            db.update("hypotheses", hid, row)
            self.bump("hypotheses_updated")
        else:
            hid = db.insert("hypotheses", {**row, "fingerprint": fp, "status": "open", "created_at": time.time()})
            self.bump("hypotheses_created")
            db.audit(self.name, "hypothesis_created", "hypothesis", hid, {"title": title, "score": score})
        with db.tx() as conn:
            for m, s in zip(members, sims):
                conn.execute("INSERT OR REPLACE INTO hypothesis_signals (hypothesis_id, signal_id, similarity) VALUES (?,?,?)",
                             (hid, m["id"], round(s, 4)))
        return hid
