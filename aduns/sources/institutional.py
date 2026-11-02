"""Institutional and ground-truth connectors (recent data only, free, keyless).

* Failed / cancelled public tenders — buyers who could not get what they needed:
    Prozorro (Ukraine, OCDS API), SECOP II (Colombia, Socrata), SAM.gov sources-sought (USA),
    World Bank procurement notices (global, 100+ borrower countries).
* WFP market prices (HDX) — measured retail/wholesale prices in local markets across ~90 countries;
  recent price spikes = affordability / scarcity needs observed on the ground (not self-reported statistics).
* GDACS — real-time global disaster alerts (sudden, urgent needs).
* openFDA drug shortages, CFPB consumer complaints (USA), recent only.
"""
from __future__ import annotations

import csv
import statistics
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

from .. import config, http
from ..nlp import clean
from .social import _rec


def _cutoff(days: int | None = None) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days or config.MAX_AGE_DAYS)


# ------------------------------------------------------------------- Prozorro (UA)
def prozorro_failed(pages: int = 5) -> list[dict]:
    out, offset = [], None
    fields = "status,title,procuringEntity,value,dateModified,tenderID"
    for _ in range(pages):
        params = {"descending": 1, "limit": 100, "opt_fields": fields}
        if offset:
            params["offset"] = offset
        data = http.fetch("https://public.api.openprocurement.org/api/2.5/tenders", params, source="prozorro", ttl=3600)
        for t in data.get("data", []):
            if t.get("status") not in ("unsuccessful", "cancelled"):
                continue
            pe = (t.get("procuringEntity") or {})
            region = ((pe.get("address") or {}).get("region")) or ""
            val = (t.get("value") or {})
            title = t.get("title") or ""
            out.append(_rec("prozorro", "structural", t["id"], f"https://prozorro.gov.ua/tender/{t.get('tenderID') or t['id']}",
                            title, f"Tender {t['status']} (no successful supplier): {title} — {pe.get('name', '')}, {region}",
                            pe.get("name"), t.get("dateModified"), 0.4,
                            {"status": t["status"], "amount": val.get("amount"), "currency": val.get("currency"),
                             "region": region, "lang": "uk"}))
        offset = (data.get("next_page") or {}).get("offset")
        if not offset:
            break
    return out


# ------------------------------------------------------------------ SECOP II (CO)
def secop_cancelled(limit: int = 200) -> list[dict]:
    since = _cutoff().strftime("%Y-%m-%dT00:00:00")
    data = http.fetch("https://www.datos.gov.co/resource/p6dx-8zbt.json",
                      {"$limit": limit, "$order": "fecha_de_publicacion_del DESC",
                       "$where": f"estado_del_procedimiento='Cancelado' AND fecha_de_publicacion_del > '{since}'"},
                      source="secop", ttl=3600)
    out = []
    for r in data:
        url = r.get("urlproceso")
        if isinstance(url, dict):
            url = url.get("url")
        name = r.get("nombre_del_procedimiento") or r.get("descripci_n_del_procedimiento") or ""
        out.append(_rec("secop", "structural", r.get("id_del_proceso"), url, name,
                        f"Proceso cancelado: {name} — {r.get('entidad', '')} ({r.get('departamento_entidad', '')})",
                        r.get("entidad"), r.get("fecha_de_publicacion_del"), 0.4,
                        {"price_base": r.get("precio_base"), "department": r.get("departamento_entidad"), "lang": "es"}))
    return out


# ------------------------------------------------------------- SAM.gov (US)
def sam_sources_sought(query: str = "", limit: int = 50) -> list[dict]:
    data = http.fetch("https://sam.gov/api/prod/sgs/v1/search/",
                      {"index": "opp", "q": f'"sources sought" {query}'.strip(), "page": 0, "size": min(limit, 100),
                       "mode": "search", "is_active": "true", "sort": "-modifiedDate"}, source="samgov", ttl=3600)
    out = []
    for r in (data.get("_embedded") or {}).get("results", []):
        desc = " ".join(clean(d.get("content")) for d in r.get("descriptions", []))[:2000]
        out.append(_rec("samgov", "structural", r.get("_id"), f"https://sam.gov/opp/{r.get('_id')}/view", r.get("title"),
                        f"{clean(r.get('title'))}. {desc}", None, r.get("publishDate"), 0.4,
                        {"type": (r.get("type") or {}).get("value")}))
    return out


# --------------------------------------------------- World Bank procurement (global)
def worldbank_procurement(country_name: str | None = None, limit: int = 50) -> list[dict]:
    params = {"format": "json", "rows": limit, "srt": "noticedate", "order": "desc",
              "fl": "id,project_name,notice_type,bid_description,project_ctry_name,submission_date,noticedate"}
    if country_name:
        params["project_ctry_name_exact"] = country_name
    data = http.fetch("https://search.worldbank.org/api/v2/procnotices", params, source="worldbank_procurement", ttl=3600)
    out = []
    for n in data.get("procnotices", []):
        desc = clean(n.get("bid_description"))
        out.append(_rec("worldbank_procurement", "structural", n.get("id"),
                        f"https://projects.worldbank.org/en/projects-operations/procurement-detail/{n.get('id')}",
                        desc[:200], f"{n.get('notice_type')}: {desc} — {n.get('project_name')} ({n.get('project_ctry_name')})",
                        n.get("project_ctry_name"), n.get("submission_date") or n.get("noticedate"), 0.3,
                        {"notice_type": n.get("notice_type"), "country": n.get("project_ctry_name")}))
    return out


# -------------------------------------------------------------------- GDACS
_G = "{http://www.gdacs.org}"


def gdacs(min_level: str = "Orange") -> list[dict]:
    body = http.fetch("https://www.gdacs.org/xml/rss.xml", None, source="gdacs", ttl=1800, expect="text")
    root = ET.fromstring(body)
    rank = {"Green": 0, "Orange": 1, "Red": 2}
    out = []
    for it in root.iter("item"):
        lvl = it.findtext(f"{_G}alertlevel") or "Green"
        if rank.get(lvl, 0) < rank[min_level]:
            continue
        pub = it.findtext("pubDate")
        try:
            pub = parsedate_to_datetime(pub).isoformat() if pub else None
        except (TypeError, ValueError):
            pub = None
        title = it.findtext("title") or ""
        out.append(_rec("gdacs", "structural", it.findtext("guid") or it.findtext("link"), it.findtext("link"), title,
                        f"{lvl} disaster alert: {title}. {clean(it.findtext('description'))}", "GDACS", pub,
                        0.5 + 0.25 * rank.get(lvl, 0),
                        {"alertlevel": lvl, "eventtype": it.findtext(f"{_G}eventtype"), "country": it.findtext(f"{_G}country")}))
    return out


# ---------------------------------------------------------- WFP market prices
def wfp_price_spikes(country_name: str, iso3: str, min_rise: float = 0.15, months_back: int = 7) -> list[dict]:
    """Recent price spikes per commodity from WFP market monitoring (HDX)."""
    data = http.fetch("https://data.humdata.org/api/3/action/package_search",
                      {"fq": f"organization:wfp AND groups:{iso3.lower()}", "q": "food prices", "rows": 5},
                      source="wfp_prices", ttl=7 * 86400)
    res_url = None
    for pkg in (data.get("result") or {}).get("results", []):
        if pkg["name"].startswith("wfp-food-prices-for-"):
            for r in pkg.get("resources", []):
                if r["name"].endswith("Food Prices"):
                    res_url = r["url"]
            break
    if not res_url:
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=31 * months_back)).date().isoformat()
    series: dict[tuple, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    units: dict[tuple, str] = {}
    try:
        with requests.get(res_url, stream=True, timeout=120, headers={"User-Agent": config.USER_AGENT}) as resp:
            resp.raise_for_status()
            lines = (l.decode("utf-8", "replace") for l in resp.iter_lines())
            header = next(lines)
            rd = csv.DictReader(lines, fieldnames=header.split(","))
            for row in rd:
                d = row.get("date") or ""
                if d < cutoff or (row.get("priceflag") or "").startswith("forecast"):
                    continue
                try:
                    price = float(row["price"])
                except (TypeError, ValueError):
                    continue
                key = (row["commodity"], row["pricetype"], row["unit"], row["currency"])
                series[key][d[:7]].append(price)
                units[key] = row.get("category", "")
    except (requests.RequestException, StopIteration) as e:
        raise http.FetchError(f"wfp_prices: {e}")
    http._health("wfp_prices", True)
    out = []
    for key, by_month in series.items():
        months = sorted(by_month)
        if len(months) < 3:
            continue
        latest = months[-1]
        if latest < (datetime.now(timezone.utc) - timedelta(days=100)).strftime("%Y-%m"):
            continue  # stale series
        cur = statistics.median(by_month[latest])
        base = statistics.median([p for m in months[-4:-1] for p in by_month[m]])
        if base <= 0:
            continue
        rise = cur / base - 1
        if rise < min_rise:
            continue
        commodity, ptype, unit, cur_code = key
        n_markets = len(by_month[latest])
        text = (f"{commodity} {ptype.lower()} price in {country_name} rose {rise:.0%} in {latest} vs the prior 3 months "
                f"(median {cur:g} {cur_code}/{unit} across {n_markets} market observations, WFP market monitoring). "
                f"Price hike — affordability pressure on {commodity.lower()}.")
        out.append(_rec("wfp_prices", "structural", f"{iso3}:{commodity}:{ptype}:{unit}:{latest}",
                        f"https://data.humdata.org/dataset/wfp-food-prices-for-{country_name.lower().replace(' ', '-')}",
                        f"{commodity} price +{rise:.0%} in {country_name}", text, "WFP", f"{latest}-15",
                        min(1.0, rise), {"rise": rise, "commodity": commodity, "category": units[key],
                                         "markets": n_markets, "currency": cur_code}))
    return out


# ------------------------------------------------------------------ openFDA
def fda_shortages(limit: int = 200) -> list[dict]:
    data = http.fetch("https://api.fda.gov/drug/shortages.json", {"search": 'status:"Current"', "limit": limit,
                                                                  "sort": "update_date:desc"}, source="openfda", ttl=6 * 3600)
    out = []
    for r in data.get("results", []):
        try:
            upd = datetime.strptime(r.get("update_date", ""), "%m/%d/%Y").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if upd < _cutoff():
            continue
        name = r.get("generic_name") or ""
        out.append(_rec("openfda", "structural", f"{r.get('package_ndc')}:{r.get('update_date')}",
                        "https://www.accessdata.fda.gov/dsp_shortages/", f"Drug shortage: {name}",
                        f"Current drug shortage: {name} ({r.get('dosage_form', '')}). Availability: {r.get('availability', '')}. "
                        f"Reason: {r.get('shortage_reason', '')}. Category: {', '.join(r.get('therapeutic_category') or [])}",
                        r.get("company_name"), upd.isoformat(), 0.5, {"availability": r.get("availability")}))
    return out


# --------------------------------------------------------------------- CFPB
def cfpb_complaints(limit: int = 100) -> list[dict]:
    since = _cutoff(60).strftime("%Y-%m-%d")
    data = http.fetch("https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/",
                      {"size": limit, "sort": "created_date_desc", "has_narrative": "true", "date_received_min": since},
                      source="cfpb", ttl=6 * 3600)
    out = []
    for h in (data.get("hits") or {}).get("hits", []):
        s = h.get("_source", {})
        narrative = s.get("complaint_what_happened") or ""
        out.append(_rec("cfpb", "scattered", h.get("_id"),
                        f"https://www.consumerfinance.gov/data-research/consumer-complaints/search/detail/{h.get('_id')}",
                        f"{s.get('product')}: {s.get('issue')}", f"{s.get('product')} — {s.get('issue')}. {narrative[:1500]}",
                        s.get("company"), s.get("date_received"), 0.2, {"state": s.get("state"), "product": s.get("product")}))
    return out
