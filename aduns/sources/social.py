"""Per-country social media, video, messaging, app-store and search-behaviour connectors.

All free and keyless. Where no free API exists, public pages are crawled politely
(rate-limited, cached, identifying User-Agent): YouTube search pages and public Telegram channel previews.

Platforms with no free legal access (X/Twitter, Facebook, Instagram, TikTok, WhatsApp groups) are not
crawled: they are login-walled and their terms forbid it. Their content is still reached indirectly
through news, YouTube, Bluesky, Telegram and field scouts.
"""
from __future__ import annotations

import html
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

from .. import config, http
from ..nlp import clean

BROWSER_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 "
              "AdunsDiscovery")


def _since(days: int | None = None) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days or config.MAX_AGE_DAYS)


def _rec(source, layer, ext_id, url, title, text, author=None, published=None, engagement=0.0, extra=None):
    return {"source": source, "layer": layer, "external_id": ext_id, "url": url, "title": clean(title)[:300],
            "text": clean(text), "author": author, "published_at": published, "engagement": engagement,
            "extra": extra or {}}


# ----------------------------------------------------------------------- Bluesky
def bluesky(query: str, lang: str | None = None, limit: int = 50, days: int = 30) -> list[dict]:
    params = {"q": query, "limit": min(limit, 100), "sort": "latest",
              "since": _since(days).strftime("%Y-%m-%dT%H:%M:%SZ")}
    if lang:
        params["lang"] = lang
    data = http.fetch("https://api.bsky.app/xrpc/app.bsky.feed.searchPosts", params, source="bluesky", ttl=1800)
    out = []
    for p in data.get("posts", []):
        rec = p.get("record") or {}
        text = rec.get("text") or ""
        handle = (p.get("author") or {}).get("handle", "")
        rkey = p["uri"].rsplit("/", 1)[-1]
        eng = (p.get("likeCount") or 0) + (p.get("repostCount") or 0) + (p.get("replyCount") or 0)
        out.append(_rec("bluesky", "scattered", p["uri"], f"https://bsky.app/profile/{handle}/post/{rkey}",
                        text[:140], text, handle, rec.get("createdAt") or p.get("indexedAt"),
                        min(1.0, eng / 50), {"langs": rec.get("langs"), "query": query}))
    return out


# ------------------------------------------------------------------ Google Trends
_HT = "{https://trends.google.com/trending/rss}"


def google_trends(geo_iso2: str) -> list[dict]:
    """Today's rising searches in a country (with the news stories explaining them)."""
    try:
        body = http.fetch("https://trends.google.com/trending/rss", {"geo": geo_iso2.upper()}, source="googletrends",
                          ttl=3600, expect="text", retries=0)
    except http.FetchError as e:
        if "HTTP 404" in str(e) or "HTTP 400" in str(e):
            return []          # Google Trends has no daily feed for this country
        raise
    root = ET.fromstring(body)
    out = []
    for it in root.iter("item"):
        title = it.findtext("title") or ""
        news = [(n.findtext(f"{_HT}news_item_title") or "", n.findtext(f"{_HT}news_item_url") or "")
                for n in it.findall(f"{_HT}news_item")]
        traffic = it.findtext(f"{_HT}approx_traffic") or ""
        pub = it.findtext("pubDate")
        try:
            pub = parsedate_to_datetime(pub).isoformat() if pub else None
        except (TypeError, ValueError):
            pub = None
        n_traffic = int(re.sub(r"\D", "", traffic) or 0)
        text = f"{title}. " + " | ".join(t for t, _ in news)
        out.append(_rec("googletrends", "invisible", f"trend:{geo_iso2}:{title}:{(pub or '')[:10]}",
                        news[0][1] if news else f"https://trends.google.com/trending?geo={geo_iso2}",
                        title, text, None, pub, min(1.0, n_traffic / 100000),
                        {"traffic": traffic, "news": news[:3], "geo": geo_iso2}))
    return out


# ------------------------------------------------------------------------ YouTube
def _yt_age_to_date(s: str | None) -> str | None:
    if not s:
        return None
    m = re.search(r"(\d+)\s+(second|minute|hour|day|week|month|year)", s)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    days = {"second": 0, "minute": 0, "hour": 0, "day": 1, "week": 7, "month": 30, "year": 365}[unit] * n
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def youtube_search(query: str, gl: str = "US", hl: str = "en", limit: int = 20) -> list[dict]:
    """Crawl YouTube search results uploaded this month (no API key)."""
    body = http.fetch("https://www.youtube.com/results",
                      {"search_query": query, "sp": "EgIIBA==", "gl": gl.upper(), "hl": hl},
                      source="youtube", ttl=3 * 3600, expect="text",
                      headers={"User-Agent": BROWSER_UA, "Accept-Language": f"{hl},en;q=0.5"})
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", body, re.S)
    if not m:
        return []
    data = json.loads(m.group(1))
    vids: list[dict] = []

    def walk(o):
        if isinstance(o, dict):
            if "videoRenderer" in o:
                vids.append(o["videoRenderer"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(data)
    out = []
    for v in vids[:limit]:
        vid = v.get("videoId")
        title = "".join(r.get("text", "") for r in (v.get("title") or {}).get("runs", []))
        snippet = " ".join("".join(r.get("text", "") for r in s.get("snippetText", {}).get("runs", []))
                           for s in v.get("detailedMetadataSnippets", []) or [])
        views = re.sub(r"\D", "", (v.get("viewCountText") or {}).get("simpleText", "") or "0") or "0"
        owner = ((v.get("ownerText") or {}).get("runs") or [{}])[0].get("text")
        out.append(_rec("youtube", "scattered", vid, f"https://www.youtube.com/watch?v={vid}", title,
                        f"{title}. {snippet}", owner, _yt_age_to_date((v.get("publishedTimeText") or {}).get("simpleText")),
                        min(1.0, int(views) / 100000), {"views": int(views), "gl": gl}))
        if out[-1]["published_at"] is None:  # search was restricted to "uploaded this month"
            out[-1]["published_at"] = datetime.now(timezone.utc).isoformat()
            out[-1]["extra"]["approx_date"] = True
    return out


# ----------------------------------------------------------------------- Telegram
_TG_RE = re.compile(r'data-post="([^"]+)".*?<div class="tgme_widget_message_text[^>]*>(.*?)</div>.*?'
                    r'<time datetime="([^"]+)"', re.S)
TG_LINK = re.compile(r"(?:https?://)?t\.me/(?:s/)?([A-Za-z][A-Za-z0-9_]{4,31})\b")


def telegram_channel(channel: str) -> list[dict]:
    """Public channel web preview (t.me/s/<channel>) — the latest ~20 posts."""
    body = http.fetch(f"https://t.me/s/{channel}", None, source="telegram", ttl=1800, expect="text",
                      headers={"User-Agent": BROWSER_UA})
    views = re.findall(r'<span class="tgme_widget_message_views">([^<]+)</span>', body)
    out = []
    for i, (post, raw, dt) in enumerate(_TG_RE.findall(body)):
        text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
        v = views[i] if i < len(views) else "0"
        mult = 1000 if v.endswith("K") else 1_000_000 if v.endswith("M") else 1
        try:
            nviews = float(v.rstrip("KM")) * mult
        except ValueError:
            nviews = 0
        out.append(_rec("telegram", "scattered", post, f"https://t.me/{post}", text[:140], text, channel, dt,
                        min(1.0, nviews / 50000), {"channel": channel}))
    return out


# ------------------------------------------------------------------- Reddit (RSS)
_ATOM = {"a": "http://www.w3.org/2005/Atom"}


def reddit_subreddit(sub: str, limit: int = 50) -> list[dict]:
    body = http.fetch(f"https://www.reddit.com/r/{sub}/new/.rss", {"limit": limit}, source="reddit", ttl=1800,
                      expect="text")
    root = ET.fromstring(body)
    out = []
    for e in root.findall("a:entry", _ATOM):
        link = e.find("a:link", _ATOM)
        title = e.findtext("a:title", default="", namespaces=_ATOM)
        content = clean(e.findtext("a:content", default="", namespaces=_ATOM)).replace("submitted by", " ")
        content = content.replace("[link] [comments]", "")
        out.append(_rec("reddit", "scattered", e.findtext("a:id", default="", namespaces=_ATOM),
                        link.get("href") if link is not None else None, title, f"{title}. {content}",
                        e.findtext("a:author/a:name", default=None, namespaces=_ATOM),
                        e.findtext("a:published", default=None, namespaces=_ATOM)
                        or e.findtext("a:updated", default=None, namespaces=_ATOM), 0.0, {"subreddit": sub}))
    return out


# ------------------------------------------------------------- Mastodon / Lemmy
MASTODON_BY_LANG = {"ja": "mstdn.jp", "fr": "piaille.fr", "it": "mastodon.uno", "es": "masto.es",
                    "de": "mastodon.social", "pt": "mastodon.social", "en": "mastodon.social"}
LEMMY_BY_LANG = {"de": "feddit.org", "fr": "jlai.lu", "nl": "feddit.nl", "fi": "sopuli.xyz", "it": "feddit.it",
                 "en": "lemmy.world", "es": "lemmy.world", "pt": "lemmy.world"}


def mastodon_tag(tag: str, lang: str = "en", limit: int = 40) -> list[dict]:
    inst = MASTODON_BY_LANG.get(lang, "mastodon.social")
    t = re.sub(r"[^\w]", "", tag)
    if not t:
        return []
    data = http.fetch(f"https://{inst}/api/v1/timelines/tag/{quote(t)}", {"limit": min(limit, 40)},
                      source="mastodon", ttl=1800)
    out = []
    for s in data:
        txt = clean(s.get("content"))
        if txt:
            eng = (s.get("favourites_count") or 0) + (s.get("reblogs_count") or 0) + (s.get("replies_count") or 0)
            out.append(_rec("mastodon", "scattered", s.get("uri"), s.get("url") or s.get("uri"), txt[:140], txt,
                            (s.get("account") or {}).get("acct"), s.get("created_at"), min(1.0, eng / 50),
                            {"lang": s.get("language"), "instance": inst}))
    return out


def lemmy_search(query: str, lang: str = "en", limit: int = 30) -> list[dict]:
    inst = LEMMY_BY_LANG.get(lang, "lemmy.world")
    params = {"q": query, "type_": "Posts", "limit": min(limit, 50), "sort": "New"}
    try:
        data = http.fetch(f"https://{inst}/api/v3/search", params, source="lemmy", ttl=1800, retries=0)
    except http.FetchError:
        if inst == "lemmy.world":
            raise
        inst = "lemmy.world"
        data = http.fetch(f"https://{inst}/api/v3/search", params, source="lemmy", ttl=1800)
    out = []
    for p in data.get("posts", []):
        post, counts = p.get("post", {}), p.get("counts", {})
        out.append(_rec("lemmy", "scattered", post.get("ap_id"), post.get("ap_id"), post.get("name"),
                        f"{post.get('name')}. {clean(post.get('body'))}", (p.get("creator") or {}).get("name"),
                        post.get("published"), min(1.0, ((counts.get("score") or 0) + (counts.get("comments") or 0)) / 100),
                        {"instance": inst}))
    return out


# ------------------------------------------------------------- App Store reviews
APP_CATEGORIES = ["bank", "electricity", "water", "pharmacy", "hospital", "taxi", "delivery", "government",
                  "internet", "insurance", "loan", "school", "transport", "farm", "health", "mobile money"]


def appstore_search(term: str, country_iso2: str, limit: int = 8) -> list[dict]:
    data = http.fetch("https://itunes.apple.com/search", {"term": term, "country": country_iso2.lower(),
                                                          "entity": "software", "limit": limit},
                      source="appstore", ttl=24 * 3600)
    return data.get("results", [])


def appstore_reviews(app_id: int, country_iso2: str, app_name: str = "") -> list[dict]:
    """Most recent customer reviews of an app in one country (complaints = unmet service needs)."""
    url = f"https://itunes.apple.com/{country_iso2.lower()}/rss/customerreviews/page=1/id={app_id}/sortby=mostrecent/json"
    data = http.fetch(url, None, source="appstore", ttl=6 * 3600)
    entries = (data.get("feed") or {}).get("entry") or []
    if isinstance(entries, dict):
        entries = [entries]
    out = []
    for e in entries:
        if "im:rating" not in e:
            continue
        rating = int(e["im:rating"]["label"])
        title = (e.get("title") or {}).get("label", "")
        body = (e.get("content") or {}).get("label", "")
        rid = (e.get("id") or {}).get("label")
        out.append(_rec("appstore", "scattered", f"{country_iso2}:{rid}",
                        f"https://apps.apple.com/{country_iso2.lower()}/app/id{app_id}",
                        f"{app_name}: {title}", f"[{app_name}] {title}. {body}",
                        (e.get("author") or {}).get("name", {}).get("label"), (e.get("updated") or {}).get("label"),
                        0.2 if rating <= 2 else 0.0, {"rating": rating, "app": app_name, "app_id": app_id}))
    return out


# --------------------------------------------------------------- Google News
_NEWS_EDITIONS = None


def google_news(query: str, iso2: str, lang: str, limit: int = 40) -> list[dict]:
    """Country edition in the local language; falls back to the language edition + query."""
    q = f"{query} when:30d"
    tried = [(f"{lang}-{iso2.upper()}" if lang == "en" else lang, iso2.upper()), ("en", "US")]
    if lang in ("es",):
        tried.insert(1, ("es-419", "US"))
    for hl, gl in tried:
        try:
            body = http.fetch("https://news.google.com/rss/search",
                              {"q": q, "hl": hl, "gl": gl, "ceid": f"{gl}:{hl.split('-')[0] if hl != 'es-419' else hl}"},
                              source="googlenews", ttl=3600, expect="text", retries=0)
        except http.FetchError:
            continue
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            continue
        out = []
        for it in root.iter("item"):
            title = clean(it.findtext("title"))
            pub = it.findtext("pubDate")
            try:
                pub = parsedate_to_datetime(pub).isoformat() if pub else None
            except (TypeError, ValueError):
                pub = None
            src = it.find("source")
            out.append(_rec("googlenews", "visible", it.findtext("guid") or it.findtext("link"), it.findtext("link"),
                            title, title, src.text if src is not None else None, pub, 0.0, {"hl": hl, "gl": gl}))
            if len(out) >= limit:
                break
        return out
    return []


# ------------------------------------------------------------ Autocomplete demand
def autocomplete(prefix: str, iso2: str, lang: str) -> list[dict]:
    data = http.fetch("https://suggestqueries.google.com/complete/search",
                      {"client": "firefox", "q": prefix, "hl": lang, "gl": iso2.lower()},
                      source="googlesuggest", ttl=12 * 3600)
    sugg = data[1] if isinstance(data, list) and len(data) > 1 else []
    now = datetime.now(timezone.utc).date().isoformat()
    return [_rec("googlesuggest", "invisible", f"suggest:{iso2}:{s}", "https://www.google.com/search?q=" + quote(s),
                 s, s, None, now, round(1 - r / 10, 2), {"prefix": prefix, "rank": r, "gl": iso2, "hl": lang})
            for r, s in enumerate(sugg) if s and s.strip().lower() != prefix.strip().lower()]


# ------------------------------------------------------------------- GDELT
def gdelt_country(query: str, country_name: str, limit: int = 75, timespan: str = "1m") -> list[dict]:
    """Local press of one country (GDELT translingual: English query terms match translated coverage)."""
    data = http.fetch("https://api.gdeltproject.org/api/v2/doc/doc",
                      {"query": f"{query} sourcecountry:{country_name.replace(' ', '').lower()}", "mode": "artlist",
                       "maxrecords": min(limit, 250), "format": "json", "timespan": timespan, "sort": "datedesc"},
                      source="gdelt", ttl=3600, retries=1)
    out = []
    for a in (data or {}).get("articles", []):
        sd = a.get("seendate")
        try:
            pub = datetime.strptime(sd, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat() if sd else None
        except ValueError:
            pub = None
        out.append(_rec("gdelt", "visible", a.get("url"), a.get("url"), a.get("title"), a.get("title"), a.get("domain"),
                        pub, 0.0, {"sourcecountry": a.get("sourcecountry"), "language": a.get("language")}))
    return out


def now_ts() -> float:
    return time.time()


# ----------------------------------------------------------- Google Play reviews
_PLAY_REVIEW = re.compile(
    r'aria-label="Rated (\d) stars out of five stars".*?<span class="bp9Aid">([^<]+)</span>.*?'
    r'<div class="h3YV2d">(.*?)</div>', re.S)


def play_search(term: str, iso2: str, lang: str = "en", limit: int = 5) -> list[str]:
    body = http.fetch("https://play.google.com/store/search", {"q": term, "c": "apps", "hl": lang, "gl": iso2.upper()},
                      source="googleplay", ttl=24 * 3600, expect="text", headers={"User-Agent": BROWSER_UA})
    ids = []
    for m in re.finditer(r"details\?id=([a-zA-Z0-9._]+)", body):
        if m.group(1) not in ids:
            ids.append(m.group(1))
    return ids[:limit]


def play_reviews(app_id: str, iso2: str, lang: str = "en") -> list[dict]:
    """Featured recent user reviews on an app's Play Store page (low ratings = unmet service needs)."""
    body = http.fetch("https://play.google.com/store/apps/details", {"id": app_id, "hl": lang, "gl": iso2.upper()},
                      source="googleplay", ttl=12 * 3600, expect="text", headers={"User-Agent": BROWSER_UA})
    name_m = re.search(r'<h1[^>]*><span[^>]*>([^<]+)</span>', body)
    name = html.unescape(name_m.group(1)) if name_m else app_id
    out = []
    for rating, date_s, raw in _PLAY_REVIEW.findall(body):
        text = html.unescape(re.sub(r"<[^>]+>", " ", raw)).strip()
        try:
            pub = datetime.strptime(date_s.strip(), "%B %d, %Y").replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            pub = None
        out.append(_rec("googleplay", "scattered", f"{app_id}:{iso2}:{hash(text) & 0xffffffff}",
                        f"https://play.google.com/store/apps/details?id={app_id}&gl={iso2}", f"{name}: {text[:100]}",
                        f"[{name}] {text}", None, pub, 0.3 if int(rating) <= 2 else 0.0,
                        {"rating": int(rating), "app": name, "app_id": app_id, "gl": iso2}))
    return out
