"""Need-language understanding without any external model.

Deterministic, inspectable rules (so every classification can be audited),
plus TF-IDF vectors / cosine similarity for clustering and matching.
An optional LLM pass (aduns.llm) can refine results when an API key exists.
"""
from __future__ import annotations

import html
import math
import re
from collections import Counter

import numpy as np

# --------------------------------------------------------------------------- text

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def clean(text: str | None) -> str:
    if not text:
        return ""
    t = html.unescape(_TAG.sub(" ", text))
    t = t.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return _WS.sub(" ", t).strip()


STOP = set("""a about above after again against all am an and any are aren't as at be because been before being below
between both but by can can't cannot could couldn't did didn't do does doesn't doing don't down during each few for from
further had hadn't has hasn't have haven't having he he'd he'll he's her here here's hers herself him himself his how
how's i i'd i'll i'm i've if in into is isn't it it's its itself let's me more most mustn't my myself no nor not of off
on once only or other ought our ours ourselves out over own same shan't she she'd she'll she's should shouldn't so some
such than that that's the their theirs them themselves then there there's these they they'd they'll they're they've this
those through to too under until up very was wasn't we we'd we'll we're we've were weren't what what's when when's where
where's which while who who's whom why why's with won't would wouldn't you you'd you'll you're you've your yours yourself
yourselves also just like get got really one two would anyone anybody someone something thing things know think want need
way even much many make made use used still yet well back going go see say said new now way lot lots www com http https
amp quot nbsp would could us via per etc ever every since already re ve ll isnt dont cant wont im ive youre thats""".split())

# Words that come from our own query templates (autocomplete prefixes) — not information about the need.
QUERY_TEMPLATE_WORDS = re.compile(
    r"\b(where to buy|where can i get|how to get|price in|prices in|near me|for sale|for rent|not available in|"
    r"supplier in|who repairs|why is|so expensive in|shortage in|cheap|cheapest)\b", re.I)

_TOKEN = re.compile(r"[a-z][a-z0-9\-]{1,30}")


def tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in STOP and len(t) > 2]


def bigrams(toks: list[str]) -> list[str]:
    return [f"{a} {b}" for a, b in zip(toks, toks[1:])]


# ------------------------------------------------------------------ need detection

# (pattern, weight). Weight ≈ how strongly the phrase signals an unmet need.
NEED_PATTERNS: dict[str, list[tuple[str, float]]] = {
    "unmet": [
        (r"\b(can't|cannot|can not|couldn't|could not|unable to) (find|get|source|buy|locate|obtain)\b", 0.9),
        (r"\b(no ?one|nobody|no company|no shop|no store|no business)( here| locally| around here)? (sells|makes|offers|provides|repairs|services|stocks|imports)\b", 1.0),
        (r"\b(not|isn't|aren't|never) (available|sold|offered|stocked)\b", 0.7),
        (r"\bunavailable\b", 0.6),
        (r"\b(impossible|very hard|really hard|so hard|difficult|hard) to (find|get|source|buy|obtain)\b", 0.9),
        (r"\b(wish|hope) (there (was|were|is)|someone (would|could)|i could (find|buy|get))\b", 0.8),
        (r"\bis there (any|a) (company|service|supplier|vendor|manufacturer|shop|app|platform|way|place)\b", 0.7),
        (r"\b(looking for|need|searching for|seeking) (a |an )?(reliable |local |affordable )?(supplier|manufacturer|vendor|distributor|source|technician|installer|repairer|provider)\b", 0.8),
        (r"\b(where|how) (can|do|could) (i|we|you) (buy|find|get|source|order)\b", 0.6),
        (r"\bdoes (anyone|anybody) know (where|of|a|any)\b", 0.5),
        (r"\b(no|lack of|without) (local )?(supplier|suppliers|distributor|distributors|service centre|service center|spare parts|technicians?)\b", 0.9),
        (r"\b(doesn't|does not|don't) exist (here|in|locally)\b", 0.9),
    ],
    "unaffordable": [
        (r"\b(too|so|very|insanely|ridiculously|extremely) (expensive|costly|pricey)\b", 0.8),
        (r"\b(can't|cannot|couldn't) afford\b", 0.9),
        (r"\b(unaffordable|overpriced|price gouging|rip-?off)\b", 0.8),
        (r"\bcosts? (a fortune|an arm and a leg|more than)\b", 0.6),
        (r"\bprices? (have |has )?(doubled|tripled|skyrocketed|soared|surged|spiked)\b", 0.8),
        (r"\b(markup|mark-up|middlemen|middleman)\b", 0.5),
    ],
    "unaware": [
        (r"\b(didn't|did not|never) (know|realise|realize) (that |there |it |such )", 0.6),
        (r"\bnever heard of\b", 0.5),
        (r"\b(no ?one|nobody) (here )?knows (about|how|that)\b", 0.6),
        (r"\bif only (we|i) (had )?known\b", 0.6),
    ],
    "normalized": [
        (r"\b(always|usually|normally) takes? (\w+ )?(days|weeks|months|hours)\b", 0.9),
        (r"\btakes? (\d+|two|three|four|five|six|several|many) (days|weeks|months)\b", 0.6),
        (r"\b(always|every (year|season|month)) (we )?(lose|losing|lost|break|breaks|fail|fails|spoil|spoils|rot)\b", 1.0),
        (r"\b(that's|thats|it's|it is) (just )?(how it is|the way it is|normal here|life)\b", 0.9),
        (r"\b(we|you|people) (just )?(live|deal|cope|put up) with (it|this)\b", 0.9),
        (r"\bonly (available|sold|done|offered|possible) (abroad|overseas|in the (capital|city)|in (europe|the us|india|china|dubai|south africa))\b", 1.0),
        (r"\b(have|had|has) to (travel|go|fly|drive) (to|all the way)\b", 0.7),
        (r"\b(always|have to be|has to be|must be|are|is) imported\b", 0.8),
        (r"\b(need|have) to (know someone|have connections|bribe|pay extra)\b", 0.9),
        (r"\b(waiting list|wait-?list|waiting times?|long queues?|queue for)\b", 0.8),
        (r"\bwait(ed|ing)? (for )?(\w+ )?(weeks|months|years)\b", 0.8),
    ],
    "inefficient": [
        (r"\b(workaround|work-around|jury-?rigged|makeshift|improvised|hacked together|duct tape)\b", 0.6),
        (r"\b(keeps|kept|always) (breaking|failing|breaking down)\b", 0.8),
        (r"\bbreaks? down (all the time|constantly|often|every)\b", 0.8),
        (r"\b(no|can't get|cannot get|can't find) (spare )?parts\b", 0.9),
        (r"\b(no ?one|nobody) (can|knows how to) (fix|repair|service|maintain)\b", 1.0),
        (r"\b(by hand|manually|on paper|with spreadsheets?) (because|since|as)\b", 0.5),
        (r"\binstead (we|i|they) (use|have to use)\b", 0.6),
    ],
    "scarcity": [
        (r"\bshortages?( of)?\b", 0.7),
        (r"\b(scarcity|scarce|rationing|rationed)\b", 0.6),
        (r"\b(out of stock|sold out|back-?order(ed)?|stock-?outs?)\b", 0.6),
        (r"\b(supply (crunch|crisis|disruption|gap)|supply chain (issues|problems|disruption))\b", 0.6),
    ],
    "institutional": [
        (r"\bsources? sought\b", 0.9),
        (r"\brequest for information\b", 0.6),
        (r"\b(no|insufficient) (responsive )?(bids|bidders|offers) (were )?(received|submitted)\b", 1.0),
        (r"\b(re-?tender|re-?advertis|re-?solicit)", 0.8),
        (r"\b(currently )?(being )?(in )?shortage\b", 0.6),
    ],
}

_COMPILED = {k: [(re.compile(p, re.I), w) for p, w in v] for k, v in NEED_PATTERNS.items()}

GAP_CAUSES: dict[str, list[str]] = {
    "affordability": ["expensive", "afford", "price", "cost", "overpriced", "cheap", "budget", "income"],
    "distribution": ["import", "shipping", "delivery", "distributor", "stock", "customs", "logistics", "rural", "far", "travel"],
    "regulation": ["regulation", "regulatory", "license", "licence", "permit", "approval", "banned", "illegal", "certification", "tariff", "duty"],
    "infrastructure": ["electricity", "power", "outage", "road", "internet", "grid", "water supply", "connectivity"],
    "awareness": ["didn't know", "never heard", "nobody knows", "aware", "information"],
    "trust": ["scam", "fake", "counterfeit", "trust", "fraud", "unreliable", "quality"],
    "capability": ["technician", "skill", "expertise", "repair", "nobody can fix", "no one can fix", "training", "engineer"],
    "supply": ["shortage", "supplier", "manufacturer", "production", "capacity", "out of stock", "discontinued"],
    "finance": ["loan", "credit", "financing", "capital", "upfront", "collateral", "interest"],
}

_INTENSIFIERS = re.compile(
    r"\b(desperate|desperately|nightmare|urgent|urgently|every day|daily|constantly|always|lost|losing|died|dying|"
    r"frustrat\w*|terrible|awful|crisis|impossible|struggl\w*|suffer\w*|ruin\w*|bankrupt\w*|millions|thousands)\b",
    re.I,
)

# Noun phrase after typical need verbs ("can't find X", "shortage of X")
_OBJ = re.compile(
    r"\b(?:find|get|source|buy|obtain|afford|repair|repairs|fix|fixes|import|imports|locate|order|sell|sells|sold|stock|stocks|"
    r"shortage of|shortages of|lack of|access to|"
    r"supply of|supplier of|suppliers of|manufacturer of|no|need|needs|needed)\s+"
    r"(?:a |an |the |any |some |good |reliable |affordable |local |cheap |quality |enough )?"
    r"([a-z][a-z0-9\-]+(?: [a-z][a-z0-9\-]+){0,3})",
    re.I,
)


_PREPS = {"in", "at", "for", "near", "from", "on", "to", "with", "because", "since", "and", "or", "but", "so", "here", "there", "anymore"}


def detect_need(text: str) -> dict:
    """Classify a text fragment as a need signal.

    Returns need_types, matched cues, gap_causes, intensity (0..1), need_score (0..1), objects.
    """
    t = clean(text)
    low = t.lower()
    types: dict[str, float] = {}
    cues: list[str] = []
    for typ, pats in _COMPILED.items():
        best = 0.0
        for rx, w in pats:
            m = rx.search(low)
            if m:
                best = max(best, w)
                cues.append(m.group(0))
        if best:
            types[typ] = best
    causes = [c for c, kws in GAP_CAUSES.items() if any(k in low for k in kws)]
    inten_hits = len(_INTENSIFIERS.findall(low))
    excl = min(t.count("!"), 3)
    intensity = min(1.0, 0.15 * inten_hits + 0.05 * excl + (0.25 if types else 0.0) + 0.1 * len(types))
    # Noisy-OR combination of cue weights
    p = 1.0
    for w in types.values():
        p *= 1.0 - w
    need_score = round(1.0 - p, 3)
    objects = []
    for m in _OBJ.finditer(low):
        words = []
        for w in m.group(1).split():
            if w in _PREPS:  # "solar freezer in lagos" → "solar freezer"
                break
            words.append(w)
        phrase = " ".join(w for w in words if w not in STOP)
        if phrase and len(phrase) > 2 and phrase not in objects:
            objects.append(phrase)
    return {
        "need_types": sorted(types, key=lambda k: -types[k]),
        "type_weights": types,
        "cues": cues[:8],
        "gap_causes": causes,
        "intensity": round(intensity, 3),
        "need_score": need_score,
        "objects": objects[:6],
    }


# --------------------------------------------------------------------- vectors

class TfIdf:
    """Small, dependency-free TF-IDF over unigrams + bigrams."""

    def __init__(self, docs: list[str], min_df: int = 1, max_features: int = 6000):
        self.docs_tokens = []
        df: Counter = Counter()
        for d in docs:
            tk = tokens(d)
            feats = tk + bigrams(tk)
            self.docs_tokens.append(feats)
            df.update(set(feats))
        n = max(len(docs), 1)
        vocab = [f for f, c in df.most_common() if c >= min_df][:max_features]
        self.vocab = {f: i for i, f in enumerate(vocab)}
        self.idf = np.array([math.log((1 + n) / (1 + df[f])) + 1 for f in vocab], dtype=np.float32)

    def transform_tokens(self, feats: list[str]) -> np.ndarray:
        v = np.zeros(len(self.vocab), dtype=np.float32)
        for f, c in Counter(feats).items():
            i = self.vocab.get(f)
            if i is not None:
                v[i] = 1 + math.log(c)
        v *= self.idf
        nrm = np.linalg.norm(v)
        return v / nrm if nrm else v

    def matrix(self) -> np.ndarray:
        if not self.vocab:
            return np.zeros((len(self.docs_tokens), 0), dtype=np.float32)
        return np.vstack([self.transform_tokens(f) for f in self.docs_tokens])

    def transform(self, text: str) -> np.ndarray:
        tk = tokens(text)
        return self.transform_tokens(tk + bigrams(tk))

    def top_terms(self, vec: np.ndarray, k: int = 8) -> list[str]:
        inv = {i: f for f, i in self.vocab.items()}
        idx = np.argsort(-vec)[: k * 3]
        out: list[str] = []
        for i in idx:
            if vec[i] <= 0:
                break
            term = inv[int(i)]
            # skip unigram if covered by an already-selected bigram
            if any(term in o.split() for o in out if " " in o):
                continue
            out.append(term)
            if len(out) >= k:
                break
        return out


def cosine_sim_matrix(m: np.ndarray) -> np.ndarray:
    return m @ m.T if m.size else np.zeros((m.shape[0], m.shape[0]))


def agglomerative(sim: np.ndarray, threshold: float = 0.28) -> list[list[int]]:
    """Average-linkage agglomerative clustering on a cosine-similarity matrix."""
    n = sim.shape[0]
    clusters: list[list[int]] = [[i] for i in range(n)]
    if n <= 1:
        return clusters
    # cluster-level similarity matrix (average linkage), updated incrementally
    S = sim.astype(np.float64).copy()
    np.fill_diagonal(S, -1)
    sizes = np.ones(n)
    alive = np.ones(n, dtype=bool)
    while True:
        Sm = np.where(alive[:, None] & alive[None, :], S, -1)
        i, j = np.unravel_index(np.argmax(Sm), Sm.shape)
        if Sm[i, j] < threshold:
            break
        # merge j into i
        new = (S[i] * sizes[i] + S[j] * sizes[j]) / (sizes[i] + sizes[j])
        S[i, :] = new
        S[:, i] = new
        S[i, i] = -1
        sizes[i] += sizes[j]
        alive[j] = False
        S[j, :] = -1
        S[:, j] = -1
        clusters[i].extend(clusters[j])
        clusters[j] = []
    return [c for c, a in zip(clusters, alive) if a and c]
