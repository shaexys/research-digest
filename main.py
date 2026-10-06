"""Literature pipeline orchestrator — 3-section architecture."""

import datetime
import json
import os
import sys
from collections import OrderedDict

from src import config, pubmed, dedup, email_format, send, medrxiv, arxiv, reporter
from src.keywords import compile_all, matches_any

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
# Topic side of the OR: whole-word psych terms (RePORTER does not stem)
REPORTER_TOPIC_KEYWORDS = arxiv.DEFAULT_API_TERMS


def main():
    today = datetime.date.today()
    is_sunday = today.weekday() == 6
    date_str = today.strftime("%Y-%m-%d")

    # Manual reruns (workflow_dispatch input) can widen the window to recover a
    # missed day; history still suppresses anything already sent.
    override = os.environ.get("DAYS_BACK", "").strip()
    days_override = int(override) if override.isdigit() and int(override) > 0 else None
    if days_override:
        print(f"DAYS_BACK override: daily window = {days_override} day(s)")
    daily_days = days_override or 1

    # Every source that errors is recorded here, named in the email banner, and
    # turns the run red (exit 1) so GitHub sends a failure notice.
    failed: list[str] = []

    # Load history for cross-day dedup
    try:
        history = dedup.load_history()
    except dedup.HistoryCorrupt as e:
        print(f"  Dedup history unreadable ({e}); continuing with empty history")
        failed.append("dedup history (repeats possible)")
        history = {"articles": {}, "last_cleanup": None}
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
        days = max(alert["days_back"], days_override or 0)
        print(f"  Searching: {alert['name']} (days_back={days})")
        try:
            pmids = pubmed.search(alert["query"], days_back=days)
            print(f"    Found {len(pmids)} PMIDs")
            articles = pubmed.fetch(pmids)
            print(f"    Fetched {len(articles)} articles")
            if alert.get("issn_query") and config.ISSN_SET:
                # Whitelist journals: search without a journal filter, keep by ISSN
                extra = pubmed.fetch(pubmed.search(alert["issn_query"], days_back=days))
                kept = [a for a in extra if config.ISSN_SET & set(a.get("issns") or [])]
                print(f"    ISSN whitelist: {len(kept)} of {len(extra)} unfiltered articles kept")
                articles.extend(kept)
        except Exception as e:
            print(f"    PubMed search failed for {alert['name']} ({e}), skipping")
            failed.append(f"PubMed: {alert.get('display_name', alert['name'])}")
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
        medrxiv_articles = medrxiv.search("medrxiv", days_back=daily_days, keywords=MEDRXIV_KEYWORDS)
        print(f"    Found {len(medrxiv_articles)} matching preprints")
    except Exception as e:
        print(f"    medRxiv search failed ({e}), skipping")
        failed.append("medRxiv")
        medrxiv_articles = []

    print("  Searching: bioRxiv preprints")
    try:
        biorxiv_articles = medrxiv.search(
            "biorxiv", days_back=daily_days, keywords=[],
            require_both=(PSYCH_KEYWORDS, ALL_METHODS_KEYWORDS),
        )
        print(f"    Found {len(biorxiv_articles)} matching preprints")
    except Exception as e:
        print(f"    bioRxiv search failed ({e}), skipping")
        failed.append("bioRxiv")
        biorxiv_articles = []

    print("  Searching: arXiv (cs.AI, cs.CL, cs.LG, stat.ML, cs.HC)")
    try:
        arxiv_articles = arxiv.search(
            days_back=daily_days,
            require_both=(PSYCH_KEYWORDS, ALL_METHODS_KEYWORDS),
        )
        print(f"    Found {len(arxiv_articles)} matching preprints")
    except Exception as e:
        print(f"    arXiv search failed ({e}), skipping")
        failed.append("arXiv")
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
            db_found = {}
            for server, label in (("medrxiv", "medRxiv"), ("biorxiv", "bioRxiv")):
                try:
                    db_found[server] = medrxiv.search(server, days_back=7, keywords=db_keywords)
                except Exception as e:
                    print(f"    Weekly {label} search failed for {db_name} ({e}), skipping")
                    failed.append(f"{label} ({db_name})")
                    db_found[server] = []
            db_medrxiv, db_biorxiv = db_found["medrxiv"], db_found["biorxiv"]

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
        print("  Searching: NIH RePORTER (NIMH + Methods + Topic; new and competing awards)")
        try:
            grants = reporter.search(REPORTER_METHODS_KEYWORDS, nimh_all=True,
                                     topic_keywords=REPORTER_TOPIC_KEYWORDS)
            print(f"    Found {len(grants)} new grants")
        except Exception as e:
            print(f"    NIH RePORTER search failed ({e}), skipping")
            failed.append("NIH RePORTER")
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

    if total == 0 and not failed:
        print("No articles found. Skipping email.")
        return
    if total == 0:
        # Nothing to list, but say which sources failed rather than send nothing
        html = email_format.failure_notice(date_str, failed)
        if os.environ.get("GMAIL_APP_PASSWORD"):
            send.send_email(html, f"\u26a0\ufe0f {date_str}: sources failed")
        _exit_if_failed(failed)
        return

    # Build email
    html = email_format.build(all_articles, date_str, failed_sources=failed)

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
        print("GMAIL_APP_PASSWORD not set: skipping email send (preview only).")

    # History is saved above BEFORE this exit, so items already emailed are not
    # resent tomorrow even though the run is marked failed.
    _exit_if_failed(failed)


def _exit_if_failed(failed: list[str]) -> None:
    if failed:
        print(f"FAILED SOURCES: {', '.join(failed)}")
        sys.exit(1)


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

    compiled = [(name, compile_all(kws)) for name, kws in subsection_keywords]

    for preprint in preprints:
        text = preprint.get("title", "") + " " + preprint.get("abstract", "")

        # Find first matching subsection (acronyms match whole words only)
        for subsection_name, patterns in compiled:
            if matches_any(text, patterns):
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
    peer_reviewed.sort(key=lambda a: -email_format.jif_for(a))

    # Sort preprints by date (newest first)
    preprints.sort(key=lambda a: a.get("date", ""), reverse=True)

    return peer_reviewed + preprints


if __name__ == "__main__":
    main()
