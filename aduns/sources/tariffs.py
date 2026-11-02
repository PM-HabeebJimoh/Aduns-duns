"""Import tariffs from free, keyless official sources.

* United States — USITC Harmonized Tariff Schedule REST API (general / MFN column).
* United Kingdom — UK Trade Tariff API (measure type 103 "Third country duty").
* Everyone else — World Bank official *country-average* applied tariffs (weighted mean, primary or manufactured
  products). Averages are clearly labelled: product-specific duties, quotas and state trading can be far higher,
  so the Red Team keeps the tariff-verification condition for them.
"""
from __future__ import annotations

import re
import time

from .. import http

_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def _parse_rate(text: str | None) -> dict:
    t = (text or "").strip()
    if not t:
        return {"ad_valorem": None, "specific": False, "text": t}
    if t.lower().startswith("free"):
        return {"ad_valorem": 0.0, "specific": False, "text": t}
    m = _PCT.search(t)
    specific = bool(re.search(r"(/kg|/t|/1000|per |¢|\$|£|€)", t))
    return {"ad_valorem": float(m.group(1)) / 100 if m else None, "specific": specific, "text": t}


def us_tariff(hs: str) -> dict | None:
    code = f"{hs[:4]}.{hs[4:6]}" if len(hs) >= 6 else hs[:4]
    data = http.fetch("https://hts.usitc.gov/reststop/search", {"keyword": code}, source="usitc", ttl=30 * 86400)
    for row in data or []:
        if str(row.get("htsno", "")).replace(".", "").startswith(hs[:6]) and row.get("general"):
            r = _parse_rate(row["general"])
            return {**r, "country": "USA", "line": row["htsno"], "description": row.get("description"),
                    "preferential": row.get("special"), "kind": "official (product line)",
                    "source": f"https://hts.usitc.gov/search?query={code}"}
    return None


def uk_tariff(hs: str) -> dict | None:
    head = http.fetch(f"https://www.trade-tariff.service.gov.uk/api/v2/headings/{hs[:4]}", None, source="uk_tariff",
                      ttl=30 * 86400)
    leaves = [x["attributes"]["goods_nomenclature_item_id"] for x in head.get("included", [])
              if x["type"] == "commodity" and x["attributes"].get("leaf")
              and x["attributes"]["goods_nomenclature_item_id"].startswith(hs[:6])]
    if not leaves:
        leaves = [x["attributes"]["goods_nomenclature_item_id"] for x in head.get("included", [])
                  if x["type"] == "commodity" and x["attributes"].get("leaf")]
    if not leaves:
        return None
    code = leaves[0]
    d = http.fetch(f"https://www.trade-tariff.service.gov.uk/api/v2/commodities/{code}", None, source="uk_tariff",
                   ttl=30 * 86400)
    inc = {(x["type"], x["id"]): x for x in d.get("included", [])}
    for x in d.get("included", []):
        if x["type"] != "measure":
            continue
        rel = x.get("relationships", {})
        if (rel.get("measure_type", {}).get("data") or {}).get("id") != "103":
            continue
        de = (rel.get("duty_expression", {}).get("data") or {}).get("id")
        base = (inc.get(("duty_expression", de)) or {}).get("attributes", {}).get("base", "")
        r = _parse_rate(re.sub(r"<[^>]+>", "", base))
        return {**r, "country": "GBR", "line": code, "kind": "official (product line)",
                "source": f"https://www.trade-tariff.service.gov.uk/commodities/{code}"}
    return None


def country_average(iso3: str, hs: str | None) -> dict | None:
    """World Bank applied weighted-mean tariff (official average) for primary vs manufactured products."""
    from . import worldbank
    primary = bool(hs) and int(hs[:2]) <= 27
    code = "TM.TAX.TCOM.WM.AR.ZS" if primary else "TM.TAX.MANF.WM.AR.ZS"
    try:
        v = worldbank.latest(code).get(iso3)
    except http.FetchError:
        return None
    if not v or v[1] < time.gmtime().tm_year - 6:
        return None
    return {"ad_valorem": v[0] / 100, "specific": False, "text": f"{v[0]:.1f}% weighted-mean ({v[1]})",
            "country": iso3, "kind": "official average (product-specific duty may differ)",
            "source": f"https://data.worldbank.org/indicator/{code}"}


def tariff_for(iso3: str, hs: str | None) -> dict | None:
    """Best available official tariff for a product entering a country."""
    if not hs:
        return None
    try:
        if iso3 == "USA":
            t = us_tariff(hs)
            if t and t["ad_valorem"] is not None:
                return t
        if iso3 == "GBR":
            t = uk_tariff(hs)
            if t and t["ad_valorem"] is not None:
                return t
    except http.FetchError:
        pass
    return country_average(iso3, hs)


_SPEC = re.compile(r"(\d+(?:[.,]\d+)?)\s*(GBP|USD|EUR|\$|£|€|¢)\s*/\s*(\d+)?\s*(kg|t|tonne|l|litre)", re.I)


def ad_valorem_equivalent(t: dict, unit_value_usd_per_kg: float | None) -> float | None:
    """Convert a specific duty ('121.00 GBP / 1000 kg', '1.4¢/kg') to an ad-valorem equivalent using the import unit value."""
    if t.get("ad_valorem") is not None:
        return t["ad_valorem"]
    m = _SPEC.search(t.get("text") or "")
    if not m or not unit_value_usd_per_kg:
        return None
    from .market import fx_usd
    amount = float(m.group(1).replace(",", "."))
    cur = {"$": "USD", "£": "GBP", "€": "EUR", "¢": "USD"}.get(m.group(2), m.group(2).upper())
    if m.group(2) == "¢":
        amount /= 100
    per = float(m.group(3) or 1) * (1000 if m.group(4).lower() in ("t", "tonne") else 1)
    fx = fx_usd()
    if cur not in fx:
        return None
    usd_per_kg = amount / fx[cur] / per
    return usd_per_kg / unit_value_usd_per_kg
