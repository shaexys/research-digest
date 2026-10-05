"""Keyword matching shared by the preprint filters and the subsection classifier."""

import re


def compile_keyword(kw: str) -> re.Pattern:
    """Compile one keyword into a case-insensitive pattern.

    Acronyms (all caps, e.g. "EMA", "EHR", "NLP") match as whole words only, so
    "EMA" no longer hits "female" and "GPS" no longer hits inside other words.
    Everything else stays a substring match, because stems such as "psychiatr"
    or "depress" are meant to catch every inflection.
    """
    letters = re.sub(r"[^A-Za-z]", "", kw)
    if letters and letters.isupper():
        return re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE)
    return re.compile(re.escape(kw), re.IGNORECASE)


def compile_all(keywords: list[str]) -> list[re.Pattern]:
    return [compile_keyword(kw) for kw in keywords]


def matches_any(text: str, patterns: list[re.Pattern]) -> bool:
    return any(p.search(text) for p in patterns)
