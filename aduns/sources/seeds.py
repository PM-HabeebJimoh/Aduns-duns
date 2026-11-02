"""Per-country local channel seeding from Wikidata (free) + YouTube channel feeds.

Wikidata records the official Telegram usernames (P3789), subreddits (P3984) and YouTube channel ids (P2397)
of a country's media outlets, broadcasters, newspapers, agencies, municipalities and companies. These become
seeds in `source_registry`, so every country starts with its *own* local channels instead of global ones.
Snowball discovery (links found in collected posts) then keeps growing the map.
"""
from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET

from .. import db, http
from ..nlp import clean
from .social import _rec

_MEDIA_TYPES = "wd:Q11032 wd:Q1110794 wd:Q1616075 wd:Q14350 wd:Q1153191 wd:Q192283 wd:Q2001305 wd:Q17232649"


def wikidata_channels(iso3: str) -> dict[str, list[tuple[str, str]]]:
    q = f"""SELECT ?item ?itemLabel ?tg ?yt ?sr WHERE {{
      ?c wdt:P298 "{iso3}". ?item wdt:P17 ?c.
      {{ ?item wdt:P3789 ?tg }} UNION {{ ?item wdt:P3984 ?sr }} UNION
      {{ ?item wdt:P2397 ?yt. ?item wdt:P31/wdt:P279? ?t. VALUES ?t {{ {_MEDIA_TYPES} }} }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }} LIMIT 600"""
    data = http.fetch("https://query.wikidata.org/sparql", {"query": q, "format": "json"}, source="wikidata",
                      ttl=30 * 86400, headers={"Accept": "application/sparql-results+json"})
    out: dict[str, list[tuple[str, str]]] = {"telegram": [], "youtube_channel": [], "subreddit": []}
    for b in data["results"]["bindings"]:
        label = b.get("itemLabel", {}).get("value", "")
        if "tg" in b:
            out["telegram"].append((b["tg"]["value"].lstrip("@"), label))
        if "yt" in b:
            out["youtube_channel"].append((b["yt"]["value"], label))
        if "sr" in b:
            sr = b["sr"]["value"]
            norm_l = re.sub(r"[^a-z0-9]", "", label.lower())
            norm_s = re.sub(r"[^a-z0-9]", "", sr.lower())
            # keep place/community subreddits (r/Nigeria, r/Oromia), not topical ones linked from many items
            if norm_l and (norm_s == norm_l or (" " not in label and norm_l in norm_s)):
                out["subreddit"].append((sr, label))
    for k in out:
        out[k] = list(dict.fromkeys(out[k]))
    return out


def seed_country(iso3: str, force: bool = False) -> dict:
    """Insert Wikidata seeds for a country into source_registry (refreshed every 30 days)."""
    key = f"seeded:{iso3}"
    st = db.q1("SELECT at FROM daemon_state WHERE key=?", (key,))
    if st and not force and time.time() - st["at"] < 30 * 86400:
        return {"skipped": True}
    ch = wikidata_channels(iso3)
    n = 0
    for kind, items in ch.items():
        for handle, label in items:
            if db.insert("source_registry", {"kind": kind, "handle": handle, "country": iso3,
                                             "discovered_from": f"wikidata:{label}"[:200], "discovered_at": time.time()},
                         ignore=True):
                n += 1
    with db.tx() as c:
        c.execute("INSERT OR REPLACE INTO daemon_state (key, value, at) VALUES (?,?,?)", (key, str(n), time.time()))
    return {k: len(v) for k, v in ch.items()} | {"new": n}


_A = {"a": "http://www.w3.org/2005/Atom", "media": "http://search.yahoo.com/mrss/", "yt": "http://www.youtube.com/xml/schemas/2015"}


def youtube_channel_feed(channel_id: str) -> list[dict]:
    """Latest ~15 videos of a channel (official RSS; no key)."""
    body = http.fetch("https://www.youtube.com/feeds/videos.xml", {"channel_id": channel_id}, source="youtube_rss",
                      ttl=3 * 3600, expect="text")
    root = ET.fromstring(body)
    author = root.findtext("a:title", default="", namespaces=_A)
    out = []
    for e in root.findall("a:entry", _A):
        vid = e.findtext("yt:videoId", default="", namespaces=_A)
        title = e.findtext("a:title", default="", namespaces=_A)
        desc = e.findtext("media:group/media:description", default="", namespaces=_A)
        views = e.find("media:group/media:community/media:statistics", _A)
        nviews = int(views.get("views", 0)) if views is not None else 0
        out.append(_rec("youtube_channel", "visible", vid, f"https://www.youtube.com/watch?v={vid}", title,
                        f"{title}. {clean(desc)[:500]}", author, e.findtext("a:published", default=None, namespaces=_A),
                        min(1.0, nviews / 100000), {"channel": channel_id, "views": nviews}))
    return out
