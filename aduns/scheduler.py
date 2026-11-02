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
                 fusion_window_days: int = 30, mission_min_score: float = 0.3):
        self.parallel = parallel_countries
        self.downstream_per_cycle = downstream_per_cycle
        self.global_every_s = global_every_s
        self.fusion_window_days = fusion_window_days
        self.mission_min_score = mission_min_score
        self._stop = threading.Event()
        self.cycle_no = 0

    # ---------------------------------------------------------------- control
    def stop(self) -> None:
        self._stop.set()

    def stopped(self) -> bool:
        return self._stop.is_set() or (config.ROOT / "data" / "STOP").exists()

    def run_forever(self, max_cycles: int | None = None) -> None:
        _set("status", "running")
        _set("started_at", time.time())
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
        last = {r["country"]: r["last_finished"] or 0 for r in db.q("SELECT country, last_finished FROM sweeps")}
        picks = []
        for cont, members in geo.by_continent().items():
            if not members:
                continue
            # least recently swept first; among never-swept, the most urbanised/populous first
            picks.append(min(members, key=lambda m: (last.get(m, 0), -len(geo.country(m)["cities"]), m)))
        return picks

    def cycle(self) -> dict:
        self.cycle_no += 1
        report: dict = {"cycle": self.cycle_no, "started": time.time()}
        _set("heartbeat", time.time())
        _set("cycle", self.cycle_no)

        countries = self.next_countries()
        report["countries"] = countries
        _set("step", f"sensing {', '.join(countries)}")

        def sweep(iso):
            if self.stopped():
                return iso, {"status": "skipped"}
            r = NeedSensingAgent().run(country=iso)
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
        report["translated_backfill"] = self.backfill_translations()
        report["finished"] = time.time()
        _set("last_cycle", report)
        _set("heartbeat", time.time())
        return report

    def downstream(self) -> list[dict]:
        """Capabilities + analogies + field mission for the strongest hypotheses not processed in 24h."""
        rows = db.q("""SELECT id, score, countries, scope FROM hypotheses
                       WHERE status NOT IN ('superseded', 'stale') AND signal_count >= 2 AND countries != '{}'
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
