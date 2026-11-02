"""Live self-test: calls every real data source once and reports PASS/FAIL with item counts.

    python -m aduns selftest
"""
from __future__ import annotations

import time

from .sources import capabilities as C
from .sources import institutional as I
from .sources import needs as N
from .sources import social as S

CHECKS = [
    ("Google Trends (KE)", lambda: S.google_trends("KE")),
    ("Google autocomplete (BR, pt)", lambda: S.autocomplete("onde comprar ", "BR", "pt")),
    ("Google News (SN, fr)", lambda: S.google_news('"pénurie"', "SN", "fr", 10)),
    ("Bluesky (es)", lambda: S.bluesky("escasez", "es", 10)),
    ("YouTube crawl (NG)", lambda: S.youtube_search("shortage Nigeria", "NG", "en", 5)),
    ("Telegram crawl", lambda: S.telegram_channel("bbcrussian")),
    ("Reddit RSS", lambda: S.reddit_subreddit("india", 10)),
    ("Mastodon (ja)", lambda: S.mastodon_tag("不足", "ja", 10)),
    ("Lemmy", lambda: S.lemmy_search("shortage", "en", 5)),
    ("Google Play reviews (NG)", lambda: S.play_reviews("com.kudabank.app", "NG")),
    ("GDELT local press (IN)", lambda: S.gdelt_country('"shortage of"', "India", 10)),
    ("WFP market prices (KEN)", lambda: I.wfp_price_spikes("Kenya", "KEN", min_rise=-1)),
    ("GDACS alerts", lambda: I.gdacs("Green")),
    ("Prozorro failed tenders", lambda: I.prozorro_failed(1)),
    ("SECOP cancelled tenders", lambda: I.secop_cancelled(10)),
    ("SAM.gov sources sought", lambda: I.sam_sources_sought("", 5)),
    ("World Bank procurement", lambda: I.worldbank_procurement("Kenya", 5)),
    ("openFDA shortages", lambda: I.fda_shortages(20)),
    ("CFPB complaints", lambda: I.cfpb_complaints(5)),
    ("Hacker News", lambda: N.hackernews("shortage", 5, days=30)),
    ("Stack Exchange", lambda: N.stackexchange("can't find", "diy", 5)),
    ("Google Patents", lambda: C.google_patents("solar dryer", 5)),
    ("Crossref", lambda: C.crossref("solar dryer", 5)),
    ("Europe PMC", lambda: C.europepmc("oxygen concentrator", 5)),
    ("GitHub", lambda: C.github_repos("solar dryer", 5)),
    ("World Bank projects", lambda: C.worldbank_programs("rural water", 5)),
    ("Wikidata orgs", lambda: C.wikidata_orgs("refrigeration", 5)),
    ("ClinicalTrials.gov", lambda: C.clinical_trials("dialysis", 5)),
    ("Play local apps (KE)", lambda: C.local_apps("pharmacy", "KE", 2)),
    ("OSM providers (Nairobi)", lambda: C.osm_providers("pharmacy", "KE", ["Nairobi"], 3)),
    ("Translation (MinT)", lambda: [x for x in __import__("aduns.translate", fromlist=["x"]).batch_to_english(
        ["uhaba wa maji"], "sw") if x]),
]


def run() -> int:
    fails = 0
    print(f"{'source':34} {'result':7} {'items':>5}  time   sample")
    for name, fn in CHECKS:
        t = time.time()
        try:
            r = fn()
            n = len(r)
            sample = (r[0].get("title") if isinstance(r[0], dict) else str(r[0]))[:60] if r else ""
            status = "PASS" if n else "EMPTY"
        except Exception as e:  # noqa: BLE001
            n, status, sample = 0, "FAIL", f"{type(e).__name__}: {str(e)[:70]}"
            fails += 1
        print(f"{name:34} {status:7} {n:5}  {time.time() - t:5.1f}s {sample}")
    print(f"\n{len(CHECKS) - fails}/{len(CHECKS)} sources reachable")
    return fails
