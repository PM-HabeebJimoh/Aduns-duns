"""Payment-provider webhooks → verified Finance entries (no human typing, no synthetic money).

Supported (all free to integrate; you supply your own account's secret):
  Paystack     header x-paystack-signature = HMAC-SHA512(body, ADUNS_PAYSTACK_SECRET)          event charge.success
  Flutterwave  header verif-hash == ADUNS_FLW_HASH                                           event charge.completed
  Stripe       header Stripe-Signature t=…,v1=HMAC-SHA256(f"{t}.{body}", ADUNS_STRIPE_WHSEC)  checkout.session.completed /
               payment_intent.succeeded (5-minute replay tolerance)
  M-Pesa       Daraja C2B confirmation; URL must carry ?token=ADUNS_MPESA_TOKEN (Daraja sends no signature)

Each payment must reference the opportunity: reference / client_reference_id / metadata.opportunity_id /
BillRefNumber of the form "AD<opportunity id>" or "AD<id>-anything". Payments are recorded only for opportunities a
human has approved; duplicates (same provider transaction id) are ignored; every entry goes into the audit ledger.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time

from . import db
from .agents import execution as X
from .agents.governance import ledger_append
from .sources import market as MK

ZERO_DECIMAL = {"BIF", "CLP", "DJF", "GNF", "JPY", "KMF", "KRW", "MGA", "PYG", "RWF", "UGX", "VND", "VUV", "XAF", "XOF", "XPF"}
_REF = re.compile(r"\bAD(\d+)(?:-[\w-]+)?\b", re.I)


class PaymentError(Exception):
    def __init__(self, status: int, msg: str):
        super().__init__(msg)
        self.status = status


def _opp_from(*refs) -> int | None:
    for r in refs:
        if r is None:
            continue
        if isinstance(r, int) or (isinstance(r, str) and r.isdigit()):
            return int(r)
        m = _REF.search(str(r))
        if m:
            return int(m.group(1))
    return None


def verify(provider: str, body: bytes, headers: dict, query: dict) -> None:
    h = {k.lower(): v for k, v in headers.items()}
    if provider == "paystack":
        sec = os.environ.get("ADUNS_PAYSTACK_SECRET")
        if not sec:
            raise PaymentError(503, "ADUNS_PAYSTACK_SECRET not configured")
        sig = hmac.new(sec.encode(), body, hashlib.sha512).hexdigest()
        if not hmac.compare_digest(sig, h.get("x-paystack-signature", "")):
            raise PaymentError(401, "bad signature")
    elif provider == "flutterwave":
        sec = os.environ.get("ADUNS_FLW_HASH")
        if not sec:
            raise PaymentError(503, "ADUNS_FLW_HASH not configured")
        if not hmac.compare_digest(sec, h.get("verif-hash", "")):
            raise PaymentError(401, "bad signature")
    elif provider == "stripe":
        sec = os.environ.get("ADUNS_STRIPE_WHSEC")
        if not sec:
            raise PaymentError(503, "ADUNS_STRIPE_WHSEC not configured")
        parts = dict(p.split("=", 1) for p in h.get("stripe-signature", "").split(",") if "=" in p)
        t = parts.get("t", "")
        exp = hmac.new(sec.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
        if not t.isdigit() or abs(time.time() - int(t)) > 300 or not hmac.compare_digest(exp, parts.get("v1", "")):
            raise PaymentError(401, "bad signature or stale timestamp")
    elif provider == "mpesa":
        tok = os.environ.get("ADUNS_MPESA_TOKEN")
        if not tok:
            raise PaymentError(503, "ADUNS_MPESA_TOKEN not configured")
        if not hmac.compare_digest(tok, (query.get("token") or "")):
            raise PaymentError(401, "bad token")
    else:
        raise PaymentError(404, "unknown provider")


def parse(provider: str, payload: dict) -> dict | None:
    """Normalise a successful-payment event to {txn, opportunity_id, amount, currency, customer}. None = ignore."""
    if provider == "paystack":
        if payload.get("event") != "charge.success":
            return None
        d = payload.get("data", {})
        cur = (d.get("currency") or "NGN").upper()
        return {"txn": f"paystack:{d.get('id') or d.get('reference')}", "currency": cur,
                "amount": (d.get("amount") or 0) / (1 if cur in ZERO_DECIMAL else 100),
                "opportunity_id": _opp_from((d.get("metadata") or {}).get("opportunity_id"), d.get("reference")),
                "customer": (d.get("customer") or {}).get("email") or (d.get("customer") or {}).get("phone")}
    if provider == "flutterwave":
        if payload.get("event") != "charge.completed" or (payload.get("data") or {}).get("status") != "successful":
            return None
        d = payload["data"]
        return {"txn": f"flutterwave:{d.get('id')}", "currency": (d.get("currency") or "NGN").upper(),
                "amount": float(d.get("amount") or 0),
                "opportunity_id": _opp_from((d.get("meta") or {}).get("opportunity_id"), d.get("tx_ref")),
                "customer": (d.get("customer") or {}).get("email") or (d.get("customer") or {}).get("phone_number")}
    if provider == "stripe":
        typ = payload.get("type")
        o = (payload.get("data") or {}).get("object") or {}
        if typ == "checkout.session.completed" and o.get("payment_status") == "paid":
            amt, cur = o.get("amount_total"), o.get("currency")
        elif typ == "payment_intent.succeeded":
            amt, cur = o.get("amount_received") or o.get("amount"), o.get("currency")
        else:
            return None
        cur = (cur or "usd").upper()
        return {"txn": f"stripe:{o.get('id')}", "currency": cur, "amount": (amt or 0) / (1 if cur in ZERO_DECIMAL else 100),
                "opportunity_id": _opp_from((o.get("metadata") or {}).get("opportunity_id"), o.get("client_reference_id")),
                "customer": (o.get("customer_details") or {}).get("email")}
    if provider == "mpesa":
        if not payload.get("TransID"):
            return None
        return {"txn": f"mpesa:{payload['TransID']}", "currency": "KES", "amount": float(payload.get("TransAmount") or 0),
                "opportunity_id": _opp_from(payload.get("BillRefNumber")), "customer": payload.get("MSISDN")}
    return None


def handle(provider: str, body: bytes, headers: dict, query: dict) -> dict:
    verify(provider, body, headers, query)
    X.ensure_tables()
    p = parse(provider, json.loads(body or b"{}"))
    if not p:
        return {"ignored": True}
    oid = p["opportunity_id"]
    if not oid or not db.q1("SELECT id FROM opportunities WHERE id=?", (oid,)):
        raise PaymentError(422, "payment does not reference a known opportunity (use reference AD<id>)")
    if not X.approved(oid):
        raise PaymentError(409, "opportunity not approved — payment not recorded; refund or investigate")
    if db.q1("SELECT id FROM finance_entries WHERE reference=?", (p["txn"],)):
        return {"duplicate": True}
    fx = MK.fx_usd()
    if p["currency"] not in fx or p["amount"] <= 0:
        raise PaymentError(422, "unsupported currency or amount")
    fid = db.insert("finance_entries", {"opportunity_id": oid, "at": time.time(), "kind": "revenue", "amount": p["amount"],
                                        "currency": p["currency"], "usd": p["amount"] / fx[p["currency"]], "units": None,
                                        "reference": p["txn"], "actor": f"provider:{provider}", "evidence_url": ""})
    if p.get("customer"):
        cust = db.q1("SELECT id FROM customers WHERE opportunity_id=? AND handle=?", (oid, p["customer"]))
        if cust:
            db.update("customers", cust["id"], {"stage": "customer"})
        else:
            db.insert("customers", {"opportunity_id": oid, "handle": p["customer"], "channel": provider,
                                    "stage": "customer", "consent_at": time.time(), "created_at": time.time()}, ignore=True)
    ledger_append(f"provider:{provider}", "payment_received", "opportunity", oid,
                  {"txn": p["txn"], "amount": p["amount"], "currency": p["currency"]})
    return {"finance_id": fid, "opportunity_id": oid}
