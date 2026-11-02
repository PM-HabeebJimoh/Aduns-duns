"""Need-side source connectors (Network A). All free, keyless, real public data.

Each connector returns a list of raw records:
    {source, layer, external_id, url, title, text, author, published_at, engagement, extra}

Layers (from the system design):
    visible     – indexed, explicit content (news, Q&A, tenders)
    scattered   – fragmentary social chatter (forums, comments, toots)
    invisible   – latent / normalized needs (search-demand autocomplete)
    structural  – institutional shortages (drug shortages, sources-sought notices)
"""
from __future__ import annotations

import math
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

from .. import config, http
from ..nlp import clean


def _iso(ts: float | int | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()


def _eng(*counts: float) -> float:
    """Log-scaled engagement in 0..1 (≈1 at ~1000 interactions)."""
    total = max(0, sum(c or 0 for c in counts))
    return round(min(1.0, math.log1p(total) / math.log1p(1000)), 3)


# ------------------------------------------------------------------ Hacker News
def hackernews(query: str, limit: int = 30, days: int = 730) -> list[dict]:
    since = int(time.time() - days * 86400)
    data = http.fetch(
        "https://hn.algolia.com/api/v1/search",
        {"query": query, "tags": "(story,comment,ask_hn)", "hitsPerPage": min(limit, 100),
         "numericFilters": f"created_at_i>{since}"},
        source="hackernews",
    )
    out = []
    for h in data.get("hits", []):
        text = clean(h.get("comment_text") or h.get("story_text") or "")
        title = clean(h.get("title") or h.get("story_title") or "")
        if not (text or title):
            continue
        oid = h["objectID"]
        out.append({
            "source": "hackernews", "layer": "scattered", "external_id": oid,
            "url": f"https://news.ycombinator.com/item?id={oid}",
            "title": title, "text": (title + ". " + text).strip(". ") if text else title,
            "author": h.get("author"), "published_at": h.get("created_at"),
            "engagement": _eng(h.get("points"), h.get("num_comments")),
        })
    return out


# --------------------------------------------------------------- Stack Exchange
STACKEXCHANGE_SITES = ["diy", "electronics", "engineering", "mechanics", "money", "sustainability",
                       "gardening", "expatriates", "travel", "law", "health", "medicalsciences",
                       "workplace", "softwarerecs", "hardwarerecs", "ham", "woodworking", "cooking"]


def stackexchange(query: str, site: str = "diy", limit: int = 30) -> list[dict]:
    params = {"q": query, "pagesize": min(limit, 100), "site": site, "order": "desc", "sort": "relevance",
              "filter": "default"}
    if config.STACKEXCHANGE_KEY:
        params["key"] = config.STACKEXCHANGE_KEY
    data = http.fetch("https://api.stackexchange.com/2.3/search/excerpts", params, source="stackexchange")
    out = []
    for it in data.get("items", []):
        qid = it.get("question_id")
        aid = it.get("answer_id")
        url = f"https://{site}.stackexchange.com/q/{qid}" if aid is None else f"https://{site}.stackexchange.com/a/{aid}"
        if site in ("stackoverflow", "superuser", "serverfault"):
            url = url.replace(f"{site}.stackexchange.com", f"{site}.com")
        out.append({
            "source": f"stackexchange:{site}", "layer": "scattered",
            "external_id": f"{site}:{aid or qid}", "url": url,
            "title": clean(it.get("title")), "text": clean(it.get("title")) + ". " + clean(it.get("body") or it.get("excerpt")),
            "author": None, "published_at": _iso(it.get("creation_date")),
            "engagement": _eng(it.get("score"), it.get("answer_count")),
            "extra": {"tags": it.get("tags", [])},
        })
    return out


# ------------------------------------------------------------------- Reddit RSS
_ATOM = {"a": "http://www.w3.org/2005/Atom"}


def reddit(query: str, subreddit: str | None = None, limit: int = 25) -> list[dict]:
    base = f"https://www.reddit.com/r/{subreddit}/search.rss" if subreddit else "https://www.reddit.com/search.rss"
    params = {"q": query, "sort": "relevance", "t": "year", "limit": min(limit, 100), "type": "link"}
    if subreddit:
        params["restrict_sr"] = "on"
    body = http.fetch(base, params, source="reddit", expect="text")
    root = ET.fromstring(body)
    out = []
    for e in root.findall("a:entry", _ATOM):
        link = e.find("a:link", _ATOM)
        url = link.get("href") if link is not None else None
        title = clean(e.findtext("a:title", default="", namespaces=_ATOM))
        content = clean(e.findtext("a:content", default="", namespaces=_ATOM))
        content = content.replace("submitted by", " ").replace("[link] [comments]", "")
        cat = e.find("a:category", _ATOM)
        out.append({
            "source": "reddit", "layer": "scattered",
            "external_id": e.findtext("a:id", default=url, namespaces=_ATOM), "url": url,
            "title": title, "text": f"{title}. {content}".strip(),
            "author": e.findtext("a:author/a:name", default=None, namespaces=_ATOM),
            "published_at": e.findtext("a:published", default=None, namespaces=_ATOM)
            or e.findtext("a:updated", default=None, namespaces=_ATOM),
            "engagement": 0.0,
            "extra": {"subreddit": cat.get("term") if cat is not None else subreddit},
        })
    return out


# ------------------------------------------------------------------------ Lemmy
def lemmy(query: str, instance: str = "lemmy.world", limit: int = 30) -> list[dict]:
    data = http.fetch(f"https://{instance}/api/v3/search",
                      {"q": query, "type_": "Posts", "limit": min(limit, 50), "sort": "TopAll"},
                      source="lemmy")
    out = []
    for p in data.get("posts", []):
        post, counts = p.get("post", {}), p.get("counts", {})
        title = clean(post.get("name"))
        out.append({
            "source": "lemmy", "layer": "scattered", "external_id": post.get("ap_id"),
            "url": post.get("ap_id"), "title": title,
            "text": f"{title}. {clean(post.get('body'))}".strip(),
            "author": (p.get("creator") or {}).get("name"), "published_at": post.get("published"),
            "engagement": _eng(counts.get("score"), counts.get("comments")),
            "extra": {"community": (p.get("community") or {}).get("name")},
        })
    return out


# --------------------------------------------------------------------- Mastodon
def mastodon_tag(tag: str, instance: str = "mastodon.social", limit: int = 40) -> list[dict]:
    tag = "".join(ch for ch in tag if ch.isalnum())
    data = http.fetch(f"https://{instance}/api/v1/timelines/tag/{quote(tag)}", {"limit": min(limit, 40)},
                      source="mastodon")
    out = []
    for s in data:
        txt = clean(s.get("content"))
        if not txt:
            continue
        out.append({
            "source": "mastodon", "layer": "scattered", "external_id": s.get("uri"),
            "url": s.get("url") or s.get("uri"), "title": txt[:120], "text": txt,
            "author": (s.get("account") or {}).get("acct"), "published_at": s.get("created_at"),
            "engagement": _eng(s.get("favourites_count"), s.get("reblogs_count"), s.get("replies_count")),
            "extra": {"lang": s.get("language")},
        })
    return out


# ------------------------------------------------------------------------ GDELT
def gdelt(query: str, limit: int = 50, timespan: str = "3m", country: str | None = None) -> list[dict]:
    """Global news (100+ languages, translated) via GDELT DOC 2.0."""
    q = query
    if country:
        q += f" sourcecountry:{country.replace(' ', '')}"
    data = http.fetch("https://api.gdeltproject.org/api/v2/doc/doc",
                      {"query": q, "mode": "artlist", "maxrecords": min(limit, 250), "format": "json",
                       "timespan": timespan, "sort": "hybridrel"},
                      source="gdelt")
    out = []
    for a in (data or {}).get("articles", []):
        title = clean(a.get("title"))
        sd = a.get("seendate")
        pub = None
        if sd:
            try:
                pub = datetime.strptime(sd, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat()
            except ValueError:
                pub = sd
        out.append({
            "source": "gdelt", "layer": "visible", "external_id": a.get("url"), "url": a.get("url"),
            "title": title, "text": title, "author": a.get("domain"), "published_at": pub,
            "engagement": 0.0,
            "extra": {"sourcecountry": a.get("sourcecountry"), "language": a.get("language")},
        })
    return out


# ------------------------------------------------------------------ Google News
def google_news(query: str, hl: str = "en-US", gl: str = "US", limit: int = 40) -> list[dict]:
    body = http.fetch("https://news.google.com/rss/search",
                      {"q": query, "hl": hl, "gl": gl, "ceid": f"{gl}:{hl.split('-')[0]}"},
                      source="googlenews", expect="text")
    root = ET.fromstring(body)
    out = []
    for it in root.iter("item"):
        title = clean(it.findtext("title"))
        pub = it.findtext("pubDate")
        try:
            pub = parsedate_to_datetime(pub).isoformat() if pub else None
        except (TypeError, ValueError):
            pass
        src = it.find("source")
        out.append({
            "source": "googlenews", "layer": "visible", "external_id": it.findtext("guid") or it.findtext("link"),
            "url": it.findtext("link"), "title": title,
            "text": f"{title}. {clean(it.findtext('description'))}",
            "author": src.text if src is not None else None, "published_at": pub, "engagement": 0.0,
            "extra": {"gl": gl},
        })
        if len(out) >= limit:
            break
    return out


# ------------------------------------------------- Google Autocomplete (latent)
SUGGEST_TEMPLATES = [
    "where to buy {x} in", "where can i get {x} in", "{x} price in", "why is {x} so expensive in",
    "{x} shortage in", "how to get {x} in", "{x} not available in", "{x} supplier in",
    "who repairs {x} in", "cheap {x} in", "{x} for rent in", "{x} near me",
]


def google_suggest(phrase: str, hl: str = "en", gl: str | None = None) -> list[str]:
    params = {"client": "firefox", "q": phrase, "hl": hl}
    if gl:
        params["gl"] = gl
    data = http.fetch("https://suggestqueries.google.com/complete/search", params, source="googlesuggest")
    return [s for s in (data[1] if isinstance(data, list) and len(data) > 1 else []) if s]


def search_demand(thing: str, place: str | None = None, templates: list[str] | None = None,
                  gl: str | None = None) -> list[dict]:
    """Real aggregated search demand: autocomplete completions reveal what many people type.

    Each completion is a latent-need signal. Completions that name a place show where
    the demand is (e.g. "where can i get solar freezer in benin city").
    """
    out = []
    for tpl in templates or SUGGEST_TEMPLATES:
        prefix = tpl.format(x=thing)
        if place:
            prefix = f"{prefix} {place}"
        try:
            sugg = google_suggest(prefix + " ", gl=gl)
        except http.FetchError:
            continue
        for rank, s in enumerate(sugg):
            out.append({
                "source": "googlesuggest", "layer": "invisible",
                "external_id": f"suggest:{s}", "url": "https://www.google.com/search?q=" + quote(s),
                "title": s, "text": s, "author": None, "published_at": datetime.now(timezone.utc).date().isoformat(),
                # autocomplete rank is a (coarse) popularity proxy
                "engagement": round(1.0 - rank / 10.0, 2),
                "extra": {"prefix": prefix, "rank": rank, "template": tpl},
            })
    return out


# --------------------------------------------------------- openFDA drug shortages
def fda_drug_shortages(query: str | None = None, limit: int = 100) -> list[dict]:
    search = 'status:"Current"'
    if query:
        search += f' AND (generic_name:"{query}" OR therapeutic_category:"{query}")'
    data = http.fetch("https://api.fda.gov/drug/shortages.json", {"search": search, "limit": min(limit, 1000)},
                      source="openfda")
    out = []
    for r in data.get("results", []):
        name = r.get("generic_name") or ""
        cats = r.get("therapeutic_category") or []
        txt = (f"Current US drug shortage: {name} ({r.get('dosage_form', '')}). Availability: {r.get('availability', '')}. "
               f"Reason: {r.get('shortage_reason', '')}. Company: {r.get('company_name', '')}. "
               f"Category: {', '.join(cats)}. {r.get('related_info', '')}")
        out.append({
            "source": "openfda", "layer": "structural",
            "external_id": f"{r.get('package_ndc')}:{r.get('update_date')}",
            "url": "https://www.accessdata.fda.gov/scripts/drugshortages/default.cfm",
            "title": f"Drug shortage: {name}", "text": txt, "author": r.get("company_name"),
            "published_at": r.get("update_date"), "engagement": 0.5,
            "extra": {"availability": r.get("availability"), "reason": r.get("shortage_reason"),
                      "categories": cats, "initial_posting_date": r.get("initial_posting_date")},
        })
    return out


# --------------------------------------------- SAM.gov sources-sought notices
def sam_sources_sought(query: str, limit: int = 25) -> list[dict]:
    """US federal 'Sources Sought' / RFI notices: government buyers searching for capabilities."""
    data = http.fetch("https://sam.gov/api/prod/sgs/v1/search/",
                      {"index": "opp", "q": f'"sources sought" {query}', "page": 0, "size": min(limit, 100),
                       "mode": "search", "is_active": "true", "sort": "-relevance"},
                      source="samgov")
    out = []
    for r in (data.get("_embedded") or {}).get("results", []):
        desc = " ".join(clean(d.get("content")) for d in r.get("descriptions", []))[:3000]
        rid = r.get("_id")
        out.append({
            "source": "samgov", "layer": "structural", "external_id": rid,
            "url": f"https://sam.gov/opp/{rid}/view", "title": clean(r.get("title")),
            "text": f"{clean(r.get('title'))}. {desc}", "author": None,
            "published_at": r.get("publishDate"), "engagement": 0.4,
            "extra": {"type": (r.get("type") or {}).get("value"), "solicitation": r.get("solicitationNumber"),
                      "response_date": r.get("responseDate"), "canceled": r.get("isCanceled")},
        })
    return out


# ------------------------------------------- World Bank procurement notices
def worldbank_procurement(query: str, limit: int = 50) -> list[dict]:
    data = http.fetch("https://search.worldbank.org/api/v2/procnotices",
                      {"format": "json", "rows": min(limit, 100), "qterm": query,
                       "fl": "id,project_name,notice_type,bid_description,project_ctry_name,submission_date,noticedate,project_id,procurement_group"},
                      source="worldbank_procurement")
    out = []
    for n in data.get("procnotices", []):
        desc = clean(n.get("bid_description"))
        out.append({
            "source": "worldbank_procurement", "layer": "structural", "external_id": n.get("id"),
            "url": f"https://projects.worldbank.org/en/projects-operations/procurement-detail/{n.get('id')}",
            "title": desc[:200], "text": f"{n.get('notice_type')}: {desc} — {n.get('project_name')} ({n.get('project_ctry_name')})",
            "author": n.get("project_ctry_name"), "published_at": n.get("submission_date"), "engagement": 0.3,
            "extra": {"notice_type": n.get("notice_type"), "country": n.get("project_ctry_name"),
                      "project_id": n.get("project_id")},
        })
    return out
