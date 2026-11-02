"""Unmet institutional demand from public procurement (recent, free, keyless).

Buyers that tried to purchase something and failed are some of the strongest need signals there are:
the need is real, budgeted, and nobody delivered.

* TED (EU + EEA + candidate countries) — lots closed with *no winner* (`winner-selection-status = clos-nw`).
* PNCP (Brazil, all public buyers) — procurements *revoked / annulled / suspended*.
* UK Find a Tender — tender *cancellations* and unsuccessful procedures.
(Prozorro UA, SECOP CO and SAM.gov live in `institutional.py`.)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .. import geo, http
from ..nlp import clean
from .social import _rec

TED_LANG_PREF = ["eng", "fra", "deu", "spa", "ita", "por", "pol", "nld"]


def _ted_text(d) -> tuple[str, str]:
    if isinstance(d, dict):
        for lang in TED_LANG_PREF:
            if d.get(lang):
                v = d[lang]
                return (v[0] if isinstance(v, list) else v), lang
        k = next(iter(d), None)
        if k:
            v = d[k]
            return (v[0] if isinstance(v, list) else v), k
    return (d or "", "eng") if isinstance(d, str) else ("", "eng")


def ted_no_winner(days: int = 14, pages: int = 4, country_iso3: str | None = None) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y%m%d")
    q = f"winner-selection-status=clos-nw AND publication-date>={since}"
    if country_iso3:
        q += f" AND buyer-country={country_iso3}"
    out = []
    for page in range(1, pages + 1):
        data = http.fetch("https://api.ted.europa.eu/v3/notices/search", method="POST", source="ted", ttl=3 * 3600,
                          json_body={"query": q, "fields": ["publication-number", "notice-title", "publication-date",
                                                            "buyer-name", "buyer-country", "classification-cpv"],
                                     "limit": 100, "page": page, "scope": "ALL"})
        notices = data.get("notices", [])
        for n in notices:
            title, lang = _ted_text(n.get("notice-title"))
            buyer, _ = _ted_text(n.get("buyer-name"))
            bc = n.get("buyer-country")
            iso = (bc[0] if isinstance(bc, list) and bc else bc) or geo.resolve(title.split("–")[0].strip())
            num = n.get("publication-number")
            out.append(_rec("ted", "structural", num, f"https://ted.europa.eu/en/notice/-/detail/{num}",
                            title, f"No winner selected (procurement closed without a contract): {title} — {buyer}",
                            buyer, (n.get("publication-date") or "")[:10], 0.4,
                            {"country": iso, "cpv": (n.get("classification-cpv") or [None])[0],
                             "lang": {"eng": "en", "fra": "fr", "deu": "de", "spa": "es", "ita": "it", "por": "pt",
                                      "pol": "pl", "nld": "nl"}.get(lang, "en")}))
        if len(notices) < 100:
            break
    return out


def pncp_failed(days: int = 7, pages: int = 5, modalities: tuple[int, ...] = (6, 8)) -> list[dict]:
    """Brazilian public procurements revoked, annulled or suspended in the last `days`."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    bad = {"Revogada", "Anulada", "Suspensa", "Deserta", "Fracassada"}
    out = []
    for mod in modalities:
        for page in range(1, pages + 1):
            try:
                data = http.fetch("https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao",
                                  {"dataInicial": start.strftime("%Y%m%d"), "dataFinal": end.strftime("%Y%m%d"),
                                   "codigoModalidadeContratacao": mod, "pagina": page, "tamanhoPagina": 50},
                                  source="pncp", ttl=3 * 3600, retries=1)
            except http.FetchError:
                break
            rows = data.get("data") or []
            for r in rows:
                if r.get("situacaoCompraNome") not in bad:
                    continue
                org = (r.get("orgaoEntidade") or {}).get("razaoSocial", "")
                uo = r.get("unidadeOrgao") or {}
                obj = clean(r.get("objetoCompra"))
                out.append(_rec("pncp", "structural", r.get("numeroControlePNCP"),
                                r.get("linkSistemaOrigem") or "https://pncp.gov.br/app/editais",
                                obj[:200], f"Contratação {r['situacaoCompraNome'].lower()}: {obj} — {org} "
                                f"({uo.get('municipioNome', '')}/{uo.get('ufSigla', '')})", org,
                                r.get("dataPublicacaoPncp"), 0.4,
                                {"status": r["situacaoCompraNome"], "value": r.get("valorTotalEstimado"),
                                 "state": uo.get("ufSigla"), "lang": "pt", "country": "BRA"}))
            if page >= (data.get("totalPaginas") or 0):
                break
    return out


def uk_cancelled(days: int = 30, limit: int = 100) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00")
    data = http.fetch("https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages",
                      {"limit": limit, "updatedFrom": since}, source="findatender", ttl=3 * 3600)
    out = []
    for r in data.get("releases", []):
        t = r.get("tender") or {}
        if "tenderCancellation" not in r.get("tag", []) and t.get("status") not in ("cancelled", "unsuccessful"):
            continue
        buyer = next((p.get("name") for p in r.get("parties", []) if "buyer" in p.get("roles", [])), "")
        title = clean(t.get("title"))
        out.append(_rec("findatender", "structural", r.get("id"), f"https://www.find-tender.service.gov.uk/Notice/{r.get('id')}",
                        title, f"Tender {t.get('status') or 'cancelled'}: {title}. {clean(t.get('description'))[:600]} — {buyer}",
                        buyer, r.get("date"), 0.4, {"status": t.get("status"), "country": "GBR", "lang": "en"}))
    return out
