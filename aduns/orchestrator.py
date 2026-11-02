"""Discovery pipeline: Sense → Detect → Explain → Match (capabilities + analogies) → Field missions.

Steps 1–4 of the engine's full loop. Later layers (delivery-route generation, economics, red team,
execution) consume the hypotheses, capabilities and analogies produced here.
"""
from __future__ import annotations

import time

from . import db
from .agents import (CapabilityDiscoveryAgent, CrossBorderAnalogyAgent, NeedSensingAgent,
                     OfflineScoutCoordinator, SignalFusionAgent)


def run_discovery(focus: str, country: str = "", depth: int = 1, top_n: int = 5, sources: list[str] | None = None,
                  create_missions: bool = True, progress=None) -> dict:
    t0 = time.time()
    log = progress or (lambda msg: None)
    report: dict = {"focus": focus, "country": country}

    log(f"Need sensing: '{focus}' {country}")
    report["sensing"] = NeedSensingAgent().run(focus=focus, country=country, depth=depth, sources=sources)

    log("Signal fusion")
    report["fusion"] = SignalFusionAgent().run(query=focus)
    hyp_ids = report["fusion"].get("hypothesis_ids", [])
    hyps = db.q(f"SELECT id, title, score, countries, domain FROM hypotheses WHERE id IN ({','.join('?' * len(hyp_ids))}) "
                "ORDER BY score DESC", hyp_ids) if hyp_ids else []
    top = hyps[:top_n]
    report["top_hypotheses"] = [{"id": h["id"], "title": h["title"], "score": h["score"]} for h in top]

    report["capabilities"], report["analogies"], report["missions"] = {}, {}, {}
    for h in top:
        log(f"Capability discovery for #{h['id']}")
        report["capabilities"][h["id"]] = CapabilityDiscoveryAgent().run(hypothesis_id=h["id"])
        has_geo = bool(db.loads(h["countries"], {})) or bool(country)
        if has_geo and h["domain"]:
            log(f"Cross-border analogies for #{h['id']}")
            report["analogies"][h["id"]] = CrossBorderAnalogyAgent().run(hypothesis_id=h["id"], country=country)
            if create_missions:
                log(f"Field mission for #{h['id']}")
                report["missions"][h["id"]] = OfflineScoutCoordinator().run(hypothesis_id=h["id"], country=country)
    report["elapsed_s"] = round(time.time() - t0, 1)
    db.audit("orchestrator", "discovery_completed", detail={k: v for k, v in report.items() if k in ("focus", "country", "elapsed_s")})
    return report
