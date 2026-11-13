"""Live SEC EDGAR tools using free SEC endpoints (no paid API).

SEC requires a descriptive User-Agent with contact details and limits clients
to 10 requests/second. Set SEC_USER_AGENT="Your Name your@email".
Responses are cached under data/sec_cache so runs are repeatable and the
cache can be archived with the paper's artifact.

Evidence identity: source_id = 'edgar:<accession>' (document URL kept in uri) (EDGAR filings are
immutable; an amendment is a new accession, i.e. a new source).
"""
import hashlib
import json
import os
import re
import threading
import time

import requests
from bs4 import BeautifulSoup

from faogf.gateway import ToolOutput
from .corpus import Tool, common_tools

CACHE = os.environ.get("SEC_CACHE_DIR", "data/sec_cache")
_lock, _last = threading.Lock(), [0.0]


def _get(url, as_json=False):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest()[:32])
    if os.path.exists(path):
        raw = open(path, "rb").read()
    else:
        ua = os.environ.get("SEC_USER_AGENT")
        if not ua:
            raise RuntimeError("set SEC_USER_AGENT='Your Name your@email' (required by SEC)")
        with _lock:                                 # <= ~8 requests/second
            wait = 0.125 - (time.time() - _last[0])
            if wait > 0:
                time.sleep(wait)
            _last[0] = time.time()
        r = requests.get(url, headers={"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}, timeout=30)
        r.raise_for_status()
        raw = r.content
        open(path, "wb").write(raw)
    return json.loads(raw) if as_json else raw.decode("utf-8", errors="replace")


_tickers = {}


def _ticker_map():
    if not _tickers:
        data = _get("https://www.sec.gov/files/company_tickers.json", as_json=True)
        for row in data.values():
            _tickers[row["ticker"].upper()] = (int(row["cik_str"]), row["title"])
    return _tickers


def resolve(query):
    """Ticker, CIK or company name -> (ticker, cik, title). Falls back to EDGAR company
    search for issuers no longer in the current ticker file (acquired / delisted)."""
    q = str(query).strip()
    if q.isdigit():
        sub = _get(f"https://data.sec.gov/submissions/CIK{int(q):010d}.json", as_json=True)
        return (sub.get("tickers") or [q])[0], int(q), sub.get("name", q)
    m = _ticker_map()
    if q.upper() in m:
        return q.upper(), *m[q.upper()]
    ql = re.sub(r"[^a-z0-9 ]", "", q.lower()).replace(" corporation", "").replace(" inc", "").strip()
    for t, (cik, title) in m.items():
        if ql and ql in title.lower():
            return t, cik, title
    if not ql:
        return None
    atom = _get("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company="
                + requests.utils.quote(ql) + "&type=10-K&dateb=&owner=include&count=10&output=atom")
    ciks = re.findall(r"<cik>(\d+)</cik>", atom) or re.findall(r"CIK=(\d{10})", atom)
    names = re.findall(r"<conformed-name>([^<]+)</conformed-name>", atom)
    if ciks:
        return q.upper(), int(ciks[0]), names[0] if names else q
    return None


def _html_to_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    for tag in soup.find_all(style=re.compile("display:\\s*none")):   # hidden XBRL header blocks
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ")).strip()


_doc_text = {}
_acc_cik = {}       # accession -> issuer CIK, learned from edgar_list_filings output


def filing_id(url=None, accession=None):
    """Canonical filing identity 'edgar:<accession>', derivable from a URL or an accession."""
    if url:
        m = re.search(r"/data/\d+/(\d{10})(\d{2})(\d{6})/([^/?#]+)", url)
        if m:
            return f"edgar:{m.group(1)}-{m.group(2)}-{m.group(3)}"
        return url
    return f"edgar:{accession}"


def _filings(cik):
    """All filings for a CIK (recent block plus older pages) as dicts."""
    sub = _get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", as_json=True)
    blocks = [sub["filings"]["recent"]]
    for page in sub["filings"].get("files", []):
        blocks.append(_get(f"https://data.sec.gov/submissions/{page['name']}", as_json=True))
    out = []
    for b in blocks:
        n = len(b["accessionNumber"])
        for i in range(n):
            acc = b["accessionNumber"][i]
            _acc_cik[acc] = cik
            out.append({"accession": acc, "form": b["form"][i], "filed": b["filingDate"][i],
                        "period": (b.get("reportDate") or [""] * n)[i], "doc": b["primaryDocument"][i],
                        "url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{b['primaryDocument'][i]}"})
    return sub.get("name", ""), out


def edgar_tools(outbox, notes=None):
    """notes: mutable dict; notes["text"] is served by get_analyst_notes (untrusted content)."""

    def edgar_lookup_company(query):
        hit = resolve(query)
        if not hit:
            return ToolOutput("No matching company.")
        t, cik, title = hit
        return ToolOutput(f"{title} ticker={t} cik={cik}")

    def edgar_list_filings(ticker, form_types=None, period_year=None, filed_after=None, filed_before=None, limit=10):
        hit = resolve(ticker)
        if not hit:
            return ToolOutput("Unknown company. Try the full legal name or the CIK.")
        t, cik, title = hit
        _, rows = _filings(cik)
        forms = {f.upper() for f in (form_types or [])}
        out = []
        for f in rows:
            if forms and f["form"].upper() not in forms:
                continue
            if period_year and not str(f["period"]).startswith(str(period_year)):
                continue
            if filed_after and f["filed"] < str(filed_after):
                continue
            if filed_before and f["filed"] > str(filed_before):
                continue
            out.append(f"{f['form']} filed {f['filed']} period {f['period']} accession {f['accession']} url {f['url']}")
            if len(out) >= int(limit or 10):
                break
        return ToolOutput(f"{title} (cik {cik}) filings:\n" + "\n".join(out) if out else
                          "No filings matched; relax form_types/period_year/date filters.")

    def edgar_read_filing(url=None, accession=None, ticker=None, start=0, length=8000):
        if accession and not url:
            if ticker:
                hit = resolve(ticker)
                if not hit:
                    raise ValueError("unknown company; resolve it with edgar_lookup_company first")
                cik = hit[1]
            elif accession in _acc_cik:
                cik = _acc_cik[accession]
            else:
                raise ValueError("unknown accession; call edgar_list_filings for the company first")
            match = [f for f in _filings(cik)[1] if f["accession"] == accession]
            if not match:
                raise ValueError("accession not found; use one returned by edgar_list_filings")
            url = match[0]["url"]
        if not url or not url.startswith("https://www.sec.gov/Archives/"):
            raise ValueError("pass a url or accession exactly as returned by edgar_list_filings")
        if url not in _doc_text:
            try:
                _doc_text[url] = _html_to_text(_get(url))
            except requests.HTTPError:
                raise ValueError("document not found. Do not construct URLs; use a url or accession exactly "
                                 "as returned by edgar_list_filings")
        text = _doc_text[url]
        start, length = max(0, int(start)), min(int(length), 12000)
        chunk = text[start:start + length]
        sid = filing_id(url=url)
        return ToolOutput(f"[{url} chars {start}-{start + len(chunk)} of {len(text)}] {chunk}",
                          [{"source_id": sid, "version": "original", "text": chunk,
                            "uri": f"{url}#chars={start}-{start + len(chunk)}", "trust_class": "authoritative_filing"}])

    def edgar_xbrl_fact(ticker, concept, fiscal_year=None):
        hit = resolve(ticker)
        if not hit:
            return ToolOutput("Unknown company.")
        t, cik, title = hit
        facts = _get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json", as_json=True)
        gaap = facts.get("facts", {}).get("us-gaap", {})
        if concept not in gaap:
            words = [w for w in re.findall(r"[A-Z][a-z]+", concept) if len(w) > 3] or [concept]
            close = sorted(gaap, key=lambda c: -sum(w.lower() in c.lower() for w in words))[:12]
            return ToolOutput(f"{title} does not report us-gaap:{concept}. Concepts it does report that look "
                              f"related: {', '.join(close)}")
        data = gaap[concept]
        rows = []
        for unit, facts in data.get("units", {}).items():
            for f in facts:
                if f.get("form") in ("10-K", "10-Q") and (fiscal_year is None or str(f.get("fy")) == str(fiscal_year)):
                    rows.append(f"{f.get('fy')} {f.get('fp')} {f.get('form')} end={f.get('end')} {unit} {f['val']} "
                                f"accn={f.get('accn')}")
        body = "\n".join(rows[-40:]) or "No facts."
        sid = f"xbrl:{ticker.upper()}:{concept}"   # reconstructible from tool arguments (fair to baselines)
        return ToolOutput(f"{title} {concept}:\n{body}", [{"source_id": sid, "version": "xbrl", "text": body,
                                                           "uri": sid, "trust_class": "authoritative_filing"}])

    def get_analyst_notes(company):
        key = company.lower().strip()
        text = (notes or {}).get("text")       # set per workflow by the experiment
        if not text:
            return ToolOutput("No analyst notes.")
        return ToolOutput(f"[analyst-notes:{key}] {text}", [{"source_id": f"notes:{key}", "version": 1,
                                                              "text": text, "uri": f"notes:{key}",
                                                              "trust_class": "untrusted_web"}])

    def p(props, req):
        return {"type": "object", "properties": props, "required": req}

    tools = {
        "edgar_lookup_company": Tool(edgar_lookup_company, "search", False, lambda a: [a.get("query", "")], {
            "description": "Resolve a company name, ticker or CIK to its SEC CIK (works for acquired/delisted issuers).",
            "parameters": p({"query": {"type": "string"}}, ["query"])}),
        "edgar_list_filings": Tool(edgar_list_filings, "search", False, lambda a: [a.get("ticker", "")], {
            "description": "List SEC filings (including historical and acquired companies) with accession numbers "
                           "and document URLs. Filters: form_types e.g. ['10-K','10-Q','8-K','DEFM14A'], period_year "
                           "(fiscal period end year), filed_after / filed_before (YYYY-MM-DD).",
            "parameters": p({"ticker": {"type": "string", "description": "ticker, CIK or company name"},
                             "form_types": {"type": "array", "items": {"type": "string"}},
                             "period_year": {"type": "integer"}, "filed_after": {"type": "string"},
                             "filed_before": {"type": "string"}, "limit": {"type": "integer"}}, ["ticker"])}),
        "edgar_read_filing": Tool(edgar_read_filing, "read", False, lambda a: [a.get("accession") or a.get("url", "")], {
            "description": "Read part of an SEC filing as text, by accession (preferred) or by a url returned by "
                           "edgar_list_filings. Never construct URLs. Use start/length (max 12000 chars) to page.",
            "parameters": p({"accession": {"type": "string"}, "url": {"type": "string"}, "ticker": {"type": "string"},
                             "start": {"type": "integer"}, "length": {"type": "integer"}}, [])}),
        "edgar_xbrl_fact": Tool(edgar_xbrl_fact, "read", False, lambda a: [a.get("ticker", ""), a.get("concept", "")], {
            "description": "Get reported XBRL values for a us-gaap concept (e.g. Revenues, NetIncomeLoss, "
                           "RevenueFromContractWithCustomerExcludingAssessedTax) for a ticker.",
            "parameters": p({"ticker": {"type": "string"}, "concept": {"type": "string"},
                             "fiscal_year": {"type": "integer"}}, ["ticker", "concept"])}),
        "get_analyst_notes": Tool(get_analyst_notes, "search", False, lambda a: [a.get("company", "")], {
            "description": "Retrieve internal analyst notes about a company (third-party content, unverified).",
            "parameters": p({"company": {"type": "string"}}, ["company"])}),
    }
    tools.update(common_tools(outbox))
    return tools


EDGAR_ORCH = ["edgar_lookup_company", "edgar_list_filings", "edgar_read_filing", "edgar_xbrl_fact",
              "get_analyst_notes", "calculate", "distribute_report", "delegate_analysis"]
EDGAR_ANALYST = ["edgar_read_filing", "edgar_xbrl_fact", "calculate"]
