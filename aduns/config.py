"""Runtime configuration (env-driven, no secrets required)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("ADUNS_DB", ROOT / "data" / "aduns.db"))

# Contact e-mail sent to polite-pool APIs (Crossref, OpenAlex, Nominatim, SEC-style UAs).
CONTACT_EMAIL = os.environ.get("ADUNS_CONTACT_EMAIL", "")
USER_AGENT = os.environ.get(
    "ADUNS_USER_AGENT",
    "AdunsDiscoveryEngine/0.1 (+https://github.com/pm-habeebjimoh/aduns-duns"
    + (f"; mailto:{CONTACT_EMAIL}" if CONTACT_EMAIL else "")
    + ")",
)

# Optional keys. Every source works without them; keys only raise rate limits.
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
STACKEXCHANGE_KEY = os.environ.get("STACKEXCHANGE_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ADUNS_LLM_MODEL", "claude-opus-5-5")
LLM_ENABLED = bool(os.environ.get("ANTHROPIC_API_KEY")) and os.environ.get("ADUNS_LLM", "1") != "0"

HTTP_TIMEOUT = float(os.environ.get("ADUNS_HTTP_TIMEOUT", "25"))
CACHE_TTL_SECONDS = int(os.environ.get("ADUNS_CACHE_TTL", str(6 * 3600)))

# Field-network compensation defaults (USD-equivalent, paid only for validated observations).
SCOUT_REWARD_SUBMITTED = float(os.environ.get("ADUNS_SCOUT_REWARD_SUBMITTED", "0.5"))
SCOUT_REWARD_VALIDATED = float(os.environ.get("ADUNS_SCOUT_REWARD_VALIDATED", "3.0"))
