"""Execution layer tests on a throw-away DB (approvals here are test fixtures, never in the real evidence store)."""
import json
import os
import tempfile
import time

os.environ.setdefault("ADUNS_DB", os.path.join(tempfile.mkdtemp(), "x.db"))

import pytest  # noqa: E402

from aduns import db  # noqa: E402
from aduns.agents import execution as X  # noqa: E402
from aduns.agents import governance as G  # noqa: E402
from aduns.agents.opportunity import _ensure_table  # noqa: E402


def _opportunity():
    _ensure_table()
    G._chain_tables()
    X.ensure_tables()
    hid = db.insert("hypotheses", {"fingerprint": f"x{time.time()}", "title": "Rice — scarcity", "need_statement": "t",
                                   "status": "open", "signal_count": 3, "source_count": 2, "layer_count": 2, "score": 0.6,
                                   "evidence_level": "corroborated", "created_at": time.time(), "key_terms": '["rice"]',
                                   "countries": '{"JPN": 3}'})
    oid = db.insert("opportunities", {"hypothesis_id": hid, "country": "JPN", "object": "rice", "market": "{}",
                                      "localization": "{}", "composition": "{}", "defensibility": "{}", "routes": "{}",
                                      "economics": json.dumps({"routes": [{"gross_margin": {"p10": 0.1, "p50": 0.2, "p90": 0.3},
                                                                           "net_margin": {"p10": -0.1, "p50": 0.05, "p90": 0.2}}]}),
                                      "best_route": "import_and_resell", "opportunity_score": 0.5, "status": "designed",
                                      "created_at": time.time(), "updated_at": time.time()})
    return hid, oid


def test_statistics():
    assert X.beta_prob_above(30, 10, 0.3) > 0.99 and X.beta_prob_above(2, 28, 0.3) < 0.01
    assert X.sample_size_for_proportion(0.3, 0.5) >= 10


def test_gates_block_outward_actions_without_human_approval():
    hid, oid = _opportunity()
    with pytest.raises(PermissionError):
        X.record_finance(oid, "Ada", "revenue", 100, "USD", reference="INV-1")
    pid = db.insert("partners", {"opportunity_id": oid, "name": "Acme Rice", "stage": "identified", "updated_at": time.time()})
    with pytest.raises(PermissionError):
        X.set_partner_stage(pid, "contacted", "Ada")
    db.insert("landing_pages", {"slug": "rice-jpn-t", "opportunity_id": oid, "content": json.dumps({"en": {}}),
                                "status": "draft", "created_at": time.time()})
    with pytest.raises(PermissionError):
        X.publish_page("rice-jpn-t", "Ada")


def test_measured_tariff_and_finance_after_approval(monkeypatch):
    hid, oid = _opportunity()
    db.insert("governance_reviews", {"opportunity_id": oid, "at": time.time(), "recommendation": "conditional_pilot",
                                     "conditions": "[]", "red_team": "{}", "legal": "{}", "verification": "{}", "impact": "{}"})
    G.approve(oid, "Test Approver", "approved_with_conditions", "test fixture")
    monkeypatch.setattr(X.MK, "fx_usd", lambda: {"USD": 1.0, "JPY": 150.0})
    eid = db.insert("experiments", {"opportunity_id": oid, "kind": "tariff_verification", "title": "t", "metric": "rate",
                                    "threshold": None, "direction": "below", "min_n": 1, "validates": "import_duty",
                                    "status": "designed", "created_at": time.time(), "updated_at": time.time()})
    with pytest.raises(ValueError):
        X.record_event(eid, "Ada", "rate", 25.0)            # evidence required
    r = X.record_event(eid, "Ada", "rate", 25.0, evidence_url="https://example.org/tariff")
    assert r["evaluation"]["status"] == "passed"
    m = db.q1("SELECT * FROM measured_inputs WHERE opportunity_id=? AND key='import_duty'", (oid,))
    assert abs(m["low"] - 0.25) < 1e-9
    X.record_finance(oid, "Ada", "revenue", 15000, "JPY", units=10, reference="INV-1")
    X.record_finance(oid, "Ada", "cogs", 9000, "JPY", reference="PO-1")
    a = X.FinanceAgent.actuals(oid)
    assert abs(a["gross_margin"] - 0.4) < 1e-9 and a["revenue_usd"] == 100.0
    assert G.verify_chain()["intact"]


def test_signup_requires_published_page_and_consent():
    hid, oid = _opportunity()
    db.insert("landing_pages", {"slug": "s1", "opportunity_id": oid, "content": "{}", "status": "draft",
                                "created_at": time.time()})
    with pytest.raises(ValueError):
        X.customer_signup("s1", "+100000", "web", consent=True)
    db.execute("UPDATE landing_pages SET status='published' WHERE slug='s1'")
    with pytest.raises(PermissionError):
        X.customer_signup("s1", "+100000", "web", consent=False)
    assert X.customer_signup("s1", "+100000", "web", consent=True)["stage"] == "waitlist"
