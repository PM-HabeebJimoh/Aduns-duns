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
    focus: str = ""
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
    include_global: bool = False
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
    for k in ("key_terms", "countries", "need_types", "gap_causes", "score_breakdown", "tests", "llm_summary", "continents"):
        r[k] = db.loads(r[k], None)
    return r


@app.get("/api/hypotheses")
def hypotheses(domain: str = "", status: str = "", min_signals: int = 1, limit: int = 100, emerging: bool = False,
               continent: str = "", country: str = ""):
    where, params = ["signal_count >= ?"], [min_signals]
    if status != "all":
        where.append("status NOT IN ('superseded', 'stale', 'rejected')")
    if emerging:
        where.append("emerging = 1")
    if continent:
        where.append("continents LIKE ?"); params.append(f'%"{continent}"%')
    if country:
        where.append("countries LIKE ?"); params.append(f'%"{country.upper()}"%')
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


@app.post("/webhooks/telegram")
async def telegram_webhook(request: Request):
    """Telegram Bot API webhook (free). Set with:
    https://api.telegram.org/bot<TOKEN>/setWebhook?url=<public-url>/webhooks/telegram
    Replies are sent back through the Bot API when ADUNS_TELEGRAM_TOKEN is configured."""
    import os
    import requests as _rq
    upd = await request.json()
    msg = upd.get("message") or upd.get("edited_message") or {}
    chat = (msg.get("chat") or {}).get("id")
    text = msg.get("text") or ""
    if not chat:
        return {"ok": True}
    sender = f"tg:{(msg.get('from') or {}).get('id', chat)}"
    reply = OfflineScoutCoordinator().handle_message(sender, text.lstrip("/"), channel="telegram")
    token = os.environ.get("ADUNS_TELEGRAM_TOKEN")
    if token:
        try:
            _rq.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat, "text": reply}, timeout=15)
        except _rq.RequestException:
            pass
    return {"ok": True, "reply": reply}


# ----------------------------------------------------------------- 24/7 daemon & coverage
from . import scheduler  # noqa: E402


@app.on_event("startup")
def _autostart():
    import os
    if os.environ.get("ADUNS_AUTOSTART_DAEMON") == "1":
        scheduler.start_background()


@app.get("/api/coverage")
def api_coverage():
    return scheduler.coverage()


@app.get("/api/daemon")
def api_daemon():
    t = scheduler._bg.get("thread")
    return {"running_in_this_process": bool(t and t.is_alive()), "state": scheduler.state()}


@app.post("/api/daemon/start")
def api_daemon_start(parallel_countries: int = 2, downstream_per_cycle: int = 3):
    return {"started": scheduler.start_background(parallel_countries=parallel_countries,
                                                  downstream_per_cycle=downstream_per_cycle)}


@app.post("/api/daemon/stop")
def api_daemon_stop():
    return {"stopping": scheduler.stop_background()}


@app.get("/api/sources/registry")
def api_registry():
    return db.q("SELECT * FROM source_registry ORDER BY discovered_at DESC LIMIT 500")



# ----------------------------------------------------------------- remote workers
class LeaseReq(BaseModel):
    worker_id: str
    per_continent: int = 1


def _check_worker(request: Request):
    import os
    tok = os.environ.get("ADUNS_WORKER_TOKEN")
    if not tok:
        raise HTTPException(403, "Remote workers disabled: set ADUNS_WORKER_TOKEN on the central server")
    if request.headers.get("X-Aduns-Token") != tok:
        raise HTTPException(401, "bad worker token")


@app.post("/api/worker/lease")
def worker_lease(req: LeaseReq, request: Request):
    _check_worker(request)
    return {"countries": scheduler.lease_countries(req.worker_id, per_continent=max(1, min(req.per_continent, 3)))}


@app.post("/api/worker/report")
async def worker_report(request: Request):
    _check_worker(request)
    body = await request.json()
    return scheduler.ingest_worker_report(body["worker_id"], body["country"], body.get("signals", []),
                                          body.get("registry", []), body.get("stats", {}),
                                          address=request.client.host if request.client else "")


@app.get("/api/workers")
def workers():
    return {"workers": db.q("SELECT * FROM workers ORDER BY last_seen DESC"),
            "leases": db.q("SELECT * FROM leases WHERE until > ?", (time.time(),))}



# ----------------------------------------------------------------- review & learning
class HypReview(BaseModel):
    verdict: str          # confirmed | rejected | duplicate | noise
    reviewer: str
    reason: str = ""


@app.post("/api/hypotheses/{hid}/review")
def review_hypothesis(hid: int, req: HypReview):
    from . import learning
    try:
        return learning.review(hid, req.verdict, req.reviewer, req.reason)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/learning")
def learning_weights():
    return {"reviews": db.q("SELECT * FROM hypothesis_reviews ORDER BY at DESC LIMIT 200"),
            "weights": db.q("SELECT * FROM learned_weights ORDER BY kind, weight")}


@app.get("/api/alerts")
def alerts_list():
    return db.q("SELECT a.*, h.title FROM alerts_sent a LEFT JOIN hypotheses h ON h.id=a.hypothesis_id ORDER BY at DESC LIMIT 200")



# ----------------------------------------------------------------- opportunity design (layer 2)
from .agents.opportunity import OpportunityDesigner, _ensure_table as _ensure_opp  # noqa: E402


class DesignReq(BaseModel):
    hypothesis_id: int
    country: str = ""


@app.post("/api/agents/opportunity-designer")
def design_opportunity(req: DesignReq):
    return _job("opportunity_designer", OpportunityDesigner().run, **req.model_dump())


def _opp(o: dict, full: bool) -> dict:
    for k in ("market", "localization", "composition", "defensibility", "routes", "economics"):
        o[k] = db.loads(o[k], {}) if full else None
    h = db.q1("SELECT title, score FROM hypotheses WHERE id=?", (o["hypothesis_id"],))
    o["hypothesis_title"] = h["title"] if h else None
    c = geo.country(o["country"])
    o["country_name"] = c["name"] if c else o["country"]
    return o


@app.get("/api/opportunities")
def opportunities(limit: int = 100):
    _ensure_opp()
    return [_opp(o, False) for o in db.q("SELECT * FROM opportunities ORDER BY opportunity_score DESC LIMIT ?", (limit,))]


@app.get("/api/opportunities/{oid}")
def opportunity(oid: int):
    _ensure_opp()
    o = db.q1("SELECT * FROM opportunities WHERE id=?", (oid,))
    if not o:
        raise HTTPException(404)
    return _opp(o, True)



# ----------------------------------------------------------------- governance (layer 3)
from .agents import governance as G  # noqa: E402


@app.post("/api/agents/governance-board")
def governance_run(req: dict):
    return _job("governance_board", G.GovernanceBoard().run, opportunity_id=int(req["opportunity_id"]))


@app.get("/api/governance")
def governance_list():
    G._chain_tables()
    rows = db.q("""SELECT g.id, g.opportunity_id, g.at, g.recommendation, g.dossier_sha256, o.object, o.country,
                   o.status, o.opportunity_score FROM governance_reviews g JOIN opportunities o ON o.id=g.opportunity_id
                   WHERE g.id IN (SELECT MAX(id) FROM governance_reviews GROUP BY opportunity_id) ORDER BY g.at DESC""")
    return rows


@app.get("/api/governance/{opportunity_id}")
def governance_detail(opportunity_id: int):
    G._chain_tables()
    r = db.q1("SELECT * FROM governance_reviews WHERE opportunity_id=? ORDER BY id DESC LIMIT 1", (opportunity_id,))
    if not r:
        raise HTTPException(404, "no governance review yet")
    for k in ("verification", "legal", "red_team", "impact", "conditions"):
        r[k] = db.loads(r[k], {})
    r["approvals"] = db.q("SELECT * FROM approvals WHERE opportunity_id=? ORDER BY id DESC", (opportunity_id,))
    o = db.q1("SELECT object, country, best_route, status FROM opportunities WHERE id=?", (opportunity_id,))
    r["opportunity"] = o
    return r


class ApprovalReq(BaseModel):
    approver: str
    decision: str          # approved | approved_with_conditions | rejected
    conditions: str = ""


@app.post("/api/governance/{opportunity_id}/approve")
def governance_approve(opportunity_id: int, req: ApprovalReq):
    try:
        return G.approve(opportunity_id, req.approver, req.decision, req.conditions)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/ledger/verify")
def ledger_verify():
    return G.verify_chain()


@app.get("/api/ledger/chain")
def ledger_chain(limit: int = 200):
    G._chain_tables()
    return db.q("SELECT * FROM ledger_chain ORDER BY id DESC LIMIT ?", (limit,))



# ----------------------------------------------------------------- execution (layer 4)
from .agents import execution as X  # noqa: E402
from fastapi.responses import HTMLResponse  # noqa: E402
from html import escape as _esc  # noqa: E402


@app.post("/api/agents/execution")
def execution_run(req: dict):
    return _job("execution_coordinator", X.ExecutionCoordinator().run, opportunity_id=int(req["opportunity_id"]))


@app.get("/api/execution/{opportunity_id}")
def execution_detail(opportunity_id: int):
    X.ensure_tables()
    exps = db.q("SELECT * FROM experiments WHERE opportunity_id=? ORDER BY id", (opportunity_id,))
    for e in exps:
        e["result"] = db.loads(e["result"], {})
        e["events"] = db.q("SELECT kind, value, success, text, evidence_url, actor, at FROM experiment_events "
                           "WHERE experiment_id=? ORDER BY at DESC LIMIT 20", (e["id"],))
    partners = db.q("SELECT * FROM partners WHERE opportunity_id=? ORDER BY fit DESC", (opportunity_id,))
    for p in partners:
        for k in ("contacts", "screening", "outreach"):
            p[k] = db.loads(p[k], {})
    plans = {r["kind"]: db.loads(r["plan"], {}) for r in db.q("SELECT kind, plan FROM execution_plans WHERE opportunity_id=?",
                                                              (opportunity_id,))}
    page = db.q1("SELECT * FROM landing_pages WHERE opportunity_id=?", (opportunity_id,))
    if page:
        page["content"] = db.loads(page["content"], {})
    o = db.q1("SELECT object, country, status, best_route FROM opportunities WHERE id=?", (opportunity_id,))
    return {"opportunity": o, "approved": X.approved(opportunity_id), "experiments": exps, "partners": partners,
            "plans": plans, "landing_page": page,
            "customers": db.q("SELECT stage, COUNT(*) n FROM customers WHERE opportunity_id=? GROUP BY stage", (opportunity_id,)),
            "measured_inputs": db.q("SELECT * FROM measured_inputs WHERE opportunity_id=?", (opportunity_id,)),
            "finance": X.FinanceAgent.actuals(opportunity_id)}


class EventReq(BaseModel):
    actor: str
    kind: str                 # quote | rate | interview | note
    value: Optional[float] = None
    success: Optional[bool] = None
    text: str = ""
    evidence_url: str = ""


@app.post("/api/experiments/{experiment_id}/events")
def experiment_event(experiment_id: int, req: EventReq):
    try:
        return X.record_event(experiment_id, req.actor, req.kind, req.value, req.success, req.text, req.evidence_url)
    except ValueError as e:
        raise HTTPException(400, str(e))


class FinanceReq(BaseModel):
    actor: str
    kind: str
    amount: float
    currency: str
    units: Optional[float] = None
    reference: str
    evidence_url: str = ""


@app.post("/api/execution/{opportunity_id}/finance")
def finance_entry(opportunity_id: int, req: FinanceReq):
    try:
        return X.record_finance(opportunity_id, req.actor, req.kind, req.amount, req.currency, req.units, req.reference,
                                req.evidence_url)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


class StageReq(BaseModel):
    stage: str
    actor: str
    notes: str = ""


@app.post("/api/partners/{partner_id}/stage")
def partner_stage(partner_id: int, req: StageReq):
    try:
        return X.set_partner_stage(partner_id, req.stage, req.actor, req.notes)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/pages/{slug}/publish")
def page_publish(slug: str, req: dict):
    try:
        return X.publish_page(slug, str(req.get("actor", "")))
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


def _page_html(p: dict, lang: str, msg: str = "") -> str:
    c = db.loads(p["content"], {})
    t = c.get(lang) or c["en"]
    langs = [k for k in c if isinstance(c[k], dict)]
    faq = "".join(f"<details><summary>{_esc(x['q'])}</summary><p>{_esc(x['a'])}</p></details>" for x in t["faq"])
    switch = " · ".join(f'<a href="?lang={l}">{l}</a>' for l in langs)
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(t['headline'])}</title><style>body{{font:16px/1.5 system-ui,sans-serif;max-width:560px;margin:0 auto;padding:16px;color:#1b1f24;background:#f6f7f9}}
.card{{background:#fff;border:1px solid #e3e6ea;border-radius:10px;padding:18px;margin:12px 0}}input,button{{font:inherit;padding:10px;width:100%;box-sizing:border-box;margin:6px 0;border-radius:6px;border:1px solid #ccd}}
button{{background:#0f6e5a;color:#fff;border:0;font-weight:600}}.ok{{color:#12754a}}.muted{{color:#667080;font-size:13px}}</style></head><body>
<p class="muted">{switch}</p><div class="card"><h1>{_esc(t['headline'])}</h1><p>{_esc(t['body'])}</p>
{f'<p class="ok">{_esc(msg)}</p>' if msg else ''}
<form method="post"><input name="handle" placeholder="Phone or email" required><label class="muted"><input type="checkbox" name="consent" required style="width:auto"> {_esc(t['consent'])}</label>
<button>{_esc(t['cta'])}</button></form><p class="muted">SMS/WhatsApp: WAIT {_esc(p['slug'])}</p></div><div class="card">{faq}</div></body></html>"""


@app.get("/x/{slug}", response_class=HTMLResponse, include_in_schema=False)
def landing(slug: str, request: Request, lang: str = "en"):
    X.ensure_tables()
    p = db.q1("SELECT * FROM landing_pages WHERE slug=?", (slug,))
    if not p or p["status"] != "published":
        raise HTTPException(404)
    X.record_visit(slug, f"{request.client.host if request.client else ''}|{request.headers.get('user-agent', '')}")
    return _page_html(p, lang)


@app.post("/x/{slug}", response_class=HTMLResponse, include_in_schema=False)
async def landing_post(slug: str, request: Request, lang: str = "en", handle: str = Form(""), consent: str = Form("")):
    p = db.q1("SELECT * FROM landing_pages WHERE slug=?", (slug,))
    if not p or p["status"] != "published":
        raise HTTPException(404)
    try:
        X.customer_signup(slug, handle, "web", consent=bool(consent))
        msg = "Thank you — you're on the waitlist."
    except (PermissionError, ValueError) as e:
        msg = str(e)
    return _page_html(p, lang, msg)



# ----------------------------------------------------------------- payment provider webhooks
@app.post("/webhooks/payments/{provider}")
async def payment_webhook(provider: str, request: Request):
    from . import payments
    body = await request.body()
    try:
        return payments.handle(provider, body, dict(request.headers), dict(request.query_params))
    except payments.PaymentError as e:
        raise HTTPException(e.status, str(e))
