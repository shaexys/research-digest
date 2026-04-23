"""medRxiv/bioRxiv API search via date range + local keyword filter."""

import re
import time
from datetime import date, timedelta

import requests

BASE = "https://api.medrxiv.org/details"


def search(server: str, days_back: int, keywords: list[str],
           require_both: tuple[list[str], list[str]] = None) -> list[dict]:
    """Fetch recent preprints and filter locally by keywords.

    Args:
        server: "medrxiv" or "biorxiv"
        days_back: how many days back to search
        keywords: list of keyword strings — match ANY one (OR logic)
        require_both: if provided, (list_A, list_B) — must match at least one
                      from A AND at least one from B. Overrides `keywords`.

    Returns:
        List of matching article dicts.
    """
    end = date.today()
    start = end - timedelta(days=days_back)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    all_papers = []
    cursor = 0

    while True:
        time.sleep(0.5)
        url = f"{BASE}/{server}/{start_str}/{end_str}/{cursor}"
        resp = None
        for attempt in range(3):
            try:
                resp = requests.get(url, timeout=60)
                if resp.status_code == 429:
                    wait = 10 * (attempt + 1)
                    print(f"    {server} 429 rate limit, retrying in {wait}s (attempt {attempt + 1}/3)")
                    time.sleep(wait)
                    continue
                break
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                wait = 10 * (attempt + 1)
                print(f"    {server} request failed ({e}), retrying in {wait}s (attempt {attempt + 1}/3)")
                time.sleep(wait)
        if resp is None:
            raise requests.exceptions.ConnectionError(f"{server} API unreachable after 3 attempts")
        resp.raise_for_status()
        data = resp.json()

        papers = data.get("collection", [])
        if not papers:
            break

        all_papers.extend(papers)
        cursor += len(papers)

        total = data.get("messages", [{}])[0].get("total", 0)
        if cursor >= total:
            break

    # Local keyword filter
    if require_both:
        pats_a = [re.compile(re.escape(kw), re.IGNORECASE) for kw in require_both[0]]
        pats_b = [re.compile(re.escape(kw), re.IGNORECASE) for kw in require_both[1]]
        matched = []
        for p in all_papers:
            text = f"{p.get('title', '')} {p.get('abstract', '')}"
            if any(pa.search(text) for pa in pats_a) and any(pb.search(text) for pb in pats_b):
                matched.append(_to_article(p, server))
    else:
        patterns = [re.compile(re.escape(kw), re.IGNORECASE) for kw in keywords]
        matched = []
        for p in all_papers:
            text = f"{p.get('title', '')} {p.get('abstract', '')}"
            if any(pat.search(text) for pat in patterns):
                matched.append(_to_article(p, server))

    return matched


def _to_article(p: dict, server: str) -> dict:
    """Convert medRxiv/bioRxiv API record to standard article dict."""
    doi = p.get("doi", "")
    authors = p.get("authors", "")
    # Truncate to first 3 authors
    parts = [a.strip() for a in authors.split(";") if a.strip()]
    if len(parts) > 3:
        authors = "; ".join(parts[:3]) + "; et al."
    else:
        authors = "; ".join(parts)

    institution = (p.get("author_corresponding_institution") or "").strip()

    return {
        "pmid": "",
        "title": p.get("title", "").strip(),
        "authors": authors,
        "journal": f"{server} (preprint)",
        "date": p.get("date", ""),
        "doi": doi,
        "issn": "",
        "url": f"https://doi.org/{doi}" if doi else "",
        "institution": institution,
    }
