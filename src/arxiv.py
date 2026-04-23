"""arXiv API search for CS/AI papers relevant to psychiatry research."""

import re
import time
import xml.etree.ElementTree as ET
from datetime import date, timedelta

import requests

BASE = "http://export.arxiv.org/api/query"

# arXiv categories relevant to methods in psychiatry
CATEGORIES = ["cs.AI", "cs.CL", "cs.LG", "stat.ML", "cs.HC"]


def search(days_back: int, require_both: tuple[list[str], list[str]]) -> list[dict]:
    """Search arXiv for recent papers matching psych AND methods keywords.

    Uses arXiv API with category filter + broad keyword search,
    then filters locally by date and psych/methods keyword intersection.

    Args:
        days_back: how many days back to include
        require_both: (psych_keywords, methods_keywords)

    Returns:
        List of article dicts.
    """
    cutoff = date.today() - timedelta(days=days_back)

    # Build search queries per psych keyword across all categories
    cat_query = " OR ".join(f"cat:{c}" for c in CATEGORIES)

    # Use a few high-signal psych terms in the API query to reduce volume
    api_terms = [
        "mental health", "psychiatry", "depression", "anxiety",
        "ADHD", "suicide", "PTSD", "psychopathology",
    ]
    ti_query = " OR ".join(f'ti:"{t}"' for t in api_terms)
    abs_query = " OR ".join(f'abs:"{t}"' for t in api_terms)
    query = f"({cat_query}) AND ({ti_query} OR {abs_query})"

    all_entries = []
    start_idx = 0
    max_results = 200

    while True:
        time.sleep(3)  # arXiv rate limit
        params = {
            "search_query": query,
            "start": start_idx,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        resp = None
        for attempt in range(3):
            try:
                resp = requests.get(BASE, params=params, timeout=60)
                if resp.status_code == 429:
                    wait = 10 * (attempt + 1)
                    print(f"    arXiv 429 rate limit, retrying in {wait}s (attempt {attempt + 1}/3)")
                    time.sleep(wait)
                    continue
                break
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                wait = 10 * (attempt + 1)
                print(f"    arXiv request failed ({e}), retrying in {wait}s (attempt {attempt + 1}/3)")
                time.sleep(wait)
        if resp is None:
            raise requests.exceptions.ConnectionError("arXiv API unreachable after 3 attempts")
        resp.raise_for_status()

        entries = _parse_entries(resp.text)
        if not entries:
            break

        # Stop paginating once we hit papers older than cutoff
        all_entries.extend(entries)
        oldest = entries[-1]["date"]
        if oldest < cutoff.isoformat():
            break

        start_idx += max_results
        if len(entries) < max_results:
            break

    # Filter by date
    recent = [e for e in all_entries if e["date"] >= cutoff.isoformat()]

    # Filter by require_both: psych AND methods
    pats_a = [re.compile(re.escape(kw), re.IGNORECASE) for kw in require_both[0]]
    pats_b = [re.compile(re.escape(kw), re.IGNORECASE) for kw in require_both[1]]

    matched = []
    for p in recent:
        text = f"{p['title']} {p['abstract']}"
        if any(pa.search(text) for pa in pats_a) and any(pb.search(text) for pb in pats_b):
            matched.append(_to_article(p))

    return matched


def _parse_entries(xml_text: str) -> list[dict]:
    """Parse arXiv Atom XML into raw dicts."""
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(xml_text)
    entries = []

    for entry in root.findall("atom:entry", ns):
        title = entry.findtext("atom:title", "", ns).strip().replace("\n", " ")
        # Skip the "no results" placeholder entry
        if title.startswith("Error"):
            continue
        abstract = entry.findtext("atom:summary", "", ns).strip()
        link = ""
        for lnk in entry.findall("atom:link", ns):
            if lnk.get("type") == "text/html":
                link = lnk.get("href", "")
                break
        if not link:
            link = entry.findtext("atom:id", "", ns)

        authors = []
        for author in entry.findall("atom:author", ns):
            name = author.findtext("atom:name", "", ns)
            if name:
                authors.append(name)

        published = entry.findtext("atom:published", "", ns)[:10]

        entries.append({
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "link": link,
            "date": published,
        })

    return entries


def _to_article(p: dict) -> dict:
    """Convert parsed arXiv entry to standard article dict."""
    authors = p["authors"]
    if len(authors) > 3:
        author_str = ", ".join(authors[:3]) + ", et al."
    else:
        author_str = ", ".join(authors)

    return {
        "pmid": "",
        "title": p["title"],
        "authors": author_str,
        "journal": "arXiv (preprint)",
        "date": p["date"],
        "doi": "",
        "issn": "",
        "url": p["link"],
    }
