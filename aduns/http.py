"""Polite real-data fetcher.

* Per-host minimum interval (respects published limits, e.g. GDELT 1 req / 5 s).
* Retries with exponential backoff on 429/5xx/network errors.
* SQLite response cache so repeated runs don't hammer free public services.
* Source-health bookkeeping so the dashboard shows which real feeds are live.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any
from urllib.parse import urlencode, urlparse

import requests

from . import config, db

# Minimum seconds between requests to a host (documented limits or courtesy).
HOST_INTERVAL = {
    "api.gdeltproject.org": 7.0,
    "www.reddit.com": 7.0,
    "suggestqueries.google.com": 1.0,
    "news.google.com": 1.5,
    "patents.google.com": 2.0,
    "nominatim.openstreetmap.org": 1.1,
    "api.github.com": 2.5,
    "www.contractsfinder.service.gov.uk": 10.5,
    "sam.gov": 1.5,
    "api.openalex.org": 1.0,
    "export.arxiv.org": 3.0,
    "query.wikidata.org": 1.0,
    "www.wikidata.org": 0.5,
    "api.stackexchange.com": 0.5,
    "hn.algolia.com": 0.3,
    "api.crossref.org": 0.3,
}
DEFAULT_INTERVAL = 0.5

_host_locks: dict[str, threading.Lock] = {}
_host_last: dict[str, float] = {}
_glock = threading.Lock()
_session = requests.Session()
_session.headers.update({"User-Agent": config.USER_AGENT, "Accept-Encoding": "gzip, deflate"})


class FetchError(RuntimeError):
    pass


def _throttle(host: str) -> None:
    with _glock:
        lock = _host_locks.setdefault(host, threading.Lock())
    with lock:
        wait = HOST_INTERVAL.get(host, DEFAULT_INTERVAL) - (time.time() - _host_last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        _host_last[host] = time.time()


def _health(source: str, ok: bool, msg: str | None = None) -> None:
    now = time.time()
    try:
        with db.tx() as conn:
            conn.execute("INSERT OR IGNORE INTO source_health (source) VALUES (?)", (source,))
            if ok:
                conn.execute(
                    "UPDATE source_health SET last_ok=?, ok_count=ok_count+1 WHERE source=?", (now, source)
                )
            else:
                conn.execute(
                    "UPDATE source_health SET last_error=?, last_error_msg=?, error_count=error_count+1 WHERE source=?",
                    (now, (msg or "")[:500], source),
                )
    except Exception:  # health is best-effort
        pass


def fetch(
    url: str,
    params: dict | None = None,
    *,
    source: str,
    method: str = "GET",
    json_body: Any = None,
    headers: dict | None = None,
    ttl: int | None = None,
    retries: int = 3,
    expect: str = "json",
) -> Any:
    """Fetch a URL and return parsed JSON (expect='json') or text (expect='text')."""
    full = url + ("?" + urlencode(params, doseq=True) if params else "")
    key = hashlib.sha256(f"{method} {full} {json.dumps(json_body, sort_keys=True)}".encode()).hexdigest()
    ttl = config.CACHE_TTL_SECONDS if ttl is None else ttl

    if ttl > 0:
        row = db.q1("SELECT body, fetched_at, status FROM http_cache WHERE key=?", (key,))
        if row and time.time() - row["fetched_at"] < ttl and row["status"] == 200:
            return json.loads(row["body"]) if expect == "json" else row["body"]

    host = urlparse(url).netloc
    hdrs = dict(headers or {})
    if host == "api.github.com" and config.GITHUB_TOKEN:
        hdrs["Authorization"] = f"Bearer {config.GITHUB_TOKEN}"
    last_err: str = ""
    for attempt in range(retries + 1):
        _throttle(host)
        try:
            resp = _session.request(
                method, full, json=json_body, headers=hdrs, timeout=config.HTTP_TIMEOUT
            )
        except requests.RequestException as e:
            last_err = f"network: {e}"
        else:
            if resp.status_code == 200:
                body = resp.text
                try:
                    parsed = json.loads(body) if expect == "json" else body
                except ValueError:
                    last_err = f"non-JSON response: {body[:200]}"
                    # GDELT returns a plain-text rate-limit notice with 200
                    if "limit requests" in body.lower() and attempt < retries:
                        time.sleep(6 * (attempt + 1))
                        continue
                    break
                if ttl > 0:
                    with db.tx() as conn:
                        conn.execute(
                            "INSERT OR REPLACE INTO http_cache (key,url,status,body,fetched_at) VALUES (?,?,?,?,?)",
                            (key, full, 200, body, time.time()),
                        )
                _health(source, True)
                return parsed
            last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                retry_after = resp.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else 2 ** (attempt + 1)
                if resp.status_code == 429:
                    delay = max(delay, HOST_INTERVAL.get(host, DEFAULT_INTERVAL) * 2)
                time.sleep(min(delay, 30))
                continue
            break
        if attempt < retries:
            time.sleep(2 ** (attempt + 1))
    _health(source, False, last_err)
    raise FetchError(f"{source}: {last_err} [{full[:200]}]")


def content_hash(*parts: Any) -> str:
    return hashlib.sha256("||".join(str(p or "") for p in parts).encode()).hexdigest()
