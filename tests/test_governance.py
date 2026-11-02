"""Governance logic tests (temp DB, no network)."""
import os
import tempfile

os.environ.setdefault("ADUNS_DB", os.path.join(tempfile.mkdtemp(), "g2.db"))

from aduns import db  # noqa: E402
from aduns.agents import governance as G  # noqa: E402
from aduns.sources import compliance as CP  # noqa: E402


def test_ledger_chain_is_tamper_evident():
    for i in range(3):
        G.ledger_append("tester", "act", "x", i, {"i": i})
    assert G.verify_chain()["intact"]
    row = db.q1("SELECT id FROM ledger_chain ORDER BY id LIMIT 1 OFFSET 1")
    db.execute("UPDATE ledger_chain SET payload_hash='tampered' WHERE id=?", (row["id"],))
    v = G.verify_chain()
    assert not v["intact"] and v["broken_at"] == row["id"]
    db.execute("DELETE FROM ledger_chain")


def test_screening_rejects_generic_names():
    CP._ensure()
    with db.tx() as c:
        c.execute("DELETE FROM screening_entities")
        c.execute("INSERT INTO screening_entities VALUES ('1','OOO GAS','ooo gas','[]','SDN','[]','RU','u')")
        c.execute("INSERT INTO screening_entities VALUES ('2','BANK MELLI IRAN','bank melli iran','[]','SDN','[]','IR','u')")
    CP._index.clear()
    assert CP.screen("GAS") == [] and CP.screen("E.S. Gas and Gas") == []
    assert CP.screen("Bank Melli Iran")[0]["matched"] == "BANK MELLI IRAN"


def test_sanctions_levels_and_recall_channels():
    assert CP.country_sanctions("CUB")["level"] == "comprehensive"
    assert CP.country_sanctions("RUS")["level"] == "sectoral"
    assert CP.country_sanctions("COD")["level"].startswith("list-based")
    assert CP.country_sanctions("KEN") is None
    assert CP.recall_channels("0401") == ["fda:food"] and CP.recall_channels("2710") == []


def test_approval_requires_review_and_name():
    G._chain_tables()
    try:
        G.approve(999, "Ada", "approved")
        assert False, "should require a governance review"
    except ValueError:
        pass


def test_stress_test_is_more_pessimistic():
    econ = {"inputs": {"price_usd": {"range": [1.0, 1.4]}, "unit_cost_usd": {"range": [0.4, 0.6]},
                       "freight_insurance": {"range": [0.08, 0.2]}, "import_duty": {"range": [0.0, 0.35]},
                       "local_logistics": {"range": [0.05, 0.12]}}}
    st = G.RedTeamAgent._stress(econ, "import_and_resell", 2000, 1)
    assert -1 <= st["net_margin_p50"] < 0.5 and 0 <= st["p_profitable"] <= 1
