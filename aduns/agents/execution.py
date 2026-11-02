"""Execution layer: six agents that turn a governed opportunity into small, cheap real-world tests and,
if they pass, an operating pilot — and feed every real outcome back into the engine.

    Experiment   – designs tests from governance kill criteria & validation priorities (sample sizes, decision
                   rules), evaluates them with Bayesian updates on *real* events, writes measured values back into
                   Economics (learning loop) and confirms/rejects the need hypothesis.
    Partnership  – shortlists real partners (suppliers, operators, distributors, know-how holders) with *publicly
                   published* contact channels, sanctions-screens them, drafts outreach in English + local language.
    Operations   – operating plan for the chosen route: workflow, lead times (great-circle shipping estimate),
                   inventory policy, KPIs, compliance tasks, infrastructure adaptations.
    Customer     – landing page (waitlist / pre-order with consent) and SMS/WhatsApp/Telegram funnel; onboarding,
                   FAQ and feedback; customers exist only when real people sign up.
    Finance      – actuals from recorded entries (revenue, COGS, CAC, opex) vs the model's p10–p90; variance flags;
                   measured margins written back.
    Expansion    – where the proven model could go next: same need in other countries, real import markets,
                   sanctions, language/currency distance.

Safety: nothing outward-facing (publishing a page, contacting a partner) happens without a human approval recorded
in the governance ledger. No outcome is ever synthesised — events come from real people, scouts or entries signed
by a named person with evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import secrets
import time

from .. import db, geo, translate
from ..sources import compliance as CP
from ..sources import market as MK
from ..sources import social as S
from .base import Agent
from .governance import ledger_append

TABLES = [
    """CREATE TABLE IF NOT EXISTS experiments (id INTEGER PRIMARY KEY AUTOINCREMENT, opportunity_id INTEGER, kind TEXT,
        title TEXT, question TEXT, metric TEXT, threshold REAL, direction TEXT, min_n INTEGER, decision_rule TEXT,
        validates TEXT, how TEXT, status TEXT DEFAULT 'designed', result TEXT, created_at REAL, updated_at REAL,
        UNIQUE(opportunity_id, kind))""",
    """CREATE TABLE IF NOT EXISTS experiment_events (id INTEGER PRIMARY KEY AUTOINCREMENT, experiment_id INTEGER,
        at REAL, kind TEXT, value REAL, success INTEGER, text TEXT, evidence_url TEXT, actor TEXT, consent INTEGER,
        hash TEXT UNIQUE)""",
    """CREATE TABLE IF NOT EXISTS measured_inputs (id INTEGER PRIMARY KEY AUTOINCREMENT, opportunity_id INTEGER,
        experiment_id INTEGER, key TEXT, low REAL, high REAL, source TEXT, at REAL)""",
    """CREATE TABLE IF NOT EXISTS partners (id INTEGER PRIMARY KEY AUTOINCREMENT, opportunity_id INTEGER, name TEXT,
        role TEXT, source TEXT, url TEXT, contacts TEXT, country TEXT, fit REAL, screening TEXT, stage TEXT,
        outreach TEXT, notes TEXT, updated_at REAL, UNIQUE(opportunity_id, name))""",
    """CREATE TABLE IF NOT EXISTS execution_plans (opportunity_id INTEGER, kind TEXT, plan TEXT, updated_at REAL,
        PRIMARY KEY (opportunity_id, kind))""",
    """CREATE TABLE IF NOT EXISTS landing_pages (slug TEXT PRIMARY KEY, opportunity_id INTEGER, experiment_id INTEGER,
        content TEXT, status TEXT, created_at REAL, published_at REAL, visits INTEGER DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS page_visits (slug TEXT, visitor TEXT, at REAL, PRIMARY KEY (slug, visitor))""",
    """CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY AUTOINCREMENT, opportunity_id INTEGER, handle TEXT,
        channel TEXT, stage TEXT, quantity REAL, consent_at REAL, created_at REAL, UNIQUE(opportunity_id, handle))""",
    """CREATE TABLE IF NOT EXISTS customer_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER, at REAL,
        direction TEXT, text TEXT)""",
    """CREATE TABLE IF NOT EXISTS finance_entries (id INTEGER PRIMARY KEY AUTOINCREMENT, opportunity_id INTEGER, at REAL,
        kind TEXT, amount REAL, currency TEXT, usd REAL, units REAL, reference TEXT, actor TEXT, evidence_url TEXT)""",
]


def ensure_tables() -> None:
    with db.tx() as c:
        for t in TABLES:
            c.execute(t)


def _opp(oid: int) -> dict:
    o = db.q1("SELECT * FROM opportunities WHERE id=?", (oid,))
    if not o:
        raise ValueError(f"opportunity {oid} not found")
    for k in ("market", "localization", "composition", "defensibility", "routes", "economics"):
        o[k] = db.loads(o[k], {})
    return o


def _review(oid: int) -> dict:
    try:
        r = db.q1("SELECT * FROM governance_reviews WHERE opportunity_id=? ORDER BY id DESC LIMIT 1", (oid,))
    except Exception:  # noqa: BLE001
        return {}
    if not r:
        return {}
    for k in ("verification", "legal", "red_team", "impact", "conditions"):
        r[k] = db.loads(r[k], {})
    return r


def approved(oid: int) -> dict | None:
    """Latest human approval (approved / approved_with_conditions) for the opportunity, if any."""
    try:
        a = db.q1("SELECT * FROM approvals WHERE opportunity_id=? ORDER BY id DESC LIMIT 1", (oid,))
    except Exception:  # noqa: BLE001
        return None
    return a if a and a["decision"].startswith("approved") else None


def _save_plan(oid: int, kind: str, plan: dict) -> None:
    with db.tx() as c:
        c.execute("INSERT OR REPLACE INTO execution_plans (opportunity_id, kind, plan, updated_at) VALUES (?,?,?,?)",
                  (oid, kind, json.dumps(plan, default=str), time.time()))


# ============================================================================== statistics
def beta_prob_above(successes: int, failures: int, threshold: float, draws: int = 20000, seed: int = 3) -> float:
    """P(p > threshold) under a Beta(1+s, 1+f) posterior (uniform prior)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    return float((rng.beta(1 + successes, 1 + failures, draws) > threshold).mean())


def sample_size_for_proportion(threshold: float, expected: float, confidence: float = 0.9, power: float = 0.8) -> int:
    """One-sided n so that a true rate `expected` is distinguishable from `threshold` (normal approximation)."""
    from statistics import NormalDist
    za, zb = NormalDist().inv_cdf(confidence), NormalDist().inv_cdf(power)
    d = abs(expected - threshold) or 0.05
    n = ((za * math.sqrt(threshold * (1 - threshold)) + zb * math.sqrt(expected * (1 - expected))) / d) ** 2
    return max(10, math.ceil(n))


# ============================================================================== Experiment
class ExperimentAgent(Agent):
    name = "experiment"

    def execute(self, opportunity_id: int) -> dict:
        ensure_tables()
        o, rev = _opp(opportunity_id), _review(opportunity_id)
        econ, red = o["economics"], rev.get("red_team") or {}
        modes = {m["failure_mode"] for m in red.get("failure_modes", [])}
        price = ((o["localization"].get("local_price_evidence") or {}).get("usd_summary") or {})
        designs = []
        n_int = sample_size_for_proportion(0.30, 0.50)
        designs.append({"kind": "problem_interviews", "title": f"Do target customers in {o['country']} have the {o['object']} problem?",
                        "question": f"Share of interviewed target customers confirming a recurring, costly {o['object']} problem",
                        "metric": "proportion_confirming", "threshold": 0.30, "direction": "above", "min_n": n_int,
                        "decision_rule": f"Pass if P(rate > 30%) ≥ 0.9 after ≥{n_int} interviews; fail if ≤ 0.1.",
                        "validates": "need", "how": "Field mission interviews (validated scout observations count automatically)."})
        designs.append({"kind": "price_discovery", "title": f"Verified local price of {o['object']}",
                        "question": "Median consumer price from ≥10 verified local quotes (USD)", "metric": "median_usd",
                        "threshold": (price.get("median") or 0) * 0.8 if price else None, "direction": "above", "min_n": 10,
                        "decision_rule": "Pass if the median of ≥10 verified quotes stays above the kill threshold; "
                                         "value is written to Economics as a measured price.",
                        "validates": "price_usd", "how": "Scout PRICE reports, receipts or shop visits with evidence."})
        if (o["market"].get("hs")):
            designs.append({"kind": "supplier_quotes", "title": "Landed supplier cost",
                            "question": "Median unit cost from ≥3 written supplier quotes (USD per unit/kg)",
                            "metric": "median_usd", "threshold": None, "direction": "below", "min_n": 3,
                            "decision_rule": "Measured cost replaces the assumption in Economics; re-run viability.",
                            "validates": "unit_cost_usd", "how": "Quotes from shortlisted suppliers (Partnership agent)."})
        if "tariff_unverified" in modes or (econ.get("inputs") or {}).get("import_duty", {}).get("kind") == "assumption":
            hs = (o["market"].get("hs") or {}).get("hs")
            designs.append({"kind": "tariff_verification", "title": f"Verify import duty for HS {hs} into {o['country']}",
                            "question": "Applied MFN/preferential duty rate (%) incl. quotas or state trading",
                            "metric": "rate", "threshold": None, "direction": "below", "min_n": 1,
                            "decision_rule": "Official rate (with source link) replaces the 0–35% assumption.",
                            "validates": "import_duty",
                            "how": f"WTO Tariff & Trade Data https://ttd.wto.org · Market Access Map https://www.macmap.org "
                                   f"· national customs tariff for HS {hs}."})
        designs.append({"kind": "smoke_test", "title": f"Will people sign up for {o['object']}?",
                        "question": "Landing-page / SMS sign-up conversion among unique visitors",
                        "metric": "conversion", "threshold": 0.02, "direction": "above",
                        "min_n": sample_size_for_proportion(0.02, 0.05),
                        "decision_rule": "Pass if P(conversion > 2%) ≥ 0.9; fail if ≤ 0.1 (after min visitors).",
                        "validates": "demand", "how": "Published landing page /x/<slug> + WAIT/ORDER SMS commands "
                                                      "(publishing requires human approval)."})
        designs.append({"kind": "pilot", "title": "Pilot with ≤50 customers for 3 months",
                        "question": "Net margin of the pilot from recorded finance entries", "metric": "net_margin",
                        "threshold": 0.0, "direction": "above", "min_n": 20,
                        "decision_rule": "Kill if net margin < 0 after 3 months / ≥20 orders.",
                        "validates": "net_margin", "how": "Finance entries (revenue, COGS, CAC, opex) with references."})
        ids = []
        now = time.time()
        for d in designs:
            ex = db.q1("SELECT id FROM experiments WHERE opportunity_id=? AND kind=?", (opportunity_id, d["kind"]))
            if ex:
                db.update("experiments", ex["id"], {**d, "updated_at": now})
                ids.append(ex["id"])
            else:
                ids.append(db.insert("experiments", {**d, "opportunity_id": opportunity_id, "status": "designed",
                                                     "created_at": now, "updated_at": now}))
        self.stats["experiments"] = len(ids)
        evals = [self.evaluate(i) for i in ids]
        return {"experiment_ids": ids, "evaluations": evals}

    # ---------------------------------------------------------------- evaluation
    @staticmethod
    def _collect(e: dict, o: dict) -> list[dict]:
        """Pull real events from the field network / customer funnel into the experiment."""
        if e["kind"] == "problem_interviews":
            for ob in db.q("""SELECT ob.id, ob.text, ob.status, ob.submitted_at FROM scout_observations ob
                              JOIN scout_missions m ON m.id=ob.mission_id WHERE m.hypothesis_id=?
                              AND ob.status IN ('validated','rejected')""", (o["hypothesis_id"],)):
                from .. import nlp
                ok = ob["status"] == "validated" and nlp.detect_need(ob["text"])["need_score"] >= 0.5
                _event(e["id"], "observation", None, int(ok), ob["text"][:300], None, "field-network", 1,
                       key=f"obs:{ob['id']}")
        if e["kind"] == "price_discovery":
            fx = MK.fx_usd()
            for ob in db.q("""SELECT ob.id, ob.price_observed, ob.currency, ob.text FROM scout_observations ob
                              JOIN scout_missions m ON m.id=ob.mission_id WHERE m.hypothesis_id=?
                              AND ob.status='validated' AND ob.price_observed IS NOT NULL""", (o["hypothesis_id"],)):
                cur = (ob["currency"] or "USD").upper()
                if cur in fx:
                    _event(e["id"], "quote", ob["price_observed"] / fx[cur], None, ob["text"][:300], None,
                           "field-network", 1, key=f"price:{ob['id']}")
        if e["kind"] == "smoke_test":
            for p in db.q("SELECT slug, visits FROM landing_pages WHERE experiment_id=?", (e["id"],)):
                visitors = db.q1("SELECT COUNT(*) n FROM page_visits WHERE slug=?", (p["slug"],))["n"]
                with db.tx() as c:
                    c.execute("UPDATE experiments SET result=json_set(COALESCE(result,'{}'), '$.visitors', ?) WHERE id=?",
                              (visitors, e["id"]))
        return db.q("SELECT * FROM experiment_events WHERE experiment_id=? ORDER BY at", (e["id"],))

    def evaluate(self, experiment_id: int) -> dict:
        import statistics
        e = db.q1("SELECT * FROM experiments WHERE id=?", (experiment_id,))
        o = _opp(e["opportunity_id"])
        ev = self._collect(e, o)
        e = db.q1("SELECT * FROM experiments WHERE id=?", (experiment_id,))     # _collect may update result
        res = db.loads(e["result"], {}) or {}
        status = "designed" if not ev else "running"
        if e["metric"] in ("proportion_confirming", "conversion"):
            s = sum(1 for x in ev if x["success"] == 1)
            f = sum(1 for x in ev if x["success"] == 0)
            if e["metric"] == "conversion":
                f = max(0, int(res.get("visitors", 0)) - s)
            n = s + f
            p_above = beta_prob_above(s, f, e["threshold"]) if n else None
            res.update({"successes": s, "failures": f, "n": n, "p_above_threshold": p_above})
            if n >= e["min_n"] and p_above is not None:
                status = "passed" if p_above >= 0.9 else "failed" if p_above <= 0.1 else "inconclusive"
        elif e["metric"] in ("median_usd", "rate"):
            vals = [x["value"] for x in ev if x["value"] is not None]
            res.update({"n": len(vals), "median": statistics.median(vals) if vals else None})
            if len(vals) >= e["min_n"]:
                med = res["median"]
                if e["threshold"]:
                    ok = med >= e["threshold"] if e["direction"] == "above" else med <= e["threshold"]
                    status = "passed" if ok else "failed"
                else:
                    status = "passed"
                key = e["validates"]
                if key in ("price_usd", "unit_cost_usd", "import_duty"):
                    lo, hi = (min(vals), max(vals)) if len(vals) > 1 else (med, med)
                    if key == "import_duty":
                        lo, hi = med / 100 if med > 1 else med, med / 100 if med > 1 else med
                    with db.tx() as c:
                        c.execute("DELETE FROM measured_inputs WHERE opportunity_id=? AND key=?", (o["id"], key))
                        c.execute("""INSERT INTO measured_inputs (opportunity_id, experiment_id, key, low, high, source, at)
                                     VALUES (?,?,?,?,?,?,?)""", (o["id"], e["id"], key, lo, hi,
                                                                 f"{len(vals)} recorded {e['kind']} values", time.time()))
        elif e["metric"] == "net_margin":
            fin = FinanceAgent.actuals(o["id"])
            res.update(fin)
            if (fin.get("orders") or 0) >= e["min_n"]:
                status = "passed" if (fin.get("net_margin") or -1) > e["threshold"] else "failed"
        prev = e["status"]
        db.update("experiments", experiment_id, {"status": status, "result": json.dumps(res, default=str),
                                                 "updated_at": time.time()})
        if status != prev and status in ("passed", "failed"):
            ledger_append(self.name, f"experiment_{status}", "experiment", experiment_id, res)
            if e["kind"] == "problem_interviews":       # real field outcome teaches the discovery layer
                from .. import learning
                learning.review(o["hypothesis_id"], "confirmed" if status == "passed" else "rejected",
                                f"experiment#{experiment_id}", f"{res.get('successes')}/{res.get('n')} confirmed")
        return {"experiment_id": experiment_id, "kind": e["kind"], "status": status, "result": res}


def _event(experiment_id: int, kind: str, value, success, text, url, actor, consent, key: str | None = None) -> int | None:
    h = hashlib.sha256(f"{experiment_id}|{key or (kind, value, text, time.time())}".encode()).hexdigest()
    return db.insert("experiment_events", {"experiment_id": experiment_id, "at": time.time(), "kind": kind, "value": value,
                                           "success": success, "text": text, "evidence_url": url, "actor": actor,
                                           "consent": consent, "hash": h}, ignore=True)


def record_event(experiment_id: int, actor: str, kind: str, value: float | None = None, success: bool | None = None,
                 text: str = "", evidence_url: str = "") -> dict:
    """A named human records a real result (quote, interview outcome, tariff rate) with evidence."""
    ensure_tables()
    if not actor.strip():
        raise ValueError("actor (your name) is required")
    if kind in ("quote", "rate") and value is None:
        raise ValueError("value required")
    if kind in ("quote", "rate") and not evidence_url:
        raise ValueError("evidence_url required for quotes and rates (receipt photo, supplier email, official tariff page)")
    eid = _event(experiment_id, kind, value, None if success is None else int(success), text, evidence_url,
                 f"human:{actor}", 1)
    ledger_append(f"human:{actor}", f"experiment_event:{kind}", "experiment", experiment_id,
                  {"value": value, "success": success, "evidence": evidence_url})
    return {"event_id": eid, "evaluation": ExperimentAgent().evaluate(experiment_id)}


# ============================================================================= Partnership
ROLE_BY_TYPE = {"local_provider": "distribution / service partner", "local_digital_solution": "channel / platform partner",
                "organization": "operator / supplier", "proven_vendor": "supplier", "ip_patent": "licensor",
                "research": "know-how partner", "open_design": "design source", "skill_knowhow": "trainer",
                "unused_asset": "capacity owner"}   # programme models are reference designs, not counterparties
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}")


class PartnershipAgent(Agent):
    name = "partnership"

    def execute(self, opportunity_id: int, max_partners: int = 15) -> dict:
        ensure_tables()
        o = _opp(opportunity_id)
        c = geo.country(o["country"])
        caps = db.q("""SELECT c.*, hc.relevance FROM capabilities c JOIN hypothesis_capabilities hc ON hc.capability_id=c.id
                       WHERE hc.hypothesis_id=? ORDER BY hc.relevance DESC""", (o["hypothesis_id"],))
        cands = []
        for cap in caps:
            if cap["capability_type"] not in ROLE_BY_TYPE:
                continue
            extra = db.loads(cap["extra"], {})
            local = c["iso2"] in db.loads(cap["countries"], []) or c["name"] in db.loads(cap["countries"], [])
            if cap["capability_type"] in ("research", "ip_patent", "skill_knowhow", "unused_asset"):
                if not cap["holder"] or len(cap["holder"]) > 80:
                    continue          # a paper/news title is not a counterparty; need a real holder/affiliation
                name = cap["holder"].split(";")[0].strip()
            else:
                name = (cap["holder"] or cap["title"])
            cands.append({"name": name[:150], "role": ROLE_BY_TYPE[cap["capability_type"]],
                          "source": cap["source"], "url": cap["url"], "local": local, "relevance": cap["relevance"] or 0,
                          "extra": extra, "type": cap["capability_type"]})
        for w in (o["composition"].get("wholesale") or [])[:5]:
            cands.append({"name": w["supplier"], "role": "supplier (FOB quote)", "source": "madeinchina", "url": w["url"],
                          "local": False, "relevance": 0.8, "extra": {"listing": w["name"], "price": [w["price_min_usd"],
                                                                                                        w["price_max_usd"]]},
                          "type": "wholesale"})
        seen, picked = set(), []
        for cd in sorted(cands, key=lambda x: (-x["local"], -x["relevance"])):
            k = cd["name"].lower()
            if k in seen or len(k) < 3:
                continue
            seen.add(k)
            picked.append(cd)
            if len(picked) >= max_partners:
                break
        self.safe("screening_list", CP.refresh_screening_list, 0)
        lang = next((l for l in c.get("langs", []) if l != "en"), None)
        vp = ((o["localization"].get("value_proposition") or {}).get("en")) or f"affordable, reliable {o['object']}"
        ids = []
        for cd in picked:
            contacts = self._contacts(cd, c)
            hits = CP.screen(cd["name"])
            fit = round(0.4 * cd["relevance"] + 0.3 * cd["local"] + 0.3 * (1 if contacts else 0), 3)
            msg = (f"Hello {cd['name']},\n\nWe are researching how to make {o['object']} more available and affordable in "
                   f"{c['name']}. Public data shows unmet demand ({vp}). We found you via {cd['source']} "
                   f"({cd['url']}) and think your role as a {cd['role']} could be part of a small pilot. "
                   f"Would you be open to a 20-minute call to explore terms? No commitment.\n\nThank you.")
            outreach = {"en": msg}
            if lang:
                outreach[lang] = translate.from_english(msg, lang)
            stage = "blocked_by_screening" if hits else "identified"
            row = {"opportunity_id": opportunity_id, "name": cd["name"], "role": cd["role"], "source": cd["source"],
                   "url": cd["url"], "contacts": json.dumps(contacts), "country": o["country"] if cd["local"] else None,
                   "fit": fit, "screening": json.dumps(hits), "outreach": json.dumps(outreach), "updated_at": time.time()}
            ex = db.q1("SELECT id, stage FROM partners WHERE opportunity_id=? AND name=?", (opportunity_id, cd["name"]))
            if ex:
                db.update("partners", ex["id"], {**row, "stage": ex["stage"] if not hits else stage})
                ids.append(ex["id"])
            else:
                ids.append(db.insert("partners", {**row, "stage": stage}))
        self.stats.update({"partners": len(ids), "with_contacts": sum(1 for p in db.q(
            "SELECT contacts FROM partners WHERE opportunity_id=?", (opportunity_id,)) if db.loads(p["contacts"], {}))})
        return {"partner_ids": ids}

    def _contacts(self, cd: dict, c: dict) -> dict:
        """Publicly published contact channels only (app developer pages, official websites, OSM contact tags)."""
        out: dict = {}
        ex = cd["extra"]
        if cd["type"] == "local_digital_solution" and ex.get("app_id"):
            page = self.safe("play_page", lambda: S.play_app_page(ex["app_id"], c["iso2"]), "") or ""
            # Play pages also show *other* apps' developers — keep only contacts on this developer's own domain,
            # derived from the package name (com.kudabank.app → kudabank).
            parts = ex["app_id"].split(".")
            core = parts[1].lower() if len(parts) > 1 else parts[0].lower()
            emails = sorted({e for e in _EMAIL.findall(page) if core in e.split("@")[-1].lower()})
            sites = sorted({u for u in re.findall(r'"(https?://[^"/]+[^"]*)"', page)
                            if core in (re.sub(r"^https?://", "", u).split("/")[0].lower())})[:2]
            if emails:
                out["emails"] = emails[:3]
            if sites:
                out["websites"] = sites
        if cd["type"] == "local_provider" and re.search(r"/(node|way|relation)/", cd["url"] or ""):
            m = re.search(r"/(node|way|relation)/(\d+)", cd["url"] or "")
            if m:
                from .. import http
                osm_id = {"node": "N", "way": "W", "relation": "R"}[m.group(1)] + m.group(2)
                data = self.safe("osm_lookup", lambda: http.fetch("https://nominatim.openstreetmap.org/lookup",
                                                                  {"osm_ids": osm_id, "format": "jsonv2", "extratags": 1},
                                                                  source="nominatim", ttl=30 * 86400), []) or []
                tags = (data[0].get("extratags") or {}) if data else {}
                for k in ("phone", "contact:phone", "website", "contact:website", "email", "contact:email"):
                    if tags.get(k):
                        out.setdefault(k.split(":")[-1] + "s", []).append(tags[k])
        if cd["type"] == "organization" and (cd["url"] or "").startswith("http") and "wikidata" not in cd["url"]:
            out["websites"] = [cd["url"]]
        if cd["type"] == "wholesale":
            out["supplier_page"] = [cd["url"]]
        return out


def set_partner_stage(partner_id: int, stage: str, actor: str, notes: str = "") -> dict:
    stages = ("identified", "contacted", "responded", "negotiating", "agreed", "declined", "blocked_by_screening")
    if stage not in stages:
        raise ValueError(f"stage must be one of {stages}")
    p = db.q1("SELECT * FROM partners WHERE id=?", (partner_id,))
    if not p:
        raise ValueError("partner not found")
    if stage == "contacted" and not approved(p["opportunity_id"]):
        raise PermissionError("Outreach requires a human approval of this opportunity (governance gate).")
    if p["stage"] == "blocked_by_screening" and stage != "declined":
        raise PermissionError("Partner matched a sanctions/export-control list; resolve screening first.")
    db.update("partners", partner_id, {"stage": stage, "notes": notes, "updated_at": time.time()})
    ledger_append(f"human:{actor}", f"partner_stage:{stage}", "partner", partner_id, {"notes": notes})
    return {"partner_id": partner_id, "stage": stage}


# ============================================================================== Operations
class OperationsAgent(Agent):
    name = "operations"

    def execute(self, opportunity_id: int) -> dict:
        ensure_tables()
        o = _opp(opportunity_id)
        route = o.get("best_route") or "import_and_resell"
        c = geo.country(o["country"])
        econ = o["economics"]
        top = (econ.get("routes") or [{}])[0]
        units = ((top.get("units_year1") or {}).get("p50")) or None
        steps = {
            "import_and_resell": ["Supplier selection & samples", "Order & pre-shipment inspection", "Freight booking",
                                  "Customs clearance & duties", "Warehousing", "Distribution to retail/agents",
                                  "Customer delivery & support"],
            "local_distribution_partnership": ["Partner agreement", "Supply from partner/importer", "Joint marketing",
                                               "Order capture (SMS/WhatsApp/app)", "Delivery via partner network", "Support"],
            "manufacture_locally": ["Design adaptation", "Fabricator selection", "Prototype & certification",
                                    "Small-batch production", "Quality control", "Distribution", "After-sales service"],
            "software_layer": ["Onboard providers", "Order routing & payments", "Quality monitoring", "Customer support"],
        }.get(route, ["Partner agreement", "Pilot setup", "Order capture", "Fulfilment", "Support & feedback"])
        lead = None
        partners = ((o["market"].get("imports") or {}).get("partners") or [])
        if partners and partners[0].get("iso3") and route in ("import_and_resell", "local_agents_retail", "bundle",
                                                               "local_distribution_partnership"):
            src = geo.country(partners[0]["iso3"])
            if src and src.get("lat") is not None and c.get("lat") is not None:
                km = _haversine(src["lat"], src["lon"], c["lat"], c["lon"])
                sea_days = km * 1.3 / (16 * 1.852 * 24)        # 16 knots, 30% route detour (assumption)
                lead = {"from": partners[0]["iso3"], "great_circle_km": round(km), "sea_transit_days": round(sea_days, 1),
                        "total_lead_time_days": [round(sea_days + 10), round(sea_days + 30)],
                        "kind": "estimate (great-circle distance, 16 kn, +10–30 days port/customs/inland — assumption)"}
        inv = None
        if units and lead:
            weekly = units / 52
            lt_w = sum(lead["total_lead_time_days"]) / 2 / 7
            safety = 1.65 * 0.3 * weekly * math.sqrt(lt_w)       # 95% service level, 30% demand CV (assumption)
            unit = "kg/l" if MK.is_bulk((o["market"].get("hs") or {}).get("hs")) else "units"
            inv = {"unit": unit, "weekly_demand_units_p50": round(weekly, 1), "reorder_point_units": round(weekly * lt_w + safety),
                   "safety_stock_units": round(safety),
                   "assumptions": f"in {unit}; demand = modelled year-1 p50 (assumption-driven until the pilot); "
                                  f"demand CV 30%, 95% service level"}
        rev = _review(opportunity_id)
        compliance_tasks = [f["finding"] for f in (rev.get("legal") or {}).get("flags", []) if f["severity"] in
                            ("medium", "high", "blocker")]
        plan = {"route": route, "workflow": steps, "lead_time": lead, "inventory_policy": inv,
                "infrastructure_adaptations": o["localization"].get("design_implications", []),
                "payment_rails": o["localization"].get("payment_rails_apps", [])[:5],
                "compliance_tasks": compliance_tasks,
                "kpis": ["on-time delivery %", "fill rate %", "stock-out days", "complaints per 100 orders",
                         "gross margin per order", "repeat-purchase rate"]}
        _save_plan(opportunity_id, "operations", plan)
        self.stats.update({"route": route, "steps": len(steps), "lead_time": bool(lead)})
        return {"plan": plan}


def _haversine(lat1, lon1, lat2, lon2) -> float:
    p = math.pi / 180
    a = 0.5 - math.cos((lat2 - lat1) * p) / 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2
    return 12742 * math.asin(math.sqrt(a))


# ================================================================================ Customer
class CustomerAgent(Agent):
    name = "customer"

    def execute(self, opportunity_id: int) -> dict:
        ensure_tables()
        o = _opp(opportunity_id)
        c = geo.country(o["country"])
        smoke = db.q1("SELECT id FROM experiments WHERE opportunity_id=? AND kind='smoke_test'", (opportunity_id,))
        lang = next((l for l in c.get("langs", []) if l != "en"), None)
        vp = (o["localization"].get("value_proposition") or {})
        price = ((o["localization"].get("local_price_evidence") or {}).get("usd_summary") or {})
        en = {"headline": vp.get("en") or f"Reliable, affordable {o['object']}",
              "body": f"We are preparing a better way to get {o['object']} in {c['name']}. Join the waitlist and we will "
                      f"contact you before launch. No payment now.",
              "faq": [{"q": "Is this available now?", "a": "Not yet — we are measuring interest before a small pilot."},
                      {"q": "What will it cost?", "a": "We will publish prices before launch; joining is free."},
                      {"q": "What do you do with my number?", "a": "Only contact you about this service. Reply STOP anytime."}],
              "cta": "Join the waitlist", "consent": "I agree to be contacted about this service."}
        content = {"en": en, "country": c["name"], "object": o["object"], "price_reference_usd": price.get("median")}
        if lang:
            content[lang] = {k: (translate.from_english(v, lang) if isinstance(v, str) else
                                 [{"q": translate.from_english(x["q"], lang), "a": translate.from_english(x["a"], lang)}
                                  for x in v]) for k, v in en.items()}
        page = db.q1("SELECT slug, status FROM landing_pages WHERE opportunity_id=?", (opportunity_id,))
        slug = page["slug"] if page else f"{re.sub(r'[^a-z0-9]+', '-', o['object'].lower()).strip('-')}-{o['country'].lower()}-{secrets.token_hex(2)}"
        with db.tx() as cx:
            cx.execute("""INSERT INTO landing_pages (slug, opportunity_id, experiment_id, content, status, created_at)
                          VALUES (?,?,?,?,?,?) ON CONFLICT(slug) DO UPDATE SET content=excluded.content""",
                       (slug, opportunity_id, smoke["id"] if smoke else None, json.dumps(content), page["status"] if page
                        else "draft", time.time()))
        n_cust = db.q("SELECT stage, COUNT(*) n FROM customers WHERE opportunity_id=? GROUP BY stage", (opportunity_id,))
        fb = db.q("""SELECT m.text FROM customer_messages m JOIN customers cu ON cu.id=m.customer_id
                     WHERE cu.opportunity_id=? AND m.direction='in' ORDER BY m.at DESC LIMIT 50""", (opportunity_id,))
        self.stats.update({"slug": slug, "customers": sum(x["n"] for x in n_cust)})
        return {"slug": slug, "status": page["status"] if page else "draft", "customers": n_cust,
                "recent_feedback": [f["text"] for f in fb[:10]],
                "sms_commands": [f"WAIT {slug}", f"ORDER {slug} <quantity>", f"FEEDBACK {slug} <text>", "STOP"]}


def publish_page(slug: str, actor: str) -> dict:
    p = db.q1("SELECT * FROM landing_pages WHERE slug=?", (slug,))
    if not p:
        raise ValueError("page not found")
    if not approved(p["opportunity_id"]):
        raise PermissionError("Publishing requires a human approval of this opportunity (governance gate).")
    db.execute("UPDATE landing_pages SET status='published', published_at=? WHERE slug=?", (time.time(), slug))
    if p["experiment_id"]:
        db.execute("UPDATE experiments SET status='running' WHERE id=?", (p["experiment_id"],))
    ledger_append(f"human:{actor}", "landing_page_published", "opportunity", p["opportunity_id"], {"slug": slug})
    return {"slug": slug, "status": "published"}


def customer_signup(slug: str, handle: str, channel: str, consent: bool, stage: str = "waitlist", quantity: float | None = None,
                    message: str = "") -> dict:
    """A real person joins the waitlist / pre-orders (web form or SMS). Counts toward the smoke test."""
    ensure_tables()
    p = db.q1("SELECT * FROM landing_pages WHERE slug=?", (slug,))
    if not p or p["status"] != "published":
        raise ValueError("unknown or unpublished page")
    if not consent:
        raise PermissionError("consent is required")
    handle = handle.strip()
    if len(handle) < 4:
        raise ValueError("contact handle required")
    now = time.time()
    ex = db.q1("SELECT id, stage FROM customers WHERE opportunity_id=? AND handle=?", (p["opportunity_id"], handle))
    if ex:
        cid = ex["id"]
        if stage == "preorder":
            db.update("customers", cid, {"stage": stage, "quantity": quantity})
    else:
        cid = db.insert("customers", {"opportunity_id": p["opportunity_id"], "handle": handle, "channel": channel,
                                      "stage": stage, "quantity": quantity, "consent_at": now, "created_at": now})
    if message:
        db.insert("customer_messages", {"customer_id": cid, "at": now, "direction": "in", "text": message[:1000]})
    if p["experiment_id"]:
        _event(p["experiment_id"], "signup", quantity, 1, stage, None, f"customer#{cid}", 1, key=f"signup:{cid}")
        ExperimentAgent().evaluate(p["experiment_id"])
    return {"customer_id": cid, "stage": stage}


def record_visit(slug: str, visitor_fingerprint: str) -> None:
    v = hashlib.sha256(visitor_fingerprint.encode()).hexdigest()[:24]       # no raw IPs stored
    with db.tx() as c:
        c.execute("INSERT OR IGNORE INTO page_visits (slug, visitor, at) VALUES (?,?,?)", (slug, v, time.time()))
        c.execute("UPDATE landing_pages SET visits=visits+1 WHERE slug=?", (slug,))


# ================================================================================= Finance
class FinanceAgent(Agent):
    name = "finance"

    @staticmethod
    def actuals(opportunity_id: int) -> dict:
        ensure_tables()
        rows = db.q("SELECT kind, SUM(usd) usd, SUM(COALESCE(units,0)) units, COUNT(*) n FROM finance_entries "
                    "WHERE opportunity_id=? GROUP BY kind", (opportunity_id,))
        t = {r["kind"]: r for r in rows}
        rev = (t.get("revenue") or {}).get("usd") or 0
        refunds = (t.get("refund") or {}).get("usd") or 0
        net_rev = rev - refunds
        cogs = (t.get("cogs") or {}).get("usd") or 0
        opex = sum((t.get(k) or {}).get("usd") or 0 for k in ("cac", "opex", "fees", "logistics"))
        capex = (t.get("capex") or {}).get("usd") or 0
        customers = db.q1("SELECT COUNT(*) n FROM customers WHERE opportunity_id=? AND stage IN ('customer','preorder')",
                          (opportunity_id,))["n"]
        out = {"revenue_usd": rev, "refunds_usd": refunds, "cogs_usd": cogs, "opex_usd": opex, "capex_usd": capex,
               "orders": (t.get("revenue") or {}).get("n", 0), "units": (t.get("revenue") or {}).get("units", 0),
               "customers": customers,
               "gross_margin": (net_rev - cogs) / net_rev if net_rev else None,
               "net_margin": (net_rev - cogs - opex) / net_rev if net_rev else None,
               "cac_per_customer_usd": ((t.get("cac") or {}).get("usd") or 0) / customers if customers else None,
               "cash_position_usd": net_rev - cogs - opex - capex}
        return out

    def execute(self, opportunity_id: int) -> dict:
        o = _opp(opportunity_id)
        act = self.actuals(opportunity_id)
        model = (o["economics"].get("routes") or [{}])[0]
        flags = []
        for k in ("gross_margin", "net_margin"):
            m = model.get(k) or {}
            if act[k] is not None and m:
                if act[k] < m.get("p10", -9):
                    flags.append(f"{k} {act[k]:.0%} is below the model's p10 ({m['p10']:.0%}) — revisit assumptions.")
                elif act[k] > m.get("p90", 9):
                    flags.append(f"{k} {act[k]:.0%} beats the model's p90 ({m['p90']:.0%}).")
        if act["orders"] >= 10 and act["gross_margin"] is not None:
            with db.tx() as c:
                c.execute("DELETE FROM measured_inputs WHERE opportunity_id=? AND key='actual_gross_margin'", (opportunity_id,))
                c.execute("""INSERT INTO measured_inputs (opportunity_id, experiment_id, key, low, high, source, at)
                             VALUES (?,?,?,?,?,?,?)""", (opportunity_id, None, "actual_gross_margin", act["gross_margin"],
                                                         act["gross_margin"], f"{act['orders']} recorded orders", time.time()))
        _save_plan(opportunity_id, "finance", {"actuals": act, "variance_flags": flags,
                                               "model_route": model.get("route")})
        self.stats.update({"orders": act["orders"], "flags": len(flags)})
        return {"actuals": act, "variance_flags": flags}


def record_finance(opportunity_id: int, actor: str, kind: str, amount: float, currency: str, units: float | None = None,
                   reference: str = "", evidence_url: str = "") -> dict:
    kinds = ("revenue", "refund", "cogs", "cac", "opex", "fees", "logistics", "capex")
    if kind not in kinds:
        raise ValueError(f"kind must be one of {kinds}")
    if not actor.strip() or not reference.strip():
        raise ValueError("actor and reference (invoice/receipt/transaction id) are required")
    if not approved(opportunity_id):
        raise PermissionError("Money moves only on approved opportunities (governance gate).")
    fx = MK.fx_usd()
    cur = currency.upper()
    if cur not in fx:
        raise ValueError(f"unknown currency {cur}")
    fid = db.insert("finance_entries", {"opportunity_id": opportunity_id, "at": time.time(), "kind": kind,
                                        "amount": amount, "currency": cur, "usd": amount / fx[cur], "units": units,
                                        "reference": reference, "actor": f"human:{actor}", "evidence_url": evidence_url})
    ledger_append(f"human:{actor}", f"finance:{kind}", "opportunity", opportunity_id,
                  {"amount": amount, "currency": cur, "reference": reference})
    return {"finance_id": fid, "actuals": FinanceAgent.actuals(opportunity_id)}


# =============================================================================== Expansion
class ExpansionAgent(Agent):
    name = "expansion"

    def execute(self, opportunity_id: int, max_candidates: int = 12) -> dict:
        ensure_tables()
        o = _opp(opportunity_id)
        hyp = db.q1("SELECT * FROM hypotheses WHERE id=?", (o["hypothesis_id"],))
        terms = set(db.loads(hyp["key_terms"], []))
        cand: dict[str, dict] = {}
        for iso, n in db.loads(hyp["countries"], {}).items():
            if iso != o["country"]:
                cand.setdefault(iso, {"same_cluster_signals": 0, "related_hypotheses": 0})["same_cluster_signals"] += n
        for h in db.q("""SELECT id, key_terms, countries FROM hypotheses WHERE id != ? AND status NOT IN
                         ('superseded','stale','rejected')""", (hyp["id"],)):
            t2 = set(db.loads(h["key_terms"], []))
            if terms and len(terms & t2) / max(1, len(terms | t2)) >= 0.25:
                for iso in db.loads(h["countries"], {}):
                    if iso != o["country"]:
                        cand.setdefault(iso, {"same_cluster_signals": 0, "related_hypotheses": 0})["related_hypotheses"] += 1
        home = geo.country(o["country"])
        hs = (o["market"].get("hs") or {}).get("hs")
        rows = []
        for iso, ev in sorted(cand.items(), key=lambda kv: -(kv[1]["same_cluster_signals"] + 3 * kv[1]["related_hypotheses"]))[:max_candidates]:
            c = geo.country(iso)
            if not c:
                continue
            imp = self.safe(f"comtrade:{iso}", lambda iso=iso: MK.comtrade_flows(iso, hs, "M"), None) if hs else None
            sanc = CP.country_sanctions(iso)
            shared_lang = bool(set(c.get("langs", [])) & set(home.get("langs", [])))
            score = (math.log1p(ev["same_cluster_signals"]) + 1.5 * math.log1p(ev["related_hypotheses"])
                     + (math.log1p((imp or {}).get("value_usd", 0) / 1e6) / 2 if imp else 0)
                     + (0.5 if shared_lang else 0) + (0.3 if c["continent"] == home["continent"] else 0)
                     - (3 if sanc and sanc["level"] == "comprehensive" else 1 if sanc and sanc["level"] == "sectoral" else 0))
            rows.append({"iso3": iso, "country": c["name"], "continent": c["continent"], **ev,
                         "imports_usd": (imp or {}).get("value_usd"), "imports_year": (imp or {}).get("year"),
                         "shared_language": shared_lang, "sanctions": sanc["level"] if sanc else None,
                         "score": round(score, 3)})
        rows.sort(key=lambda r: -r["score"])
        _save_plan(opportunity_id, "expansion", {"candidates": rows,
                                                 "rule": "expand only after the home pilot passes; re-run discovery "
                                                         "and governance per country"})
        self.stats.update({"candidates": len(rows), "top": rows[0]["iso3"] if rows else None})
        return {"candidates": rows}


# ============================================================================= Coordinator
class ExecutionCoordinator(Agent):
    """Plans execution for a governed opportunity; outward actions stay locked until a human approves."""
    name = "execution_coordinator"

    def execute(self, opportunity_id: int) -> dict:
        ensure_tables()
        rev = _review(opportunity_id)
        if not rev:
            raise ValueError("run the Governance Board first")
        if rev["recommendation"] == "reject" and not approved(opportunity_id):
            return {"skipped": "governance recommended reject and no human override"}
        out = {}
        o = _opp(opportunity_id)
        if not db.q1("SELECT 1 FROM hypothesis_capabilities WHERE hypothesis_id=? LIMIT 1", (o["hypothesis_id"],)):
            from .capability_discovery import CapabilityDiscoveryAgent
            out["capability_discovery"] = {"status": CapabilityDiscoveryAgent().run(hypothesis_id=o["hypothesis_id"])["status"]}
        for agent in (ExperimentAgent, PartnershipAgent, OperationsAgent, CustomerAgent, FinanceAgent, ExpansionAgent):
            r = agent().run(opportunity_id=opportunity_id)
            out[agent.name] = {"status": r["status"], **{k: v for k, v in r["stats"].items() if k != "errors"}}
        out["approved_for_outward_actions"] = bool(approved(opportunity_id))
        self.stats.update({"agents": len(out) - 1, "approved": out["approved_for_outward_actions"]})
        return out
