"""Payment webhook tests (temp DB; payloads are test fixtures)."""
import hashlib
import hmac
import json
import os
import tempfile
import time

os.environ.setdefault("ADUNS_DB", os.path.join(tempfile.mkdtemp(), "p.db"))

import pytest  # noqa: E402

from aduns import db, payments  # noqa: E402
from aduns.agents import execution as X  # noqa: E402
from aduns.agents import governance as G  # noqa: E402
from aduns.agents.opportunity import _ensure_table  # noqa: E402


def _opp(approve: bool) -> int:
    _ensure_table(); G._chain_tables(); X.ensure_tables()
    _opp.n = getattr(_opp, "n", 0) + 1
    oid = db.insert("opportunities", {"hypothesis_id": 10_000 + _opp.n, "country": "NGA", "object": "x", "market": "{}", "localization": "{}",
                                      "composition": "{}", "defensibility": "{}", "routes": "{}", "economics": "{}",
                                      "status": "designed", "created_at": time.time(), "updated_at": time.time()})
    if approve:
        db.insert("governance_reviews", {"opportunity_id": oid, "at": time.time(), "recommendation": "conditional_pilot",
                                         "conditions": "[]", "red_team": "{}", "legal": "{}", "verification": "{}", "impact": "{}"})
        G.approve(oid, "Test Approver", "approved", "")
    return oid


def _paystack(oid, monkeypatch, txid=1):
    monkeypatch.setenv("ADUNS_PAYSTACK_SECRET", "sk_test")
    monkeypatch.setattr(payments.MK, "fx_usd", lambda: {"NGN": 1500.0, "USD": 1.0, "KES": 130.0, "JPY": 150.0})
    body = json.dumps({"event": "charge.success", "data": {"id": txid, "reference": f"AD{oid}-r{txid}", "amount": 150000,
                                                           "currency": "NGN", "customer": {"email": "buyer@example.org"}}}).encode()
    sig = hmac.new(b"sk_test", body, hashlib.sha512).hexdigest()
    return body, {"x-paystack-signature": sig}


def test_paystack_signature_gate_and_dedupe(monkeypatch):
    oid = _opp(approve=False)
    body, h = _paystack(oid, monkeypatch)
    with pytest.raises(payments.PaymentError) as e:
        payments.handle("paystack", body, {"x-paystack-signature": "bad"}, {})
    assert e.value.status == 401
    with pytest.raises(payments.PaymentError) as e:
        payments.handle("paystack", body, h, {})
    assert e.value.status == 409                              # not approved → not recorded
    oid2 = _opp(approve=True)
    body, h = _paystack(oid2, monkeypatch, txid=7)
    r = payments.handle("paystack", body, h, {})
    assert r["opportunity_id"] == oid2
    assert payments.handle("paystack", body, h, {})["duplicate"]
    a = X.FinanceAgent.actuals(oid2)
    assert a["revenue_usd"] == 1.0 and a["customers"] == 1


def test_stripe_signature_and_zero_decimal(monkeypatch):
    oid = _opp(approve=True)
    monkeypatch.setenv("ADUNS_STRIPE_WHSEC", "whsec_test")
    monkeypatch.setattr(payments.MK, "fx_usd", lambda: {"USD": 1.0, "JPY": 150.0})
    body = json.dumps({"type": "checkout.session.completed", "data": {"object": {
        "id": "cs_1", "payment_status": "paid", "amount_total": 3000, "currency": "jpy", "client_reference_id": f"AD{oid}"}}}).encode()
    t = str(int(time.time()))
    v1 = hmac.new(b"whsec_test", f"{t}.".encode() + body, hashlib.sha256).hexdigest()
    payments.handle("stripe", body, {"Stripe-Signature": f"t={t},v1={v1}"}, {})
    assert X.FinanceAgent.actuals(oid)["revenue_usd"] == 20.0      # ¥3000 (zero-decimal) / 150
    with pytest.raises(payments.PaymentError):
        payments.handle("stripe", body, {"Stripe-Signature": f"t={int(t) - 1000},v1={v1}"}, {})


def test_mpesa_token_and_reference(monkeypatch):
    oid = _opp(approve=True)
    monkeypatch.setenv("ADUNS_MPESA_TOKEN", "tok")
    monkeypatch.setattr(payments.MK, "fx_usd", lambda: {"KES": 130.0, "USD": 1.0})
    body = json.dumps({"TransID": "QK123", "TransAmount": "1300", "BillRefNumber": f"AD{oid}", "MSISDN": "2547000"}).encode()
    with pytest.raises(payments.PaymentError):
        payments.handle("mpesa", body, {}, {"token": "wrong"})
    payments.handle("mpesa", body, {}, {"token": "tok"})
    assert X.FinanceAgent.actuals(oid)["revenue_usd"] == 10.0
    assert G.verify_chain()["intact"]
