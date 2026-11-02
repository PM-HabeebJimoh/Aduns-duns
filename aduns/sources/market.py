"""Market data for opportunity design — real, free, keyless.

* UN Comtrade (public preview API): a country's imports of a product (value, volume, unit value, supplier
  countries) → market size, landed import price, supply concentration, sourcing options.
* HS nomenclature (Comtrade reference) → maps a need object ("milk", "solar freezer") to HS6 codes.
* Made-in-China.com search pages → real FOB wholesale prices from manufacturers (import / resell routes).
* open.er-api.com → daily exchange rates; Wikidata → each country's currency (ISO 4217).
* Local price mentions → prices people actually quote in the collected signals ("KSh 70 per litre").
* World Bank lending rate (official, secondary) → cost of working capital.
"""
from __future__ import annotations

import html
import re
import statistics
import time

from .. import geo, http, nlp
from .social import BROWSER_UA

_REF = "https://comtradeapi.un.org/files/v1/app/reference"


# ------------------------------------------------------------------- HS codes
def _hs_table() -> list[dict]:
    data = http.fetch(f"{_REF}/HS.json", None, source="comtrade", ttl=30 * 86400)
    return [r for r in data["results"] if r.get("aggrLevel") in (4, 6) and r["id"].isdigit()]


# Everyday need objects → HS headings (HS wording often never names the everyday product, e.g. diesel → 2710).
COMMON_HS = {
    "milk": ["0401", "0402"], "dairy": ["0401", "0402"], "cheese": ["0406"], "butter": ["0405"], "eggs": ["0407"],
    "rice": ["1006"], "maize": ["1005"], "corn": ["1005"], "wheat": ["1001"], "flour": ["1101"], "bread": ["1905"],
    "sugar": ["1701"], "cooking oil": ["1511", "1512", "1507"], "oil": ["2709", "2710"], "beans": ["0713"],
    "onion": ["0703"], "onions": ["0703"], "tomato": ["0702"], "potato": ["0701"], "meat": ["0201", "0207"],
    "fish": ["0302", "0303"], "coffee": ["0901"], "tea": ["0902"], "salt": ["2501"], "baby formula": ["1901"],
    "fuel": ["2710"], "diesel": ["2710"], "petrol": ["2710"], "gasoline": ["2710"], "kerosene": ["2710"],
    "gas": ["2711"], "lpg": ["2711"], "cooking gas": ["2711"], "coal": ["2701"], "electricity": ["2716"],
    "fertilizer": ["3102", "3105"], "fertiliser": ["3102", "3105"], "seeds": ["1209"], "pesticide": ["3808"],
    "medicines": ["3004"], "medicine": ["3004"], "drugs": ["3004"], "insulin": ["300431"], "vaccine": ["3002"],
    "vaccines": ["3002"], "antibiotics": ["3004"], "contraceptives": ["3006"], "syringes": ["9018"],
    "oxygen": ["2804"], "cement": ["2523"], "steel": ["7214", "7213"], "solar panel": ["854143"],
    "solar panels": ["854143"], "battery": ["8507"], "batteries": ["8507"], "generator": ["8502"],
    "inverter": ["850440"], "freezer": ["841830", "841840"], "fridge": ["841810", "841821"],
    "refrigerator": ["841810", "841821"], "phone": ["851713"], "phones": ["851713"], "laptop": ["847130"],
    "computer": ["8471"], "memory": ["8542"], "chips": ["8542"], "semiconductor": ["8542"], "tyres": ["4011"],
    "tires": ["4011"], "car": ["8703"], "cars": ["8703"], "spare parts": ["8708"], "water filter": ["842121"],
    "water": ["220190", "842121"], "pump": ["8413"], "tractor": ["8701"], "clothes": ["6109", "6203"],
    "shoes": ["6403", "6404"], "paper": ["4802"], "plastic": ["3901"], "fertilizers": ["3102", "3105"],
}


def hs_lookup(query: str, k: int = 3) -> list[dict]:
    """Best HS codes for a product phrase: curated everyday mapping first, then head-noun lexical match."""
    table = {r["id"]: r for r in _hs_table()}
    q_low = query.lower().strip()
    out: list[dict] = []
    keys = sorted(COMMON_HS, key=len, reverse=True)
    for key in keys:
        if re.search(rf"\b{re.escape(key)}\b", q_low):
            for code in COMMON_HS[key]:
                r = table.get(code)
                out.append({"hs": code, "description": (r["text"].split(" - ", 1)[-1] if r else key), "match": 1.5})
            break
    q = {t[:6] for t in nlp.tokens(query)}
    if q:
        scored = []
        for r in table.values():
            text = r["text"].split(" - ", 1)[-1].lower()
            if "legacy" in text:
                continue
            head = {t[:6] for t in nlp.tokens(re.split(r"[;,(]", text)[0])}
            toks = {t[:6] for t in nlp.tokens(text)}
            hit = len(q & toks)
            if not hit or not (q & head):      # the word must be the subject, not a modifier
                continue
            score = hit / len(q) + 0.3 * len(q & head) / len(q) + (0.1 if r["aggrLevel"] == 6 else 0) - len(toks) / 400
            scored.append((score, r))
        scored.sort(key=lambda x: -x[0])
        out += [{"hs": r["id"], "description": r["text"].split(" - ", 1)[-1], "match": round(sc, 3)} for sc, r in scored]
    seen, uniq = set(), []
    for c in out:
        if c["hs"] not in seen:
            seen.add(c["hs"])
            uniq.append(c)
    return uniq[:k]


# ------------------------------------------------------------------ Comtrade
def _m49() -> dict[str, int]:
    data = http.fetch(f"{_REF}/Reporters.json", None, source="comtrade", ttl=30 * 86400)
    out = {}
    for r in data["results"]:
        iso = r.get("reporterCodeIsoAlpha3")
        if iso and not r.get("isGroup"):
            out[iso] = r["reporterCode"]
    return out


def _partner_iso() -> dict[int, str]:
    data = http.fetch(f"{_REF}/partnerAreas.json", None, source="comtrade", ttl=30 * 86400)
    return {r["PartnerCode"]: r.get("PartnerCodeIsoAlpha3") for r in data["results"]}


def comtrade_flows(iso3: str, hs: str, flow: str = "M", years: tuple[int, ...] | None = None) -> dict | None:
    """Most recent available year of a country's imports (M) or exports (X) of an HS code."""
    code = _m49().get(iso3)
    if not code:
        return None
    this = time.gmtime().tm_year
    for year in years or (this - 1, this - 2, this - 3):
        try:
            data = http.fetch("https://comtradeapi.un.org/public/v1/preview/C/A/HS",
                              {"reporterCode": code, "period": year, "cmdCode": hs, "flowCode": flow},
                              source="comtrade", ttl=7 * 86400, retries=2)
        except http.FetchError:
            continue
        rows = data.get("data") or []
        if not rows:
            continue
        world = next((r for r in rows if r.get("partnerCode") == 0), None)
        partners = [r for r in rows if r.get("partnerCode") not in (0, None)]
        total_v = (world or {}).get("primaryValue") or sum(r.get("primaryValue") or 0 for r in partners)
        total_w = (world or {}).get("netWgt") or sum(r.get("netWgt") or 0 for r in partners)
        total_q = (world or {}).get("qty") or 0
        piso = _partner_iso()
        tops = sorted(partners, key=lambda r: -(r.get("primaryValue") or 0))
        shares = [(r.get("primaryValue") or 0) / total_v for r in tops] if total_v else []
        return {
            "reporter": iso3, "hs": hs, "flow": flow, "year": year, "value_usd": total_v, "net_kg": total_w,
            "qty": total_q, "unit_value_usd_per_kg": (total_v / total_w) if total_w else None,
            "partners": [{"iso3": piso.get(r["partnerCode"]), "value_usd": r.get("primaryValue"),
                          "share": round((r.get("primaryValue") or 0) / total_v, 4) if total_v else None,
                          "unit_value_usd_per_kg": (r["primaryValue"] / r["netWgt"]) if r.get("netWgt") else None}
                         for r in tops[:8]],
            "hhi": round(sum(s * s for s in shares), 4) if shares else None,
            "source_url": f"https://comtradeplus.un.org/TradeFlow?Frequency=A&Flows={flow}&CommodityCodes={hs}"
                          f"&Partners=0&Reporters={code}&period={year}&AggregateBy=none&BreakdownMode=plus",
        }
    return None


# ----------------------------------------------------------------- FX / currency
def fx_usd() -> dict[str, float]:
    data = http.fetch("https://open.er-api.com/v6/latest/USD", None, source="fx", ttl=12 * 3600)
    return data.get("rates", {})


def currencies() -> dict[str, str]:
    q = """SELECT ?iso3 ?cur WHERE { ?c wdt:P298 ?iso3; wdt:P38 ?x. ?x wdt:P498 ?cur.
           FILTER NOT EXISTS { ?c wdt:P38 ?x. ?x wdt:P582 ?end } }"""
    data = http.fetch("https://query.wikidata.org/sparql", {"query": q, "format": "json"}, source="wikidata",
                      ttl=30 * 86400, headers={"Accept": "application/sparql-results+json"})
    out: dict[str, str] = {}
    for b in data["results"]["bindings"]:
        out.setdefault(b["iso3"]["value"], b["cur"]["value"])
    return out


def currency_of(iso3: str) -> str:
    return currencies().get(iso3, "USD")


# ------------------------------------------------------------ wholesale prices
_MIC = re.compile(r'class="prod-name[^"]*"[^>]*title="([^"]+)"[^>]*href="([^"]+)".{0,600}?class="prod-price[^"]*"[^>]*'
                  r'title="US\$([0-9.,]+)(?:-([0-9.,]+))?"', re.S)


def wholesale_prices(query: str, limit: int = 20) -> list[dict]:
    """Manufacturer FOB price listings (Made-in-China.com search results)."""
    def run():
        slug = "_".join(w.capitalize() for w in re.sub(r"[^A-Za-z0-9 ]", " ", query).split())
        body = http.fetch(f"https://www.made-in-china.com/products-search/hot-china-products/{slug}.html", None,
                          source="madeinchina", ttl=0, expect="text", headers={"User-Agent": BROWSER_UA})
        out, seen = [], set()
        for name, url, lo, hi in _MIC.findall(body):
            name = html.unescape(name).strip()
            if url in seen:
                continue
            seen.add(url)
            lo_v = float(lo.replace(",", ""))
            hi_v = float(hi.replace(",", "")) if hi else lo_v
            supplier = re.sub(r"^https?://([^./]+)\..*", r"\1", url)
            out.append({"name": name, "price_min_usd": lo_v, "price_max_usd": hi_v, "url": url if url.startswith("http")
                        else "https:" + url, "supplier": supplier})
            if len(out) >= limit:
                break
        return out
    return http.cached(f"mic:{query}", 3 * 86400, run)


# -------------------------------------------------------------- local prices
_SYMBOLS = {"₦": "NGN", "KSh": "KES", "Ksh": "KES", "KES": "KES", "R": "ZAR", "₹": "INR", "Rs": "INR", "€": "EUR",
            "£": "GBP", "$": "USD", "US$": "USD", "¥": "JPY", "₱": "PHP", "Rp": "IDR", "₫": "VND", "৳": "BDT",
            "GH₵": "GHS", "₵": "GHS", "TSh": "TZS", "USh": "UGX", "E£": "EGP", "₺": "TRY", "₽": "RUB", "₴": "UAH",
            "R$": "BRL", "S/": "PEN", "Bs": "BOB", "₩": "KRW", "฿": "THB", "Br": "ETB", "CFA": "XOF", "FCFA": "XAF"}
_AMOUNT = re.compile(r"(?:(?P<sym>US\$|R\$|GH₵|E£|KSh|Ksh|TSh|USh|FCFA|CFA|Rs|Rp|S/|Bs|Br|[₦₹€£$¥₱₫৳₵₺₽₴₩฿R])\s?"
                     r"(?P<a>\d[\d,\.]*)\s?(?P<mult>k|m|million|bn|billion)?)|(?:(?P<b>\d[\d,\.]*)\s?"
                     r"(?P<code>[A-Z]{3})\b)")


_CUR_WORDS = {"shilling": ("KES", "TZS", "UGX", "SOS"), "shillings": ("KES", "TZS", "UGX", "SOS"),
              "naira": ("NGN",), "rupee": ("INR", "PKR", "LKR", "NPR"), "rupees": ("INR", "PKR", "LKR", "NPR"),
              "peso": ("MXN", "COP", "ARS", "CLP", "PHP", "UYU", "DOP", "CUP"), "pesos": ("MXN", "COP", "ARS", "CLP", "PHP", "UYU", "DOP", "CUP"),
              "cedi": ("GHS",), "cedis": ("GHS",), "rand": ("ZAR",), "birr": ("ETB",), "kwacha": ("ZMW", "MWK"),
              "dirham": ("MAD", "AED"), "dirhams": ("MAD", "AED"), "pound": ("EGP", "GBP", "LBP", "SDG"),
              "pounds": ("EGP", "GBP", "LBP", "SDG"), "taka": ("BDT",), "rupiah": ("IDR",), "dong": ("VND",),
              "reais": ("BRL",), "real": ("BRL",), "soles": ("PEN",), "bolivianos": ("BOB",), "lira": ("TRY",),
              "rubles": ("RUB",), "roubles": ("RUB",), "hryvnia": ("UAH",), "yen": ("JPY",), "yuan": ("CNY",),
              "dollars": ("USD",), "euros": ("EUR",), "francs": ("XOF", "XAF", "CDF", "RWF", "BIF", "GNF")}
_WORD_AMOUNT = re.compile(r"(?P<n>\d[\d,\.]*)\s?(?P<mult>k|m|million|bn|billion)?\s?(?P<w>[A-Za-z]+)")
_SH = re.compile(r"\bSh\.?\s?(?P<n>\d[\d,\.]*)")


_NOT_A_PRICE = re.compile(r"\b(price target|target|shares?|stocks?|rating|valuation|market cap|salary|salaries|wages?|"
                         r"a month|per month|monthly|a year|per year|annual|budget|revenue|profit|investment|invest|"
                         r"fund|funding|loan|billion|million|bn|subsid\w*|tax|fine|bribe|debt|deal|contract|"
                         r"turnover|earnings|dividend)\b", re.I)


def _near(text: str, start: int, end: int, words: list[str], window: int = 50) -> bool:
    seg = text[max(0, start - window): end + window].lower()
    return any(w in seg for w in words)


def price_mentions(texts: list[str], local_currency: str, object_words: list[str]) -> list[dict]:
    """Extract consumer prices of the need object from real collected texts.

    A quote counts only if the object is mentioned within ~50 characters of the amount and the context is not
    financial/salary/budget language (stock price targets, wages, investments are rejected)."""
    raw = _price_mentions_raw(texts, local_currency, object_words)
    pats = [re.compile(rf"(?<!\w){re.escape(w.lower()[:6])}", re.I) for w in object_words if len(w) > 2]
    out = []
    for m in raw:
        ctx = m["context"]
        if _NOT_A_PRICE.search(ctx):
            continue
        if pats and not any(p.search(ctx) for p in pats):   # whole-word (prefix) match: 'rice' ≠ 'price'
            continue
        out.append(m)
    return out


def _price_mentions_raw(texts: list[str], local_currency: str, object_words: list[str]) -> list[dict]:
    fx = fx_usd()
    out = []
    shilling = local_currency in ("KES", "TZS", "UGX", "SOS")
    for t in texts:
        obj = [re.compile(rf"(?<!\w){re.escape(w.lower()[:6])}", re.I) for w in object_words if len(w) > 2]
        if obj and not any(o.search(t) for o in obj):
            continue
        for m in _WORD_AMOUNT.finditer(t):
            w = m.group("w").lower()
            if w in _CUR_WORDS:
                opts = _CUR_WORDS[w]
                cur = local_currency if local_currency in opts else opts[0]
                try:
                    val = float(m.group("n").replace(",", "")) * {"k": 1e3, "m": 1e6, "million": 1e6, "bn": 1e9,
                                                                    "billion": 1e9}.get((m.group("mult") or "").lower(), 1)
                except ValueError:
                    continue
                if cur in fx and 0 < val < 1e7:
                    out.append({"amount": val, "currency": cur, "usd": round(val / fx[cur], 4),
                                "context": t[max(0, m.start() - 50): m.end() + 50].strip()})
        if shilling:
            for m in _SH.finditer(t):
                try:
                    val = float(m.group("n").replace(",", ""))
                except ValueError:
                    continue
                if local_currency in fx and 0 < val < 1e7:
                    out.append({"amount": val, "currency": local_currency, "usd": round(val / fx[local_currency], 4),
                                "context": t[max(0, m.start() - 50): m.end() + 50].strip()})
    obj = [w.lower()[:5] for w in object_words if len(w) > 2]
    for t in texts:
        obj = [re.compile(rf"(?<!\w){re.escape(w.lower()[:6])}", re.I) for w in object_words if len(w) > 2]
        if obj and not any(o.search(t) for o in obj):
            continue
        for m in _AMOUNT.finditer(t):
            if m.group("sym"):
                cur = _SYMBOLS.get(m.group("sym"), local_currency)
                if m.group("sym") == "$" and local_currency not in ("USD",):
                    cur = "USD"
                raw = m.group("a")
            else:
                cur, raw = m.group("code"), m.group("b")
                if cur not in fx:
                    continue
            try:
                val = float(raw.replace(",", ""))
            except ValueError:
                continue
            mult = {"k": 1e3, "m": 1e6, "million": 1e6, "bn": 1e9, "billion": 1e9}.get((m.group("mult") or "").lower(), 1)
            val *= mult
            if val <= 0 or val > 1e7 or cur not in fx:
                continue
            ctx = t[max(0, m.start() - 50): m.end() + 50]
            out.append({"amount": val, "currency": cur, "usd": round(val / fx[cur], 4), "context": ctx.strip()})
    return out


def lending_rate(iso3: str) -> tuple[float, int] | None:
    from . import worldbank
    try:
        v = worldbank.latest("FR.INR.LEND").get(iso3)
    except http.FetchError:
        return None
    return v if v and v[1] >= time.gmtime().tm_year - 4 else None


def summarize_prices(values: list[float]) -> dict | None:
    if not values:
        return None
    v = sorted(values)
    return {"n": len(v), "min": v[0], "median": statistics.median(v), "max": v[-1],
            "p25": v[max(0, int(len(v) * 0.25) - 1)], "p75": v[min(len(v) - 1, int(len(v) * 0.75))]}


def _country_name(iso3: str) -> str:
    c = geo.country(iso3)
    return c["name"] if c else iso3


def best_hs_for_market(query: str, iso3: str, k: int = 6) -> tuple[dict | None, dict | None]:
    """Pick the HS code for `query` that the country actually trades most (data-driven disambiguation)."""
    cands = hs_lookup(query, k)
    best, best_flow = None, None
    for c in cands:
        if c["match"] < 1.0:
            continue
        f = comtrade_flows(iso3, c["hs"], "M")
        if f and (best_flow is None or (f["value_usd"] or 0) > (best_flow["value_usd"] or 0)):
            best, best_flow = c, f
    return (best or (cands[0] if cands else None)), best_flow



BULK_HS_CHAPTERS = set(range(1, 28)) | {31}   # food, agri, minerals, fuels, fertilisers — sold by kg/litre


def is_bulk(hs: str | None) -> bool:
    return bool(hs) and int(hs[:2]) in BULK_HS_CHAPTERS


_PER_UNIT = re.compile(r"\b(per|a|/)\s?(kg|kilo|kilogram|litre|liter|l|ltr|bag|bottle|packet|unit|tablet|dose|piece)\b", re.I)


_QTY = re.compile(r"(?:per|a|/|for)?\s?(\d+(?:[.,]\d+)?)\s?-?\s?(kg|kgs|kilo|kilos|kilogram|kilograms|l|litre|litres|liter|liters|"
                  r"ltr|tonne|tonnes|ton|tons|g|ml)\b", re.I)
_TO_KG = {"kg": 1, "kgs": 1, "kilo": 1, "kilos": 1, "kilogram": 1, "kilograms": 1, "l": 1, "litre": 1, "litres": 1,
          "liter": 1, "liters": 1, "ltr": 1, "tonne": 1000, "tonnes": 1000, "ton": 1000, "tons": 1000, "g": 0.001,
          "ml": 0.001}


def _per_kg(m: dict) -> dict:
    """'¥4,200 per 5kg bag' → ¥840/kg. Leaves the quote unchanged if no pack size is stated."""
    q = _QTY.search(m["context"])
    if not q:
        return m
    qty = float(q.group(1).replace(",", ".")) * _TO_KG[q.group(2).lower()]
    if qty <= 0 or abs(qty - 1) < 1e-9:
        return {**m, "unit": "per kg/l"}
    return {**m, "amount": m["amount"] / qty, "usd": round(m["usd"] / qty, 4), "unit": f"per kg/l (from {q.group(0).strip()})"}


def clean_price_mentions(mentions: list[dict], bulk: bool) -> list[dict]:
    """Remove outliers (>10x from median); for bulk goods keep quotes that state a unit and normalise to per kg/l."""
    if bulk:
        unit = [_per_kg(m) for m in mentions if _PER_UNIT.search(m["context"]) or _QTY.search(m["context"])]
        mentions = unit or mentions
    if len(mentions) >= 3:
        med = statistics.median(m["usd"] for m in mentions)
        mentions = [m for m in mentions if med / 10 <= m["usd"] <= med * 10]
    # de-duplicate identical quotes
    seen, out = set(), []
    for m in mentions:
        k = (round(m["usd"], 3), m["context"][:60])
        if k not in seen:
            seen.add(k)
            out.append(m)
    return out
