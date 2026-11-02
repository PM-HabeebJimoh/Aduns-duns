"""Free translation to English so needs found in any language can be fused globally.

Primary: Wikimedia MinT (cxserver.wikimedia.org, keyless, 200+ languages, batched).
Fallback: MyMemory public API.

* Cached forever in SQLite (same text is never translated twice).
* Daily character budget (anonymous 5k/day; 50k/day when ADUNS_CONTACT_EMAIL is set) — when exhausted,
  untranslated signals are queued and back-filled by the scheduler the next day.
* Original text is always kept; translation is stored alongside it.
"""
from __future__ import annotations

import time

from . import config, db, http

_API = "https://api.mymemory.translated.net/get"
_MINT = "https://cxserver.wikimedia.org/v2/translate/{src}/en/MinT"


def _ensure() -> None:
    with db.tx() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS translations (
            key TEXT PRIMARY KEY, src_lang TEXT, text TEXT, text_en TEXT, at REAL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS translation_budget (day TEXT PRIMARY KEY, chars INTEGER)""")


def daily_limit() -> int:
    return 48000 if config.CONTACT_EMAIL else 4800


def used_today() -> int:
    _ensure()
    r = db.q1("SELECT chars FROM translation_budget WHERE day=?", (time.strftime("%Y-%m-%d"),))
    return r["chars"] if r else 0


def to_english(text: str, src_lang: str) -> str | None:
    """Translate up to 450 chars to English. Returns None if unavailable (budget, error)."""
    if not text:
        return None
    if src_lang in ("en", "", None):
        return text
    _ensure()
    t = text[:450]
    key = http.content_hash(src_lang, t)
    hit = db.q1("SELECT text_en FROM translations WHERE key=?", (key,))
    if hit:
        return hit["text_en"]
    res = batch_to_english([t], src_lang)
    if res and res[0]:
        return res[0]
    if used_today() + len(t) > daily_limit():
        return None
    params = {"q": t, "langpair": f"{src_lang}|en"}
    if config.CONTACT_EMAIL:
        params["de"] = config.CONTACT_EMAIL
    try:
        data = http.fetch(_API, params, source="mymemory", ttl=0, retries=1)
    except http.FetchError:
        return None
    out = (data.get("responseData") or {}).get("translatedText")
    if not out or data.get("quotaFinished") or "MYMEMORY WARNING" in out.upper():
        return None
    day = time.strftime("%Y-%m-%d")
    with db.tx() as c:
        c.execute("INSERT OR REPLACE INTO translations (key, src_lang, text, text_en, at) VALUES (?,?,?,?,?)",
                  (key, src_lang, t, out, time.time()))
        c.execute("INSERT INTO translation_budget (day, chars) VALUES (?, ?) ON CONFLICT(day) DO UPDATE SET chars=chars+?",
                  (day, len(t), len(t)))
    return out


def _cache_get(src: str, t: str) -> str | None:
    hit = db.q1("SELECT text_en FROM translations WHERE key=?", (http.content_hash(src, t),))
    return hit["text_en"] if hit else None


def _cache_put(src: str, t: str, en: str) -> None:
    with db.tx() as c:
        c.execute("INSERT OR REPLACE INTO translations (key, src_lang, text, text_en, at) VALUES (?,?,?,?,?)",
                  (http.content_hash(src, t), src, t, en, time.time()))


def batch_to_english(texts: list[str], src_lang: str, chunk: int = 12) -> list[str | None]:
    """Translate many short texts with Wikimedia MinT (one HTTP call per `chunk` texts)."""
    import html as _html
    import re as _re

    _ensure()
    if src_lang in ("en", "", None):
        return list(texts)
    texts = [(t or "")[:450] for t in texts]
    out: list[str | None] = [_cache_get(src_lang, t) for t in texts]
    todo = [i for i, v in enumerate(out) if v is None and texts[i]]
    for k in range(0, len(todo), chunk):
        idx = todo[k:k + chunk]
        body = "<div>" + "".join(f'<p id="t{i}">{_html.escape(texts[i])}</p>' for i in idx) + "</div>"
        try:
            data = http.fetch(_MINT.format(src=src_lang), method="POST", json_body={"html": body},
                              source="mint", ttl=0, retries=1)
        except http.FetchError:
            continue
        frag = data.get("contents") or ""
        for i in idx:
            m = _re.search(rf'<p[^>]*id="t{i}"[^>]*>(.*?)</p>', frag, _re.S)
            if m:
                en = _html.unescape(_re.sub(r"<[^>]+>", "", m.group(1))).strip()
                if en:
                    out[i] = en
                    _cache_put(src_lang, texts[i], en)
    return out


def from_english(text: str, tgt_lang: str) -> str:
    """Translate a short English phrase into a target language (MinT). Falls back to the English text."""
    import html as _html
    import re as _re

    if not text or tgt_lang in ("en", "", None):
        return text
    _ensure()
    key_lang = f"en>{tgt_lang}"
    hit = _cache_get(key_lang, text)
    if hit:
        return hit
    try:
        data = http.fetch(f"https://cxserver.wikimedia.org/v2/translate/en/{tgt_lang}/MinT", method="POST",
                          json_body={"html": f"<div><p>{_html.escape(text)}</p></div>"}, source="mint", ttl=0, retries=1)
    except http.FetchError:
        return text
    out = _html.unescape(_re.sub(r"<[^>]+>", "", data.get("contents") or "")).strip()
    if out:
        _cache_put(key_lang, text, out)
        return out
    return text
