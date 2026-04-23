# Research Digest

One HTML email at 8am with new PubMed papers, preprints, and NIH grants — filtered to your research focus, delivered by GitHub Actions cron. Free, self-hosted, no SaaS account.

📖 **For the design rationale** (why 3 daily sections + 2 weekly, why bioRxiv uses AND but medRxiv uses OR, etc.): see [DESIGN.md](DESIGN.md).

> *Screenshot: insert email preview here after first setup*

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

*Note: Section names above reflect the default template (psychiatry + clinical informatics). Rename freely when you fork — e.g., rename `PSYCH` → `CARDIO` and relabel "Psych × Methods" → "Cardio × Methods". See [Customization](#customization).*

- **Daily volume**: typically 20-60 papers total, triaged by reading titles and journal tags.
- **Deduplication**: across sources (DOI + fuzzy title), across sections (higher-priority section wins), across a 7-day window.
- **Sources**: PubMed, medRxiv, bioRxiv, arXiv, NIH RePORTER.
- **Tags in email**: journal (color-coded), impact factor (if configured), institution, grant activity code.

---

## Setup prerequisites

You will need:

| Component | Why | Account needed |
|-----------|-----|----------------|
| GitHub account | Hosts the repo and runs the cron via Actions | Yes |
| Gmail account (with 2-Step Verification) | Sends the daily email via SMTP; app password needed | Yes |
| NCBI account → API key | Raises PubMed rate limit (recommended, not strictly required) | Yes (free) |
| Destination email | Where the digest is delivered (can be the same Gmail or another inbox) | — |

These data sources are queried via **public APIs** and need no account or key:

- arXiv
- medRxiv / bioRxiv
- NIH RePORTER

---

## Two ways to install

### 🛠 Track 1 — Fork + configure (10 minutes)

For anyone comfortable with GitHub.

1. Click **"Use this template"** at the top of this repo → create your own copy.
2. Edit `src/config.py`:
   - Replace domain keywords (`PSYCH`) with your topic keywords.
   - Edit journal whitelists (`JOURNAL_TOP_MED`, `JOURNAL_TOP_PSYCH`, `JOURNAL_CLINICAL_INFORMATICS`) for your field.
   - Optional: populate `_ISSN_LIST` for Section 1 breadth (see [DESIGN.md § ISSN Whitelist](DESIGN.md#issn-whitelist)).
3. Get a Gmail app password:
   - Google Account → Security → 2-Step Verification → App passwords → generate.
4. Get an NCBI API key (improves PubMed rate limits):
   - https://account.ncbi.nlm.nih.gov/settings/ → API Key Management.
5. In your fork → Settings → Secrets and variables → Actions → add 4 repository secrets:
   - `GMAIL_USER` — your sending Gmail address
   - `GMAIL_APP_PASSWORD` — the app password from step 3
   - `EMAIL_TO` — where you want the digest delivered
   - `NCBI_API_KEY` — from step 4
6. Actions tab → **Research Digest** workflow → "Run workflow" (manual trigger) to test.
7. Check your inbox. Daily runs at 8am EST.

### 🤖 Track 2 — Claude Code skill (5 minutes, conversational)

If you use [Claude Code](https://claude.com/claude-code), this repo ships a companion setup skill.

```bash
# One-time install
git clone https://github.com/shaexys/research-digest.git
ln -s $(pwd)/research-digest/.claude/skills/research-digest-setup ~/.claude/skills/research-digest-setup
```

Then in Claude Code:

```
/research-digest-setup
```

The skill will ask you about your research focus, help you fork this repo, set your secrets via `gh` CLI, and trigger the first test run.

---

## Customization

### Adapting to a non-psychiatry field

This template ships with default modules for psychiatry × clinical informatics. To repurpose for your field:

1. Rename and rewrite the domain module. E.g., change `PSYCH = ...` in `src/config.py` to `CARDIO = '"Cardiovascular Diseases"[MeSH] OR ...'`.
2. Edit or replace the methods subsections (`EHR_METHODS`, `WEARABLES_METHODS`, `AI_METHODS`, `DIGITAL_PHENOTYPING_METHODS`) with methods modules relevant to your work.
3. Update the journal whitelists (`JOURNAL_TOP_MED` can stay; `JOURNAL_TOP_PSYCH` becomes `JOURNAL_TOP_CARDIO` or similar).
4. Update `METHODS_SUBSECTIONS` and `ALERTS` to reference the renamed modules.

The two-layer design (see [DESIGN.md § Two-layer module structure](DESIGN.md#1-two-layer-module-structure)) means you never touch the API code in `src/pubmed.py` etc. — only the config.

### Adding a new methods module

Open `src/config.py` and add:

```python
CAUSAL_METHODS = (
    '"Causal Inference"[MeSH] OR '
    '"instrumental variable*"[tiab] OR '
    '"propensity score"[tiab] OR ...'
)
```

Then reference it in `METHODS_SUBSECTIONS` and in the `ALERTS` list. The API code in `src/pubmed.py` doesn't need changes — module composition is table-driven.

### Adding a new research database (weekly section)

Add to `DATABASE_KEYWORDS` and `ALERTS`. Keep queries specific (full database name in quotes) — broad terms drown the weekly section.

### Changing the schedule

Edit `.github/workflows/daily.yml`:

```yaml
on:
  schedule:
    - cron: '0 13 * * *'  # 8am EST / 1pm UTC
```

Adjust for your timezone. Note: cron uses UTC.

### Trimming or expanding journals

Journal whitelists live in `src/config.py`. Default lists are calibrated for psychiatry + clinical informatics; edit freely.

---

## Optional: Impact Factor tags

The pipeline can render a per-journal **Impact Factor** tag in the email. This requires Clarivate JCR data, which JCR's terms of service prohibit redistributing — so this template ships without it.

**You do not need IF tags for the pipeline to work.** If you skip this step, the email still renders correctly; IF tags simply won't appear.

If you want IF tags and have institutional JCR access: see [DESIGN.md § ISSN Whitelist](DESIGN.md#issn-whitelist) for how to generate `data/jif_lookup.json` locally. This file is `.gitignore`d — do not commit it. The same applies to any custom `_ISSN_LIST` you add to `src/config.py`.

---

## Limits and known issues

- **TOC anchor links in the email don't work in some clients** (notably Outlook web and Gmail web). The browser version works fine if you "view in browser" or receive in Apple Mail. See [DESIGN.md § Email Design Rationale](DESIGN.md).
- **arXiv preprints** are filtered locally because the API doesn't support date-range + category + keyword in combination. A busy day can pull a lot of arXiv papers before filtering.
- **No historical backfill.** On first run you get today's papers; earlier days are not retroactively indexed.

---

## License

MIT. See [LICENSE](LICENSE).

## Acknowledgments

Built to solve a personal morning-coffee problem. If it solves yours too, fork away — and consider sharing what you customize.

For the design rationale behind every choice, read [DESIGN.md](DESIGN.md).
