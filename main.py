"""Literature pipeline orchestrator — 3-section architecture."""

import datetime
import json
import os
from collections import OrderedDict

from src import config, pubmed, dedup, email_format, send, medrxiv, arxiv, reporter

# ---------------------------------------------------------------------------
# Impact Factor lookup for sorting
# ---------------------------------------------------------------------------
_JIF_LOOKUP: dict[str, float] = {}


def _load_jif():
    """Load JIF lookup from data file."""
    global _JIF_LOOKUP
    if _JIF_LOOKUP:
        return
    path = os.path.join(os.path.dirname(__file__), "data", "jif_lookup.json")
    if os.path.exists(path):
        with open(path) as f:
            _JIF_LOOKUP = json.load(f)

# ---------------------------------------------------------------------------
# Preprint Keywords (for filtering medRxiv/bioRxiv/arXiv)
# ---------------------------------------------------------------------------

# Psych keywords for preprint filtering
PSYCH_KEYWORDS = [
    "psychiatr", "mental health", "mental disorder", "depress",
    "anxiety", "PTSD", "suicid", "self-harm", "ADHD", "bipolar",
    "internalizing", "externalizing", "psychopathol",
]

# Methods keywords by subsection for preprint filtering
METHODS_KEYWORDS_EHR = [
    "electronic health record", "EHR", "EMR", "clinical informatics",
    "real-world evidence", "real-world data", "claims data",
    "phenotyping algorithm", "clinical note", "clinical data",
    "multimodal", "data fusion", "integrated data",
]

METHODS_KEYWORDS_WEARABLES = [
    "wearable", "smartwatch", "smart device", "smart ring",
    "accelerom", "actigraphy", "fitbit", "mobile sensor",
    "sensor-based", "GPS tracking", "location tracking",
    "sensor fusion", "multimodal sensing",
]

METHODS_KEYWORDS_AI = [
    "machine learning", "deep learning", "artificial intelligence",
    "natural language processing", "NLP", "large language model", "LLM",
    "GPT", "ChatGPT", "transformer", "foundation model",
    "neural network", "random forest", "XGBoost", "gradient boosting",
    "predictive model", "clinical decision support",
    "text mining", "text classification",
    "time series", "functional data analysis",
    "precision psychiatry", "computational psychiatry",
]

METHODS_KEYWORDS_DIGIPHEN = [
    "digital phenotyp", "ecological momentary assessment", "EMA",
    "passive sensing", "passive data", "digital biomarker",
    "experience sampling", "intensive longitudinal",
    "real-time assessment", "real-time monitoring",
    "daily diary", "momentary data",
    "just-in-time adaptive intervention", "JITAI",
    "digital monitor", "behavioral monitoring",
    "emotion recognition", "screenomics", "app usage",
]

# All methods keywords combined
ALL_METHODS_KEYWORDS = (
    METHODS_KEYWORDS_EHR + METHODS_KEYWORDS_WEARABLES +
    METHODS_KEYWORDS_AI + METHODS_KEYWORDS_DIGIPHEN
)

# NIH RePORTER: Methods keywords (searched across all institutes)
# Logic: NIMH (all grants) OR Methods_Keywords (any institute)
REPORTER_METHODS_KEYWORDS = ALL_METHODS_KEYWORDS


def main():
    today = datetime.date.today()
    is_sunday = today.weekday() == 6
    date_str = today.strftime("%Y-%m-%d")

    # Load JIF lookup for IF sorting
    _load_jif()

    # Load history for cross-day dedup
    history = dedup.load_history()
    history = dedup.cleanup_old_history(history)
    print(f"Loaded history: {len(history.get('articles', {}))} articles from past 7 days")

    # Determine active alerts
    active = [a for a in config.ALERTS if a["daily"] or (a["sunday_only"] and is_sunday)]

    if not active:
        print("No active alerts for today.")
        return

    print(f"Running {len(active)} PubMed alert(s) for {date_str}")

    # ---------------------------------------------------------------------------
    # Step 1: Fetch PubMed articles for each alert
    # ---------------------------------------------------------------------------
    all_articles: OrderedDict[str, dict] = OrderedDict()
    for alert in active:
        print(f"  Searching: {alert['name']} (days_back={alert['days_back']})")
        try:
            pmids = pubmed.search(alert["query"], days_back=alert["days_back"])
            print(f"    Found {len(pmids)} PMIDs")
            articles = pubmed.fetch(pmids)
            print(f"    Fetched {len(articles)} articles")
        except Exception as e:
            print(f"    PubMed search failed for {alert['name']} ({e}), skipping")
            articles = []
        all_articles[alert["name"]] = {
            "articles": articles,
            "section": alert.get("section"),
            "priority": alert["priority"],
            "subsection_order": alert.get("subsection_order", 0),
            "display_name": alert.get("display_name", alert["name"]),
        }

    # ---------------------------------------------------------------------------
    # Step 2: Fetch preprints (daily only)
    # ---------------------------------------------------------------------------
    # For medRxiv: match any keyword (broader — medRxiv is already clinical)
    MEDRXIV_KEYWORDS = PSYCH_KEYWORDS + ALL_METHODS_KEYWORDS

    print("  Searching: medRxiv preprints")
    try:
        medrxiv_articles = medrxiv.search("medrxiv", days_back=1, keywords=MEDRXIV_KEYWORDS)
        print(f"    Found {len(medrxiv_articles)} matching preprints")
    except Exception as e:
        print(f"    medRxiv search failed ({e}), skipping")
        medrxiv_articles = []

    print("  Searching: bioRxiv preprints")
    try:
        biorxiv_articles = medrxiv.search(
            "biorxiv", days_back=1, keywords=[],
            require_both=(PSYCH_KEYWORDS, ALL_METHODS_KEYWORDS),
        )
        print(f"    Found {len(biorxiv_articles)} matching preprints")
    except Exception as e:
        print(f"    bioRxiv search failed ({e}), skipping")
        biorxiv_articles = []

    print("  Searching: arXiv (cs.AI, cs.CL, cs.LG, stat.ML, cs.HC)")
    try:
        arxiv_articles = arxiv.search(
            days_back=1,
            require_both=(PSYCH_KEYWORDS, ALL_METHODS_KEYWORDS),
        )
        print(f"    Found {len(arxiv_articles)} matching preprints")
    except Exception as e:
        print(f"    arXiv search failed ({e}), skipping")
        arxiv_articles = []

    # Combine all preprints
    all_preprints = medrxiv_articles + biorxiv_articles + arxiv_articles

    # ---------------------------------------------------------------------------
    # Step 3: Classify preprints into subsections
    # ---------------------------------------------------------------------------
    preprints_by_subsection = classify_preprints(all_preprints)

    # Add preprints to Section 1 subsections (Psych × Methods)
    for subsection_name in ["EHR", "Wearables", "AI/ML", "Digital Phenotyping"]:
        if subsection_name in all_articles:
            preprints = preprints_by_subsection.get(subsection_name, [])
            # Mark preprints for sorting (peer-reviewed first, preprints last)
            for p in preprints:
                p["_is_preprint"] = True
            all_articles[subsection_name]["articles"].extend(preprints)

    # ---------------------------------------------------------------------------
    # Step 4: Fetch database preprints (weekly only)
    # ---------------------------------------------------------------------------
    if is_sunday:
        for db_name, db_keywords in config.DATABASE_KEYWORDS.items():
            try:
                db_medrxiv = medrxiv.search("medrxiv", days_back=7, keywords=db_keywords)
                db_biorxiv = medrxiv.search("biorxiv", days_back=7, keywords=db_keywords)
            except Exception as e:
                print(f"    Weekly preprint search failed for {db_name} ({e}), skipping")
                continue

            db_preprints = db_medrxiv + db_biorxiv
            if db_name in all_articles and db_preprints:
                for p in db_preprints:
                    p["_is_preprint"] = True
                all_articles[db_name]["articles"].extend(db_preprints)
                print(f"    Added {len(db_preprints)} preprints to {db_name}")

    # ---------------------------------------------------------------------------
    # Step 5: Hierarchical deduplication
    # ---------------------------------------------------------------------------
    # Group alerts by section
    sections = {}
    for name, data in all_articles.items():
        section = data.get("section", "Other")
        if section not in sections:
            sections[section] = OrderedDict()
        sections[section][name] = data

    # Dedup within each section first (higher priority subsection keeps article)
    for section_name, section_alerts in sections.items():
        # Sort by priority within section
        sorted_names = sorted(section_alerts.keys(), key=lambda n: section_alerts[n]["priority"])
        flat = OrderedDict((n, section_alerts[n]["articles"]) for n in sorted_names)
        deduped = dedup.deduplicate(flat)
        for n in sorted_names:
            all_articles[n]["articles"] = deduped[n]

    # Global dedup across sections (Section 1 > Section 2 > Section 3 > Weekly)
    all_names = sorted(all_articles.keys(), key=lambda n: all_articles[n]["priority"])
    flat = OrderedDict((n, all_articles[n]["articles"]) for n in all_names)
    deduped = dedup.deduplicate(flat)
    for n in all_names:
        all_articles[n]["articles"] = deduped[n]

    # ---------------------------------------------------------------------------
    # Step 6: NIH RePORTER (weekly, Sundays only)
    # ---------------------------------------------------------------------------
    if is_sunday:
        print("  Searching: NIH RePORTER (NIMH + Methods)")
        try:
            grants = reporter.search(REPORTER_METHODS_KEYWORDS, nimh_all=True)
            print(f"    Found {len(grants)} new grants")
        except Exception as e:
            print(f"    NIH RePORTER search failed ({e}), skipping")
            grants = []
        if grants:
            all_articles["NIH RePORTER (New Grants)"] = {
                "articles": grants,
                "section": "NIH RePORTER",
                "priority": 5,
                "subsection_order": 0,
            }

    # ---------------------------------------------------------------------------
    # Step 7: Cross-day dedup and sort
    # ---------------------------------------------------------------------------
    # Cross-day dedup: remove articles sent in previous days
    all_names = list(all_articles.keys())
    flat = OrderedDict((n, all_articles[n]["articles"]) for n in all_names)
    filtered = dedup.filter_against_history(flat, history)
    for n in all_names:
        all_articles[n]["articles"] = filtered[n]

    # Sort articles within each subsection (peer-reviewed by date, preprints last)
    for name, data in all_articles.items():
        data["articles"] = sort_within_subsection(data["articles"])

    # Sort alerts by priority
    all_articles = OrderedDict(
        sorted(all_articles.items(), key=lambda x: x[1]["priority"])
    )

    # ---------------------------------------------------------------------------
    # Step 8: Build and send email
    # ---------------------------------------------------------------------------
    total = sum(len(v["articles"]) for v in all_articles.values())
    print(f"Total articles after dedup: {total}")

    if total == 0:
        print("No articles found. Skipping email.")
        return

    # Build email
    html = email_format.build(all_articles, date_str)

    # Write HTML preview
    preview_path = os.path.join(os.path.dirname(__file__), "preview.html")
    with open(preview_path, "w") as f:
        f.write(html)
    print(f"Preview saved to {preview_path}")

    # Send email if credentials available
    if os.environ.get("GMAIL_APP_PASSWORD"):
        subject = f"\U0001f4da {date_str}"
        send.send_email(html, subject)

        # Update history with sent articles
        flat = OrderedDict((n, all_articles[n]["articles"]) for n in all_articles.keys())
        history = dedup.update_history(flat, history)
        dedup.save_history(history)
        print(f"Updated history: {len(history.get('articles', {}))} total articles")
    else:
        print("GMAIL_APP_PASSWORD not set — skipping email send.")


def classify_preprints(preprints: list[dict]) -> dict[str, list[dict]]:
    """Classify preprints into methods subsections based on title/abstract.

    Each preprint goes to the FIRST matching subsection (priority order).
    Returns dict of subsection_name -> list of preprints.
    """
    result = {
        "EHR": [],
        "Wearables": [],
        "AI/ML": [],
        "Digital Phenotyping": [],
    }

    subsection_keywords = [
        ("EHR", METHODS_KEYWORDS_EHR),
        ("Wearables", METHODS_KEYWORDS_WEARABLES),
        ("AI/ML", METHODS_KEYWORDS_AI),
        ("Digital Phenotyping", METHODS_KEYWORDS_DIGIPHEN),
    ]

    for preprint in preprints:
        text = (preprint.get("title", "") + " " + preprint.get("abstract", "")).lower()

        # Find first matching subsection
        for subsection_name, keywords in subsection_keywords:
            if any(kw.lower() in text for kw in keywords):
                result[subsection_name].append(preprint)
                break  # Only assign to first matching subsection

    return result


def sort_within_subsection(articles: list[dict]) -> list[dict]:
    """Sort articles: peer-reviewed by IF descending, preprints at end.

    Peer-reviewed articles are sorted by Impact Factor (highest first).
    Within the same IF, articles are sorted by date (newest first).
    Preprints are placed at the end, sorted by date.
    """
    peer_reviewed = [a for a in articles if not a.get("_is_preprint")]
    preprints = [a for a in articles if a.get("_is_preprint")]

    # Two-pass stable sort: first by date desc, then by IF desc
    # This ensures within same IF tier, newest articles come first
    peer_reviewed.sort(key=lambda a: a.get("date", ""), reverse=True)
    peer_reviewed.sort(key=lambda a: -_JIF_LOOKUP.get(a.get("issn", ""), 0.0))

    # Sort preprints by date (newest first)
    preprints.sort(key=lambda a: a.get("date", ""), reverse=True)

    return peer_reviewed + preprints


if __name__ == "__main__":
    main()
