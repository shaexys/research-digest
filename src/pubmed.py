"""PubMed E-utilities search and fetch."""

import re
import os
import time
import xml.etree.ElementTree as ET

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Configure retry strategy for transient failures
_retry_strategy = Retry(
    total=3,
    backoff_factor=1,  # 1s, 2s, 4s between retries
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST"],
    raise_on_status=False,
)
_adapter = HTTPAdapter(max_retries=_retry_strategy)
_session = requests.Session()
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)

# Month name to number mapping for date parsing
MONTH_MAP = {
    "jan": "01", "january": "01",
    "feb": "02", "february": "02",
    "mar": "03", "march": "03",
    "apr": "04", "april": "04",
    "may": "05",
    "jun": "06", "june": "06",
    "jul": "07", "july": "07",
    "aug": "08", "august": "08",
    "sep": "09", "september": "09",
    "oct": "10", "october": "10",
    "nov": "11", "november": "11",
    "dec": "12", "december": "12",
}
API_KEY = os.environ.get("NCBI_API_KEY", "")
RATE_DELAY = 0.1 if API_KEY else 0.34  # 10/sec with key, 3/sec without


def _params(**kw):
    p = dict(kw)
    if API_KEY:
        p["api_key"] = API_KEY
    return p


def search(query: str, days_back: int = 1) -> list[str]:
    """Return list of PMIDs matching query within the last `days_back` days."""
    pmids: list[str] = []
    retstart = 0
    retmax = 500

    while True:
        time.sleep(RATE_DELAY)
        resp = _session.post(
            f"{BASE}/esearch.fcgi",
            data=_params(
                db="pubmed",
                term=query,
                datetype="edat",
                reldate=str(days_back),
                retmax=str(retmax),
                retstart=str(retstart),
                retmode="json",
            ),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()["esearchresult"]
        # PubMed reports query errors (e.g. "number of Boolean operators exceeds
        # 2048") inside an HTTP 200 body; without this check they read as 0 hits.
        if "ERROR" in data or "count" not in data:
            raise RuntimeError(f"PubMed rejected the query: {data.get('ERROR', data)}")
        batch = data.get("idlist", [])
        pmids.extend(batch)

        total = int(data.get("count", 0))
        retstart += retmax
        if retstart >= total or not batch:
            break

    return pmids


def fetch(pmids: list[str]) -> list[dict]:
    """Fetch article metadata for a list of PMIDs. Returns list of dicts."""
    if not pmids:
        return []

    articles = []
    # Fetch in batches of 200
    for i in range(0, len(pmids), 200):
        batch = pmids[i : i + 200]
        time.sleep(RATE_DELAY)
        resp = _session.post(
            f"{BASE}/efetch.fcgi",
            data=_params(
                db="pubmed",
                id=",".join(batch),
                rettype="xml",
                retmode="xml",
            ),
            timeout=60,
        )
        resp.raise_for_status()
        articles.extend(_parse_xml(resp.text))

    return articles


def _parse_xml(xml_text: str) -> list[dict]:
    """Parse PubMed XML into article dicts."""
    root = ET.fromstring(xml_text)
    results = []

    for article_el in root.findall(".//PubmedArticle"):
        medline = article_el.find("MedlineCitation")
        if medline is None:
            continue

        pmid_el = medline.find("PMID")
        pmid = pmid_el.text if pmid_el is not None else ""

        art = medline.find("Article")
        if art is None:
            continue

        # Title
        title_el = art.find("ArticleTitle")
        title = "".join(title_el.itertext()) if title_el is not None else ""

        # Journal
        journal_el = art.find("Journal/Title")
        journal = journal_el.text if journal_el is not None else ""

        # ISSNs (for Impact Factor lookup): keep print and electronic, since a
        # JIF table may list a journal under either one
        issns = [el.text.strip() for el in art.findall("Journal/ISSN") if el.text]
        issn = issns[0] if issns else ""

        # Date — try ArticleDate first, then PubDate
        date_str = _extract_date(art)

        # Authors (first 3 + et al)
        authors = _extract_authors(art)

        # DOI
        doi = ""
        for id_el in article_el.findall(".//ArticleId"):
            if id_el.get("IdType") == "doi":
                doi = id_el.text or ""
                break

        results.append(
            {
                "pmid": pmid,
                "title": title.strip(),
                "authors": authors,
                "journal": journal,
                "date": date_str,
                "doi": doi,
                "issn": issn,
                "issns": issns,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            }
        )

    return results


def _extract_date(art_el) -> str:
    """Best-effort date string from article element."""
    for path in [
        "ArticleDate",
        "Journal/JournalIssue/PubDate",
    ]:
        d = art_el.find(path)
        if d is not None:
            y = d.findtext("Year", "")
            m = d.findtext("Month", "")
            day = d.findtext("Day", "")
            if y:
                parts = [y]
                if m:
                    # Convert month name to number if needed
                    if m.isdigit():
                        parts.append(m.zfill(2))
                    else:
                        month_num = MONTH_MAP.get(m.lower(), "")
                        if month_num:
                            parts.append(month_num)
                        # Skip month if not recognized (will show year only)
                if day:
                    parts.append(day.zfill(2))
                return "-".join(parts)
            # Older or seasonal issues carry free text instead, e.g. "2024 Jan-Feb"
            medline = d.findtext("MedlineDate", "")
            m = re.match(r"(\d{4})(?:\s+([A-Za-z]{3}))?", medline)
            if m:
                month = MONTH_MAP.get((m.group(2) or "").lower(), "")
                return f"{m.group(1)}-{month}" if month else m.group(1)
    return ""


def _extract_authors(art_el) -> str:
    """First 3 authors + et al."""
    author_list = art_el.find("AuthorList")
    if author_list is None:
        return ""

    names = []
    for au in author_list.findall("Author"):
        last = au.findtext("LastName", "")
        initials = au.findtext("Initials", "")
        if last:
            names.append(f"{last} {initials}".strip())

    if len(names) > 3:
        return ", ".join(names[:3]) + ", et al."
    return ", ".join(names)
