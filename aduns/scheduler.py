"""24/7 autonomous discovery scheduler.

Every cycle:
  1. picks the least-recently-swept country on EACH continent (Africa, Asia, Europe, North America,
     South America, Oceania) → equal, continuous worldwide coverage; every country is revisited in rotation;
  2. runs Need Sensing sweeps for them (in parallel, per-host rate limits respected);
  3. hourly: global feeds (disaster alerts, shortages, failed tenders, complaints, HN, Stack Exchange);
  4. Signal Fusion over the recent window;
  5. for the strongest new/updated hypotheses: Capability Discovery, Cross-Border Analogy and an
     Offline Scout mission (drafted, in the local language);
  6. back-fills English translations for signals whose translation was deferred.

State (heartbeat, cycle, current step, errors) lives in `daemon_state`, so the API/dashboard can show it.
Stop by calling Daemon.stop() or creating the file data/STOP.
"""
from __future__ import annotations

import json
import os
import socket
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

from . import config, db, geo, translate
from .agents import (CapabilityDiscoveryAgent, CrossBorderAnalogyAgent, NeedSensingAgent, OfflineScoutCoordinator,
                     SignalFusionAgent)


def _set(key: str, value) -> None:
    with db.tx() as c:
        c.execute("INSERT OR REPLACE INTO daemon_state (key, value, at) VALUES (?,?,?)",
                  (key, json.dumps(value, default=str), time.time()))


def state() -> dict:
    return {r["key"]: {"value": db.loads(r["value"], r["value"]), "at": r["at"]} for r in db.q("SELECT * FROM daemon_state")}


class Daemon:
    def __init__(self, parallel_countries: int = 2, downstream_per_cycle: int = 3, global_every_s: int = 3600,
                 fusion_window_days: int = 30, mission_min_score: float = 0.3, worker_id: str | None = None,
                 sense_locally: bool = True):
        self.parallel = parallel_countries
        self.downstream_per_cycle = downstream_per_cycle
        self.global_every_s = global_every_s
        self.fusion_window_days = fusion_window_days
        self.mission_min_score = mission_min_score
        self._stop = threading.Event()
        self.cycle_no = 0
        self.worker_id = worker_id or f"local:{socket.gethostname()}:{os.getpid()}"
        self.sense_locally = sense_locally

    # ---------------------------------------------------------------- control
    def stop(self) -> None:
        self._stop.set()

    def stopped(self) -> bool:
        return self._stop.is_set() or (config.ROOT / "data" / "STOP").exists()

    def run_forever(self, max_cycles: int | None = None, max_seconds: float | None = None) -> None:
        deadline = time.time() + max_seconds if max_seconds else None
        if deadline:
            # graceful time box (e.g. CI runners): stop starting new cycles near the deadline
            threading.Timer(max(1.0, max_seconds), self.stop).start()
        _set("status", "running")
        _set("started_at", time.time())
        # runs left 'running' by a previous process that was stopped are closed as aborted
        db.execute("UPDATE agent_runs SET status='aborted', finished_at=? WHERE status='running' AND started_at < ?",
                   (time.time(), time.time() - 7200))
        db.execute("DELETE FROM leases WHERE until < ?", (time.time(),))
        while not self.stopped() and (max_cycles is None or self.cycle_no < max_cycles):
            try:
                self.cycle()
            except Exception as e:  # noqa: BLE001 — the daemon must survive anything
                _set("last_error", f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1500:]}")
                time.sleep(30)
            time.sleep(config.SWEEP_PAUSE_SECONDS)
        _set("status", "stopped")

    # ------------------------------------------------------------------ cycle
    def next_countries(self) -> list[str]:
        return lease_countries(self.worker_id, per_continent=1)

    def cycle(self) -> dict:
        self.cycle_no += 1
        report: dict = {"cycle": self.cycle_no, "started": time.time()}
        _set("heartbeat", time.time())
        _set("cycle", self.cycle_no)

        countries = self.next_countries() if self.sense_locally else []
        report["countries"] = countries
        _set("step", f"sensing {', '.join(countries)}")

        def sweep(iso):
            if self.stopped():
                return iso, {"status": "skipped"}
            try:
                r = NeedSensingAgent().run(country=iso)
            finally:
                release(self.worker_id, iso)
            return iso, {"status": r["status"], "stored": r["stats"].get("signals_stored", 0)}
        with ThreadPoolExecutor(max_workers=self.parallel) as ex:
            report["sweeps"] = dict(ex.map(sweep, countries))
        _set("heartbeat", time.time())

        last_global = (state().get("last_global") or {}).get("value") or 0
        if time.time() - float(last_global) > self.global_every_s and not self.stopped():
            _set("step", "global feeds")
            g = NeedSensingAgent().run(include_global=True)
            report["global"] = g["stats"].get("signals_stored", 0)
            _set("last_global", time.time())

        if self.stopped():
            return report
        _set("step", "signal fusion")
        f = SignalFusionAgent().run(window_days=self.fusion_window_days, max_per_partition=3000)
        report["fusion"] = {k: f["stats"].get(k) for k in ("hypotheses", "hypotheses_created", "hypotheses_updated",
                                                           "superseded", "signals_considered")}

        report["downstream"] = self.downstream()
        report["designed"] = self.design_opportunities()
        report["governed"] = self.govern()
        report["execution"] = self.execute_plans()
        from . import alerts
        report["alerts"] = len(alerts.check())
        report["translated_backfill"] = self.backfill_translations()
        from . import http as _http
        last_prune = float((state().get("last_prune") or {}).get("value") or 0)
        if time.time() - last_prune > 86400:
            report["cache_pruned"] = _http.prune_cache(vacuum=True)
            _set("last_prune", time.time())
        report["finished"] = time.time()
        _set("last_cycle", report)
        _set("heartbeat", time.time())
        return report

    def downstream(self) -> list[dict]:
        """Capabilities + analogies + field mission for the strongest hypotheses not processed in 24h."""
        rows = db.q("""SELECT id, score, countries, scope FROM hypotheses
                       WHERE status NOT IN ('superseded', 'stale', 'rejected') AND signal_count >= 2 AND countries != '{}'
                       AND (processed_at IS NULL OR processed_at < ?) ORDER BY score DESC LIMIT ?""",
                    (time.time() - 86400, self.downstream_per_cycle))
        done = []
        for h in rows:
            if self.stopped():
                break
            _set("step", f"downstream hypothesis #{h['id']}")
            item = {"hypothesis": h["id"]}
            item["capabilities"] = CapabilityDiscoveryAgent().run(hypothesis_id=h["id"])["stats"].get("linked", 0)
            item["analogies"] = CrossBorderAnalogyAgent().run(hypothesis_id=h["id"])["stats"].get("analogies", 0)
            has_mission = db.q1("SELECT id FROM scout_missions WHERE hypothesis_id=?", (h["id"],))
            if h["score"] >= self.mission_min_score and not has_mission:
                m = OfflineScoutCoordinator().run(hypothesis_id=h["id"])
                item["mission"] = m.get("code")
            db.update("hypotheses", h["id"], {"processed_at": time.time()})
            done.append(item)
        return done

    def design_opportunities(self, per_cycle: int = 2) -> list[dict]:
        """Layer 2: design opportunities for strong hypotheses whose capabilities/analogies are in (refresh 3-daily)."""
        from .agents.opportunity import OpportunityDesigner, _ensure_table
        _ensure_table()
        rows = db.q("""SELECT h.id FROM hypotheses h WHERE h.status NOT IN ('superseded','stale','rejected')
                       AND h.processed_at IS NOT NULL AND h.countries != '{}'
                       AND NOT EXISTS (SELECT 1 FROM opportunities o WHERE o.hypothesis_id=h.id AND o.updated_at > ?)
                       ORDER BY (h.status='validated') DESC, h.score DESC LIMIT ?""", (time.time() - 3 * 86400, per_cycle))
        out = []
        for r in rows:
            if self.stopped():
                break
            _set("step", f"designing opportunity for hypothesis #{r['id']}")
            res = OpportunityDesigner().run(hypothesis_id=r["id"])
            out.append({"hypothesis": r["id"], **{k: res["stats"].get(k) for k in ("best_route", "score", "p_profitable")}})
        return out

    def govern(self, per_cycle: int = 2) -> list[dict]:
        """Layer 3: Governance Board for opportunities designed/updated since their last review."""
        from .agents.governance import GovernanceBoard, _chain_tables
        _chain_tables()
        rows = db.q("""SELECT o.id FROM opportunities o WHERE o.status NOT LIKE 'human:%' AND NOT EXISTS
                       (SELECT 1 FROM governance_reviews g WHERE g.opportunity_id=o.id AND g.at >= o.updated_at - 1)
                       ORDER BY o.opportunity_score DESC LIMIT ?""", (per_cycle,))
        out = []
        for r in rows:
            if self.stopped():
                break
            _set("step", f"governance review of opportunity #{r['id']}")
            res = GovernanceBoard().run(opportunity_id=r["id"])
            out.append({"opportunity": r["id"], "recommendation": res["stats"].get("recommendation")})
        return out

    def execute_plans(self, per_cycle: int = 1) -> dict:
        """Layer 4: plan execution for governed opportunities (outward actions stay gated) and evaluate live experiments."""
        from .agents import execution as X
        X.ensure_tables()
        rows = db.q("""SELECT g.opportunity_id id FROM governance_reviews g WHERE g.recommendation != 'reject'
                       AND g.id IN (SELECT MAX(id) FROM governance_reviews GROUP BY opportunity_id)
                       AND NOT EXISTS (SELECT 1 FROM execution_plans p WHERE p.opportunity_id=g.opportunity_id
                                       AND p.updated_at > ?) LIMIT ?""", (time.time() - 3 * 86400, per_cycle))
        planned = []
        for r in rows:
            if self.stopped():
                break
            _set("step", f"execution planning for opportunity #{r['id']}")
            planned.append(X.ExecutionCoordinator().run(opportunity_id=r["id"])["status"])
        evaluated = 0
        for e in db.q("SELECT id FROM experiments WHERE status IN ('designed','running','inconclusive')"):
            X.ExperimentAgent().evaluate(e["id"])
            evaluated += 1
        return {"planned": len(planned), "experiments_evaluated": evaluated}

    @staticmethod
    def backfill_translations(limit: int = 120) -> int:
        rows = db.q("SELECT id, lang, text FROM signals WHERE text_en IS NULL AND lang IS NOT NULL AND lang != 'en' "
                    "ORDER BY id DESC LIMIT ?", (limit,))
        by_lang: dict[str, list[dict]] = {}
        for r in rows:
            by_lang.setdefault(r["lang"], []).append(r)
        n = 0
        for lang, rs in by_lang.items():
            for r, en in zip(rs, translate.batch_to_english([x["text"][:300] for x in rs], lang)):
                if en:
                    db.update("signals", r["id"], {"text_en": en})
                    n += 1
        return n


_bg: dict = {}


def start_background(**kw) -> bool:
    if _bg.get("thread") and _bg["thread"].is_alive():
        return False
    d = Daemon(**kw)
    t = threading.Thread(target=d.run_forever, daemon=True, name="aduns-daemon")
    _bg.update(daemon=d, thread=t)
    t.start()
    return True


def stop_background() -> bool:
    d = _bg.get("daemon")
    if d:
        d.stop()
        return True
    return False


def coverage() -> dict:
    """Signals, hypotheses and sweep status per continent and country (recent window)."""
    cutoff = time.time() - config.MAX_AGE_DAYS * 86400
    sig = {r["scope_country"]: r for r in db.q(
        """SELECT scope_country, COUNT(*) n, COUNT(DISTINCT source) sources, MAX(COALESCE(published_ts, retrieved_at)) latest
           FROM signals WHERE COALESCE(published_ts, retrieved_at) >= ? AND scope_country IS NOT NULL
           GROUP BY scope_country""", (cutoff,))}
    sw = {r["country"]: r for r in db.q("SELECT * FROM sweeps")}
    hyp_c: dict[str, int] = {}
    for h in db.q("SELECT countries FROM hypotheses WHERE status != 'superseded'"):
        for c in db.loads(h["countries"], {}):
            hyp_c[c] = hyp_c.get(c, 0) + 1
    out = {}
    for cont, members in geo.by_continent().items():
        rows = []
        for iso in members:
            c = geo.country(iso)
            s, w = sig.get(iso, {}), sw.get(iso, {})
            rows.append({"iso3": iso, "name": c["name"], "signals": s.get("n", 0), "sources": s.get("sources", 0),
                         "latest_signal": s.get("latest"), "last_sweep": w.get("last_finished"), "sweeps": w.get("runs", 0),
                         "hypotheses": hyp_c.get(iso, 0), "sources_ok": db.loads(w.get("sources_ok"), []),
                         "sources_failed": db.loads(w.get("sources_failed"), [])})
        rows.sort(key=lambda r: -r["signals"])
        out[cont] = {"countries": len(members), "swept": sum(1 for r in rows if r["sweeps"]),
                     "signals": sum(r["signals"] for r in rows), "rows": rows}
    return out



# ------------------------------------------------------------------ leases (distributed workers)
def lease_countries(owner: str, per_continent: int = 1, ttl: int = 1800) -> list[str]:
    """Atomically lease the least-recently-swept, unleased countries — `per_continent` on every continent.

    Local daemons and remote workers share this, so any number of machines (on different IPs, each with its own
    rate-limit budget) can sweep the world together without duplicating work and with equal continent coverage."""
    now = time.time()
    picks: list[str] = []
    with db.tx() as conn:
        last = {r[0]: r[1] or 0 for r in conn.execute("SELECT country, last_finished FROM sweeps").fetchall()}
        busy = {r[0] for r in conn.execute("SELECT country FROM leases WHERE until > ? AND owner != ?", (now, owner))}
        for cont, members in geo.by_continent().items():
            free = [m for m in members if m not in busy]
            free.sort(key=lambda m: (last.get(m, 0), -len(geo.country(m)["cities"]), m))
            for iso in free[:per_continent]:
                conn.execute("INSERT OR REPLACE INTO leases (country, owner, until) VALUES (?,?,?)", (iso, owner, now + ttl))
                picks.append(iso)
    return picks


def release(owner: str, country: str) -> None:
    db.execute("DELETE FROM leases WHERE country=? AND owner=?", (country, owner))


def ingest_worker_report(worker_id: str, country: str, signals: list[dict], registry: list[dict], stats: dict,
                         address: str = "") -> dict:
    """Store a remote worker's sweep results centrally (dedup by content hash)."""
    cols = {r["name"] for r in db.q("PRAGMA table_info(signals)")} - {"id", "run_id"}
    stored = 0
    for s in signals:
        row = {k: v for k, v in s.items() if k in cols}
        if not row.get("content_hash") or not row.get("text"):
            continue
        row["extra"] = row.get("extra") if isinstance(row.get("extra"), str) else json.dumps(row.get("extra") or {})
        if db.insert("signals", row, ignore=True):
            stored += 1
    for r in registry:
        db.insert("source_registry", {"kind": r["kind"], "handle": r["handle"], "country": r.get("country"),
                                      "discovered_from": f"worker:{worker_id}:{r.get('discovered_from', '')}"[:200],
                                      "discovered_at": time.time()}, ignore=True)
    c = geo.country(country)
    with db.tx() as conn:
        conn.execute("""INSERT INTO sweeps (country, continent, last_started, last_finished, runs, signals_last, signals_total,
                        sources_ok, sources_failed) VALUES (?,?,?,?,1,?,?,?,?)
                        ON CONFLICT(country) DO UPDATE SET last_finished=excluded.last_finished, runs=runs+1,
                        signals_last=excluded.signals_last, signals_total=signals_total+excluded.signals_last,
                        sources_ok=excluded.sources_ok, sources_failed=excluded.sources_failed""",
                     (country, c["continent"] if c else None, time.time(), time.time(), stored, stored,
                      json.dumps(stats.get("sources_ok", [])), json.dumps(stats.get("sources_failed", []))))
        conn.execute("""INSERT INTO workers (id, last_seen, sweeps, signals, address) VALUES (?,?,1,?,?)
                        ON CONFLICT(id) DO UPDATE SET last_seen=excluded.last_seen, sweeps=sweeps+1,
                        signals=signals+excluded.signals, address=excluded.address""",
                     (worker_id, time.time(), stored, address))
    release(worker_id, country)
    db.audit(worker_id, "worker_report", "sweep", None, {"country": country, "stored": stored, "received": len(signals)})
    return {"stored": stored, "received": len(signals)}
