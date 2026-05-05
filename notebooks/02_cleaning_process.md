# 02 — Data Cleaning Pipeline: Process Documentation

**Status:** Complete. Output file confirmed at `data/processed/postings_unified.parquet`.  
**Code:** `notebooks/02_cleaning.ipynb` / `notebooks/02_cleaning.py` (jupytext-synced pair)  
**Last run:** 2026-05-05

---

## Purpose

Transform three raw job-posting datasets into a single unified parquet file ready for skill extraction (notebook 03). The pipeline normalises schema, tags geography, extracts seniority, deduplicates, and runs seven diagnostic checks before saving.

---

## Design Decisions (Non-Negotiable)

### Three isolated snapshots, not a time series

The analysis uses three datasets as **discrete time-point cross-sections**, not a continuous series:

| Snapshot | Source | Period |
|---|---|---|
| ~2020 | Glassdoor | No exact dates — all rows assigned `2020-01-01` as anchor |
| Apr 2024 | LinkedIn Arshkon | `listed_time` Unix ms timestamps → converted to dates |
| Apr 2026 | Open-Apply (Greenhouse + Lever + Ashby) | `posted_at` ISO 8601 timestamps |

Trend language in the article (e.g. "Python held steady") refers to comparisons between these three point-in-time snapshots, not to monthly trend lines.

### LukeBarousse dataset excluded

LukeBarousse collected postings via Google Search for the term **"data analyst"**. Any Data Scientist rows in that dataset are a biased subset — only DS-adjacent enough to surface in an analyst search query. This makes it unsuitable for cross-role analysis or measuring the speciation thesis. It is not loaded in this pipeline. It would be valid for an analyst-only time series (2022–2025) in a future separate analysis.

### Geography: US only

The primary analysis uses US postings only. Non-US rows are dropped in Section 3.5 (Check 3) before deduplication. This is applied to all three sources consistently.

### Unit of analysis: company-level demand

After deduplication, each row represents **one company's open position of a given title**. If Google had 12 simultaneous ML Engineer openings in April 2024, they collapse to one row. Prevalence figures therefore measure *"fraction of hiring companies requiring skill X"* — a more meaningful signal than raw posting counts.

---

## Input Files

| Source | Local path | File type | Notes |
|---|---|---|---|
| Glassdoor 2020 | `data/raw/glassdoor_2020/Uncleaned_DS_jobs.csv` | CSV | 672 rows total |
| LinkedIn Arshkon | `data/raw/linkedin_arshkon/postings.csv` | CSV | 123,849 rows, 158 MB |
| Open-Apply Greenhouse | `data/raw/open_apply_2026/greenhouse.parquet` | Parquet | 146,689 rows |
| Open-Apply Lever | `data/raw/open_apply_2026/lever.parquet` | Parquet | 47,213 rows |
| Open-Apply Ashby | `data/raw/open_apply_2026/ashby.parquet` | Parquet | 37,265 rows |

---

## Output File

`data/processed/postings_unified.parquet`

**Schema:**

| Column | Type | Notes |
|---|---|---|
| `posting_id` | str | `{source}:{original_id}` |
| `source` | str | `glassdoor_2020`, `linkedin_arshkon`, `open_apply_2026` |
| `date` | date | Posting date (or 2020-01-01 anchor for Glassdoor) |
| `year` | int | Derived from date |
| `quarter` | str | e.g. `2024Q2` |
| `canonical_title` | str | Normalised to 8-label taxonomy (see below) |
| `raw_title` | str | Original title string |
| `company` | str | Cleaned company name |
| `geo` | str | `US` / `UK` / `EU` / `APAC` / `Other` |
| `seniority` | str | `entry` / `mid` / `senior` / `lead` / `unclassified` |
| `description_text` | str | Plain text (HTML stripped for Open-Apply) |
| `skills_present` | list[str] | Empty list — populated in notebook 03 |
| `is_duplicate` | bool | True if flagged by dedup logic |

**Row counts:**  
- Total rows: **5,373**  
- Clean rows (`is_duplicate=False`): **3,275**  
- File size: ~3–5 MB

---

## Pipeline Steps

### Step 1 — Shared helpers (Section 1)

Four reusable functions built once and applied to all sources:

**`normalise_title(raw)`** — maps messy raw titles to 8 canonical roles using ordered regex rules. Order matters: Applied Scientist and Research Scientist must match before Data Scientist (which is a substring of both).

Canonical role set:
- Applied Scientist
- Research Scientist
- ML Engineer
- AI Engineer
- Analytics Engineer
- Data Engineer
- Data Scientist
- Data Analyst
- Other / Unclassified

**`tag_geo(location)`** — classifies location strings to `US / UK / EU / APAC / Other`. US detection: "united states", ", US", ", USA", "Remote" keywords, or two-letter state abbreviation pattern `, XX` at end of string.

**`extract_seniority(title, level_hint)`** — extracts from title text (sr., senior, junior, etc.) with optional `formatted_experience_level` hint from LinkedIn. Returns `entry / mid / senior / lead / unclassified`.

**`strip_html(raw)`** — HTML entity decode → BeautifulSoup text extraction → whitespace collapse. Applied to Open-Apply descriptions which come as raw HTML.

---

### Step 2 — Per-source loading and transformation (Section 2)

**Glassdoor 2020 (Section 2.1):**
- Strips Glassdoor rating from company name: `"Healthfirst\n3.1"` → `"Healthfirst"` via `str.split("\n").str[0]`
- No date column exists — assigns `2020-01-01` to all rows as the period anchor
- `posting_id` = `glassdoor_2020:{row_index}`

**LinkedIn Arshkon (Section 2.3):**
- `listed_time` column is Unix milliseconds → converted via `pd.to_datetime(unit="ms")`
- Uses `formatted_experience_level` as a seniority hint where available
- `posting_id` = `linkedin_arshkon:{job_id}`
- Filtered to DS_TITLES immediately after processing

**Open-Apply 2026 (Section 2.4):**
- Three parquet files (greenhouse, lever, ashby) concatenated with `_ats` source tag
- `description_html` column requires `strip_html()` — raw HTML with tags and entities
- `locations` column is a list field → resolved by taking `val[0]` for the first location
- `posted_at` column has UTC timezone → stripped to naive datetime for consistency
- `posting_id` = `open_apply_2026:{id}`
- Filtered to DS_TITLES immediately after processing

**`DS_TITLES` filter (applied to all sources):**
```
{"Data Scientist", "ML Engineer", "Applied Scientist", "Analytics Engineer",
 "Data Analyst", "AI Engineer", "Data Engineer", "Research Scientist"}
```
Rows with `canonical_title = "Other / Unclassified"` are dropped before the merge.

---

### Step 3 — Merge (Section 3)

Simple `pd.concat` of three DS-filtered dataframes. No join logic needed — sources do not share columns beyond the unified schema. Schema alignment is done inside each source's `finalise()` call.

---

### Step 3.5 — Pre-analysis diagnostics (7 checks)

Runs before deduplication to surface data quality issues while they are still diagnosable.

**Check 1 — Source × year cross-tab:** Confirmed the expected distribution: Glassdoor rows are all year=2020, LinkedIn is all year=2024, Open-Apply has a mix (including anomalous years — see Check 2).

**Check 2 — Drop anomalous years:**  
KEEP_YEARS = `{2020, 2024, 2025, 2026}`. Open-Apply contributed **1,844 rows** with `posted_at` dates in 2016–2019 and 2021–2023. These are confirmed timestamp parsing artifacts (the ATS scrape date is April 2026; multi-year-old dates are implausible for live job postings). All dropped. Rows remaining after this filter: **5,373**.

**Check 3 — US-only filter:**  
Applied after year cleanup. Non-US rows removed across all sources. After filter:

| Source | US rows kept |
|---|---|
| glassdoor_2020 | 594 |
| linkedin_arshkon | 1,834 |
| open_apply_2026 | 2,945 |
| **Total** | **5,373** |

**Check 4 — Role distribution at each snapshot:**  
Reveals the speciation signal and a LinkedIn platform bias. Full table in the Summary section.

**Check 5 — Description length by source:**  
Risk assessed: if Glassdoor descriptions are much shorter, regex matching will find fewer skills → artificially lower 2020 prevalence figures (not a real trend signal).

| Source | Median chars | 95th percentile |
|---|---|---|
| glassdoor_2020 | 3,333 | 6,038 |
| linkedin_arshkon | 3,366 | 7,680 |
| open_apply_2026 | 5,070 | 8,758 |

Glassdoor/Open-Apply ratio: 66% (threshold was 50%). Flag in article: 2020 skill prevalence may have a mild downward bias for peripherally-mentioned skills. Core skills (Python, SQL) appear in the opening paragraph of job descriptions and are unaffected.

**Check 6 — Cross-source duplicates:**  
Checks for same year + company + canonical_title appearing in more than one source. Result: **0 cross-source duplicates**. Sources do not overlap within any given year.

**Check 7 — Manual spot-check:** 
Verifies that `description_text` contains real job posting text (not HTML artifacts, not empty strings). Confirmed across all three sources.

---

### Step 4 — Deduplication (Section 4)

**Logic:** Sort rows by `(company, canonical_title, date)`. Within each group, flag a row as duplicate if its date is within 30 days of the previous row in the same group. First occurrence in each group is never flagged.

**Edge case fix:** `groupby()` silently drops rows with null `company`. Using `.reindex(unified.index, fill_value=False)` after the apply ensures null-company rows are retained as non-duplicates rather than silently lost. Without this fix, row counts diverged by 24.

**Results:**

| Source | Before dedup | After dedup | Dedup rate |
|---|---|---|---|
| glassdoor_2020 | 594 | 403 | 32% |
| linkedin_arshkon | 1,834 | 1,283 | 30% |
| open_apply_2026 | 2,945 | 1,589 | 46% |
| **Total** | **5,373** | **3,275** | **39%** |

Highest dedup rates by role in Open-Apply: Research Scientist 60%, ML Engineer 52%, Data Engineer 51%. This reflects large tech companies posting many simultaneous openings.

Duplicates are **flagged, not deleted**. The parquet file retains all 5,373 rows. Downstream notebooks filter with `df[~df['is_duplicate']]` to get the 3,275 clean rows.

---

### Step 5 — Quality checks (Section 5)

- **Null rates:** 0.4% null company names — treated as non-duplicate by the reindex fix.
- **Seniority distribution:** Glassdoor 2020 is 88% `unclassified` — raw titles in the 2020 dataset rarely contain parseable seniority markers. Do not use seniority for comparative analysis involving the 2020 snapshot.

---

### Step 6 — Save (Section 6)

Written to `data/processed/postings_unified.parquet` using pandas `.to_parquet()`. Schema verified by reload sanity check. `skills_present` column saved as empty list per row — will be populated by `src/extract_skills.py` in notebook 03.

---

## Key Findings from This Pipeline

### Role speciation signal (clean rows, US only)

| Role | Glassdoor ~2020 | Open-Apply 2026 | Change |
|---|---|---|---|
| Data Scientist | **76.7%** | 20.5% | −56 pp |
| Data Analyst | 0.5% | 3.5% | +3 pp |
| Data Engineer | 8.7% | 20.5% | +12 pp |
| ML Engineer | 4.2% | **15.9%** | +12 pp |
| AI Engineer | 0.0% | **10.1%** | +10 pp |
| Analytics Engineer | 0.0% | 4.6% | +5 pp |
| Research Scientist | 0.5% | 6.8% | +6 pp |
| Applied Scientist | 9.5% | 18.1% | +9 pp |

This is the speciation thesis confirmed in clean data: "Data Scientist" has collapsed from 77% to 20% of DS-adjacent postings, replaced by specialised roles that did not exist (AI Engineer) or barely existed (ML Engineer) in 2020.

### LinkedIn 2024 excluded from role share analysis

LinkedIn shows 48% Data Analyst vs 20% on Open-Apply. This is platform bias — LinkedIn is a general professional network; Open-Apply pulls from company career pages directly (more technical roles). LinkedIn 2024 data is **valid for skill prevalence analysis only**, not for role share comparison.

---

## Known Issues and Mitigations

### Residual Open-Apply date artifacts (fix in notebook 03)

After all filters, 2 Open-Apply US rows tagged `year=2020` and 15 tagged `year=2024` survived the pipeline. A 2026 ATS scrape producing 2020 dates is implausible — these are artifacts. Apply this fix at the start of notebook 03:

```python
df = df[~((df['source'] == 'open_apply_2026') & (df['year'] < 2025))]
```

This drops 17 rows, all from Open-Apply, cleaning the 2026 snapshot to years 2025–2026 only.

### Description length bias

Open-Apply descriptions are 52% longer than Glassdoor. Peripheral skills mentioned only once near the end of a long description will have higher detection rates in 2026 than 2020 regardless of actual skill demand change. Mitigation: flag in the article; focus trend claims on skills that appear in >10% of postings at each snapshot (large prevalence, not marginal).

### Glassdoor seniority unusable

88% of Glassdoor 2020 rows have `seniority = "unclassified"`. Do not report seniority trends involving the 2020 snapshot.

### Glassdoor dates are all 2020-01-01

No temporal variation within the 2020 snapshot. Quarter-level analysis is not possible for Glassdoor. All 2020 analysis is cross-sectional only.

---

## What This File Does NOT Do

- **Skill extraction** — `skills_present` is an empty list per row. Filled in notebook 03 using `taxonomy/skills_taxonomy.csv`.
- **Statistical analysis** — no prevalence calculations, confidence intervals, or comparisons. Notebook 03.
- **Visualisation** — notebook 04.
- **LukeBarousse analysis** — excluded entirely from this pipeline.

---

## Reproducibility Notes

- All paths are relative to the repository root via `ROOT = Path("..")` from the `notebooks/` directory.
- No hardcoded local paths.
- `skills_present` column initialised as empty list to satisfy parquet list-type schema.
- Jupytext sync: `02_cleaning.py` and `02_cleaning.ipynb` are kept in sync via `jupytext --sync notebooks/02_cleaning.ipynb`. Edit the `.py` file, sync to `.ipynb`, then Restart & Run All in Jupyter.
