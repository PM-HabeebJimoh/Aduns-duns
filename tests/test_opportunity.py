"""Unit tests for opportunity design logic (no network)."""
import os
import tempfile

os.environ.setdefault("ADUNS_DB", os.path.join(tempfile.mkdtemp(), "o.db"))

from aduns.sources import market as MK  # noqa: E402


def test_bulk_classification():
    assert MK.is_bulk("0401") and MK.is_bulk("2710") and MK.is_bulk("3102")
    assert not MK.is_bulk("3004") and not MK.is_bulk("841830") and not MK.is_bulk(None)


def test_clean_price_mentions_outliers_and_units():
    ms = [{"usd": 0.5, "context": "milk Sh65 per litre"}, {"usd": 0.55, "context": "milk at Sh70 a litre"},
          {"usd": 0.6, "context": "milk Sh 78 per litre"}, {"usd": 900.0, "context": "dairy firm raises Sh 117,000"}]
    out = MK.clean_price_mentions(ms, bulk=True)
    assert all(m["usd"] < 1 for m in out) and len(out) == 3


def test_hs_curated_mapping():
    # curated mapping does not need the HS table to resolve common goods
    assert "2710" in MK.COMMON_HS["diesel"] and "0401" in MK.COMMON_HS["milk"]


def test_economics_monte_carlo_with_real_inputs(monkeypatch):
    from aduns.agents import opportunity as O
    monkeypatch.setattr(O.MK, "lending_rate", lambda iso3: (12.0, 2025))
    ctx = {"iso3": "KEN", "hyp": {"id": 1, "score": 0.5}}
    market = {"hs": {"hs": "0401"}, "imports": {"value_usd": 24e6, "year": 2025}}
    loc = {"local_price_evidence": {"usd_summary": {"n": 5, "min": 0.5, "median": 0.6, "max": 0.7, "p25": 0.55,
                                                    "p75": 0.65}}}
    routes = {"inputs": {"unit_cost_usd": 0.3, "unit_cost_source": "Comtrade"},
              "routes": [{"route": "local_distribution_partnership", "label": "x", "feasible": True},
                         {"route": "software_layer", "label": "y", "feasible": True}]}
    r = O.EconomicsAgent().run(ctx=ctx, market=market, loc=loc, routes=routes, n=2000)
    assert r["econ_status"] == "modelled"
    lp = r["routes"][0]
    n_assume = sum(1 for d in lp["top_drivers"][:2] if d["kind"] == "assumption")
    assert r["evidence_confidence"] == round(1.0 * (1 - 0.25 * n_assume), 3)
    assert 0 < lp["gross_margin"]["p50"] < 1 and 0 <= lp["p_profitable"] <= 1
    assert lp["net_margin"]["p10"] <= lp["net_margin"]["p50"] <= lp["net_margin"]["p90"]
    assert all(d["kind"] in ("real", "official", "official_average", "measured", "assumption") for d in lp["top_drivers"])


def test_economics_refuses_without_price_or_cost():
    from aduns.agents import opportunity as O
    r = O.EconomicsAgent().run(ctx={"iso3": "KEN", "hyp": {"id": 1}}, market={}, loc={"local_price_evidence": {"usd_summary": None}},
                               routes={"inputs": {"unit_cost_usd": None}, "routes": []})
    assert r["econ_status"] == "insufficient_data"
