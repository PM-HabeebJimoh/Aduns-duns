"""Offline Scout Coordinator — the human-and-machine sensing network.

Responsibilities
  * Design field missions from open hypotheses: where to go (real OSM places near major cities),
    whom to ask, which languages (Wikidata official languages), and a non-leading interview guide.
  * Register scouts only with explicit, recorded consent.
  * Accept observations via web form, JSON API, or SMS / WhatsApp webhooks (Twilio-compatible).
  * Turn each observation into an `offline` layer signal (same evidence graph as online signals).
  * Corroborate automatically (independent scouts, online signals) and route to human validation.
  * Compensate: a ledger entry on submission and a larger one on validation — the people revealing
    local knowledge share in the value.

This agent never fabricates field data: observations exist only when a real person submits them.
"""
from __future__ import annotations

import json
import re
import secrets
import time

from .. import config, db, geo, http, nlp, taxonomy
from ..sources import places
from .base import Agent

RESPONDENTS = {
    "energy": ["shop owners running generators", "solar installers", "households off-grid", "small manufacturers"],
    "cold_chain": ["farmers", "market traders of perishables", "fishmongers", "pharmacies", "cold-room operators"],
    "water_sanitation": ["households", "water vendors", "borehole drillers", "school administrators"],
    "health": ["health workers", "clinic managers", "patients and caregivers", "medical equipment technicians"],
    "medicines": ["pharmacists", "patent-medicine vendors", "clinic managers", "patients"],
    "agriculture": ["smallholder farmers", "agro-dealers", "cooperative leaders", "processors / millers"],
    "finance": ["market traders", "SME owners", "mobile-money agents", "cooperative treasurers"],
    "digital": ["phone/computer repairers", "cyber-café owners", "SME owners", "students"],
    "logistics": ["truck drivers", "clearing agents", "importers", "market wholesalers"],
    "manufacturing": ["workshop owners", "machine technicians", "spare-parts dealers", "factory managers"],
    "education_skills": ["teachers", "vocational trainers", "apprentices", "employers"],
    "housing_construction": ["builders", "building-material dealers", "tenants", "artisans"],
    "business_services": ["SME owners", "accountants", "agents who help with permits", "trade associations"],
}
VENUES = {
    "energy": ["market", "electronics market"], "cold_chain": ["market", "fish market"],
    "water_sanitation": ["market", "water"], "health": ["hospital", "clinic"], "medicines": ["pharmacy", "hospital"],
    "agriculture": ["market", "farm"], "finance": ["market", "bank"], "digital": ["computer village", "market"],
    "logistics": ["truck park", "port"], "manufacturing": ["industrial estate", "spare parts market"],
    "education_skills": ["school", "vocational"], "housing_construction": ["building materials market", "market"],
    "business_services": ["market", "business district"],
}

CONSENT_SCRIPT = (
    "Hello, I am a field researcher with the Aduns opportunity project. We are learning how people in this area "
    "get {topic} and what problems they face. Taking part is voluntary; you may stop at any time or skip any "
    "question. We will not record your name unless you want to be contacted again. What you share may help "
    "create better services here, and contributors are compensated. Do you agree to answer a few questions? "
    "(Record YES/NO.)"
)


class OfflineScoutCoordinator(Agent):
    name = "offline_scout"

    # ----------------------------------------------------------- mission design
    def execute(self, hypothesis_id: int, country: str = "", quota: int = 20,
                reward_per_validated: float | None = None, max_locations: int = 6) -> dict:
        hyp = db.q1("SELECT * FROM hypotheses WHERE id=?", (hypothesis_id,))
        if not hyp:
            raise ValueError(f"hypothesis {hypothesis_id} not found")
        iso3 = geo.resolve(country) if country else None
        if not iso3:
            from collections import Counter
            ranked = Counter(db.loads(hyp["countries"], {})).most_common()
            iso3 = next((c for c, _ in ranked if geo.country(c)), None)
        if not iso3:
            raise ValueError("mission needs a country (none in hypothesis signals); pass country=")
        c = geo.country(iso3)
        domain = hyp["domain"] or "business_services"
        terms = db.loads(hyp["key_terms"], [])
        topic = terms[0] if terms else domain.replace("_", " ")

        locations = []
        cities = [x["name"] for x in c["cities"][:3]] or [c["capital"] or c["name"]]
        for city in cities:
            for venue in VENUES.get(domain, ["market"]):
                if len(locations) >= max_locations:
                    break
                hits = self.safe("nominatim", lambda q=f"{venue} {city}": places.geocode(q, c["iso2"], limit=2), [])
                for h in hits or []:
                    if all(abs(h["lat"] - l["lat"]) > 1e-4 for l in locations):
                        locations.append({**h, "city": city, "venue_query": venue})
        guide = self.interview_guide(hyp, topic)
        code = f"M{hyp['id']}-{secrets.token_hex(2).upper()}"
        mid = db.insert("scout_missions", {
            "code": code, "hypothesis_id": hyp["id"],
            "title": f"Field validation: {hyp['title']}"[:200],
            "objective": "Confirm or reject the hypothesis with first-hand evidence. Falsification tests: "
                         + " | ".join(db.loads(hyp["tests"], [])),
            "country": iso3, "locations": json.dumps(locations), "languages": json.dumps(c.get("languages") or []),
            "target_respondents": json.dumps(RESPONDENTS.get(domain, ["local residents", "shop owners"])),
            "interview_guide": json.dumps(guide), "consent_script": CONSENT_SCRIPT.format(topic=topic),
            "reward_per_validated": reward_per_validated if reward_per_validated is not None else config.SCOUT_REWARD_VALIDATED,
            "quota": quota, "status": "open", "created_at": time.time(),
        })
        db.update("hypotheses", hyp["id"], {"status": "validating", "updated_at": time.time()})
        db.audit(self.name, "mission_created", "scout_mission", mid, {"code": code, "country": iso3})
        self.stats.update({"mission_id": mid, "code": code, "locations": len(locations)})
        return {"mission_id": mid, "code": code}

    @staticmethod
    def interview_guide(hyp: dict, topic: str) -> list[dict]:
        types = db.loads(hyp["need_types"], {})
        q = [
            {"id": "context", "q": f"How do you currently get {topic}? Walk me through the last time.", "kind": "open"},
            {"id": "frequency", "q": f"How often do you need {topic}? When did you last need it?", "kind": "open"},
            {"id": "pain", "q": "What is the hardest part of that? What happened as a result?", "kind": "open"},
            {"id": "normal", "q": "Is there anything about this you've come to accept as 'just how it is' here? Why?",
             "kind": "normalized_probe"},
            {"id": "elsewhere", "q": "Do you know anywhere (another town or country) where this works better? How do they do it?",
             "kind": "analogy_probe"},
            {"id": "workaround", "q": "What do you do instead when you can't get it? What does that cost you?", "kind": "open"},
            {"id": "spend", "q": f"How much did you pay the last time you got {topic}, and where? (record amount + currency)",
             "kind": "price"},
            {"id": "wtp_too_cheap", "q": "At what price would it be so cheap you'd doubt the quality?", "kind": "van_westendorp"},
            {"id": "wtp_expensive", "q": "At what price would it start to feel expensive but still worth it?", "kind": "van_westendorp"},
            {"id": "wtp_too_expensive", "q": "At what price would you not consider it at all?", "kind": "van_westendorp"},
            {"id": "suppliers", "q": "Who sells, repairs or provides this now — even informally? Any idle machines, "
                                     "workshops or people with the skills nearby?", "kind": "capability_probe"},
            {"id": "followup", "q": "May we contact you again if we find a better option? (optional phone)", "kind": "consent"},
        ]
        if "unaffordable" in types:
            q.insert(7, {"id": "price_breakdown", "q": "Do you know why it costs that much here (import duty, transport, middlemen)?",
                         "kind": "open"})
        if "institutional" in types:
            q.insert(1, {"id": "procurement", "q": "Has your organisation tried to buy this formally? Did suppliers respond?",
                         "kind": "open"})
        return q

    # ------------------------------------------------------------- scouts & data
    @staticmethod
    def register_scout(handle: str, consent: bool, display_name: str = "", role: str = "", country: str = "",
                       locality: str = "", languages: str = "", payout_method: str = "") -> int:
        if not consent:
            raise ValueError("Scouts can only be registered with explicit consent.")
        handle = handle.strip()
        existing = db.q1("SELECT id FROM scouts WHERE handle=?", (handle,))
        fields = {"display_name": display_name, "role": role, "country": geo.resolve(country) if country else None,
                  "locality": locality, "languages": languages, "payout_method": payout_method,
                  "consent_at": time.time(),
                  "consent_text": "Agreed to share observations for opportunity research; paid per submission/validation; "
                                  "may withdraw anytime."}
        if existing:
            db.update("scouts", existing["id"], {k: v for k, v in fields.items() if v})
            return existing["id"]
        sid = db.insert("scouts", {"handle": handle, **fields, "created_at": time.time()})
        db.audit("offline_scout", "scout_registered", "scout", sid, {"role": role, "country": fields["country"]})
        return sid

    def submit_observation(self, mission_code: str | None, scout_handle: str, text: str, channel: str = "web",
                           consent_confirmed: bool = False, language: str = "", location: str = "",
                           lat: float | None = None, lon: float | None = None, price: float | None = None,
                           currency: str = "", respondent_type: str = "", media_urls: list[str] | None = None) -> dict:
        scout = db.q1("SELECT * FROM scouts WHERE handle=?", (scout_handle.strip(),))
        if not scout or not scout["consent_at"]:
            raise PermissionError("Unknown scout or no consent on record. Register first (send JOIN …).")
        if not consent_confirmed:
            raise PermissionError("Respondent consent must be confirmed for every observation.")
        text = nlp.clean(text)
        if len(text) < 10:
            raise ValueError("Observation text too short.")
        mission = db.q1("SELECT * FROM scout_missions WHERE code=?", (mission_code,)) if mission_code else None
        if mission_code and not mission:
            raise ValueError(f"Unknown mission code {mission_code}")

        det = nlp.detect_need(text)
        countries = geo.find_countries(f"{text} {location}")
        if mission and mission["country"] not in countries:
            countries.append(mission["country"])
        elif scout["country"] and scout["country"] not in countries:
            countries.append(scout["country"])
        now = time.time()
        h = http.content_hash("field", scout["id"], text)
        sig_id = db.insert("signals", {
            "source": f"field:{channel}", "layer": "offline", "external_id": f"scout{scout['id']}:{int(now)}",
            "url": None, "title": text[:140], "text": text, "author": f"scout#{scout['id']}",
            "published_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)), "retrieved_at": now,
            "content_hash": h, "query": None,
            "domain": taxonomy.classify_domain(text)[0] or (
                db.q1("SELECT domain FROM hypotheses WHERE id=?", (mission["hypothesis_id"],))["domain"] if mission else None),
            "need_types": json.dumps(det["need_types"] or ["unmet"]), "gap_causes": json.dumps(det["gap_causes"]),
            "intensity": det["intensity"], "need_score": max(det["need_score"], 0.5),
            "countries": json.dumps(countries), "entities": json.dumps(det["objects"]), "engagement": 0.0,
            "extra": json.dumps({"price": price, "currency": currency, "respondent_type": respondent_type,
                                 "location": location, "lat": lat, "lon": lon}),
        }, ignore=True)
        if not sig_id:
            raise ValueError("Duplicate observation.")
        if mission:
            with db.tx() as conn:
                conn.execute("INSERT OR IGNORE INTO hypothesis_signals (hypothesis_id, signal_id, similarity) VALUES (?,?,?)",
                             (mission["hypothesis_id"], sig_id, None))
        oid = db.insert("scout_observations", {
            "mission_id": mission["id"] if mission else None, "scout_id": scout["id"], "channel": channel, "text": text,
            "language": language, "location": location, "lat": lat, "lon": lon, "price_observed": price,
            "currency": currency, "respondent_type": respondent_type, "media_urls": json.dumps(media_urls or []),
            "consent_confirmed": 1, "status": "submitted", "signal_id": sig_id, "submitted_at": now,
        })
        db.insert("compensation_ledger", {"scout_id": scout["id"], "observation_id": oid,
                                          "amount": config.SCOUT_REWARD_SUBMITTED, "reason": "submission",
                                          "created_at": now})
        db.audit("offline_scout", "observation_submitted", "scout_observation", oid, {"channel": channel})
        status = self.corroborate(oid)
        return {"observation_id": oid, "signal_id": sig_id, "status": status, "need": det}

    @staticmethod
    def corroborate(observation_id: int, min_sim: float = 0.2) -> str:
        """Auto-corroboration: ≥1 other scout or ≥2 online signals of the same hypothesis say the same thing."""
        o = db.q1("SELECT * FROM scout_observations WHERE id=?", (observation_id,))
        if not o or not o["mission_id"]:
            return o["status"] if o else "missing"
        m = db.q1("SELECT * FROM scout_missions WHERE id=?", (o["mission_id"],))
        others = db.q("""SELECT text, scout_id FROM scout_observations WHERE mission_id=? AND id!=? AND scout_id!=?
                         AND status!='rejected'""", (o["mission_id"], o["id"], o["scout_id"]))
        online = db.q("""SELECT s.text FROM signals s JOIN hypothesis_signals hs ON hs.signal_id=s.id
                         WHERE hs.hypothesis_id=? AND s.layer!='offline' LIMIT 200""", (m["hypothesis_id"],))
        docs = [o["text"]] + [x["text"] for x in others] + [x["text"] for x in online]
        if len(docs) == 1:
            return o["status"]
        tf = nlp.TfIdf(docs)
        M = tf.matrix()
        sims = M[1:] @ M[0]
        scout_hits = {others[i]["scout_id"] for i in range(len(others)) if sims[i] >= min_sim}
        online_hits = int((sims[len(others):] >= min_sim).sum())
        note = f"auto: {len(scout_hits)} independent scout(s), {online_hits} online signal(s) similar ≥{min_sim}"
        if (len(scout_hits) >= 1 or online_hits >= 2) and o["status"] == "submitted":
            db.update("scout_observations", o["id"], {"status": "corroborated", "validation_notes": note})
            return "corroborated"
        db.update("scout_observations", o["id"], {"validation_notes": note})
        return o["status"]

    @staticmethod
    def review(observation_id: int, decision: str, reviewer: str, notes: str = "") -> dict:
        """Human validation gate. Validated observations earn the larger reward."""
        if decision not in ("validated", "rejected"):
            raise ValueError("decision must be validated|rejected")
        o = db.q1("SELECT * FROM scout_observations WHERE id=?", (observation_id,))
        if not o:
            raise ValueError("observation not found")
        if o["status"] in ("validated", "rejected"):
            return {"status": o["status"], "unchanged": True}
        db.update("scout_observations", observation_id, {
            "status": decision, "validation_notes": f"{o['validation_notes'] or ''} | {reviewer}: {notes}".strip(" |")})
        if decision == "validated":
            m = db.q1("SELECT * FROM scout_missions WHERE id=?", (o["mission_id"],)) if o["mission_id"] else None
            amount = m["reward_per_validated"] if m else config.SCOUT_REWARD_VALIDATED
            db.insert("compensation_ledger", {"scout_id": o["scout_id"], "observation_id": o["id"], "amount": amount,
                                              "reason": "validated observation", "created_at": time.time()})
            if m:
                n = db.q1("SELECT COUNT(*) n FROM scout_observations WHERE mission_id=? AND status='validated'",
                          (m["id"],))["n"]
                if n >= 2:
                    db.update("hypotheses", m["hypothesis_id"], {"evidence_level": "field_verified",
                                                                 "updated_at": time.time()})
                if n >= (m["quota"] or 0):
                    db.update("scout_missions", m["id"], {"status": "quota_met"})
        else:
            db.execute("UPDATE signals SET need_score = 0 WHERE id=?", (o["signal_id"],))
        db.audit(reviewer, f"observation_{decision}", "scout_observation", observation_id, {"notes": notes})
        return {"status": decision}

    # ----------------------------------------------------------- SMS / WhatsApp
    HELP = ("Aduns field network. Commands:\n"
            "JOIN <name> | <role> | <country> | <town>  (you agree to share observations; paid per validated report)\n"
            "OBS <mission-code> <what you saw/heard>  (respondent agreed)\n"
            "PRICE <mission-code> <amount> <currency> <item> @ <place>\n"
            "MISSIONS  – list open missions\nSTOP – withdraw")

    def handle_message(self, sender: str, body: str, channel: str = "sms") -> str:
        """Parse an inbound SMS/WhatsApp message and return the reply text."""
        b = (body or "").strip()
        cmd = b.split(" ", 1)[0].upper() if b else "HELP"
        rest = b[len(cmd):].strip()
        try:
            if cmd == "JOIN":
                parts = [p.strip() for p in rest.split("|")]
                parts += [""] * (4 - len(parts))
                self.register_scout(sender, consent=True, display_name=parts[0], role=parts[1], country=parts[2],
                                    locality=parts[3])
                return "Welcome to the Aduns field network. You can withdraw any time with STOP. Send MISSIONS to see open tasks."
            if cmd == "STOP":
                s = db.q1("SELECT id FROM scouts WHERE handle=?", (sender,))
                if s:
                    db.update("scouts", s["id"], {"consent_at": None})
                    db.audit("offline_scout", "scout_withdrew", "scout", s["id"])
                return "You have been withdrawn. Owed rewards will still be paid."
            if cmd == "MISSIONS":
                s = db.q1("SELECT country FROM scouts WHERE handle=?", (sender,))
                rows = db.q("SELECT code, title FROM scout_missions WHERE status='open' AND (country=? OR ? IS NULL) "
                            "ORDER BY id DESC LIMIT 5", ((s or {}).get("country"), (s or {}).get("country")))
                return "\n".join(f"{r['code']}: {r['title'][:80]}" for r in rows) or "No open missions right now."
            if cmd == "OBS":
                code, _, txt = rest.partition(" ")
                r = self.submit_observation(code.upper(), sender, txt, channel=channel, consent_confirmed=True)
                return f"Thanks! Observation #{r['observation_id']} recorded ({r['status']})."
            if cmd == "PRICE":
                m = re.match(r"(\S+)\s+([\d.,]+)\s+([A-Za-z]{3})\s+(.+?)(?:\s+@\s+(.+))?$", rest)
                if not m:
                    return "Format: PRICE <code> <amount> <currency> <item> @ <place>"
                code, amt, cur, item, place = m.groups()
                amount = float(amt.replace(",", ""))
                r = self.submit_observation(code.upper(), sender, f"Observed price for {item}: {amount} {cur.upper()}"
                                            + (f" at {place}" if place else ""), channel=channel, consent_confirmed=True,
                                            price=amount, currency=cur.upper(), location=place or "")
                return f"Price recorded (#{r['observation_id']}). Thank you."
        except (PermissionError, ValueError) as e:
            return f"Sorry: {e}"
        return self.HELP
