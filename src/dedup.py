"""Cross-alert deduplication by DOI and fuzzy title matching."""

import json
import os
from datetime import datetime, timedelta
from difflib import SequenceMatcher

SIMILARITY_THRESHOLD = 0.92
HISTORY_FILE = os.path.join(os.path.dirname(__file__), "..", "sent_history.json")
HISTORY_DAYS = 7  # Keep history for 7 days to catch duplicates


def deduplicate(all_articles: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Deduplicate articles across alerts. Higher-priority alerts keep the paper.

    Args:
        all_articles: {alert_name: [article_dicts]} ordered by priority (highest first).

    Returns:
        Same structure with duplicates removed from lower-priority alerts.
    """
    seen_dois: set[str] = set()
    seen_titles: list[str] = []  # for fuzzy matching
    result: dict[str, list[dict]] = {}

    for alert_name, articles in all_articles.items():
        kept = []
        for art in articles:
            doi = art.get("doi", "").strip().lower()
            title = art.get("title", "").strip().lower()

            # Check DOI exact match
            if doi and doi in seen_dois:
                continue

            # Check fuzzy title match
            if _is_title_duplicate(title, seen_titles):
                continue

            kept.append(art)
            if doi:
                seen_dois.add(doi)
            if title:
                seen_titles.append(title)

        result[alert_name] = kept

    return result


def _is_title_duplicate(title: str, seen: list[str]) -> bool:
    """Check if title is a fuzzy match to any previously seen title."""
    if not title:
        return False
    for prev in seen:
        if SequenceMatcher(None, title, prev).ratio() >= SIMILARITY_THRESHOLD:
            return True
    return False


# --- Cross-day deduplication using history file ---


def load_history() -> dict:
    """Load sent article history from file."""
    if not os.path.exists(HISTORY_FILE):
        return {"articles": {}, "last_cleanup": None}

    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"articles": {}, "last_cleanup": None}


def save_history(history: dict) -> None:
    """Save sent article history to file."""
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def cleanup_old_history(history: dict) -> dict:
    """Remove entries older than HISTORY_DAYS."""
    cutoff = (datetime.now() - timedelta(days=HISTORY_DAYS)).isoformat()
    history["articles"] = {
        key: date for key, date in history["articles"].items()
        if date >= cutoff
    }
    history["last_cleanup"] = datetime.now().isoformat()
    return history


def filter_against_history(
    all_articles: dict[str, list[dict]], history: dict
) -> dict[str, list[dict]]:
    """Remove articles that were already sent in previous days.

    Args:
        all_articles: {alert_name: [article_dicts]}
        history: History dict with "articles" containing DOI/title -> date mapping

    Returns:
        Same structure with previously-sent articles removed.
    """
    sent = history.get("articles", {})
    result: dict[str, list[dict]] = {}

    for alert_name, articles in all_articles.items():
        kept = []
        for art in articles:
            doi = art.get("doi", "").strip().lower()
            title = art.get("title", "").strip().lower()

            # Use DOI as primary key, fallback to title
            key = doi if doi else title

            if key and key in sent:
                continue  # Already sent before

            kept.append(art)

        result[alert_name] = kept

    return result


def update_history(
    all_articles: dict[str, list[dict]], history: dict
) -> dict:
    """Add newly sent articles to history.

    Args:
        all_articles: {alert_name: [article_dicts]} - articles that will be sent
        history: History dict to update

    Returns:
        Updated history dict.
    """
    today = datetime.now().isoformat()

    for articles in all_articles.values():
        for art in articles:
            doi = art.get("doi", "").strip().lower()
            title = art.get("title", "").strip().lower()

            # Use DOI as primary key, fallback to title
            key = doi if doi else title

            if key:
                history["articles"][key] = today

    return history
