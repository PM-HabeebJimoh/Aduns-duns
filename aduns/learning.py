"""Learning from human review.

Reviewers confirm or reject hypotheses (verdicts: confirmed | rejected | duplicate | noise). From these
decisions the engine learns, with Bayesian (Beta(1,1)) smoothing, how reliable each *source*, *need type*
and *language* is at producing real needs. Signal Fusion multiplies each hypothesis score by the learned
reliability of its evidence, so noisy feeds sink and reliable ones rise — automatically, worldwide.

Rejected hypotheses keep their status: if the same evidence re-clusters it is recognised (stable identity)
and stays rejected instead of resurfacing.
"""
from __future__ import annotations

import time
from collections import defaultdict

from . import db

VERDICTS = {"confirmed": "validated", "rejected": "rejected", "duplicate": "rejected", "noise": "rejected"}


def review(hypothesis_id: int, verdict: str, reviewer: str, reason: str = "") -> dict:
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {sorted(VERDICTS)}")
    if not db.q1("SELECT id FROM hypotheses WHERE id=?", (hypothesis_id,)):
        raise ValueError("hypothesis not found")
    db.insert("hypothesis_reviews", {"hypothesis_id": hypothesis_id, "reviewer": reviewer, "verdict": verdict,
                                     "reason": reason, "at": time.time()})
    db.update("hypotheses", hypothesis_id, {"status": VERDICTS[verdict], "updated_at": time.time()})
    db.audit(reviewer, f"hypothesis_{verdict}", "hypothesis", hypothesis_id, {"reason": reason})
    return {"status": VERDICTS[verdict], "weights": recompute()}


def recompute() -> int:
    """Rebuild learned weights from all reviews (latest verdict per hypothesis wins)."""
    latest = {}
    for r in db.q("SELECT hypothesis_id, verdict FROM hypothesis_reviews ORDER BY at"):
        latest[r["hypothesis_id"]] = r["verdict"]
    counts: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for hid, verdict in latest.items():
        good = verdict == "confirmed"
        for s in db.q("""SELECT s.source, s.lang, s.need_types FROM signals s JOIN hypothesis_signals hs
                         ON hs.signal_id=s.id WHERE hs.hypothesis_id=?""", (hid,)):
            keys = [("source", s["source"].split(":")[0]), ("lang", s["lang"] or "en")]
            keys += [("need_type", t) for t in db.loads(s["need_types"], [])[:2]]
            for k in keys:
                counts[k][0 if good else 1] += 1
    now = time.time()
    with db.tx() as c:
        c.execute("DELETE FROM learned_weights")
        for (kind, key), (conf, rej) in counts.items():
            c.execute("INSERT INTO learned_weights (kind, key, confirmed, rejected, weight, at) VALUES (?,?,?,?,?,?)",
                      (kind, key, conf, rej, (conf + 1) / (conf + rej + 2), now))
    _cache.clear()
    return len(counts)


_cache: dict = {}


def weights() -> dict[tuple[str, str], float]:
    if not _cache or time.time() - _cache.get("_at", 0) > 300:
        _cache.clear()
        _cache.update({(r["kind"], r["key"]): r["weight"] for r in db.q("SELECT kind, key, weight FROM learned_weights")})
        _cache["_at"] = time.time()
    return _cache


def reliability(members: list[dict]) -> float:
    """Mean learned reliability of a hypothesis's evidence (0.5 = no information yet)."""
    w = weights()
    vals = []
    for m in members:
        parts = [w.get(("source", (m.get("source") or "").split(":")[0]), 0.5), w.get(("lang", m.get("lang") or "en"), 0.5)]
        vals.append(sum(parts) / len(parts))
    return sum(vals) / len(vals) if vals else 0.5
