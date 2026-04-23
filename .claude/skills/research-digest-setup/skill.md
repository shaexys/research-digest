---
name: research-digest-setup
description: Walk a user through setting up their own instance of the research-digest pipeline. Use when the user wants to install research-digest, configure their research focus, set up GitHub Actions secrets, or trigger the first test run. Handles forking, config.py editing, secret management, and graceful handling of optional components like JCR data.
---

# Research Digest Setup

You are guiding a user to set up their own personal instance of the research-digest pipeline. Target outcome: a working GitHub Actions cron job that delivers a daily literature email to the user's inbox.

## Before starting

1. Read `DESIGN.md` (in this repo) to understand the pipeline architecture — specifically the 3 daily + 2 weekly section structure and the two-layer module design (alert strategies vs module definitions).
2. Read `README.md` § Setup prerequisites for the full list of accounts and tools the user will need.

Announce your plan briefly: "I'll walk you through this in 5 phases: research context → fork → configure → secrets → test. Stop me anytime to adjust."

## Phase 0: Check prerequisites

Run these checks silently and report results in one table:

```bash
which git
which gh
gh auth status
```

Confirm with the user that they have:
- A GitHub account (required)
- A Gmail account with 2-Step Verification enabled (required — needed for app passwords)
- A destination email (can be the same Gmail)
- *Optional:* NCBI account for an API key (raises PubMed rate limit)
- *Optional:* institutional access to Clarivate JCR for IF tags

If `gh` is not installed, stop and tell them: `brew install gh && gh auth login`.

## Phase 1: Gather research context

Ask questions one at a time. Each question uses a **collect → validate → confirm** rhythm: gather keywords from the user, build a PubMed query, run `esearch.fcgi` against PubMed, show count + 5 sample titles via `esummary.fcgi`, then get sign-off before proceeding.

**Smart defaults for AND/OR logic (do not ask the user when defaults obviously apply):**
- Synonym group within a keyword module → **OR** (never ask — "cancer OR tumor OR oncology" is obviously union)
- Topic + population or geographic constraint → **AND** (state the interpretation in one line when showing the validated query; user can override)
- Topic × Methodology across axes → **AND** (never ask — near-universal)

**Only ask AND vs OR explicitly** when the user has 2+ independent modules on the **same axis** (e.g., two methodology modules — unclear whether intersection or union). In those cases, show both interpretations side-by-side with validated counts + samples, and let the user pick by example — never ask the abstract AND/OR question without showing results.

**Presentation (Flat vs Split subsections)** is a separate decision from logic. Split only applies under OR logic. Ask only after logic is confirmed.

**Never showcase this template's default research focus** (psychiatry, EHR, wearables, AI) as "recommended." They are one researcher's defaults, not best practices. Use generic examples (RCTs, cohort studies, survival analysis, machine learning) when illustrating categories.

### Q1. Topic focus (required)

Ask:

"What topic do you want to filter papers on? This can be:
- A broad domain (e.g., oncology, cardiology, epidemiology)
- A narrower subfield (e.g., breast cancer, heart failure)
- A specific theme within a domain (e.g., oncology + nutrition, depression + inflammation)
- Multiple related areas in combination
- Any of the above with a population or geographic cut (e.g., pediatric oncology, US adult cardiology cohorts)

Describe it in plain English — I'll build a PubMed-compatible keyword module and verify it returns what you expect."

After they describe the topic:

1. Build a `TOPIC` keyword module: MeSH umbrella terms + `[tiab]` free-text synonyms. Use wildcards (`metasta*`) only when you are confident they resolve to well under 600 variants.
2. If the user's description embedded a population/geographic cut (e.g., "pediatric oncology", "older adults"), build it as a separate `POPULATION` module and combine as `TOPIC AND POPULATION`.
3. Run live validation: `esearch.fcgi?reldate=7` for count and IDs, then `esummary.fcgi` for 5 sample titles.
4. Show the user:

    ```
    Proposed keyword modules:
      TOPIC = <query block>
      POPULATION = <query block>   (if applicable)

    Validated against last 7 days of PubMed:
      Count: N papers
      Query translation: <echo what PubMed parsed>
      Samples: <5 titles with journal names>

    Interpretation: papers about <topic> in <population>  (TOPIC AND POPULATION)

    Looks right?
    ```

5. Common adjustments the user may ask: narrow further (specific subtypes), exclude noise, expand with additional synonyms, swap out terms. Re-validate after each adjustment.

### Q2. Methodology focus (optional — skip if no methodology filter)

Ask:

"Do you want to filter on specific methodologies? Skip if you care about topic alone and want any methodology. Methodology has two sub-axes — pick from either or both, or define your own:

**Design** (what the study IS):
- Study design: randomized controlled trials, cohort, case-control, cross-sectional, systematic review / meta-analysis
- Data source: clinical trial data, electronic health records, registries, claims, imaging, administrative data

**Analysis** (how analysis is done):
- Regression modeling: linear, logistic, survival (Cox / hazard ratios), mixed-effects
- Machine learning / prediction modeling
- Causal inference: target trial emulation, IPTW, matching, instrumental variables
- Longitudinal / latent-class / trajectory modeling
- Meta-analysis / functional data / time-series

List the categories that matter, or say **skip**. For each you list, I'll build a keyword module and validate it — ANDed with your confirmed TOPIC AND POPULATION filter."

For each module the user provides:

1. Build keywords: MeSH + `[tiab]` + `[Publication Type]` where relevant (e.g., `"Randomized Controlled Trial"[Publication Type]` for RCTs).
2. Validate each module alone (intersected with TOPIC AND POPULATION) via `esearch.fcgi?reldate=30`. Fetch samples.
3. Show each validated module with count + samples.

### Q2b. Logic between methodology modules (only if 2+ modules)

If user provided 2+ methodology modules, show both interpretations side by side:

```
Option A — AND (intersection): papers match all modules
  Query: TOPIC AND POPULATION AND M1 AND M2
  Validated (180d): N papers
  Samples: ...

Option B — OR (union): papers match any module
  Query: TOPIC AND POPULATION AND (M1 OR M2)
  Validated (30d): M papers
  Samples: ...
```

"Which interpretation matches what you want?" Near-zero AND counts usually mean OR was intended. Pick by example, not abstract.

### Q3. Section 1 structure (auto-infer when possible)

Based on what was collected, infer Section 1's subsection structure:

| Collected | Default structure | Ask user? |
|-----------|-------------------|-----------|
| 1 topic, 0 methods | 1 subsection: `TOPIC AND POP` | No |
| 1 topic, 1 method | 1 subsection: `TOPIC AND POP AND M1` | No |
| 1 topic, 2+ methods + AND logic | 1 subsection: `TOPIC AND POP AND M1 AND M2` | No |
| 1 topic, 2+ methods + OR logic | **Ask:** Flat (one subsection `(M1 OR M2)`) vs Split (N subsections, each `Mi`) | Yes |
| 2+ topics | Ask AND/OR (Q1-style side-by-side) then Flat/Split | Yes |

Default recommendation when asking Flat vs Split: **Split**. Users who define independent methodologies typically want to track each as its own feed. If user hesitates, show what each subsection would contain.

Show the final Section 1 structure as a confirmation table:

```
| Subsection    | Query                                              |
| 1.1 × <name>  | TOPIC AND POP AND M1 AND <journal_whitelist>      |
| 1.2 × <name>  | TOPIC AND POP AND M2 AND <journal_whitelist>      |
```

### Q4. Top-tier journals in their field (required)

"Give me 5-15 top journals in your field. I'll split them into:
- **General medical** (JAMA, Lancet, NEJM, BMJ, Nature Medicine, etc.)
- **Domain-specific** (the flagship journals of your primary field)
- **Methodological / cross-cutting** (e.g., if you care about methods papers — JCE, Stat Med, J Biomed Inform)"

If they don't know, offer to suggest based on their topic from Q1.

### Q5. Research databases to track weekly (optional)

"Any specific research databases or cohorts you want to track weekly? (e.g., UK Biobank, All of Us, NHANES, MIMIC-III, ABCD Study, CPRD, SEER)"

If none, tell them you will remove the weekly Research Databases section and keep only NIH RePORTER weekly.

### Q6. NIH RePORTER (optional)

"Do you want weekly NIH grant updates? If yes, which NIH institute(s) primarily fund your field? (NIMH, NHLBI, NIA, NCI, NLM, NIDDK, etc.)"

### Q7. Impact Factor data (optional)

"Do you have a journal Impact Factor table? Most users get this from Clarivate JCR via their university library, but any CSV / Excel with ISSN + JIF columns works — the skill will auto-detect the schema. If no table, we skip this — pipeline still works."

If they have JCR access and want to pull fresh data:

1. Tell them the URL: https://jcr.clarivate.com/jcr/browse-journals
2. Walk them through: Sign In → institutional SSO → apply JIF filter (default ≥ 7) → Export the filtered list → save the CSV or Excel locally.

If they already have a table from another source (library LibGuide, manually curated, older JCR export, Scimago, etc.): fine, Phase 3 will inspect columns and propose a mapping regardless of format.

If they say no, unsure, or want to try later: leave `_ISSN_LIST = ""` and skip `jif_lookup.json`. IF tags won't render in the email, everything else works.

**Do not pretend to know the exact JCR navigation at their institution** — SSO flows vary. If they can't find JCR, suggest: "check your university library's Databases → search for 'Journal Citation Reports' or 'Web of Science'."

## Phase 2: Fork and clone

Ask where they want the local clone (default: `~/code/research-digest`).

Run:
```bash
gh repo fork shaexys/research-digest --clone=false
gh repo clone <user>/research-digest <target-dir>
cd <target-dir>
```

If they already have the repo forked, `gh repo clone` alone suffices.

## Phase 3: Configure `src/config.py`

Edit `src/config.py` to reflect their answers. Structure the edits as a single commit they can review before pushing.

### Domain module

Replace `PSYCH = (...)` with their domain keywords. Use MeSH terms + `[tiab]` free-text combinations. Example transformation for cardiology:

```python
PSYCH = (  # Keep variable name or rename to CARDIO / etc.
    '"Cardiovascular Diseases"[MeSH] OR "Heart Failure"[MeSH] OR '
    'cardiovascular[tiab] OR "heart failure"[tiab] OR '
    '"atrial fibrillation"[tiab] OR hypertension[tiab] OR ...'
)
```

If renaming the variable, update all references in `ALERTS` too.

### Method modules

The template ships with `EHR_METHODS`, `WEARABLES_METHODS`, `AI_METHODS`, `DIGITAL_PHENOTYPING_METHODS` as starter examples — these reflect one researcher's defaults, not a prescribed set. For each methodology module the user defined in Q2:

- **Reuse** a shipped module if keywords match (e.g., user defined an EHR filter → reuse `EHR_METHODS`).
- **Rename + refill** a shipped module if the slot is unused (e.g., user wants an RCT filter → rename `WEARABLES_METHODS` → `RCT_METHODS` and replace keywords).
- **Add** a new module following the same pattern for anything that doesn't match.
- **Delete** unused shipped modules from `config.py` entirely — don't leave dangling references.

Update `METHODS_SUBSECTIONS` and `ALERTS` to reference only the modules the user actually uses. Apply the Section 1 structure confirmed in Q3 (Flat vs Split, AND vs OR combinations).

### Journal whitelists

Replace the three journal lists with the user's actual journals. Keep the PubMed query syntax: `"Journal Name"[journal] OR ...`.

Verify journal abbreviations on PubMed (the `[journal]` tag requires the official NLM abbreviation). If unsure, search PubMed for one paper and copy the journal name from the citation.

### Database module

Replace `DB_ABCD`, `DB_EPIC_COSMOS`, `DB_ALL_OF_US` with the user's chosen databases. Update `DATABASES`, `DATABASE_KEYWORDS`, and the relevant `ALERTS` entries.

If user has no databases, remove that section and keep only NIH RePORTER weekly.

### ISSN whitelist + JIF lookup (skip entirely if no JIF table)

Handle any JIF table robustly, regardless of source (JCR export, library-provided list, manually curated, Scimago export, etc.) — **do not assume a fixed schema**. Inspect columns, propose a mapping, confirm with the user.

**Workflow when user provides the file:**

1. Ask for the file path (e.g., `~/Downloads/jcr_export.csv`, `.xlsx`, `.tsv`).
2. Load with pandas: `pd.read_csv` / `pd.read_excel` based on extension. If `.xlsx` has multiple sheets, list the sheet names and ask which to use.
3. Show a short preview: column names + first 3 rows.
4. Propose a column mapping using case-insensitive fuzzy matching:

    | Target field | Column name patterns to try (in order) |
    |--------------|----------------------------------------|
    | ISSN | `issn`, `print issn`, `pissn`, `linking issn` |
    | eISSN | `eissn`, `e-issn`, `online issn`, `electronic issn` |
    | JIF | `jif`, `impact factor`, `journal impact factor`, any `YYYY jif` / `YYYY if` (prefer most recent year) |
    | Journal name | `journal name`, `full title`, `title`, `journal title` |

5. Present the proposal and ask user to confirm or correct:

    ```
    Proposed mapping:
      ISSN         → "ISSN"
      eISSN        → "eISSN"
      JIF          → "2024 JIF"
      Journal name → "Journal name"

    Looks right? (yes / tell me which columns to use instead)
    ```

    **Shortcut:** if columns exactly match the canonical JCR Export (`ISSN`, `eISSN`, `2024 JIF`, `Journal name`), skip confirmation and state: "Detected standard JCR export, applying default mapping." Proceed.

    **Ambiguity handling:** if two columns match the same field, or no column matches a required field (ISSN or JIF), ask user to point at the right one.

6. Ask JIF cutoff (default: 7).
7. Filter rows: `JIF >= cutoff`. Coerce non-numeric JIF to NaN and drop. Drop rows where both ISSN and eISSN are missing.
8. Build outputs:
    - `_ISSN_LIST`: pipe-separated ISSNs. Fall back to eISSN where ISSN is blank.
    - `jif_lookup.json`: `{ISSN: JIF, eISSN: JIF, ...}`. Include both keys where both are present (downstream lookup tries both).
9. Write:
    - `_ISSN_LIST` inline in `src/config.py` (edit the placeholder).
    - `jif_lookup.json` to `data/jif_lookup.json` (create if missing).
10. Confirm counts: "Parsed N journals → M keys in ISSN whitelist, K entries in JIF lookup."

**Safety reminders after the write:**
- Remind user: **do not commit `data/jif_lookup.json` or the populated `_ISSN_LIST`** if the fork will stay public. JCR data is not redistributable.
- Verify `.gitignore` includes `data/jif_lookup.json` before any `git add`.

If user has no JIF table: leave both empty. Pipeline runs fine without them.

## Phase 4: GitHub Actions secrets

Walk through the 4 required secrets.

### Gmail app password

Give them the URL: https://myaccount.google.com/apppasswords

They need 2-Step Verification enabled first. If not, direct them to https://myaccount.google.com/security → 2-Step Verification.

Once they generate the app password (16 characters, no spaces needed), set it:

```bash
echo "<their-app-password>" | gh secret set GMAIL_APP_PASSWORD
gh secret set GMAIL_USER --body "<their-sending-gmail>"
gh secret set EMAIL_TO --body "<their-destination-email>"
```

### NCBI API key (optional but recommended)

URL: https://account.ncbi.nlm.nih.gov/settings/ → API Key Management.

```bash
gh secret set NCBI_API_KEY --body "<their-key>"
```

If they skip this, the pipeline still works — just with a lower PubMed rate limit.

## Phase 5: Test run

Commit the config changes:

```bash
git add src/config.py
git commit -m "Configure for my research"
git push origin main
```

Trigger the workflow manually:

```bash
gh workflow run daily.yml
```

Watch the run status:

```bash
gh run list --workflow=daily.yml --limit 1
gh run watch
```

Once the run completes, ask them to check their destination inbox. The email subject will be `📚 {date}`.

**If the email doesn't arrive**, run through:

1. Workflow logs (`gh run view --log`) — any Python errors?
2. Gmail app password correct?
3. `EMAIL_TO` correct?
4. Gmail "sent" folder — did it actually send? (If yes, check destination spam folder.)
5. Any filter queries returning 0 results due to over-narrow config?

## Phase 6: Optional follow-ups

Once it works:

1. **Rename fork** to something personal (e.g., `my-research-digest`) via GitHub settings.
2. **Adjust schedule** — default is 8am EST (`0 13 * * *` UTC). Change in `.github/workflows/daily.yml` if needed.
3. **Add more modules** — iterate on keywords after a week of real emails.
4. **Populate IF tags later** if JCR access becomes available — generate `data/jif_lookup.json` locally, never commit.

## Graceful degradation — skill should handle all of these

| User state | Handle how |
|------------|------------|
| No NCBI key | Continue without it; note rate limits are lower |
| No JCR access | Leave ISSN whitelist empty; IF tags won't render |
| No research databases | Remove weekly Research Databases section entirely |
| Gmail 2FA not enabled | Pause and direct them to enable it first; cannot proceed without |
| `gh` not installed | Stop, direct to `brew install gh` + `gh auth login` |
| Already forked repo | Skip fork step, use existing |
| Wants to test locally first | Offer to run `python main.py` locally with a dummy `.env` before setting GHA secrets |

## Principles when running this skill

- **Don't lecture about design** — they'll read DESIGN.md if curious. Focus on their setup.
- **Never commit sensitive files** — verify `.gitignore` covers `data/jif_lookup.json`, `.env`, `sent_history.json` before any `git add`.
- **Preserve user's custom edits** — if they've already edited `config.py`, merge your changes; don't overwrite.
- **Concrete over abstract** — when asking about keywords or journals, always offer to propose a starter list if they're unsure. Show validated queries with real counts and sample titles instead of asking abstract questions like "AND or OR?"
- **Smart defaults over explicit asks** — only prompt for AND/OR logic when there are 2+ independent modules on the same axis. Never ask for defaults that obviously apply (synonym OR, topic×methodology AND, topic+population AND).
- **Validation before proposal** — every keyword module proposed to the user must be live-validated against PubMed first (count + 5 sample titles). This prevents hallucinated MeSH terms and bad wildcards from reaching the user.
- **Never showcase this template's defaults as recommended** — the template ships with one researcher's topic/methods as starter content. Treat them as placeholders, not best practice. Use domain-neutral examples (RCTs, cohort studies, Cox regression, machine learning) when illustrating categories.
