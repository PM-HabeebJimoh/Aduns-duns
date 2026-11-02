"""On-demand discovery pipeline (the 24/7 path is aduns.scheduler.Daemon).

Sense → Fuse → for top hypotheses: Capabilities, Cross-border analogies, Field missions.
`country` → local-language sweep of that country; no country → the focus is searched worldwide.
"""
from __future__ import annotations

import time

from . import db
from .agents import (CapabilityDiscoveryAgent, CrossBorderAnalogyAgent, NeedSensingAgent,
                     OfflineScoutCoordinator, SignalFusionAgent)


def run_discovery(focus: str = "", country: str = "", depth: int = 1, top_n: int = 5, sources: list[str] | None = None,
                  create_missions: bool = True, progress=None) -> dict:
    t0 = time.time()
    log = progress or (lambda msg: None)
    report: dict = {"focus": focus, "country": country}
    log(f"Need sensing: focus='{focus}' country='{country or 'worldwide'}'")
    report["sensing"] = NeedSensingAgent().run(focus=focus, country=country, depth=depth, sources=sources,
                                               include_global=not country and not focus)
    report["sensing"].pop("signal_ids", None)
    log("Signal fusion")
    fusion = SignalFusionAgent().run(query=focus, country=country)
    hyp_ids = fusion.get("hypothesis_ids", [])
    report["fusion"] = fusion["stats"]
    hyps = db.q(f"SELECT id, title, score, countries, domain FROM hypotheses WHERE id IN ({','.join('?' * len(hyp_ids))}) "
                "ORDER BY score DESC", hyp_ids) if hyp_ids else []
    top = hyps[:top_n]
    report["top_hypotheses"] = [{"id": h["id"], "title": h["title"], "score": h["score"]} for h in top]
    report["capabilities"], report["analogies"], report["missions"] = {}, {}, {}
    for h in top:
        log(f"Capability discovery for #{h['id']}")
        report["capabilities"][h["id"]] = CapabilityDiscoveryAgent().run(hypothesis_id=h["id"])["stats"]
        if db.loads(h["countries"], {}) or country:
            log(f"Cross-border analogies for #{h['id']}")
            report["analogies"][h["id"]] = CrossBorderAnalogyAgent().run(hypothesis_id=h["id"], country=country)["stats"]
            if create_missions:
                log(f"Field mission for #{h['id']}")
                report["missions"][h["id"]] = OfflineScoutCoordinator().run(hypothesis_id=h["id"], country=country).get("code")
    report["elapsed_s"] = round(time.time() - t0, 1)
    db.audit("orchestrator", "discovery_completed", detail={"focus": focus, "country": country,
                                                            "elapsed_s": report["elapsed_s"]})
    return report
