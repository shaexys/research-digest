# Research Digest — Design

A lightweight, opinionated pipeline for daily literature discovery. One HTML email in your inbox at 8am with new PubMed papers, preprints, and NIH grants, filtered to your research focus.

This document explains **why** the pipeline is structured the way it is. If you want to install and run it, see the [README](README.md). If you want to understand the design tradeoffs so you can adapt it, read on.

---

## Overview

```
📬 Research Digest
│
├── 📊 Daily Sections
│   │
│   ├── 1. Psych × Methods ────────────────── Core intersection
│   │   ├── EHR ──────────────────────── PubMed + Preprints
│   │   ├── Wearables ───────────────── PubMed + Preprints
│   │   ├── AI / ML ──────────────────── PubMed + Preprints
│   │   └── Digital Phenotyping ─────── PubMed + Preprints
│   │
│   ├── 2. General Psychiatry ─────────────────── No subsections
│   │   └── (flat list, no preprints)
│   │
│   └── 3. General Methods ─────────────────── Methods only, no Psych filter
│       ├── EHR ──────────────────────── PubMed only
│       ├── Wearables ───────────────── PubMed only
│       ├── AI / ML ──────────────────── PubMed only
│       └── Digital Phenotyping ─────── PubMed only
│
└── 📅 Weekly Sections (Sunday)
    │
    ├── Research Databases ──────────────── Papers using specific databases
    │   ├── ABCD Study ──────────────── PubMed + Preprints
    │   ├── Epic Cosmos ─────────────── PubMed + Preprints
    │   └── All of Us ───────────────── PubMed + Preprints
    │
    └── NIH RePORTER ───────────────────── Newly funded grants
        └── Institute filter ∪ Methods keywords
```

**Design tenets:**

1. **Triage by title**, not by AI summary. Scanning 40 one-line titles with a journal tag is faster than reading 40 AI-generated abstracts.
2. **Modular**. Adding a new topic is a new Python dict, not a new API integration.
3. **Free**. GitHub Actions cron + Gmail SMTP costs $0/month for personal volume.
4. **Self-hosted**. No user data leaves your infrastructure.

The pipeline is deliberately **not a SaaS**. Each user forks and configures their own instance.

---

## Section Logic

Before the section-by-section details, a quick map of **what kinds of filters are in play**. The pipeline composes four filter dimensions, each with a distinct purpose:

| Filter Type | Example | Rationale |
|-------------|---------|-----------|
| **Named-journal whitelists** | `JOURNAL_TOP_MED`, `JOURNAL_TOP_PSYCH`, `JOURNAL_CLINICAL_INFORMATICS` | Hard-coded quality anchor. You trust papers in *Lancet* / *JAMA* / *BMJ* / your top field journals regardless of topic. Used in all PubMed sections. |
| **IF-based ISSN whitelist** | `_ISSN_LIST` (IF ≥ your cutoff, from JCR) | Breadth extension. Catches high-quality work in specialized journals you didn't pre-list. Used only in Section 1 (where strong topic filter already anchors relevance). |
| **Topic keyword modules** | `PSYCH` (domain), `EHR_METHODS` / `AI_METHODS` / `WEARABLES_METHODS` / ... | The substantive filter. Combines with journal filter via `AND` to get papers that are *both* in good journals *and* on your topic. Used in all sections. |
| **Exclusion list** | `WET_LAB_TERMS` (mouse, rodent, GWAS, knockout, ...) | Safety net for the comprehensive positive filter. Catches items your broad keyword search pulls in but you know you don't want — e.g., an informatics researcher can exclude wildlife / marine terms; a clinical epi researcher excludes molecular biology terms. Currently used only in NIH RePORTER (where wet lab signal-to-noise is worst). |

The `∪` (union) notation in each section's "Journals" line below means "any of these journal lists" — PubMed's `OR` operator combining the whitelists. The pipeline then layers topic keywords via `AND` on top.

### Section 1 — Psych × Methods

```
Query:    (AllJournals) AND (Psych) AND (Methods_Subsection)
Journals: TopMed ∪ TopPsych ∪ ClinicalInformatics ∪ ISSN_Whitelist (IF ≥ cutoff)
Content:  4 subsections by methods type (EHR / Wearables / AI-ML / Digital Phenotyping)
Preprint: Yes — medRxiv / bioRxiv / arXiv with Psych × Methods keywords
Sorting:  IF descending, preprints last
```

Section 1 is **the intersection**: papers at the overlap of your domain and your methods interest. These are the papers you're most likely to cite. Journal set is widest (including the ISSN whitelist) because signal is strong after the intersection filter.

Throughout this document, section and variable names use the default template (psychiatry). When you fork for another field, the same structure applies — rename `PSYCH` to `CARDIO` / `NEURO` / etc. and relabel the sections accordingly.

### Section 2 — General Psychiatry

```
Query:    (TopPsych all) OR ((TopMed ∪ ClinicalInformatics) AND Psych)
Journals: TopMed ∪ TopPsych ∪ ClinicalInformatics (no ISSN whitelist)
Content:  Flat list, no subsections
Preprint: No (volume too high without a methods filter — see note below)
Dedup:    Against Section 1
Sorting:  IF descending
```

Section 2 catches **domain papers outside your methods focus**. Kept flat because sub-dividing a small daily volume fragments the list. ISSN whitelist dropped because top-tier domain journals already anchor quality — adding the whitelist here would swamp the section with tangential work.

**Preprints are excluded** because the domain-only filter (no methods intersection) matches too many medRxiv / bioRxiv papers per day to triage. Preprints are quality-variable; without the additional methods filter (as in Section 1), the email becomes unreadable.

### Section 3 — General Methods

```
Query:    (TopMed ∪ ClinicalInformatics) AND (Methods_Subsection)
Journals: TopMed ∪ ClinicalInformatics only (no ISSN whitelist, no TopPsych)
Content:  4 subsections matching Section 1
Preprint: No (same volume reason as Section 2)
Dedup:    Against Sections 1 + 2
Sorting:  IF descending
```

Section 3 captures **methods innovations from other fields**. A new EHR phenotyping method in oncology may transport to your domain — you want to see it, but only from quality medical journals (not the full whitelist, which would dilute the signal).

Preprints excluded for the same reason as Section 2: without the domain intersection, the daily volume of methods preprints is too high for email triage.

### Weekly — Research Databases

```
Query:    Database-specific keywords
Sources:  PubMed + medRxiv + bioRxiv
Sections: One subsection per database
Preprint: Yes
```

Designed around **specific data sources** (public research databases, registries, cohorts). A weekly cadence suits these because daily volume is often 0-1.

### Weekly — NIH RePORTER

```
Query:    Institute_filter (e.g., NIMH all grants) OR Methods_Keywords (any institute)
Filter:   newly_added_projects_only: true
Exclude:  Wet lab terms (mouse, GWAS, cell line, knockout, etc.)
Display:  Activity code (R01, K99), Institution, Start / award dates
```

**Why weekly, not daily:** RePORTER updates roughly weekly in batches. Polling daily yields many empty days punctuated by large drops.

---

## Design Decisions

This section documents the non-obvious choices embedded in the pipeline. Each is a checkpoint you may want to reconsider when adapting the pipeline.

### 1. Two-layer module structure

Alert strategies (topic × method logic) and module definitions (keyword lists) are separated.

```python
# Layer 1: module definitions (keyword lists)
PSYCH = '"Mental Health"[MeSH] OR ...'
EHR_METHODS = '"Electronic Health Records"[MeSH] OR ...'

# Layer 2: alert strategies (how modules combine)
ALERTS = [{"query": f"({PSYCH}) AND ({EHR_METHODS})", ...}]
```

Adding a new topic = add one module + reference it in alert definitions. You never touch the API code in `pubmed.py` / `medrxiv.py` / etc.

### 2. POST for PubMed, not GET (handles long queries)

PubMed's E-utilities accept queries via two HTTP methods: **GET** (query in URL) or **POST** (query in request body). GET has a URL length ceiling (~2000 characters). When the ISSN whitelist grows past ~1500 journals, the query string exceeds this and the API returns a `414 URI Too Long` error.

POST has no meaningful length limit on the body, so the pipeline uses POST throughout. Practical effect: your whitelist can grow to tens of thousands of ISSNs without breaking anything.

### 3. bioRxiv uses AND logic; medRxiv uses OR

medRxiv is medicine-focused: base rate of wet lab noise is low. OR logic (any match to domain OR methods keywords) yields manageable volume (~4/day).

bioRxiv is biology-dominant: ~80% of OR-matched papers are molecular wet lab work. AND logic (topic × method both required) cuts volume from ~74/day to ~8/day, mostly relevant.

### 4. arXiv: category filter in API, keyword filter locally

arXiv's API does not support `submittedDate` range with a `cat:` prefix. Workaround: submit a broad category query (`cat:cs.AI OR cat:cs.CL OR cat:cs.LG OR cat:stat.ML OR cat:cs.HC`), then filter results locally by domain × methods keywords.

### 5. NIH RePORTER: 30-term wet lab exclusion

Roughly half of NIMH R01 grants are animal model / molecular biology. A 30-term exclusion list (`mouse`, `mice`, `rodent`, `GWAS`, `knockout`, `optogenetic`, ...) cuts that noise by ~60% without losing clinical epidemiology or informatics grants.

Removed from the list because they over-trigger: `protein`, `blood sample`, `biospecimen`, `plasma level`. These appear in relevant work (e.g., biomarker prediction modeling).

### 6. Institute filter vs keyword filter (RePORTER)

Query is `NIMH_all_grants OR Methods_Keywords_any_institute`. Rationale:

- Psychiatry-related grants are clustered at NIMH — capturing the institute captures most domain work without needing keywords.
- Methods/AI grants are distributed across NIMH, NLM, NHLBI, OD, etc. — captured via keyword OR.

### 7. Gmail SMTP over SendGrid

SendGrid's free tier expires after 60 days. Gmail app passwords are permanent and free for personal sending volume (<500/day). For a personal digest sending to one inbox, Gmail wins on simplicity and durability.

### 8. DOI links over PubMed URLs

DOI links go directly to the publisher. PubMed URLs add a click before the article. Where no DOI exists, fall back to PubMed URL.

### 9. Global dedup across sources

A paper can appear in PubMed (published version) and medRxiv (preprint version) on different days. DOI match catches identical DOIs; fuzzy title (≥92% Levenshtein similarity) catches cases where DOIs differ or are missing.

Dedup cascade across sections: Section 1 → Section 2 → Section 3 → Weekly. A paper matched in a higher-priority section does not appear in lower-priority sections.

### 10. 7-day cross-day dedup history

In addition to within-email dedup, a persistent 7-day history file (`sent_history.json`) prevents the same paper from reappearing in subsequent daily emails. Cached across GitHub Actions runs via `actions/cache`.

Why 7 days and not longer: papers from 8+ days ago can reappear if still relevant, which is intentional — catches slow-indexing journals and preprint-to-publication transitions.

### 11. Preprints only in Section 1 (and Weekly Databases)

Sections 2 and 3 are peer-reviewed only. Adding preprints to General Psychiatry or General Methods sections would flood the email: without the Psych × Methods intersection, medRxiv / bioRxiv / arXiv volumes are too high for morning triage, and preprints are quality-variable.

Preprints belong where the filter is tightest (Section 1 — Psych × Methods intersection) and in the weekly database section (where filtering is by specific database name, so signal is already narrow).

### 12. Daily vs weekly cadence

- **Daily**: PubMed sections + preprints. New peer-reviewed papers show up continuously; daily polling catches them fresh.
- **Weekly (Sunday)**: Research Databases + NIH RePORTER.
  - *Research Databases* use very specific queries (e.g., `"UK Biobank"[tiab]`), so daily volume is often 0-1. Weekly batching keeps the weekend review readable.
  - *NIH RePORTER* updates grants in batches roughly weekly. Polling daily yields many empty days punctuated by large drops.

### 13. No AI summaries

This is a deliberate design choice, not a missing feature. A human reading a journal-tagged title scans faster than reading an AI abstract — especially when the AI occasionally hallucinates. The pipeline optimizes for **triage density**, not depth.

---

## ISSN Whitelist

### Purpose

Section 1 uses a large ISSN whitelist (e.g., journals with IF ≥ 7) as an **inclusive journal filter**. This catches high-quality work in specialized journals (e.g., statistics methods journals, specific clinical subfields) that wouldn't be in your top-tier lists.

Sections 2 and 3 intentionally do **not** use this whitelist — their top-tier lists are already sufficient.

### Licensing note

Journal Impact Factor data comes from Clarivate JCR, which prohibits redistribution of the dataset. **This template ships with an empty ISSN whitelist**, and the pipeline falls back gracefully when JIF data is absent (IF tags simply don't render in the email; everything else works).

If you have access to JCR (typically through a university library subscription):

1. Go to https://jcr.clarivate.com/jcr/browse-journals → Sign In with your institution's SSO (the exact path varies — your library's Databases page usually links to JCR or Web of Science).
2. Apply a JIF filter (e.g., ≥ 7) and Export the filtered list. JCR Export has a per-session row limit — if your filtered set exceeds it, either raise the cutoff or export in batches (by IF band, Category, or Edition).
3. Save the CSV / Excel anywhere locally.
4. Either:
    - **Use the Claude Code skill** (`research-digest-setup`) → hand it the file path → it auto-parses ISSN + JIF columns and writes both `_ISSN_LIST` in `src/config.py` and `data/jif_lookup.json`.
    - **Or do it manually:** copy the ISSN column from the export, paste as a pipe-separated string into `_ISSN_LIST`; compute `jif_lookup.json` as `{ISSN: JIF}` mapping.

If you don't have JCR access, **skip this**. Section 1 will fall back to the top-tier journal sets (TopMed ∪ TopPsych ∪ ClinicalInformatics) and still produce useful results.

Same principle applies to `jif_lookup.json` (the per-ISSN IF values rendered as email tags): compute it locally from your JCR export, or simply don't provide the file. Never commit it.

---

## Deduplication Rules

| Level | Rule |
|-------|------|
| Cross-section | Section 1 → 2 → 3 → Weekly. Higher-priority section keeps the article. |
| Within-section | Subsections deduped in order (EHR → Wearables → AI/ML → Digital Phenotyping). |
| Cross-day | Persistent 7-day history file prevents repeat sends across daily runs. |
| Matching | DOI exact match first; fuzzy title (Levenshtein ≥ 92% similarity) as fallback. |

The 7-day history file is cached across GitHub Actions runs via `actions/cache`. Articles from 8+ days ago can reappear if they're still relevant — this is intentional (surfaces slow-indexing journals and preprint-to-publication transitions).

---

## Data Source Tradeoffs

| Source | API | Method | Keyword Support | Affiliation Data |
|--------|-----|--------|-----------------|------------------|
| PubMed | E-utilities esearch / efetch | POST (long queries) | Full boolean + MeSH | No |
| medRxiv / bioRxiv | `api.medrxiv.org/details/{server}/{date1}/{date2}` | GET, date-range pull | Local only (no server-side) | Yes (`author_corresponding_institution`) |
| arXiv | `export.arxiv.org/api/query` | GET, category + keyword | `cat:` + `ti:` / `abs:` | No (rarely populated) |
| NIH RePORTER | `api.reporter.nih.gov/v2/projects/search` | POST JSON | `advanced_text_search` | Yes (institution) |

**Why these four and not others:**

- **Scopus / Web of Science:** paid APIs, not useful for a free template.
- **Google Scholar:** no public API, scraping is fragile and ToS-problematic.
- **Semantic Scholar:** excellent but overlaps heavily with PubMed for clinical work, adds dedup complexity.
- **ClinicalTrials.gov:** not a journal source, different triage cadence — would belong in a separate weekly section if added.

---

## Email Design Rationale

| Decision | Rationale |
|----------|-----------|
| Table of contents at top | Summarizes daily volume. Anchors are unreliable in some email clients (see README). |
| Journal tag = colored pill, IF tag = grey outline | IF is secondary; journal name carries more information per millimeter of screen space. |
| Institution tag (pink) for preprint corresponding authors + RePORTER orgs | Affiliations matter for triage ("oh, it's from that group"). |
| h3 subsection headers with grey background + left border | Distinguishes from article titles at a glance. |
| Title casing for journal names | Keeps acronyms (BMJ, JAMA) intact, lowercases small words (of, the), capitalizes rest. |
| DOI link wrapping title, not separate "DOI:" line | Every pixel of vertical space costs scroll. |
| No AI summaries | See Design Decision #10. |

---

## What's not in this template

This pipeline does **not**:

- Summarize papers with AI.
- Rank by a "relevance score" beyond journal IF.
- Track which papers you've opened or saved.
- Integrate with Zotero, Mendeley, or any reference manager.
- Notify you in real-time — it's a daily batch.

These are deliberate omissions. If you want these features, this pipeline is the wrong starting point. If the simplicity resonates, fork away.

---

## References

Built on top of:

- [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25497/) (PubMed search)
- [medRxiv / bioRxiv API](https://api.biorxiv.org/)
- [arXiv API](https://info.arxiv.org/help/api/index.html)
- [NIH RePORTER API v2](https://api.reporter.nih.gov/)
- [GitHub Actions](https://docs.github.com/en/actions) (scheduler)
- Gmail SMTP (delivery)

No Python dependencies beyond `requests` and `python-Levenshtein`.
