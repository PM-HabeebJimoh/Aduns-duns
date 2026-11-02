"""Need Sensing Agent — universal, multilingual, recent.

Sweeps one country at a time (the scheduler rotates every country on every continent) or runs a focused
search. For each country it listens to that country's own platforms *in its own languages*:

  invisible   Google Trends (today's rising searches), Google autocomplete (what people try to buy/get/afford)
  scattered   Bluesky, YouTube (this month), Reddit country communities, Telegram channels (auto-discovered),
              Mastodon, Lemmy, Google Play reviews of the country's essential-service apps
  visible     Google News country edition (last 30 days), GDELT local press (translingual)
  structural  WFP measured market-price spikes, World Bank procurement notices, failed/cancelled tenders
              (Prozorro, SECOP, SAM.gov), drug shortages, consumer complaints, GDACS disaster alerts

Every candidate is (1) date-checked (older than ADUNS_MAX_AGE_DAYS → dropped), (2) need-detected in its own
language (69-language lexicon) and (3) translated to English (Wikimedia MinT) so the Signal Fusion Agent can
merge needs across languages and countries. New Telegram channels and subreddits mentioned in collected text
are added to the source registry (snowball discovery) and crawled on the next sweep.
"""
from __future__ import annotations

import json
import re
import statistics
import time
from datetime import datetime, timezone

from .. import config, db, geo, http, lexicon, nlp, taxonomy, translate
from ..sources import institutional as I
from ..sources import procurement as P
from ..sources import seeds
from ..sources import needs as legacy
from ..sources import social as S
from ..sources import worldbank
from .base import Agent

GLOBAL_SOURCES = ["gdacs", "fda", "cfpb", "samgov", "prozorro", "secop", "hackernews"]
COUNTRY_SOURCES = ["trends", "autocomplete", "news", "bluesky", "youtube", "reddit", "telegram", "mastodon", "lemmy",
                   "gdelt", "googleplay", "wfp", "wb_procurement", "local_channels", "procurement"]
INSTITUTIONAL = ("prozorro", "secop", "samgov", "worldbank_procurement", "ted", "pncp", "findatender")
NO_QUERY_SOURCES = {"googletrends", "reddit", "telegram", "gdacs", "prozorro", "secop", "wfp_prices", "openfda",
                    "worldbank_procurement", "cfpb", "samgov"}
ALWAYS_NEED = {"wfp_prices", "prozorro", "secop", "openfda", "samgov", "gdacs", "ted", "pncp", "findatender"}
SUBREDDIT_RE = re.compile(r"(?<![\w/])r/([A-Za-z0-9_]{3,21})\b")


def _ts(s: str | None) -> float | None:
    if not s:
        return None
    s = str(s).strip()
    for fmt in (None, "%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S.%f", "%Y"):
        try:
            if fmt is None:
                d = datetime.fromisoformat(s.replace("Z", "+00:00"))
            else:
                d = datetime.strptime(s, fmt)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return d.timestamp()
        except ValueError:
            continue
    return None


_SHARED: dict[str, bool] = {}


def _shared_language(lang: str) -> bool:
    """Is this language spoken as a primary language in several countries (needs a country keyword)?"""
    if lang not in _SHARED:
        _SHARED[lang] = sum(1 for c in geo.countries().values() if lang in c["langs"][:2]) >= 2
    return _SHARED[lang]


class NeedSensingAgent(Agent):
    name = "need_sensing"

    # ------------------------------------------------------------------ entry
    def execute(self, country: str = "", focus: str = "", sources: list[str] | None = None, depth: int = 1,
                min_need_score: float = 0.3, include_global: bool = False, **_) -> dict:
        iso3 = geo.resolve(country) if country else None
        focus = (focus or "").strip()
        if not iso3 and not focus and not include_global:
            raise ValueError("Pass country= (sweep), focus= (worldwide focused search) or include_global=True")
        stored: list[int] = []
        if iso3:
            stored += self.sweep_country(iso3, focus=focus, sources=sources, depth=depth, min_need_score=min_need_score)
        elif focus:
            stored += self.focused_worldwide(focus, depth=depth, min_need_score=min_need_score)
        if include_global:
            stored += self.global_feeds(min_need_score=min_need_score)
        self.stats["signals_stored"] = len(stored)
        return {"signal_ids": stored}

    # ----------------------------------------------------------- country sweep
    def sweep_country(self, iso3: str, focus: str = "", sources: list[str] | None = None, depth: int = 1,
                      min_need_score: float = 0.3) -> list[int]:
        c = geo.country(iso3)
        if not c:
            raise ValueError(f"unknown country {iso3}")
        srcs = set(sources or COUNTRY_SOURCES)
        iso2, name = c["iso2"], c["name"].split(",")[0]
        langs = [l for l in c["langs"] if lexicon.L.get(l, {}).get("search")][:2] or ["en"]
        if "en" not in langs and depth > 1:
            langs.append("en")
        self.stats.update({"country": iso3, "continent": c["continent"], "langs": langs, "focus": focus})
        raw: list[tuple[dict, str]] = []   # (record, language of the text)
        jobs: list[tuple[str, object, str]] = []

        def add(label: str, fn, lang: str):
            jobs.append((label, fn, lang))

        primary = langs[0]
        if "trends" in srcs:
            add("googletrends", lambda: S.google_trends(iso2), primary)
        if "autocomplete" in srcs:
            for lang in langs:
                for tpl in lexicon.suggest_templates(lang)[: 3 + depth]:
                    prefix = tpl.split("{x}")[0].strip()
                    if focus:
                        prefix = tpl.replace("{x}", focus) if "{x}" in tpl else f"{tpl} {focus}"
                    if prefix:
                        add("googlesuggest", lambda p=prefix, l=lang: S.autocomplete(p + " ", iso2, l), lang)
        cues_by_lang = {l: ([focus] if focus else lexicon.search_terms(l, 4 + depth)) for l in langs}
        if "news" in srcs:
            for lang in langs:
                terms = cues_by_lang[lang]
                q = " OR ".join(f'"{t}"' for t in terms[:6])
                if focus:
                    q = f'"{focus}" ({" OR ".join(chr(34) + t + chr(34) for t in lexicon.search_terms(lang, 4))})'
                if _shared_language(lang) and lang != "en" or (lang == "en" and iso3 not in ("USA", "GBR")):
                    q = f"({q}) {name}"
                add("googlenews", lambda q=q, l=lang: S.google_news(q, iso2, l, 40), lang)
        if "bluesky" in srcs:
            for lang in langs:
                shared = _shared_language(lang) or lang == "en"
                for t in cues_by_lang[lang][: 2 + depth]:
                    q = f"{t} {name}" if shared else t
                    add("bluesky", lambda q=q, l=lang: S.bluesky(q, l if l != "en" else None, 40), lang)
        if "youtube" in srcs:
            for t in cues_by_lang[primary][: 1 + depth]:
                add("youtube", lambda t=t: S.youtube_search(f"{t} {name}", iso2, primary), primary)
        if "reddit" in srcs:
            for sub in self._subreddits(c):
                add(f"reddit:{sub}", lambda sub=sub: S.reddit_subreddit(sub), primary)
        if "local_channels" in srcs:
            # Wikidata seeds this country's own media/agency channels (Telegram, YouTube, subreddits) once a month.
            seeded = self.safe("wikidata_seeds", lambda: seeds.seed_country(iso3), {}) or {}
            if seeded and not seeded.get("skipped"):
                self.stats["seeded"] = seeded
            for ch in db.q("SELECT handle FROM source_registry WHERE kind='youtube_channel' AND country=? AND active=1 "
                           "ORDER BY COALESCE(last_crawled,0) LIMIT ?", (iso3, 4 * depth)):
                add(f"youtube_channel:{ch['handle']}", lambda h=ch["handle"]: seeds.youtube_channel_feed(h), primary)
                db.execute("UPDATE source_registry SET last_crawled=? WHERE kind='youtube_channel' AND handle=?",
                           (time.time(), ch["handle"]))
        if "telegram" in srcs:
            for ch in db.q("SELECT handle FROM source_registry WHERE kind='telegram' AND country=? AND active=1 "
                           "ORDER BY COALESCE(last_crawled,0) LIMIT ?", (iso3, 4 * depth)):
                add(f"telegram:{ch['handle']}", lambda h=ch["handle"]: S.telegram_channel(h), primary)
                db.execute("UPDATE source_registry SET last_crawled=? WHERE kind='telegram' AND handle=?",
                           (time.time(), ch["handle"]))
        if "mastodon" in srcs:
            for t in cues_by_lang[primary][:2]:
                if " " not in t:
                    add("mastodon", lambda t=t: S.mastodon_tag(t, primary), primary)
        if "lemmy" in srcs and primary in S.LEMMY_BY_LANG:
            add("lemmy", lambda: S.lemmy_search(f"{cues_by_lang[primary][0]} {name}", primary), primary)
        if "gdelt" in srcs:
            q = '("shortage of" OR "price hike" OR "scarcity" OR "lack of" OR "long queues")'
            if focus:
                q = f'"{focus}"'
            add("gdelt", lambda: S.gdelt_country(q, name, 75), "en")
        if "googleplay" in srcs:
            k = int(time.time() // 3600) % len(S.APP_CATEGORIES)          # rotate categories over time
            cats = [S.APP_CATEGORIES[k], S.APP_CATEGORIES[(k + 5) % len(S.APP_CATEGORIES)]]

            def play_job(cats=cats):
                out = []
                for cat in cats:
                    for app in S.play_search(cat, iso2, "en", 3):
                        try:
                            out += S.play_reviews(app, iso2, "en")
                        except http.FetchError:
                            pass
                return out
            add("googleplay", play_job, "en")
        if "wfp" in srcs:
            add("wfp_prices", lambda: I.wfp_price_spikes(name, iso3), "en")
        if "wb_procurement" in srcs:
            add("worldbank_procurement", lambda: I.worldbank_procurement(c["name"], 30), "en")
        if "procurement" in srcs:
            if c["continent"] == "Europe" and iso3 not in ("RUS", "BLR", "UKR"):
                add("ted", lambda: [r for r in P.ted_no_winner(21, 2, iso3)], c["langs"][0] if c["langs"] else "en")
            if iso3 == "BRA":
                add("pncp", lambda: P.pncp_failed(7, 4), "pt")
            if iso3 == "GBR":
                add("findatender", lambda: P.uk_cancelled(30, 100), "en")
        if iso3 == "UKR":
            add("prozorro", lambda: I.prozorro_failed(3), "uk")
        if iso3 == "COL":
            add("secop", lambda: I.secop_cancelled(150), "es")
        if iso3 == "USA":
            add("samgov", lambda: I.sam_sources_sought(focus, 50), "en")
            add("openfda", lambda: I.fda_shortages(200), "en")
            add("cfpb", lambda: I.cfpb_complaints(80), "en")
        # Run all fetches concurrently; aduns.http throttles per host, so different platforms proceed in parallel
        # while each platform's own rate limit is still respected.
        from concurrent.futures import ThreadPoolExecutor

        def run(job):
            label, fn, lang = job
            recs = self.safe(label, fn, []) or []
            return label, lang, recs
        with ThreadPoolExecutor(max_workers=8) as ex:
            for label, lang, recs in ex.map(run, jobs):
                self.bump(f"fetched:{label.split(':')[0]}", len(recs))
                raw.extend((r, lang) for r in recs)
        self.stats["shared_langs"] = {l: _shared_language(l) for l in langs}
        stored = self.process(raw, scope=iso3, focus=focus, min_need_score=min_need_score)
        self._record_sweep(iso3, c["continent"], len(stored))
        return stored

    def _subreddits(self, c: dict) -> list[str]:
        base = c["name"].split(",")[0]
        cands = {base.replace(" ", ""), base.replace(" ", "_")}
        if c["capital"]:
            cands.add(c["capital"].replace(" ", ""))
        known = db.q("SELECT handle FROM source_registry WHERE kind='subreddit' AND country=? AND active=1 "
                     "ORDER BY COALESCE(last_crawled,0) LIMIT 4", (c["iso3"],))
        out = list(dict.fromkeys([k["handle"] for k in known] + sorted(cands)))
        return out[:4]

    # ------------------------------------------------------ worldwide focused
    def focused_worldwide(self, focus: str, depth: int = 1, min_need_score: float = 0.3) -> list[int]:
        """A focus searched across all languages at once (Bluesky, YouTube, GDELT, HN, Stack Exchange)."""
        raw: list[tuple[dict, str]] = []
        for lang in ["en", "es", "fr", "pt", "ar", "ru", "hi", "id", "sw", "zh"][: 4 + 3 * depth]:
            cue = lexicon.search_terms(lang, 1)[0]
            local_focus = translate.from_english(focus, lang)
            q = f"{local_focus} {cue}" if lang != "en" else f"{focus} shortage OR \"{focus}\" expensive"
            raw += [(r, lang) for r in self.safe("bluesky", lambda q=q, l=lang: S.bluesky(q, l if l != "en" else None, 40), [])]
        raw += [(r, "en") for r in self.safe("youtube", lambda: S.youtube_search(f"{focus} shortage", "US", "en"), [])]
        raw += [(r, "en") for r in self.safe("hackernews", lambda: legacy.hackernews(f'"{focus}"', 50, days=config.MAX_AGE_DAYS), [])]
        raw += [(r, "en") for r in self.safe("gdelt", lambda: legacy.gdelt(f'"{focus}" (shortage OR expensive OR "lack of")',
                                                                         100, timespan="1m"), [])]
        return self.process(raw, scope=None, focus=focus, min_need_score=min_need_score)

    # ---------------------------------------------------------------- global
    def global_feeds(self, min_need_score: float = 0.3) -> list[int]:
        raw: list[tuple[dict, str]] = []
        raw += [(r, "en") for r in self.safe("gdacs", lambda: I.gdacs("Orange"), [])]
        raw += [(r, "en") for r in self.safe("hackernews", lambda: legacy.hackernews(
            '"can\'t find" OR "no one sells" OR "wish there was"', 50, days=30), [])]
        for site in ["diy", "money", "expatriates", "engineering"]:
            raw += [(r, "en") for r in self.safe(f"stackexchange:{site}", lambda s=site: legacy.stackexchange(
                "can't find", s, 30), [])]
        return self.process(raw, scope=None, focus="", min_need_score=min_need_score)

    # -------------------------------------------------------------- processing
    def process(self, raw: list[tuple[dict, str]], scope: str | None, focus: str, min_need_score: float) -> list[int]:
        cutoff = time.time() - config.MAX_AGE_DAYS * 86400
        now = time.time()
        cands: list[tuple[dict, str, float]] = []
        seen: set[str] = set()
        for r, lang in raw:
            text = nlp.clean(r.get("text") or r.get("title"))
            if len(text) < 6:
                continue
            ts = _ts(r.get("published_at"))
            if ts is None:
                self.bump("dropped_undated")
                continue
            if ts < cutoff:
                self.bump("dropped_old")
                continue
            h = http.content_hash(r["source"], r.get("external_id"), text[:300])
            if h in seen:
                continue
            seen.add(h)
            rl = (r.get("extra") or {}).get("langs") or [(r.get("extra") or {}).get("lang")]
            lang = (rl[0] if rl and rl[0] else lang) or "en"
            lang = lang.split("-")[0]
            r["text"] = text
            r["_hash"], r["_ts"] = h, min(ts, now)
            cands.append((r, lang, ts))
        # translate non-English candidates in batches per language
        by_lang: dict[str, list[dict]] = {}
        for r, lang, _ in cands:
            if lang != "en":
                by_lang.setdefault(lang, []).append(r)
        for lang, recs in by_lang.items():
            ens = translate.batch_to_english([x["text"][:300] for x in recs], lang)
            for x, en in zip(recs, ens):
                x["_en"] = en
            self.bump("translated", sum(1 for e in ens if e))
        stored: list[int] = []
        focus_toks = set(nlp.tokens(focus))
        for r, lang, ts in cands:
            text, en = r["text"], r.get("_en") or (r["text"] if lang == "en" else None)
            det_en = nlp.detect_need(en or "")
            det_loc = lexicon.detect(text, [lang, "en"])
            types = dict(det_en["type_weights"])
            for typ in det_loc:
                types[typ] = max(types.get(typ, 0), 0.75)
            p = 1.0
            for w in types.values():
                p *= 1 - w
            need_score = 1 - p
            src = r["source"]
            if src in ALWAYS_NEED:
                need_score = max(need_score, 0.6)
            if src == "googlesuggest":
                # latent demand counts as a need only when the completion carries need semantics
                # (price / shortage / can't find…) or names something in a tangible need domain
                tpl = (r.get("extra") or {}).get("prefix", "")
                priced = bool(det_en["type_weights"]) or bool(det_loc) or any(
                    w in (en or text).lower() for w in ("price", "expensive", "cost", "shortage", "not available"))
                if priced or taxonomy.classify_domain(en or text)[0]:
                    types.setdefault("latent_search", 0.5)
                    need_score = max(need_score, 0.5 if priced else 0.4)
                elif "{x}" not in tpl:
                    need_score = min(need_score, 0.2)
            if src in INSTITUTIONAL:
                types.setdefault("institutional", 0.7)
            if src == "googleplay" and (r.get("extra") or {}).get("rating", 5) <= 2:
                types.setdefault("inefficient", 0.6)
                need_score = max(need_score, 0.6)
            if src == "wfp_prices":
                types.setdefault("unaffordable", 0.8)
            if src == "gdacs":
                types.setdefault("scarcity", 0.7)
            # Precision rule: a local-language cue alone ("lack of", "falta de", "mungesë") must refer to something
            # tangible — a recognised need domain in the English text — or be backed by an English need phrase.
            dom = taxonomy.classify_domain(en or text)[0]
            if (not det_en["type_weights"] and not dom and src not in ALWAYS_NEED and src != "googleplay"
                    and src not in INSTITUTIONAL and src != "googlesuggest"):
                self.bump("dropped_vague")
                continue
            if focus_toks and not (focus_toks & set(nlp.tokens(f"{en or ''} {text}"))):
                self.bump("dropped_off_focus")
                continue
            if need_score < min_need_score:
                self.bump("dropped_low_need")
                continue
            basis = en or text
            countries = geo.find_countries(f"{r.get('title') or ''} {basis}")
            extra = r.get("extra") or {}
            for k in ("sourcecountry", "country"):
                if extra.get(k):
                    iso = geo.resolve(extra[k])
                    if iso and iso not in countries:
                        countries.append(iso)
            # Global platforms (posts from everywhere): accept for this country only if the post names the country
            # or is written in a language that is specific to it.
            if scope and src in ("mastodon", "bluesky", "lemmy", "hackernews") and scope not in countries:
                if lang == "en" or _shared_language(lang) or lang not in (geo.country(scope) or {}).get("langs", []):
                    self.bump("dropped_not_about_country")
                    continue
            # Country-scoped feeds belong to the sweep country even when the text doesn't name it.
            # Inherently local feeds are pinned to the sweep country; for news/video, an explicit mention of other
            # countries wins (the item is attributed to where it is actually about).
            if scope and scope not in countries and (src in ("googletrends", "googlesuggest", "reddit", "telegram",
                                                             "googleplay", "wfp_prices", "worldbank_procurement",
                                                             *INSTITUTIONAL) or not countries):
                countries.insert(0, scope)
            sig_scope = scope if scope in countries else (countries[0] if countries else None)
            cont = geo.country(sig_scope)["continent"] if sig_scope and geo.country(sig_scope) else None
            ntypes = sorted(types, key=lambda k: -types[k])
            layer = r["layer"]
            if "normalized" in ntypes and layer in ("visible", "scattered"):
                layer = "invisible"
            sid = db.insert("signals", {
                "source": src, "layer": layer, "external_id": str(r.get("external_id") or "")[:500],
                "url": r.get("url"), "title": (r.get("title") or "")[:500], "text": text[:4000], "author": r.get("author"),
                "published_at": r.get("published_at"), "published_ts": r["_ts"], "retrieved_at": now,
                "content_hash": r["_hash"], "query": focus or None,
                "domain": dom or "general",
                "need_types": json.dumps(ntypes), "gap_causes": json.dumps(det_en["gap_causes"]),
                "intensity": det_en["intensity"], "need_score": round(need_score, 3), "countries": json.dumps(countries),
                "entities": json.dumps(det_en["objects"]), "engagement": r.get("engagement") or 0.0, "run_id": self.run_id,
                "extra": json.dumps({**extra, "cues": det_en["cues"] + [c for v in det_loc.values() for c in v][:6]},
                                    default=str),
                "lang": lang, "text_en": (en or "")[:4000] or None, "scope_country": sig_scope, "continent": cont,
            }, ignore=True)
            if sid:
                stored.append(sid)
                self.bump(f"stored:{src}")
                self._snowball(f"{text} {r.get('url') or ''}", sig_scope, src)
            else:
                self.bump("duplicates")
        return stored

    # -------------------------------------------------------- snowball sources
    def _snowball(self, text: str, country: str | None, via: str) -> None:
        for m in S.TG_LINK.finditer(text):
            h = m.group(1)
            if h.lower() in ("share", "joinchat", "addstickers", "proxy", "s", "iv"):
                continue
            if db.insert("source_registry", {"kind": "telegram", "handle": h, "country": country, "discovered_from": via,
                                             "discovered_at": time.time()}, ignore=True):
                self.bump("discovered:telegram")
        for m in SUBREDDIT_RE.finditer(text):
            if db.insert("source_registry", {"kind": "subreddit", "handle": m.group(1), "country": country,
                                             "discovered_from": via, "discovered_at": time.time()}, ignore=True):
                self.bump("discovered:subreddit")

    def _record_sweep(self, iso3: str, continent: str, n: int) -> None:
        ok = sorted({k.split(":", 1)[1] for k in self.stats if k.startswith("fetched:") and self.stats[k] > 0})
        failed = sorted({e.split(":", 1)[0] for e in self.errors})
        with db.tx() as conn:
            conn.execute("""INSERT INTO sweeps (country, continent, last_started, last_finished, runs, signals_last,
                            signals_total, sources_ok, sources_failed) VALUES (?,?,?,?,1,?,?,?,?)
                            ON CONFLICT(country) DO UPDATE SET last_finished=excluded.last_finished, runs=runs+1,
                            signals_last=excluded.signals_last, signals_total=signals_total+excluded.signals_last,
                            sources_ok=excluded.sources_ok, sources_failed=excluded.sources_failed""",
                         (iso3, continent, time.time(), time.time(), n, n, json.dumps(ok), json.dumps(failed)))

    # ------------------------------------- official statistics (secondary context)
    def structural_gaps(self, domain_list: list[str] | None = None, country: str | None = None,
                        z_threshold: float = 0.75) -> list[int]:
        """Optional: official WDI statistics vs income peers. Secondary context only — ground signals lead."""
        cs = geo.countries()
        stored: list[int] = []
        for dom in domain_list or [d for d in taxonomy.DOMAINS if taxonomy.DOMAINS[d]["indicators"]]:
            for code, label, better in taxonomy.DOMAINS[dom]["indicators"]:
                data = self.safe(f"wdi:{code}", lambda code=code: worldbank.latest(code), {})
                peers: dict[str, list[float]] = {}
                for iso, (v, _) in data.items():
                    if iso in cs:
                        peers.setdefault(cs[iso]["income_id"], []).append(v)
                for iso in ([country] if country else list(data)):
                    if iso not in data or iso not in cs or len(peers.get(cs[iso]["income_id"], [])) < 5:
                        continue
                    v, year = data[iso]
                    if year < time.gmtime().tm_year - 3:
                        continue  # no stale statistics
                    vals = peers[cs[iso]["income_id"]]
                    med, sd = statistics.median(vals), statistics.pstdev(vals) or 1e-9
                    z = (v - med) / sd if better == "higher" else (med - v) / sd
                    if z > -z_threshold:
                        continue
                    text = (f"Official statistic (secondary): {label} in {cs[iso]['name']} = {v:.1f} ({year}) vs "
                            f"{med:.1f} median of {cs[iso]['income']} peers.")
                    sid = db.insert("signals", {
                        "source": "worldbank_wdi", "layer": "structural", "external_id": f"{code}:{iso}:{year}",
                        "url": f"https://data.worldbank.org/indicator/{code}?locations={cs[iso]['iso2']}",
                        "title": f"{label}: {cs[iso]['name']}", "text": text, "author": "World Bank WDI",
                        "published_at": str(year), "published_ts": _ts(f"{year}-12-31"), "retrieved_at": time.time(),
                        "content_hash": http.content_hash("wdi", code, iso, year), "domain": dom,
                        "need_types": json.dumps(["institutional"]), "gap_causes": "[]", "intensity": 0.2,
                        "need_score": 0.4, "countries": json.dumps([iso]), "entities": json.dumps([label]),
                        "engagement": 0.0, "run_id": self.run_id, "lang": "en", "text_en": text, "scope_country": iso,
                        "continent": cs[iso]["continent"],
                    }, ignore=True)
                    if sid:
                        stored.append(sid)
        return stored


def rescore_existing() -> dict:
    """Re-apply the current precision rules to stored signals (after rule upgrades)."""
    changed = 0
    for r in db.q("SELECT id, source, text, text_en, need_score, domain FROM signals"):
        en = r["text_en"] or r["text"]
        det = nlp.detect_need(en)
        dom = taxonomy.classify_domain(en)[0]
        new = r["need_score"]
        if r["source"] == "googlesuggest":
            priced = bool(det["type_weights"]) or any(w in en.lower() for w in ("price", "expensive", "cost", "shortage"))
            new = 0.5 if priced else (0.4 if dom else 0.2)
        elif not det["type_weights"] and not dom and r["source"] not in ALWAYS_NEED and r["source"] not in (
                "googleplay", "prozorro", "secop", "worldbank_procurement"):
            new = 0.15
        if abs(new - r["need_score"]) > 1e-6 or (dom or "general") != r["domain"]:
            db.update("signals", r["id"], {"need_score": new, "domain": dom or "general"})
            changed += 1
    return {"rescored": changed}
