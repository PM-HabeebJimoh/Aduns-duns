"""SQLite persistence: the evidence graph needs → capabilities → analogies → field reality.

Every row that originates outside the system carries provenance (source, url,
retrieved_at, content hash) so the Verification/Audit agents (later layers) can
trace any claim back to the real-world record it came from.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

from . import config

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS http_cache (
    key TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    status INTEGER,
    body TEXT,
    fetched_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS source_health (
    source TEXT PRIMARY KEY,
    last_ok REAL,
    last_error REAL,
    last_error_msg TEXT,
    ok_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent TEXT NOT NULL,
    params TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    started_at REAL NOT NULL,
    finished_at REAL,
    stats TEXT,
    error TEXT
);

-- Raw need signals (Network A). One row per real observed fragment.
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,            -- e.g. hackernews, stackexchange:diy, gdelt, field
    layer TEXT NOT NULL,             -- visible | scattered | offline | invisible | structural
    external_id TEXT,
    url TEXT,
    title TEXT,
    text TEXT NOT NULL,
    author TEXT,
    published_at TEXT,
    retrieved_at REAL NOT NULL,
    content_hash TEXT NOT NULL UNIQUE,
    query TEXT,
    domain TEXT,
    need_types TEXT,                 -- JSON list: unmet, unaffordable, unaware, normalized, inefficient, scarcity, latent_search, institutional
    gap_causes TEXT,                 -- JSON list: affordability, distribution, regulation, infrastructure, awareness, trust, capability, supply
    intensity REAL,                  -- 0..1 strength of the pain expressed
    need_score REAL,                 -- 0..1 probability this is a real need signal
    countries TEXT,                  -- JSON list of ISO3 codes mentioned
    entities TEXT,                   -- JSON list of key noun phrases (the thing needed)
    engagement REAL,                 -- normalised social proof (points, votes, comments)
    run_id INTEGER,
    extra TEXT
);
CREATE INDEX IF NOT EXISTS ix_signals_domain ON signals(domain);
CREATE INDEX IF NOT EXISTS ix_signals_source ON signals(source);

-- Fused hypotheses (Signal Fusion Agent output)
CREATE TABLE IF NOT EXISTS hypotheses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT UNIQUE,
    title TEXT NOT NULL,
    need_statement TEXT NOT NULL,
    domain TEXT,
    key_terms TEXT,                  -- JSON list
    countries TEXT,                  -- JSON {iso3: count}
    need_types TEXT,                 -- JSON {type: count}
    gap_causes TEXT,                 -- JSON {cause: count}
    signal_count INTEGER,
    source_count INTEGER,
    layer_count INTEGER,
    score REAL,
    score_breakdown TEXT,            -- JSON
    evidence_level TEXT,             -- claim | corroborated | field_verified
    tests TEXT,                      -- JSON list of falsification tests
    status TEXT DEFAULT 'open',      -- open | validating | validated | rejected
    created_at REAL,
    updated_at REAL,
    llm_summary TEXT
);

CREATE TABLE IF NOT EXISTS hypothesis_signals (
    hypothesis_id INTEGER NOT NULL,
    signal_id INTEGER NOT NULL,
    similarity REAL,
    PRIMARY KEY (hypothesis_id, signal_id)
);

-- Capability map (Network B)
CREATE TABLE IF NOT EXISTS capabilities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    capability_type TEXT NOT NULL,   -- ip_patent | research | open_design | supplier | proven_vendor | program_model | clinical | organization
    external_id TEXT,
    url TEXT,
    title TEXT NOT NULL,
    description TEXT,
    holder TEXT,
    countries TEXT,                  -- JSON list ISO3 / names
    year INTEGER,
    maturity REAL,                   -- 0..1
    transferability TEXT,            -- JSON list of delivery routes this capability suggests
    retrieved_at REAL NOT NULL,
    content_hash TEXT NOT NULL UNIQUE,
    extra TEXT
);

CREATE TABLE IF NOT EXISTS hypothesis_capabilities (
    hypothesis_id INTEGER NOT NULL,
    capability_id INTEGER NOT NULL,
    relevance REAL,
    rationale TEXT,
    PRIMARY KEY (hypothesis_id, capability_id)
);

-- Cross-border analogies (positive deviants)
CREATE TABLE IF NOT EXISTS analogies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hypothesis_id INTEGER,
    target_country TEXT NOT NULL,
    analog_country TEXT NOT NULL,
    indicator_code TEXT NOT NULL,
    indicator_name TEXT,
    target_value REAL,
    analog_value REAL,
    target_year INTEGER,
    analog_year INTEGER,
    analog_change_10y REAL,
    income_similarity REAL,
    deviance_score REAL,
    evidence TEXT,                    -- JSON list of {title,url,source}
    retrieved_at REAL NOT NULL,
    UNIQUE (hypothesis_id, target_country, analog_country, indicator_code)
);

-- Offline sensing network
CREATE TABLE IF NOT EXISTS scouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    handle TEXT UNIQUE NOT NULL,     -- phone number / username
    display_name TEXT,
    role TEXT,                        -- shop_owner, technician, farmer, health_worker, researcher, ...
    country TEXT,
    locality TEXT,
    languages TEXT,
    payout_method TEXT,
    consent_at REAL,                  -- explicit consent timestamp (required)
    consent_text TEXT,
    created_at REAL
);

CREATE TABLE IF NOT EXISTS scout_missions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    hypothesis_id INTEGER,
    title TEXT NOT NULL,
    objective TEXT,
    country TEXT,
    locations TEXT,                   -- JSON [{name, lat, lon, osm_url}]
    languages TEXT,                   -- JSON list (from REST Countries)
    target_respondents TEXT,          -- JSON list
    interview_guide TEXT,             -- JSON list of questions
    consent_script TEXT,
    reward_per_validated REAL,
    quota INTEGER,
    status TEXT DEFAULT 'open',
    created_at REAL
);

CREATE TABLE IF NOT EXISTS scout_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id INTEGER,
    scout_id INTEGER,
    channel TEXT,                     -- web | sms | whatsapp | phone | api
    text TEXT NOT NULL,
    language TEXT,
    translated_text TEXT,
    location TEXT,
    lat REAL, lon REAL,
    price_observed REAL,
    currency TEXT,
    respondent_type TEXT,
    media_urls TEXT,
    consent_confirmed INTEGER NOT NULL DEFAULT 0,
    status TEXT DEFAULT 'submitted',  -- submitted | corroborated | validated | rejected
    validation_notes TEXT,
    signal_id INTEGER,
    submitted_at REAL
);

CREATE TABLE IF NOT EXISTS compensation_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scout_id INTEGER NOT NULL,
    observation_id INTEGER,
    amount REAL NOT NULL,
    currency TEXT DEFAULT 'USD',
    reason TEXT,
    status TEXT DEFAULT 'owed',       -- owed | paid
    created_at REAL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at REAL NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    object_type TEXT,
    object_id INTEGER,
    detail TEXT
);
"""

MIGRATIONS = [
    "ALTER TABLE signals ADD COLUMN lang TEXT",
    "ALTER TABLE signals ADD COLUMN text_en TEXT",
    "ALTER TABLE signals ADD COLUMN scope_country TEXT",
    "ALTER TABLE signals ADD COLUMN continent TEXT",
    "ALTER TABLE signals ADD COLUMN published_ts REAL",
    "ALTER TABLE hypotheses ADD COLUMN continents TEXT",
    "ALTER TABLE hypotheses ADD COLUMN processed_at REAL",
    "ALTER TABLE hypotheses ADD COLUMN scope TEXT",
    "ALTER TABLE capabilities ADD COLUMN country TEXT",
    "ALTER TABLE analogies ADD COLUMN method TEXT",
    "ALTER TABLE analogies ADD COLUMN topic TEXT",
    """CREATE TABLE IF NOT EXISTS sweeps (
        country TEXT PRIMARY KEY, continent TEXT, last_started REAL, last_finished REAL, runs INTEGER DEFAULT 0,
        signals_last INTEGER, signals_total INTEGER DEFAULT 0, sources_ok TEXT, sources_failed TEXT)""",
    """CREATE TABLE IF NOT EXISTS source_registry (
        id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, handle TEXT NOT NULL, country TEXT,
        discovered_from TEXT, discovered_at REAL, last_crawled REAL, items_total INTEGER DEFAULT 0,
        active INTEGER DEFAULT 1, UNIQUE(kind, handle))""",
    """CREATE TABLE IF NOT EXISTS daemon_state (key TEXT PRIMARY KEY, value TEXT, at REAL)""",
    "CREATE INDEX IF NOT EXISTS ix_signals_scope ON signals(scope_country)",
    "CREATE INDEX IF NOT EXISTS ix_signals_pub ON signals(published_ts)",
]

_lock = threading.RLock()
_conns: dict[str, sqlite3.Connection] = {}


def _path() -> Path:
    return Path(config.DB_PATH)


def connect() -> sqlite3.Connection:
    p = str(_path())
    with _lock:
        conn = _conns.get(p)
        if conn is None:
            _path().parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(p, check_same_thread=False, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.executescript(SCHEMA)
            for m in MIGRATIONS:
                try:
                    conn.execute(m)
                except sqlite3.OperationalError:
                    pass  # already applied
            conn.commit()
            _conns[p] = conn
        return conn


def reset_connections() -> None:
    with _lock:
        for c in _conns.values():
            c.close()
        _conns.clear()


@contextmanager
def tx():
    conn = connect()
    with _lock:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def q(sql: str, params: Iterable[Any] = ()) -> list[dict]:
    conn = connect()
    with _lock:
        return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]


def q1(sql: str, params: Iterable[Any] = ()) -> dict | None:
    rows = q(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: Iterable[Any] = ()) -> int:
    with tx() as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.lastrowid


def insert(table: str, row: dict, ignore: bool = False) -> int | None:
    cols = list(row.keys())
    vals = [json.dumps(v) if isinstance(v, (list, dict)) else v for v in row.values()]
    verb = "INSERT OR IGNORE" if ignore else "INSERT"
    sql = f"{verb} INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})"
    with tx() as conn:
        cur = conn.execute(sql, vals)
        return cur.lastrowid if cur.rowcount else None


def update(table: str, row_id: int, fields: dict) -> None:
    sets = ",".join(f"{k}=?" for k in fields)
    vals = [json.dumps(v) if isinstance(v, (list, dict)) else v for v in fields.values()]
    with tx() as conn:
        conn.execute(f"UPDATE {table} SET {sets} WHERE id=?", (*vals, row_id))


def audit(actor: str, action: str, object_type: str | None = None, object_id: int | None = None, detail: Any = None) -> None:
    insert(
        "audit_log",
        {
            "at": time.time(),
            "actor": actor,
            "action": action,
            "object_type": object_type,
            "object_id": object_id,
            "detail": json.dumps(detail, default=str) if detail is not None else None,
        },
    )


def loads(v: Any, default: Any = None) -> Any:
    if v is None:
        return default
    if isinstance(v, (list, dict)):
        return v
    try:
        return json.loads(v)
    except (TypeError, ValueError):
        return default
