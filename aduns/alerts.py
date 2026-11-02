"""Alerts for new strong or emerging needs (free channels only).

* ADUNS_ALERT_WEBHOOK  – any URL accepting JSON POST (Slack/Discord/Mattermost-compatible `text` field included)
* ADUNS_TELEGRAM_TOKEN + ADUNS_ALERT_CHAT_ID – Telegram bot message
Each (hypothesis, kind) is alerted once.
"""
from __future__ import annotations

import os
import time

import requests

from . import db


def _send(text: str, payload: dict) -> bool:
    sent = False
    hook = os.environ.get("ADUNS_ALERT_WEBHOOK")
    if hook:
        try:
            requests.post(hook, json={"text": text, "content": text, **payload}, timeout=15)
            sent = True
        except requests.RequestException:
            pass
    tok, chat = os.environ.get("ADUNS_TELEGRAM_TOKEN"), os.environ.get("ADUNS_ALERT_CHAT_ID")
    if tok and chat:
        try:
            requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", json={"chat_id": chat, "text": text},
                          timeout=15)
            sent = True
        except requests.RequestException:
            pass
    return sent


def check(min_score: float = 0.75, max_per_run: int = 10) -> list[dict]:
    """Alert on hypotheses that are strong (score ≥ min_score) or emerging, once each. Returns alerts raised."""
    raised = []
    rows = db.q("""SELECT id, title, score, emerging, momentum, countries, scope FROM hypotheses
                   WHERE status NOT IN ('superseded', 'stale', 'rejected') AND (score >= ? OR emerging = 1)
                   ORDER BY score DESC LIMIT 50""", (min_score,))
    for h in rows:
        kind = "emerging" if h["emerging"] else "strong"
        key = f"{h['id']}:{kind}"
        if db.q1("SELECT key FROM alerts_sent WHERE key=?", (key,)):
            continue
        text = (f"[Aduns] {'EMERGING' if kind == 'emerging' else 'Strong'} need #{h['id']}: {h['title']} "
                f"(score {h['score']:.2f}, momentum {h['momentum'] or 1:.1f}x, {h['scope']})")
        delivered = _send(text, {"hypothesis_id": h["id"], "kind": kind})
        db.insert("alerts_sent", {"key": key, "hypothesis_id": h["id"], "kind": kind, "at": time.time()}, ignore=True)
        raised.append({"hypothesis_id": h["id"], "kind": kind, "delivered": delivered, "text": text})
        if len(raised) >= max_per_run:
            break
    return raised
