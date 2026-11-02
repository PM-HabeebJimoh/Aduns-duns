"""Tests for the universal/global layer (offline logic; geography uses the live gazetteer)."""
import os
import tempfile
import time

os.environ.setdefault("ADUNS_DB", os.path.join(tempfile.mkdtemp(), "g.db"))

from aduns import lexicon  # noqa: E402


def test_lexicon_multilingual_detection():
    assert "scarcity" in lexicon.detect("Hakuna maji, uhaba mkubwa Nairobi", ["sw"])
    assert "scarcity" in lexicon.detect("pénurie de carburant à Dakar", ["fr"])
    assert "unaffordable" in lexicon.detect("los precios: muy caro todo", ["es"])
    assert "scarcity" in lexicon.detect("停电三天了", ["zh"])
    assert lexicon.detect("beautiful sunny day", ["en"]) == {}


def test_every_language_has_search_terms_or_fallback():
    for lang, spec in lexicon.L.items():
        assert "cues" in spec and "search" in spec


def test_recency_gate_and_country_gate():
    from aduns.agents.need_sensing import NeedSensingAgent, _ts
    a = NeedSensingAgent()
    a.run_id = None
    old = {"source": "googlenews", "layer": "visible", "external_id": "x1", "url": "u", "title": "shortage of fuel",
           "text": "shortage of fuel in town", "published_at": "2019-01-01T00:00:00Z", "extra": {}}
    new = dict(old, external_id="x2", published_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    ids = a.process([(old, "en"), (new, "en")], scope=None, focus="", min_need_score=0.3)
    assert len(ids) == 1 and a.stats.get("dropped_old") == 1
    assert _ts("2026-10-01") and _ts("10/29/2026")


def test_scheduler_picks_one_country_per_continent():
    from aduns import geo
    from aduns.scheduler import Daemon
    picks = Daemon().next_countries()
    conts = [geo.country(p)["continent"] for p in picks]
    assert sorted(conts) == sorted(set(conts)) and len(conts) == 6


def test_need_object_and_publisher_strip():
    from aduns import nlp
    assert nlp.need_object("Milk shortage") == "milk"
    assert nlp.need_object("Fuel supply crisis") == "fuel"
    assert nlp.strip_publisher("Milk shortage bites - The Star, Kenya") == "Milk shortage bites"


def test_fusion_merges_across_languages_via_translation():
    import json
    import time as _t
    from aduns import db
    from aduns.agents import SignalFusionAgent
    now = _t.time()
    texts = [("es", "escasez de insulina en farmacias", "insulin shortage in pharmacies", "ARG", "South America"),
             ("fr", "pénurie d'insuline dans les pharmacies", "insulin shortage in pharmacies", "SEN", "Africa"),
             ("en", "Insulin shortage hits pharmacies again", "Insulin shortage hits pharmacies again", "PHL", "Asia")]
    for i, (lang, t, en, c, cont) in enumerate(texts):
        db.insert("signals", {"source": ["bluesky", "googlenews", "youtube"][i], "layer": "scattered", "external_id": f"t{i}",
                              "url": None, "title": t, "text": t, "text_en": en, "lang": lang, "retrieved_at": now,
                              "published_ts": now, "content_hash": f"fuse-test-{i}", "domain": "medicines",
                              "need_types": json.dumps(["scarcity"]), "gap_causes": "[]", "intensity": 0.5,
                              "need_score": 0.8, "countries": json.dumps([c]), "entities": json.dumps(["insulin"]),
                              "engagement": 0.1, "scope_country": c, "continent": cont})
    r = SignalFusionAgent().run(domain="medicines", window_days=5)
    hs = db.q("SELECT * FROM hypotheses WHERE id IN (%s)" % ",".join(map(str, r["hypothesis_ids"])))
    big = max(hs, key=lambda h: h["signal_count"])
    assert big["signal_count"] == 3 and big["scope"] == "global"


def test_review_learning_and_rejected_stays_rejected():
    import json
    import time as _t
    from aduns import db, learning
    now = _t.time()
    hid = db.insert("hypotheses", {"fingerprint": f"rv{now}", "title": "t", "need_statement": "t", "status": "open",
                                   "signal_count": 1, "source_count": 1, "layer_count": 1, "score": 0.5,
                                   "evidence_level": "claim", "created_at": now})
    sid = db.insert("signals", {"source": "youtube", "layer": "scattered", "text": "x shortage", "retrieved_at": now,
                                "content_hash": f"rv-{now}", "need_types": json.dumps(["scarcity"]), "lang": "es",
                                "countries": "[]", "entities": "[]"})
    db.execute("INSERT INTO hypothesis_signals (hypothesis_id, signal_id, similarity) VALUES (?,?,1)", (hid, sid))
    out = learning.review(hid, "noise", "tester", "not a need")
    assert out["status"] == "rejected"
    w = {(r["kind"], r["key"]): r["weight"] for r in db.q("SELECT * FROM learned_weights")}
    assert w[("source", "youtube")] < 0.5
    assert learning.reliability([{"source": "youtube", "lang": "es"}]) < 0.5


def test_lease_countries_are_exclusive_and_cover_all_continents():
    from aduns import geo
    from aduns.scheduler import lease_countries, release
    a = lease_countries("worker-A")
    b = lease_countries("worker-B")
    assert not set(a) & set(b)
    assert len({geo.country(x)["continent"] for x in a}) == 6
    for x in a:
        release("worker-A", x)
    for x in b:
        release("worker-B", x)
