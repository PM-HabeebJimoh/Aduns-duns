"""Optional LLM enrichment (Claude). Used only when ANTHROPIC_API_KEY is set.

The engine is fully functional without it; the LLM never invents evidence — it
only rewrites/structures text that came from real signals, and its output is
stored separately (llm_summary) from the evidence itself.
"""
from __future__ import annotations

import json

from . import config

_client = None


def enabled() -> bool:
    return config.LLM_ENABLED


def _get():
    global _client
    if _client is None:
        import anthropic  # optional dependency

        _client = anthropic.Anthropic()
    return _client


HYPOTHESIS_SCHEMA = {
    "type": "object",
    "properties": {
        "need_statement": {"type": "string"},
        "who_is_affected": {"type": "string"},
        "where": {"type": "string"},
        "why_gap_exists": {"type": "string"},
        "normalized_need": {"type": "boolean"},
        "falsification_test": {"type": "string"},
        "evidence_caveats": {"type": "string"},
    },
    "required": ["need_statement", "who_is_affected", "where", "why_gap_exists", "normalized_need",
                 "falsification_test", "evidence_caveats"],
    "additionalProperties": False,
}


def summarize_hypothesis(key_terms: list[str], evidence: list[dict]) -> dict | None:
    """Structure a cluster of real signals into a need hypothesis. Returns None if disabled/failing."""
    if not enabled():
        return None
    lines = "\n".join(f"- [{e['source']}] {e['text'][:400]} ({e.get('url', '')})" for e in evidence[:25])
    prompt = (
        "You are the Signal Fusion analyst of a venture-discovery engine. Below are real, retrieved "
        "signals that were clustered together (key terms: " + ", ".join(key_terms) + ").\n"
        "Using ONLY this evidence, describe the underlying unmet or poorly served need. Do not invent facts, "
        "numbers or places that are not in the evidence; say 'unknown' where the evidence is silent.\n\n" + lines
    )
    try:
        resp = _get().messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=4000,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": HYPOTHESIS_SCHEMA}},
            messages=[{"role": "user", "content": prompt}],
        )
        if resp.stop_reason == "refusal":
            return None
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        return json.loads(text)
    except Exception:  # noqa: BLE001 — enrichment is best-effort
        return None
