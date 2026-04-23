"""NIH RePORTER API search for funded grants."""

import re
import time

import requests
from datetime import date

BASE = "https://api.reporter.nih.gov/v2/projects/search"

# Wet lab exclusion terms — filter out basic science / animal model grants
# Note: removed protein, blood sample, biospecimen, plasma level (too broad)
WET_LAB_TERMS = [
    "mouse", "mice", "rodent", "rat ", "murine", "in vivo", "in vitro",
    "cell line", "cell culture", "genome-wide", "GWAS",
    "transcriptom", "proteom", "metabolom", "gene expression",
    "knockout", "transgenic", "optogenetic", "electrophysiolog",
    "hippocamp", "cortical slice", "neural circuit",
    "receptor binding", "synaptic", "dendritic",
    "drosophila", "zebrafish", "primate model",
]


def search(keywords: list[str], fiscal_years: list[int] = None,
           nimh_all: bool = False) -> list[dict]:
    """Search NIH RePORTER for grants.

    Logic: NIMH (all grants) OR Methods_Keywords (any institute)

    Args:
        keywords: search terms for Methods (OR logic)
        fiscal_years: fiscal years to search (default: current year)
        nimh_all: if True, also fetch all NIMH grants without keyword filter

    Returns:
        List of grant dicts, with wet lab grants filtered out, deduplicated.
    """
    if fiscal_years is None:
        fiscal_years = [date.today().year]

    all_results = {}

    # Query 1: Methods keywords (any institute)
    if keywords:
        criteria1 = {
            "advanced_text_search": {
                "operator": "or",
                "search_field": "projecttitle,terms",
                "search_text": " ".join(keywords),
            },
            "fiscal_years": fiscal_years,
            "newly_added_projects_only": True,
        }
        results1 = _fetch_and_filter(criteria1)
        for r in results1:
            all_results[r.get("_appl_id", r["title"])] = r

    # Query 2: NIMH (all grants, no keyword filter)
    if nimh_all:
        criteria2 = {
            "agencies": ["NIMH"],
            "fiscal_years": fiscal_years,
            "newly_added_projects_only": True,
        }
        results2 = _fetch_and_filter(criteria2)
        for r in results2:
            key = r.get("_appl_id", r["title"])
            if key not in all_results:
                all_results[key] = r

    # Sort by start date descending
    results = list(all_results.values())
    results.sort(key=lambda a: a.get("_start_date", ""), reverse=True)
    return results


def _fetch_and_filter(criteria: dict) -> list[dict]:
    """Fetch grants from API and filter out wet lab."""
    payload = {
        "criteria": criteria,
        "offset": 0,
        "limit": 100,
        "sort_field": "project_start_date",
        "sort_order": "desc",
    }

    resp = None
    for attempt in range(3):
        try:
            resp = requests.post(BASE, json=payload, timeout=60)
            if resp.status_code in (429, 500, 502, 503, 504):
                wait = 10 * (attempt + 1)
                print(f"    RePORTER {resp.status_code}, retrying in {wait}s (attempt {attempt + 1}/3)")
                time.sleep(wait)
                continue
            break
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            wait = 10 * (attempt + 1)
            print(f"    RePORTER request failed ({e}), retrying in {wait}s (attempt {attempt + 1}/3)")
            time.sleep(wait)
    if resp is None:
        raise requests.exceptions.ConnectionError("NIH RePORTER API unreachable after 3 attempts")
    resp.raise_for_status()
    data = resp.json()

    # Build exclusion patterns
    exclude_pats = [re.compile(re.escape(t), re.IGNORECASE) for t in WET_LAB_TERMS]

    results = []
    for proj in data.get("results", []):
        # Check title + terms for wet lab signals
        title = proj.get("project_title", "")
        terms = proj.get("terms", "") or ""
        abstract = proj.get("abstract_text", "") or ""
        text = f"{title} {terms} {abstract}"

        if any(pat.search(text) for pat in exclude_pats):
            continue

        results.append(_to_article(proj))

    return results


def _to_article(proj: dict) -> dict:
    """Convert RePORTER project to standard article dict."""
    pi_names = []
    for pi in proj.get("principal_investigators", []):
        name = pi.get("full_name", "").strip()
        if name:
            pi_names.append(name.title())

    pi_str = ", ".join(pi_names[:3])
    if len(pi_names) > 3:
        pi_str += ", et al."

    project_num = proj.get("project_num", "")
    title = proj.get("project_title", "").strip()

    # Activity code (R01, K99, etc.) - extract from project number
    activity_code = proj.get("activity_code", "")
    if not activity_code and project_num:
        # Project number format: 5R01MH123456-02
        parts = project_num.split("-")[0] if "-" in project_num else project_num
        # Extract activity code (e.g., R01, K99, U01)
        import re
        match = re.search(r'([A-Z]\d{2})', parts)
        if match:
            activity_code = match.group(1)

    # Institution in title case
    org = proj.get("organization", {}).get("org_name", "")
    if org:
        org = org.title()

    # Both dates: start date tells you if it's new vs renewal
    start_date = (proj.get("project_start_date") or "")[:10]
    award_date = (proj.get("award_notice_date") or "")[:10]

    date_parts = []
    if start_date:
        date_parts.append(f"Start {start_date}")
    if award_date:
        date_parts.append(f"Awarded {award_date}")
    date_str = " · ".join(date_parts)

    appl_id = proj.get("appl_id")

    return {
        "pmid": "",
        "title": title,
        "authors": pi_str,
        "journal": org,
        "date": date_str,
        "doi": "",
        "issn": "",
        "url": f"https://reporter.nih.gov/project-details/{appl_id}" if appl_id else "",
        "source": "reporter",
        "activity_code": activity_code,  # R01, K99, etc.
        "_start_date": start_date,
        "_appl_id": appl_id,
    }
