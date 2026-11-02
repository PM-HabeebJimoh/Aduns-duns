"""Cross-Border Analogy Agent — finds places that solved a similar problem differently.

Ground-truth method (recent, multilingual, every continent — no reliance on self-reported statistics):

For the need's topic T and a target country, sample peer countries from *every* continent (same income group
first). For each country, measured in its own language and news edition over the last 90 days:

  solution_activity  – local news about solutions for T launching / expanding / working
                       ("startup", "launches", "now available", "expands", "solved", "reduced" …)
  need_pressure      – local news about T being short / unaffordable / in crisis, plus the engine's own
                       sensed need signals about T in that country

Positive deviants = countries with ≥3 recent local solution reports and a lower need-pressure share than the target.
Their solution headlines and apps are returned as the evidence of *how* they solved it.
Official WDI statistics are available as an optional, clearly-labelled secondary cross-check.
"""
from __future__ import annotations

import json
import math

import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from .. import db, geo, lexicon, nlp, taxonomy, translate
from ..sources import social as S
from .base import Agent

SOLUTION_WORDS = {
    "en": ["startup", "launches", "launched", "now available", "expands", "solution", "solved", "reduced", "new service"],
    "fr": ["startup", "lance", "lancement", "solution", "désormais disponible", "réduit"],
    "es": ["startup", "lanza", "lanzamiento", "solución", "ya disponible", "reduce"],
    "pt": ["startup", "lança", "lançamento", "solução", "já disponível", "reduz"],
    "ar": ["إطلاق", "حل", "شركة ناشئة", "متاح الآن"],
    "ru": ["стартап", "запустил", "решение", "теперь доступно"],
    "de": ["Startup", "startet", "Lösung", "jetzt verfügbar"],
    "id": ["startup", "meluncurkan", "solusi", "kini tersedia"],
    "sw": ["imezindua", "suluhisho", "kampuni changa"],
    "hi": ["स्टार्टअप", "लॉन्च", "समाधान"],
    "zh": ["初创", "推出", "解决方案", "上线"],
    "ja": ["スタートアップ", "開始", "解決", "提供開始"],
    "vi": ["khởi nghiệp", "ra mắt", "giải pháp"],
    "tr": ["girişim", "başlattı", "çözüm"],
}


def _topic_from_hyp(hyp: dict) -> str:
    base = (hyp.get("title") or "").split(" — ")[0]
    words = nlp.tokens(nlp.need_object(geo.strip_places(base)))
    if not words:
        words = db.loads(hyp.get("key_terms"), [])[:1]
    return " ".join(dict.fromkeys(words))[:60]


class CrossBorderAnalogyAgent(Agent):
    name = "cross_border_analogy"

    def execute(self, hypothesis_id: int | None = None, country: str = "", topic: str = "", domain: str = "",
                peers_per_continent: int = 3, top_k: int = 6, include_official: bool = False, **_) -> dict:
        hyp = db.q1("SELECT * FROM hypotheses WHERE id=?", (hypothesis_id,)) if hypothesis_id else None
        topic = topic or (_topic_from_hyp(hyp) if hyp else "")
        if not topic:
            raise ValueError("topic or hypothesis_id required")
        iso3 = geo.resolve(country) if country else None
        if not iso3 and hyp:
            ranked = Counter(db.loads(hyp["countries"], {})).most_common()
            iso3 = next((c for c, _ in ranked if geo.country(c)), None)
        if not iso3:
            raise ValueError("No target country: pass country= or use a hypothesis with geographic signals")
        domain = domain or (hyp or {}).get("domain") or taxonomy.classify_domain(topic)[0] or "general"
        target = geo.country(iso3)
        peers = self._peers(iso3, peers_per_continent, topic)
        self.stats.update({"target": iso3, "topic": topic, "domain": domain, "peers": len(peers),
                           "continents_sampled": sorted({geo.country(p)["continent"] for p in peers})})

        with ThreadPoolExecutor(max_workers=6) as ex:
            measures = dict(zip([iso3] + peers, ex.map(lambda k: self._measure(k, topic), [iso3] + peers)))
        t = measures[iso3]
        self.stats["target_measure"] = {k: v for k, v in t.items() if k != "evidence"}
        ranked = []
        for k in peers:
            m = measures[k]
            # needs real evidence of solutions (≥3 recent local reports) and lower pressure than the target
            if m["solution"] < 3 or m["pressure_share"] >= t["pressure_share"]:
                continue
            gain = math.log1p(m["solution"]) / math.log1p(40)
            relief = t["pressure_share"] - m["pressure_share"]
            same_income = geo.country(k)["income_id"] == target["income_id"]
            score = round(max(0.0, gain) * 0.6 + max(0.0, relief) * 0.8 + (0.2 if same_income else 0.0), 4)
            if score > 0:
                ranked.append((score, k, m, same_income))
        ranked.sort(key=lambda x: -x[0])
        ids: list[int] = []
        for score, k, m, same_income in ranked[:top_k]:
            row = {"hypothesis_id": hyp["id"] if hyp else None, "target_country": iso3, "analog_country": k,
                   "indicator_code": "ground:solution_vs_pressure",
                   "indicator_name": f"Recent solution activity vs need pressure for '{topic}' (local news, apps, sensed signals)",
                   "target_value": round(t["pressure_share"], 3), "analog_value": round(m["pressure_share"], 3),
                   "target_year": time.gmtime().tm_year, "analog_year": time.gmtime().tm_year,
                   "analog_change_10y": None, "income_similarity": 1.0 if same_income else 0.5,
                   "deviance_score": score, "evidence": json.dumps(m["evidence"][:8]), "retrieved_at": time.time(),
                   "method": "ground_signals", "topic": topic}
            existing = db.q1("""SELECT id FROM analogies WHERE hypothesis_id IS ? AND target_country=? AND analog_country=?
                                AND indicator_code=?""", (row["hypothesis_id"], iso3, k, row["indicator_code"]))
            if existing:
                db.update("analogies", existing["id"], {kk: vv for kk, vv in row.items() if kk not in ("hypothesis_id",)})
                ids.append(existing["id"])
            else:
                ids.append(db.insert("analogies", row))
            self.bump("analogies")
        if include_official and domain in taxonomy.DOMAINS and taxonomy.DOMAINS[domain]["indicators"]:
            ids += self._official(hyp, iso3, domain)
        if hyp:
            db.update("hypotheses", hyp["id"], {"processed_at": time.time()})
        return {"analogy_ids": ids, "target": target["name"], "measures": {
            k: {kk: vv for kk, vv in v.items() if kk != "evidence"} for k, v in measures.items()}}

    # ------------------------------------------------------------- peers
    def _peers(self, iso3: str, per_continent: int, topic: str) -> list[str]:
        cs = geo.countries()
        tgt = cs[iso3]
        swept = {r["country"] for r in db.q("SELECT country FROM sweeps")}
        salt = sum(map(ord, topic))
        out: list[str] = []
        for cont, members in geo.by_continent().items():
            k = per_continent + (2 if cont == tgt["continent"] else 0)
            cands = [m for m in members if m != iso3 and cs[m]["income_id"] not in ("", "NA")]
            cands.sort(key=lambda m: (cs[m]["income_id"] != tgt["income_id"], m not in swept,
                                      -len(cs[m]["cities"]), (hash(m) + salt) % 97))
            out += cands[:k]
        return out

    # ------------------------------------------------------------ measures
    def _measure(self, iso3: str, topic: str) -> dict:
        c = geo.country(iso3)
        lang = next((l for l in c["langs"] if l in lexicon.L), "en")
        name = c["name"].split(",")[0]
        local_topic = translate.from_english(topic, lang) if lang != "en" else topic
        sol_words = SOLUTION_WORDS.get(lang, SOLUTION_WORDS["en"])
        need_words = lexicon.search_terms(lang, 4)
        shared = lang == "en" or sum(1 for x in geo.countries().values() if x["langs"] and x["langs"][0] == lang) > 2
        loc = f" {name}" if shared else ""
        q_sol = f'"{local_topic}" ({" OR ".join(chr(34) + w + chr(34) for w in sol_words[:5])}){loc}'
        q_need = f'"{local_topic}" ({" OR ".join(chr(34) + w + chr(34) for w in need_words)}){loc}'
        sol = self.safe(f"news_sol:{iso3}", lambda: S.google_news(q_sol.replace(" when:30d", ""), c["iso2"], lang, 40), []) or []
        need = self.safe(f"news_need:{iso3}", lambda: S.google_news(q_need, c["iso2"], lang, 40), []) or []
        cutoff = time.time() - 90 * 86400
        from .need_sensing import _ts
        sol = [s for s in sol if (_ts(s["published_at"]) or 0) >= cutoff]
        need = [s for s in need if (_ts(s["published_at"]) or 0) >= cutoff]
        apps_rel: list[str] = []   # Play search is not storefront-specific, so apps are not used as a country measure
        own = db.q1("""SELECT COUNT(*) n FROM signals WHERE scope_country=? AND (text_en LIKE ? OR text LIKE ?)
                       AND COALESCE(published_ts, retrieved_at) >= ?""",
                    (iso3, f"%{topic.split()[0]}%", f"%{local_topic.split()[0]}%", cutoff))["n"]
        pressure = len(need) + own
        share = (pressure + 1) / (pressure + len(sol) + 2)
        evidence = [{"source": "news", "title": s["title"], "url": s["url"], "date": (s["published_at"] or "")[:10],
                     "kind": "solution"} for s in sol[:6]]
        evidence += [{"source": "googleplay", "title": a, "url": f"https://play.google.com/store/apps/details?id={a}&gl={c['iso2']}",
                      "kind": "app"} for a in apps_rel[:4]]
        return {"solution": len(sol), "need_news": len(need), "own_signals": own, "apps": len(apps_rel),
                "pressure_share": share, "lang": lang, "local_topic": local_topic, "evidence": evidence}

    # ------------------------------------------- optional official statistics
    def _official(self, hyp: dict | None, iso3: str, domain: str) -> list[int]:
        from ..sources import worldbank
        ids = []
        cs = geo.countries()
        for code, label, better in taxonomy.DOMAINS[domain]["indicators"][:1]:
            lat = self.safe(f"wdi:{code}", lambda code=code: worldbank.latest(code), {})
            if iso3 not in lat:
                continue
            v_t, y_t = lat[iso3]
            peers = [(k, v) for k, (v, y) in lat.items() if k in cs and k != iso3 and y >= time.gmtime().tm_year - 3
                     and cs[k]["income_id"] == cs[iso3]["income_id"]]
            peers.sort(key=lambda kv: -kv[1] if better == "higher" else kv[1])
            for k, v in peers[:3]:
                ids.append(db.insert("analogies", {
                    "hypothesis_id": hyp["id"] if hyp else None, "target_country": iso3, "analog_country": k,
                    "indicator_code": code, "indicator_name": f"(official, secondary) {label}", "target_value": v_t,
                    "analog_value": v, "target_year": y_t, "analog_year": lat[k][1], "income_similarity": 1.0,
                    "deviance_score": 0.1, "evidence": "[]", "retrieved_at": time.time(), "method": "official_statistics",
                    "topic": domain}, ignore=True))
        return [i for i in ids if i]
