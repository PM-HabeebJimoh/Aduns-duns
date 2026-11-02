"""HTTP API + dashboard for the Discovery layer.

Run:  python -m aduns serve   (or: uvicorn aduns.api:app)
"""
from __future__ import annotations

import threading
import time
import traceback
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import db, geo, llm, taxonomy
from .agents import (CapabilityDiscoveryAgent, CrossBorderAnalogyAgent, NeedSensingAgent,
                     OfflineScoutCoordinator, SignalFusionAgent)
from .orchestrator import run_discovery

WEB = Path(__file__).parent / "web"
app = FastAPI(title="Aduns — Global Opportunity-to-Reality Engine", version="0.1.0",
              description="Discovery layer: need sensing, signal fusion, capability discovery, cross-border analogy, "
                          "offline scout coordination. Real, free public data only.")
app.mount("/static", StaticFiles(directory=WEB), name="static")

JOBS: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _job(kind: str, fn, **params) -> dict:
    jid = f"{kind}-{int(time.time() * 1000)}"
    job = {"id": jid, "kind": kind, "params": params, "status": "running", "log": [], "started_at": time.time()}
    with _jobs_lock:
        JOBS[jid] = job

    def runner():
        try:
            job["result"] = fn(**params, progress=lambda m: job["log"].append(f"{time.strftime('%H:%M:%S')} {m}")) \
                if kind == "discover" else fn(**params)
            job["status"] = "done"
        except Exception as e:  # noqa: BLE001
            job["status"] = "error"
            job["error"] = f"{type(e).__name__}: {e}"
            job["trace"] = traceback.format_exc()[-1500:]
        job["finished_at"] = time.time()

    threading.Thread(target=runner, daemon=True).start()
    return {"job_id": jid}


# ----------------------------------------------------------------- pages
@app.get("/", include_in_schema=False)
def index():
    return FileResponse(WEB / "index.html")


@app.get("/scout", include_in_schema=False)
def scout_page():
    return FileResponse(WEB / "scout.html")


# ----------------------------------------------------------------- meta
@app.get("/api/status")
def status():
    counts = {t: db.q1(f"SELECT COUNT(*) n FROM {t}")["n"] for t in
              ("signals", "hypotheses", "capabilities", "analogies", "scouts", "scout_missions", "scout_observations")}
    layers = db.q("SELECT layer, COUNT(*) n FROM signals GROUP BY layer")
    sources = db.q("SELECT * FROM source_health ORDER BY source")
    return {"counts": counts, "layers": layers, "sources": sources, "llm_enabled": llm.enabled(),
            "domains": list(taxonomy.DOMAINS)}


@app.get("/api/runs")
def runs(limit: int = 50):
    rows = db.q("SELECT * FROM agent_runs ORDER BY id DESC LIMIT ?", (limit,))
    for r in rows:
        r["params"] = db.loads(r["params"], {})
        r["stats"] = db.loads(r["stats"], {})
    return rows


@app.get("/api/jobs")
def jobs():
    return sorted(JOBS.values(), key=lambda j: -j["started_at"])[:20]


@app.get("/api/jobs/{jid}")
def job(jid: str):
    if jid not in JOBS:
        raise HTTPException(404)
    return JOBS[jid]


@app.get("/api/audit")
def audit(limit: int = 100):
    return db.q("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))


# ----------------------------------------------------------------- runs
class DiscoverReq(BaseModel):
    focus: str = Field(..., min_length=2)
    country: str = ""
    depth: int = Field(1, ge=1, le=3)
    top_n: int = Field(5, ge=1, le=20)
    sources: Optional[list[str]] = None
    create_missions: bool = True


@app.post("/api/discover")
def discover(req: DiscoverReq):
    return _job("discover", run_discovery, focus=req.focus, country=req.country, depth=req.depth, top_n=req.top_n,
                sources=req.sources, create_missions=req.create_missions)


class SenseReq(BaseModel):
    focus: str = ""
    country: str = ""
    depth: int = 1
    sources: Optional[list[str]] = None


@app.post("/api/agents/need-sensing")
def sense(req: SenseReq):
    return _job("need_sensing", NeedSensingAgent().run, **req.model_dump())


class FuseReq(BaseModel):
    query: str = ""
    domain: str = ""
    country: str = ""
    threshold: float = 0.22
    min_cluster_size: int = 2


@app.post("/api/agents/signal-fusion")
def fuse(req: FuseReq):
    return _job("signal_fusion", SignalFusionAgent().run, **req.model_dump())


class CapReq(BaseModel):
    hypothesis_id: Optional[int] = None
    query: str = ""
    sources: Optional[list[str]] = None


@app.post("/api/agents/capability-discovery")
def capabilities_run(req: CapReq):
    return _job("capability_discovery", CapabilityDiscoveryAgent().run, **req.model_dump())


class AnalogyReq(BaseModel):
    hypothesis_id: Optional[int] = None
    country: str = ""
    domain: str = ""


@app.post("/api/agents/cross-border-analogy")
def analogy_run(req: AnalogyReq):
    return _job("cross_border_analogy", CrossBorderAnalogyAgent().run, **req.model_dump())


class MissionReq(BaseModel):
    hypothesis_id: int
    country: str = ""
    quota: int = 20
    reward_per_validated: Optional[float] = None


@app.post("/api/agents/offline-scout/missions")
def mission_run(req: MissionReq):
    return OfflineScoutCoordinator().run(**req.model_dump())


# ----------------------------------------------------------------- data
@app.get("/api/signals")
def signals(source: str = "", layer: str = "", domain: str = "", q: str = "", country: str = "",
            limit: int = 100, offset: int = 0):
    where, params = ["1=1"], []
    if source:
        where.append("source LIKE ?"); params.append(f"{source}%")
    if layer:
        where.append("layer = ?"); params.append(layer)
    if domain:
        where.append("domain = ?"); params.append(domain)
    if q:
        where.append("text LIKE ?"); params.append(f"%{q}%")
    if country:
        where.append("countries LIKE ?"); params.append(f'%"{country.upper()}"%')
    rows = db.q(f"SELECT * FROM signals WHERE {' AND '.join(where)} ORDER BY need_score DESC, id DESC LIMIT ? OFFSET ?",
                (*params, min(limit, 500), offset))
    for r in rows:
        for k in ("need_types", "gap_causes", "countries", "entities", "extra"):
            r[k] = db.loads(r[k], [])
    return rows


def _hyp(r: dict) -> dict:
    for k in ("key_terms", "countries", "need_types", "gap_causes", "score_breakdown", "tests", "llm_summary"):
        r[k] = db.loads(r[k], None)
    return r


@app.get("/api/hypotheses")
def hypotheses(domain: str = "", status: str = "", min_signals: int = 1, limit: int = 100):
    where, params = ["signal_count >= ?"], [min_signals]
    if status != "all":
        where.append("status != 'superseded'")
    if domain:
        where.append("domain = ?"); params.append(domain)
    if status and status != "all":
        where.append("status = ?"); params.append(status)
    rows = db.q(f"SELECT * FROM hypotheses WHERE {' AND '.join(where)} ORDER BY score DESC LIMIT ?", (*params, limit))
    return [_hyp(r) for r in rows]


@app.get("/api/hypotheses/{hid}")
def hypothesis(hid: int):
    h = db.q1("SELECT * FROM hypotheses WHERE id=?", (hid,))
    if not h:
        raise HTTPException(404)
    h = _hyp(h)
    h["signals"] = signals_for(hid)
    caps = db.q("""SELECT c.*, hc.relevance, hc.rationale FROM capabilities c JOIN hypothesis_capabilities hc
                   ON hc.capability_id=c.id WHERE hc.hypothesis_id=? ORDER BY hc.relevance DESC""", (hid,))
    for c in caps:
        c["countries"] = db.loads(c["countries"], [])
        c["transferability"] = db.loads(c["transferability"], [])
        c["extra"] = db.loads(c["extra"], {})
    h["capabilities"] = caps
    an = db.q("SELECT * FROM analogies WHERE hypothesis_id=? ORDER BY deviance_score DESC", (hid,))
    for a in an:
        a["evidence"] = db.loads(a["evidence"], [])
        c = geo.country(a["analog_country"])
        a["analog_name"] = c["name"] if c else a["analog_country"]
        t = geo.country(a["target_country"])
        a["target_name"] = t["name"] if t else a["target_country"]
    h["analogies"] = an
    h["missions"] = [_mission(m) for m in db.q("SELECT * FROM scout_missions WHERE hypothesis_id=?", (hid,))]
    return h


def signals_for(hid: int):
    rows = db.q("""SELECT s.*, hs.similarity FROM signals s JOIN hypothesis_signals hs ON hs.signal_id=s.id
                   WHERE hs.hypothesis_id=? ORDER BY hs.similarity DESC""", (hid,))
    for r in rows:
        for k in ("need_types", "gap_causes", "countries", "entities", "extra"):
            r[k] = db.loads(r[k], [])
    return rows


@app.get("/api/capabilities")
def capabilities(capability_type: str = "", q: str = "", limit: int = 100):
    where, params = ["1=1"], []
    if capability_type:
        where.append("capability_type = ?"); params.append(capability_type)
    if q:
        where.append("(title LIKE ? OR description LIKE ?)"); params += [f"%{q}%", f"%{q}%"]
    rows = db.q(f"SELECT * FROM capabilities WHERE {' AND '.join(where)} ORDER BY maturity DESC LIMIT ?", (*params, limit))
    for c in rows:
        c["countries"] = db.loads(c["countries"], [])
        c["transferability"] = db.loads(c["transferability"], [])
        c["extra"] = db.loads(c["extra"], {})
    return rows


@app.get("/api/analogies")
def analogies(limit: int = 100):
    rows = db.q("SELECT * FROM analogies ORDER BY deviance_score DESC LIMIT ?", (limit,))
    for a in rows:
        a["evidence"] = db.loads(a["evidence"], [])
    return rows


@app.get("/api/countries")
def countries():
    return [{k: c[k] for k in ("iso3", "iso2", "name", "region", "income")} for c in geo.countries().values()]


# ----------------------------------------------------------------- field network
def _mission(m: dict) -> dict:
    for k in ("locations", "languages", "target_respondents", "interview_guide"):
        m[k] = db.loads(m[k], [])
    m["observations"] = db.q("SELECT COUNT(*) n FROM scout_observations WHERE mission_id=?", (m["id"],))[0]["n"]
    return m


@app.get("/api/missions")
def missions(status: str = "open"):
    rows = db.q("SELECT * FROM scout_missions WHERE status=? OR ?='' ORDER BY id DESC", (status, status))
    return [_mission(m) for m in rows]


@app.get("/api/missions/{code}")
def mission(code: str):
    m = db.q1("SELECT * FROM scout_missions WHERE code=?", (code.upper(),))
    if not m:
        raise HTTPException(404)
    return _mission(m)


class ScoutReq(BaseModel):
    handle: str
    consent: bool
    display_name: str = ""
    role: str = ""
    country: str = ""
    locality: str = ""
    languages: str = ""
    payout_method: str = ""


@app.post("/api/scouts")
def register_scout(req: ScoutReq):
    try:
        return {"scout_id": OfflineScoutCoordinator.register_scout(**req.model_dump())}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/scouts")
def scouts():
    return db.q("""SELECT s.id, s.display_name, s.role, s.country, s.locality, s.consent_at, s.created_at,
                   (SELECT COUNT(*) FROM scout_observations o WHERE o.scout_id=s.id) observations,
                   (SELECT COALESCE(SUM(amount),0) FROM compensation_ledger l WHERE l.scout_id=s.id) earned
                   FROM scouts s ORDER BY s.id DESC""")


class ObsReq(BaseModel):
    mission_code: Optional[str] = None
    scout_handle: str
    text: str
    consent_confirmed: bool
    channel: str = "web"
    language: str = ""
    location: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    price: Optional[float] = None
    currency: str = ""
    respondent_type: str = ""


@app.post("/api/observations")
def submit_observation(req: ObsReq):
    try:
        return OfflineScoutCoordinator().submit_observation(**req.model_dump())
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/observations")
def observations(status: str = "", limit: int = 200):
    return db.q("""SELECT o.*, m.code mission_code FROM scout_observations o LEFT JOIN scout_missions m ON m.id=o.mission_id
                   WHERE o.status=? OR ?='' ORDER BY o.id DESC LIMIT ?""", (status, status, limit))


class ReviewReq(BaseModel):
    decision: str
    reviewer: str
    notes: str = ""


@app.post("/api/observations/{oid}/review")
def review(oid: int, req: ReviewReq):
    try:
        return OfflineScoutCoordinator.review(oid, req.decision, req.reviewer, req.notes)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/ledger")
def ledger():
    return db.q("SELECT * FROM compensation_ledger ORDER BY id DESC LIMIT 500")


@app.post("/webhooks/sms", include_in_schema=True)
async def sms_webhook(request: Request, From: str = Form(""), Body: str = Form("")):
    """Twilio-compatible SMS/WhatsApp webhook. Returns TwiML."""
    channel = "whatsapp" if From.startswith("whatsapp:") else "sms"
    sender = From.replace("whatsapp:", "")
    reply = OfflineScoutCoordinator().handle_message(sender, Body, channel=channel)
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{escape(reply)}</Message></Response>',
                    media_type="application/xml")
