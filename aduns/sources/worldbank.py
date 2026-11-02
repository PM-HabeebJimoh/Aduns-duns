"""World Bank World Development Indicators (free, keyless)."""
from __future__ import annotations

from .. import http

_TTL = 7 * 24 * 3600


def _all_pages(url: str, params: dict) -> list[dict]:
    rows: list[dict] = []
    page = 1
    while True:
        data = http.fetch(url, {**params, "page": page}, source="worldbank", ttl=_TTL)
        if not isinstance(data, list) or len(data) < 2 or data[1] is None:
            break
        rows.extend(data[1])
        if page >= int(data[0].get("pages", 1)):
            break
        page += 1
    return rows


def latest(indicator: str) -> dict[str, tuple[float, int]]:
    """ISO3 → (most recent non-empty value, year), for every economy."""
    rows = _all_pages(f"https://api.worldbank.org/v2/country/all/indicator/{indicator}",
                      {"format": "json", "per_page": 1000, "mrnev": 1})
    out: dict[str, tuple[float, int]] = {}
    for r in rows:
        iso = r.get("countryiso3code")
        if iso and r.get("value") is not None:
            out[iso] = (float(r["value"]), int(r["date"]))
    return out


def series(indicator: str, start: int, end: int) -> dict[str, dict[int, float]]:
    """ISO3 → {year: value} over a date range, for every economy."""
    rows = _all_pages(f"https://api.worldbank.org/v2/country/all/indicator/{indicator}",
                      {"format": "json", "per_page": 5000, "date": f"{start}:{end}"})
    out: dict[str, dict[int, float]] = {}
    for r in rows:
        iso = r.get("countryiso3code")
        if iso and r.get("value") is not None:
            out.setdefault(iso, {})[int(r["date"])] = float(r["value"])
    return out


def projects(query: str, country: str | None = None, limit: int = 20) -> list[dict]:
    """World Bank financed projects — real, implemented interventions (programme models).

    `country` is an ISO2 code."""
    params = {"format": "json", "rows": min(limit, 100), "qterm": query,
              "fl": "id,project_name,countryshortname,countrycode,status,closingdate,totalamt,url,project_abstract,boardapprovaldate,pdo"}
    if country:
        params["countrycode_exact"] = country
    data = http.fetch("https://search.worldbank.org/api/v2/projects", params, source="worldbank_projects", ttl=_TTL)
    projs = data.get("projects") or {}
    out = []
    for p in (projs.values() if isinstance(projs, dict) else projs):
        abstract = p.get("project_abstract")
        if isinstance(abstract, dict):
            abstract = abstract.get("cdata!", "")
        out.append({
            "id": p.get("id"), "name": p.get("project_name"), "country": p.get("countryshortname"),
            "countrycode": p.get("countrycode"),
            "status": p.get("status"), "approved": p.get("boardapprovaldate"), "closing": p.get("closingdate"),
            "amount": p.get("totalamt"), "url": p.get("url"),
            "abstract": abstract or p.get("pdo") or "",
        })
    return out
