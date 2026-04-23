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

Ask the user these questions, one at a time. Confirm each answer before moving on.

### Q1. Research domain (required)

"What research domain do you work in? (e.g., psychiatry, cardiology, epidemiology, oncology)"

Capture the keyword list they'd use to filter papers. Example:

- Psychiatry → mental health, depression, anxiety, suicide, ADHD, bipolar, etc.
- Cardiology → cardiovascular, heart failure, hypertension, arrhythmia, etc.

If they're unsure, offer to propose a starter list from their domain and iterate.

### Q2. Methods focus (required)

"What methodology or data types do you most care about? Pick any subset:
- EHR / clinical informatics
- Wearables / sensor data
- AI / ML / NLP
- Digital phenotyping / EMA
- Something else (causal inference, simulation, qualitative, etc.)"

They can pick 1-4. Each will become a subsection in Section 1 and Section 3.

### Q3. Top-tier journals in their field (required)

"Give me 5-15 top journals in your field. I'll split them into:
- **General medical** (JAMA, Lancet, NEJM, BMJ, Nature Medicine, etc.)
- **Domain-specific** (e.g., for psychiatry: Lancet Psychiatry, JAMA Psychiatry, Am J Psychiatry)
- **Clinical informatics / digital health** (JAMIA, J Biomed Inform, npj Digit Med, etc.)"

If they don't know, offer to suggest based on their domain.

### Q4. Research databases to track weekly (optional)

"Any specific research databases or cohorts you want to track weekly? (e.g., UK Biobank, All of Us, NHANES, MIMIC-III, ABCD Study, CPRD)"

If none, tell them you'll remove the weekly Research Databases section and just keep NIH RePORTER weekly.

### Q5. NIH RePORTER (optional)

"Do you want weekly NIH grant updates? If yes, which NIH institute(s) primarily fund your field? (NIMH, NHLBI, NIA, NCI, NLM, etc.)"

### Q6. Impact Factor data (optional)

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

For each methods focus the user picked, keep/edit the corresponding module (`EHR_METHODS`, `WEARABLES_METHODS`, `AI_METHODS`, `DIGITAL_PHENOTYPING_METHODS`). Remove any they don't want.

If they want a new methods subsection, add a new module following the same pattern and reference it in `METHODS_SUBSECTIONS` and `ALERTS`.

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
- **Concrete over abstract** — when asking about keywords or journals, always offer to propose a starter list if they're unsure.
- **One email of friction > five emails of help** — minimize back-and-forth. Batch your questions when possible.
