"""Unit tests for the deterministic logic (no network).

These use short literal sentences purely to exercise the code paths; they run against a throw-away
database and never touch the production evidence store.
"""
import os
import tempfile

import numpy as np
import pytest

os.environ["ADUNS_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

from aduns import db, nlp, taxonomy  # noqa: E402
from aduns.agents.signal_fusion import SignalFusionAgent  # noqa: E402


def test_detect_need_types():
    d = nlp.detect_need("We always lose half the harvest because nobody here sells cold rooms and it's too expensive to import")
    assert {"unmet", "normalized", "unaffordable"} <= set(d["need_types"])
    assert d["need_score"] > 0.9
    assert "cold rooms" in " ".join(d["objects"])
    assert "affordability" in d["gap_causes"]


def test_detect_non_need():
    d = nlp.detect_need("The weather is lovely and the match was great.")
    assert d["need_types"] == [] and d["need_score"] == 0


def test_normalized_only_abroad():
    d = nlp.detect_need("Dialysis is only available abroad, so families have to travel to India.")
    assert "normalized" in d["need_types"]


def test_domain_classification():
    assert taxonomy.classify_domain("our freezer and cold room keep failing, spoilage everywhere")[0] == "cold_chain"
    assert taxonomy.classify_domain("no bank will give us a loan without collateral")[0] == "finance"


def test_tfidf_and_clustering():
    docs = ["cannot find spare parts for tractor", "no spare parts for tractors anywhere",
            "insulin shortage at the pharmacy", "pharmacy has no insulin again"]
    tf = nlp.TfIdf(docs)
    M = tf.matrix()
    clusters = nlp.agglomerative(nlp.cosine_sim_matrix(M), threshold=0.15)
    groups = sorted(sorted(c) for c in clusters)
    assert [0, 1] in groups and [2, 3] in groups


def test_score_bounds():
    members = [{"source": "reddit", "layer": "scattered", "published_at": "2026-01-01T00:00:00Z", "countries": '["NGA"]',
                "need_types": '["unmet"]', "intensity": 0.5, "engagement": 0.2},
               {"source": "gdelt", "layer": "visible", "published_at": "2026-02-01T00:00:00Z", "countries": '["NGA"]',
                "need_types": '["normalized"]', "intensity": 0.7, "engagement": 0.0}]
    s, parts = SignalFusionAgent.score(members)
    assert 0 < s < 1
    assert parts["geo_focus"] == 1.0 and parts["source_diversity"] == 0.5


def test_scout_consent_required():
    from aduns.agents.offline_scout import OfflineScoutCoordinator
    with pytest.raises(ValueError):
        OfflineScoutCoordinator.register_scout("+10000000000", consent=False)
    sid = OfflineScoutCoordinator.register_scout("+10000000001", consent=True, role="trader")
    assert db.q1("SELECT consent_at FROM scouts WHERE id=?", (sid,))["consent_at"]
    with pytest.raises(PermissionError):
        OfflineScoutCoordinator().submit_observation(None, "+10000000001", "nobody sells cold rooms here", consent_confirmed=False)


def test_sms_help_and_stop():
    from aduns.agents.offline_scout import OfflineScoutCoordinator
    c = OfflineScoutCoordinator()
    assert "JOIN" in c.handle_message("+10000000002", "hello")
    assert "Sorry" in c.handle_message("+10000000002", "OBS M1-XXXX nothing")  # not registered
