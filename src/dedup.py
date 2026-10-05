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


class HistoryCorrupt(Exception):
    """sent_history.json exists but cannot be read."""


def load_history() -> dict:
    """Load sent article history from file.

    A missing file is normal (first run, or cache expired) and returns an empty
    history. An unreadable file is NOT treated as empty silently: it is moved
    aside to sent_history.corrupt.json and HistoryCorrupt is raised, so the
    caller can still send today's digest but report the run as failed.
    """
    if not os.path.exists(HISTORY_FILE):
        return _empty_history()

    try:
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
        if not isinstance(history.get("articles"), dict):
            raise ValueError("missing 'articles' mapping")
        return history
    except (json.JSONDecodeError, OSError, ValueError, AttributeError) as e:
        aside = HISTORY_FILE.replace(".json", ".corrupt.json")
        try:
            os.replace(HISTORY_FILE, aside)
        except OSError:
            pass
        raise HistoryCorrupt(f"{e}; moved to {os.path.basename(aside)}") from e


def _empty_history() -> dict:
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


def _history_keys(art: dict) -> list[str]:
    """Every key an article is remembered under: its DOI and its title.

    Storing both (not DOI-or-title) lets a preprint sent under its DOI be
    recognised later when the published version arrives with a different DOI
    but the same title.
    """
    doi = art.get("doi", "").strip().lower()
    title = art.get("title", "").strip().lower()
    return [k for k in (f"doi:{doi}" if doi else "", f"title:{title}" if title else "") if k]


def filter_against_history(
    all_articles: dict[str, list[dict]], history: dict
) -> dict[str, list[dict]]:
    """Remove articles that were already sent in previous days.

    An article counts as already sent when its DOI matches, its title matches
    exactly, or its title is a fuzzy match (same threshold as same-run dedup)
    to any title in the history.
    """
    sent = history.get("articles", {})
    sent_titles = [k[len("title:"):] for k in sent if k.startswith("title:")]
    # Entries written before 2026-10-05 carry a bare DOI or a bare title as key
    legacy = {k for k in sent if not k.startswith(("doi:", "title:"))}
    sent_titles += [k for k in legacy if not k.startswith("10.")]
    result: dict[str, list[dict]] = {}

    for alert_name, articles in all_articles.items():
        kept = []
        for art in articles:
            doi = art.get("doi", "").strip().lower()
            title = art.get("title", "").strip().lower()
            if any(k in sent for k in _history_keys(art)) or (doi and doi in legacy):
                continue
            if _is_title_duplicate(title, sent_titles):
                continue
            kept.append(art)

        result[alert_name] = kept

    return result


def update_history(
    all_articles: dict[str, list[dict]], history: dict
) -> dict:
    """Add newly sent articles to history, under both DOI and title."""
    today = datetime.now().isoformat()

    for articles in all_articles.values():
        for art in articles:
            for key in _history_keys(art):
                history["articles"][key] = today

    return history
