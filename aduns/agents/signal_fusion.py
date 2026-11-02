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

WEIGHTS = {"volume": 0.16, "source_diversity": 0.18, "layer_diversity": 0.10, "need_strength": 0.16,
           "intensity": 0.10, "engagement": 0.06, "recency": 0.08, "latent_normalized": 0.08, "geo_focus": 0.08}


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

    def execute(self, query: str = "", domain: str = "", country: str = "", continent: str = "",
                min_need_score: float = 0.35, threshold: float = 0.17, min_cluster_size: int = 2,
                window_days: int | None = None, max_per_partition: int = 3000,
                allow_structural_singletons: bool = True) -> dict:
        """Cluster recent signals (English translations) into hypotheses, partitioned by need domain.

        Partitioning keeps clustering tractable when the 24/7 sweep accumulates tens of thousands of signals
        while still letting one hypothesis span many countries and continents (global needs)."""
        from .. import config
        window = window_days or config.MAX_AGE_DAYS
        where, params = ["need_score >= ?", "COALESCE(published_ts, retrieved_at) >= ?"], \
            [min_need_score, time.time() - window * 86400]
        if query:
            where.append("(query = ? OR text LIKE ? OR text_en LIKE ?)")
            params += [query, f"%{query}%", f"%{query}%"]
        if domain:
            where.append("domain = ?")
            params.append(domain)
        iso3 = geo.resolve(country) if country else None
        if iso3:
            where.append("countries LIKE ?")
            params.append(f'%"{iso3}"%')
        if continent:
            where.append("continent = ?")
            params.append(continent)
        # One clustering space for all needs (a need's words — not our domain label — decide what merges);
        # very large windows are processed newest-first in slices of max_per_partition.
        doms = [domain] if domain else [None]
        full_run = not (query or domain or iso3 or continent)
        hyp_ids: list[int] = []
        self._taken: set[int] = set()
        considered: set[int] = set()
        for dom in doms:
            dom_sql, dom_p = ("AND domain = ?", (dom,)) if dom else ("", ())
            rows = db.q(f"SELECT * FROM signals WHERE {' AND '.join(where)} {dom_sql} "
                        "ORDER BY COALESCE(published_ts, retrieved_at) DESC LIMIT ?", (*params, *dom_p, max_per_partition))
            if not rows:
                continue
            self.bump("signals_considered", len(rows))
            considered |= {r["id"] for r in rows}
            docs = []
            for r in rows:
                objs = " ".join(db.loads(r["entities"], []))
                body = r.get("text_en") or r["text"]
                if r["source"] in ("googlenews", "gdelt"):
                    body = nlp.strip_publisher(body)
                title = r["title"] if r["title"] and r["title"] not in r["text"] and not r.get("text_en") else ""
                objs = f"{objs} {objs}"   # the needed object weighs more than incidental words
                # Geography is tracked separately: strip place names so "X in Lagos" and "X in Kano" cluster together.
                doc = geo.strip_places(f"{title} {body} {objs} {objs}")
                docs.append(nlp.normalize_need_words(nlp.QUERY_TEMPLATE_WORDS.sub(" ", doc)))
            tf = nlp.TfIdf(docs, min_df=1)
            M = tf.matrix()
            if M.shape[1] == 0:
                continue
            clusters = nlp.agglomerative(nlp.cosine_sim_matrix(M), threshold=threshold)
            self.bump("clusters", len(clusters))
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
                    self._taken.add(hid)
        self.stats["hypotheses"] = len(hyp_ids)
        self._supersede(hyp_ids, considered)
        if full_run and hyp_ids:
            # hypotheses no longer supported by current evidence are retired (field-verified ones are kept)
            stale = db.q(f"""SELECT id FROM hypotheses WHERE status IN ('open') AND evidence_level != 'field_verified'
                             AND id NOT IN ({','.join('?' * len(hyp_ids))})""", hyp_ids)
            for h in stale:
                db.update("hypotheses", h["id"], {"status": "stale", "updated_at": time.time()})
            self.stats["retired"] = len(stale)
        return {"hypothesis_ids": hyp_ids}

    @staticmethod
    def _sigs(hid: int) -> set[int]:
        return {r["signal_id"] for r in db.q("SELECT signal_id FROM hypothesis_signals WHERE hypothesis_id=?", (hid,))}

    def _match_existing(self, member_ids: set[int], taken: set[int]) -> int | None:
        """Stable identity: an existing live hypothesis sharing >= 50% of its evidence with this cluster."""
        best, best_ov = None, 0.0
        cands = db.q(f"""SELECT DISTINCT hs.hypothesis_id id FROM hypothesis_signals hs JOIN hypotheses h ON h.id=hs.hypothesis_id
                         WHERE h.status != 'superseded' AND hs.signal_id IN ({','.join('?' * len(member_ids))})""",
                     list(member_ids))
        for c in cands:
            if c["id"] in taken:
                continue
            sigs = self._sigs(c["id"])
            ov = len(sigs & member_ids) / max(1, min(len(sigs), len(member_ids)))
            if ov >= 0.5 and ov > best_ov:
                best, best_ov = c["id"], ov
        return best

    def _supersede(self, current: list[int], considered: set[int]) -> None:
        """Older hypotheses whose evidence (within this run's scope) now lives mostly in a current one."""
        if not current:
            return
        cur_sigs = {h: self._sigs(h) for h in current}
        for old in db.q(f"SELECT id FROM hypotheses WHERE status != 'superseded' AND id NOT IN ({','.join('?' * len(current))})",
                        current):
            sigs = self._sigs(old["id"]) & considered
            if not sigs:
                continue
            for h, cs in cur_sigs.items():
                if len(sigs & cs) / len(sigs) >= 0.5:
                    db.update("hypotheses", old["id"], {"status": "superseded", "updated_at": time.time()})
                    db.audit(self.name, "hypothesis_superseded", "hypothesis", old["id"], {"by": h})
                    self.bump("superseded")
                    break

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
            ts = m.get("published_ts") or _parse_date(m.get("published_at"))
            if ts:
                dated += 1
                recent += 0.5 ** (max(0.0, now - ts) / (30 * 86400))   # 30-day half-life
        countries = Counter(c for m in members for c in db.loads(m["countries"], []))
        latent = sum(1 for m in members if "normalized" in set(db.loads(m["need_types"], [])))
        pain_types = {"unmet", "unaffordable", "scarcity", "inefficient", "institutional", "normalized"}
        strength = float(np.mean([(m.get("need_score") or 0.5) * (1.0 if pain_types & set(db.loads(m["need_types"], []))
                                                            else 0.5) for m in members]))
        geo_focus = (countries.most_common(1)[0][1] / n) if countries else 0.0
        # a need that recurs in many countries is a bigger, more replicable market
        spread = min(1.0, len(countries) / 8)
        geo_focus = max(geo_focus, spread)
        parts = {
            "volume": min(1.0, math.log1p(n) / math.log1p(40)),
            "source_diversity": min(1.0, len(sources) / 4),
            "layer_diversity": min(1.0, len(layers) / 3),
            "intensity": float(np.mean([m["intensity"] or 0 for m in members])),
            "engagement": float(np.mean([m["engagement"] or 0 for m in members])),
            "recency": (recent / dated) if dated else 0.5,
            "latent_normalized": latent / n,
            "need_strength": strength,
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
        continents = Counter(m.get("continent") for m in members if m.get("continent"))
        scope = ("global" if len(continents) >= 3 else "multi-country" if len(countries) >= 2 else
                 "local" if countries else "unlocated")
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
        member_ids = {m["id"] for m in members}
        hid_match = self._match_existing(member_ids, self._taken)
        existing = {"id": hid_match} if hid_match else db.q1(
            "SELECT id FROM hypotheses WHERE fingerprint=? AND status != 'superseded'", (fp,))
        if existing and existing["id"] in self._taken:
            existing = None
        if not existing and db.q1("SELECT id FROM hypotheses WHERE fingerprint=?", (fp,)):
            fp = http.content_hash(fp, time.time())  # fingerprint held by a superseded/other hypothesis
        row = {
            "title": title[:200], "need_statement": statement, "domain": domain,
            "key_terms": json.dumps(terms), "countries": json.dumps(dict(countries.most_common(10))),
            "need_types": json.dumps(dict(types)), "gap_causes": json.dumps(dict(causes)),
            "signal_count": len(members), "source_count": len(sources), "layer_count": len(layers),
            "score": score, "score_breakdown": json.dumps(breakdown), "evidence_level": evidence,
            "tests": json.dumps(tests), "updated_at": time.time(),
            "continents": json.dumps(dict(continents)), "scope": scope,
        }
        if llm.enabled():
            summ = llm.summarize_hypothesis(terms, [dict(m) for m in members])
            if summ:
                row["llm_summary"] = json.dumps(summ)
        if existing:
            hid = existing["id"]
            db.update("hypotheses", hid, row)
            with db.tx() as conn:  # evidence set is recomputed each run
                conn.execute("DELETE FROM hypothesis_signals WHERE hypothesis_id=? AND signal_id NOT IN "
                             "(SELECT id FROM signals WHERE source LIKE 'field:%')", (hid,))
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
