# data/

This directory holds Impact Factor lookup data used to render per-journal IF tags in the email.

## What goes here

`jif_lookup.json` — a JSON map from ISSN to JIF value, e.g.:

```json
{
  "0028-4793": 176.0,
  "0140-6736": 168.9,
  "0098-7484": 120.7
}
```

## Why this file is not committed

Journal Impact Factor values are produced by [Clarivate JCR](https://jcr.clarivate.com/). JCR's terms of service prohibit redistribution of the dataset. This repository intentionally ships **without** `jif_lookup.json`.

If you access JCR through your institution, you can generate your own copy:

1. Open JCR and export the journal table for your chosen year.
2. For each row, extract the ISSN and the 2-year Impact Factor.
3. Save as JSON at `data/jif_lookup.json`.

The file is `.gitignore`d to prevent accidental commits.

## Running without IF data

The pipeline works without `jif_lookup.json`. IF tags simply won't appear in the email. Every other feature (journal tags, institution tags, dedup, sorting by date) is unaffected.

Sorting within sections uses `jif_lookup` when available, falling back to alphabetical journal name otherwise.
