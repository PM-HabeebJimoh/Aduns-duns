"""OpenStreetMap Nominatim geocoding (free; 1 req/s usage policy respected by aduns.http)."""
from __future__ import annotations

from .. import http


def geocode(q: str, country_iso2: str | None = None, limit: int = 5) -> list[dict]:
    params = {"q": q, "format": "jsonv2", "limit": limit, "addressdetails": 1}
    if country_iso2:
        params["countrycodes"] = country_iso2.lower()
    data = http.fetch("https://nominatim.openstreetmap.org/search", params, source="nominatim", ttl=30 * 86400)
    return [{
        "name": d.get("display_name"), "lat": float(d["lat"]), "lon": float(d["lon"]),
        "type": d.get("type"), "category": d.get("category"),
        "osm_url": f"https://www.openstreetmap.org/{d.get('osm_type')}/{d.get('osm_id')}",
    } for d in data]
