"""End-to-end test of the field-network API (temp DB, no network: missions built with max_locations=0)."""
import json
import os
import tempfile
import time

os.environ["ADUNS_DB"] = os.path.join(tempfile.mkdtemp(), "field.db")

from aduns import config, db  # noqa: E402

db.reset_connections()
config.DB_PATH = os.environ["ADUNS_DB"]

from fastapi.testclient import TestClient  # noqa: E402

from aduns.agents.offline_scout import OfflineScoutCoordinator  # noqa: E402
from aduns.api import app  # noqa: E402


def _mission() -> str:
    hid = db.insert("hypotheses", {"fingerprint": "t", "title": "test", "need_statement": "test", "domain": "cold_chain",
                                   "key_terms": json.dumps(["cold room"]), "countries": json.dumps({}),
                                   "need_types": json.dumps({"unmet": 1}), "gap_causes": json.dumps({}),
                                   "signal_count": 1, "source_count": 1, "layer_count": 1, "score": 0.1,
                                   "evidence_level": "claim", "tests": json.dumps([]), "created_at": time.time()})
    code = "MT-0001"
    db.insert("scout_missions", {"code": code, "hypothesis_id": hid, "title": "t", "country": None, "quota": 2,
                                 "reward_per_validated": 3.0, "status": "open", "created_at": time.time()})
    return code


def test_field_flow():
    c = TestClient(app)
    code = _mission()
    assert c.post("/api/scouts", json={"handle": "a", "consent": False}).status_code == 400
    assert c.post("/api/scouts", json={"handle": "a", "consent": True, "role": "trader"}).status_code == 200
    r = c.post("/api/observations", json={"mission_code": code, "scout_handle": "a", "consent_confirmed": True,
                                          "text": "Fish traders say nobody here sells cold rooms; we always lose fish by noon."})
    assert r.status_code == 200, r.text
    oid = r.json()["observation_id"]
    # SMS path: a second, independent scout corroborates
    xml = c.post("/webhooks/sms", data={"From": "whatsapp:+2340000", "Body": "JOIN B | fishmonger | Ghana | Tema"}).text
    assert "Welcome" in xml
    xml = c.post("/webhooks/sms", data={"From": "whatsapp:+2340000",
                                        "Body": f"OBS {code} nobody sells cold rooms here, fish spoil before noon every day"}).text
    assert "corroborated" in xml
    assert c.post(f"/api/observations/{oid}/review", json={"decision": "validated", "reviewer": "qa"}).json()["status"] == "validated"
    earned = {s["id"]: s["earned"] for s in c.get("/api/scouts").json()}
    assert max(earned.values()) == config.SCOUT_REWARD_SUBMITTED + 3.0
    assert c.get("/api/status").json()["counts"]["scout_observations"] == 2
    # STOP withdraws consent
    assert "withdrawn" in c.post("/webhooks/sms", data={"From": "+2340000", "Body": "STOP"}).text
    assert OfflineScoutCoordinator().handle_message("+2340000", f"OBS {code} more text here please").startswith("Sorry")
