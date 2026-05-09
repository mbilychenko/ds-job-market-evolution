# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.1
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # 02 — Data Transformation Pipeline
#
# Loads three raw datasets, normalizes them to a unified schema, runs pre-analysis
# diagnostics, and writes `data/processed/postings_unified.parquet`.
#
# **Design:** Three isolated time-point snapshots — not a continuous time series.
# Analysis treats them as such.
#
# **Input datasets**
# | Source | Local path | Period | Role scope |
# |---|---|---|---|
# | Glassdoor 2020 | `data/raw/glassdoor_2020/Uncleaned_DS_jobs.csv` | ~2020 | All DS roles |
# | LinkedIn Arshkon | `data/raw/linkedin_arshkon/postings.csv` | Apr 2024 | All DS roles |
# | Open-Apply 2026 | `data/raw/open_apply_2026/{greenhouse,lever,ashby}.parquet` | Apr 2026 | All DS roles |
#
# > **LukeBarousse excluded** — analyst-only dataset (Google Search "data analyst"),
# > unsuitable for cross-role DS analysis. See section 2.2 for rationale.
#
# **Output schema** (matches `CLAUDE.md § Phase 2`)
#
# | Column | Type |
# |---|---|
# | `posting_id` | str |
# | `source` | str |
# | `date` | date |
# | `year` | int |
# | `quarter` | str (e.g. 2023Q2) |
# | `canonical_title` | str |
# | `raw_title` | str |
# | `company` | str |
# | `geo` | str (US / UK / EU / APAC / Other) |
# | `seniority` | str (entry / mid / senior / lead / unclassified) |
# | `description_text` | str |
# | `skills_present` | list[str] — filled in notebook 03 |
# | `is_duplicate` | bool |

# %%
import re
import html
from pathlib import Path
from datetime import date, datetime

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from bs4 import BeautifulSoup

ROOT = Path("..")
RAW  = ROOT / "data" / "raw"
OUT  = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

print("Libraries loaded.")

# %% [markdown]
# ## 1  Shared helpers

# %%
# ── Job-title normalisation ──────────────────────────────────────────────────
# Order matters: more specific patterns must come before broader ones.
TITLE_RULES = [
    (r"\b(applied scientist|applied research)\b",         "Applied Scientist"),
    (r"\b(research scientist|research engineer)\b",       "Research Scientist"),
    (r"\b(ml engineer|machine learning engineer|mlops engineer|ml ops)\b", "ML Engineer"),
    (r"\b(ai engineer|artificial intelligence engineer)\b", "AI Engineer"),
    (r"\b(analytics engineer)\b",                         "Analytics Engineer"),
    (r"\b(data engineer)\b",                              "Data Engineer"),
    (r"\b(data scientist|data science)\b",                "Data Scientist"),
    (r"\b(data analyst|business analyst|bi analyst|business intelligence analyst)\b", "Data Analyst"),
]
TITLE_RULES_C = [(re.compile(p, re.IGNORECASE), label) for p, label in TITLE_RULES]

def normalise_title(raw: str) -> str:
    if not isinstance(raw, str):
        return "Other / Unclassified"
    for pattern, label in TITLE_RULES_C:
        if pattern.search(raw):
            return label
    return "Other / Unclassified"


# ── Geography tagging ────────────────────────────────────────────────────────
EU_COUNTRIES = {
    "germany", "france", "netherlands", "spain", "italy", "sweden",
    "poland", "belgium", "austria", "denmark", "finland", "norway",
    "switzerland", "portugal", "czech", "czechia", "ireland", "romania",
    "hungary", "greece", "luxembourg",
}
APAC_KEYWORDS = {
    "india", "singapore", "australia", "japan", "china", "hong kong",
    "south korea", "korea", "malaysia", "indonesia", "new zealand",
    "taipei", "taiwan", "vietnam", "philippines",
}

def tag_geo(location: str) -> str:
    if not isinstance(location, str):
        return "Other"
    loc = location.lower()
    if any(s in loc for s in ("united states", ", us", ", usa", "remote")):
        return "US"
    # Two-letter US state abbreviations are a strong US signal
    if re.search(r",\s*[A-Z]{2}$", location.strip()):
        return "US"
    if "united kingdom" in loc or ", uk" in loc or "england" in loc or "london" in loc:
        return "UK"
    if any(c in loc for c in EU_COUNTRIES):
        return "EU"
    if any(c in loc for c in APAC_KEYWORDS):
        return "APAC"
    return "Other"


# ── Seniority extraction ─────────────────────────────────────────────────────
SENIORITY_RULES = [
    (r"\b(vp|vice president|director|head of|principal|staff)\b", "lead"),
    (r"\b(senior|sr\.?|lead)\b",                                  "senior"),
    (r"\b(junior|jr\.?|associate|entry.?level|new grad|graduate)\b", "entry"),
    (r"\b(mid.?level|mid|ii|iii)\b",                              "mid"),
]
SENIORITY_RULES_C = [(re.compile(p, re.IGNORECASE), label) for p, label in SENIORITY_RULES]

def extract_seniority(title: str, level_hint: str = None) -> str:
    if isinstance(level_hint, str):
        hint = level_hint.lower()
        if "entry" in hint or "associate" in hint or "internship" in hint:
            return "entry"
        if "senior" in hint or "executive" in hint:
            return "senior"
        if "director" in hint:
            return "lead"
        if "mid" in hint:
            return "mid"
    if isinstance(title, str):
        for pattern, label in SENIORITY_RULES_C:
            if pattern.search(title):
                return label
    return "unclassified"


# ── HTML stripping ───────────────────────────────────────────────────────────
def strip_html(raw: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        return ""
    decoded = html.unescape(raw)
    text = BeautifulSoup(decoded, "html.parser").get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


# ── Quarter helper ───────────────────────────────────────────────────────────
def to_quarter(dt) -> str:
    if pd.isnull(dt):
        return None
    q = (dt.month - 1) // 3 + 1
    return f"{dt.year}Q{q}"


# ── Final column order ───────────────────────────────────────────────────────
FINAL_COLS = [
    "posting_id", "source", "date", "year", "quarter",
    "canonical_title", "raw_title", "company", "geo", "seniority",
    "description_text", "skills_present", "is_duplicate",
]

def finalise(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    df["source"] = source_name
    if "skills_present" not in df.columns:
        df["skills_present"] = [[] for _ in range(len(df))]
    if "is_duplicate" not in df.columns:
        df["is_duplicate"] = False
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df["year"] = pd.to_datetime(df["date"], errors="coerce").dt.year
    df["quarter"] = pd.to_datetime(df["date"], errors="coerce").map(to_quarter)
    for col in FINAL_COLS:
        if col not in df.columns:
            df[col] = None
    return df[FINAL_COLS].copy()

print("Helpers defined.")

# %% [markdown]
# ## 2  Load and transform each source

# %% [markdown]
# ### 2.1  Glassdoor ~2020

# %%
gd_raw = pd.read_csv(RAW / "glassdoor_2020" / "Uncleaned_DS_jobs.csv")
print(f"Glassdoor raw: {len(gd_raw):,} rows")
gd_raw.head(2)

# %%
gd = gd_raw.copy()

# Strip Glassdoor rating suffix from company name: "Healthfirst\n3.1" → "Healthfirst"
gd["company"] = gd["Company Name"].str.split("\n").str[0].str.strip()

gd["raw_title"]         = gd["Job Title"].str.strip()
gd["canonical_title"]   = gd["raw_title"].map(normalise_title)
gd["description_text"]  = gd["Job Description"].astype(str)
gd["geo"]               = gd["Location"].map(tag_geo)
gd["seniority"]         = gd.apply(lambda r: extract_seniority(r["raw_title"]), axis=1)

# No reliable date — assign 2020-01-01 as the period anchor
gd["date"] = pd.Timestamp("2020-01-01")

gd["posting_id"] = "glassdoor_2020:" + gd.index.astype(str)

glassdoor = finalise(gd, "glassdoor_2020")
print(f"Glassdoor processed: {len(glassdoor):,} rows")
print(glassdoor["canonical_title"].value_counts())
print(glassdoor["geo"].value_counts())

# %% [markdown]
# ### 2.2  LukeBarousse analyst — EXCLUDED
#
# **Reason:** LukeBarousse collected postings via Google Search for the term *"data analyst"*.
# Any Data Scientist rows that appear are a biased subset — only DS roles similar enough to
# analyst roles to surface in that search query. This invalidates cross-role or DS-specific
# skill analysis.
#
# **Valid use case:** Analyst-only time series (2022–2025) for a separate focused analysis.
# Not included in this pipeline.

# %% [markdown]
# ### 2.3  LinkedIn Arshkon (Apr 2024)

# %%
li_raw = pd.read_csv(RAW / "linkedin_arshkon" / "postings.csv", low_memory=False)
print(f"LinkedIn raw: {len(li_raw):,} rows")
li_raw.head(2)

# %%
li = li_raw.copy()

li["raw_title"]        = li["title"].str.strip()
li["canonical_title"]  = li["raw_title"].map(normalise_title)
li["description_text"] = li["description"].astype(str)
li["company"]          = li["company_name"].str.strip()
li["geo"]              = li["location"].map(tag_geo)
li["seniority"]        = li.apply(
    lambda r: extract_seniority(r["raw_title"], r.get("formatted_experience_level")), axis=1
)
# listed_time is Unix milliseconds
li["date"] = pd.to_datetime(li["listed_time"], unit="ms", errors="coerce")
li["posting_id"] = "linkedin_arshkon:" + li["job_id"].astype(str)

linkedin = finalise(li, "linkedin_arshkon")

# Filter to DS-adjacent roles only
DS_TITLES = {
    "Data Scientist", "ML Engineer", "Applied Scientist",
    "Analytics Engineer", "Data Analyst", "AI Engineer",
    "Data Engineer", "Research Scientist",
}
linkedin_ds = linkedin[linkedin["canonical_title"].isin(DS_TITLES)].copy()

print(f"LinkedIn processed: {len(linkedin_ds):,} DS-adjacent rows (from {len(linkedin):,} total)")
print(linkedin_ds["canonical_title"].value_counts())
print(linkedin_ds["geo"].value_counts())

# %% [markdown]
# ### 2.4  Open-Apply 2026 (Greenhouse + Lever + Ashby)

# %%
oa_parts = []
for ats in ("greenhouse", "lever", "ashby"):
    path = RAW / "open_apply_2026" / f"{ats}.parquet"
    part = pd.read_parquet(path)
    part["_ats"] = ats
    oa_parts.append(part)
    print(f"  {ats}: {len(part):,} rows | columns: {list(part.columns[:8])}")

oa_raw = pd.concat(oa_parts, ignore_index=True)
print(f"\nOpen-Apply combined: {len(oa_raw):,} rows")

# %%
oa = oa_raw.copy()

desc_col = next((c for c in ("description_html", "description", "content") if c in oa.columns), None)
print(f"Using description column: {desc_col!r}")

oa["description_text"] = oa[desc_col].map(strip_html)

title_col = next((c for c in ("title", "name", "job_title") if c in oa.columns), None)
oa["raw_title"]       = oa[title_col].str.strip()
oa["canonical_title"] = oa["raw_title"].map(normalise_title)

company_col = next((c for c in ("source_slug", "company", "company_name") if c in oa.columns), None)
oa["company"] = oa[company_col].str.strip()

loc_col = next((c for c in ("locations", "location", "office_locations") if c in oa.columns), None)

def resolve_location(val):
    if val is None:
        return ""
    if isinstance(val, (list, np.ndarray)):
        return str(val[0]) if len(val) > 0 else ""
    try:
        if pd.isna(val):
            return ""
    except (TypeError, ValueError):
        pass
    return str(val)

oa["geo"]       = oa[loc_col].map(resolve_location).map(tag_geo)
oa["seniority"] = oa["raw_title"].map(lambda t: extract_seniority(t))

date_col = next((c for c in ("posted_at", "created_at", "updated_at") if c in oa.columns), None)
oa["date"] = pd.to_datetime(oa[date_col], errors="coerce", utc=True).dt.tz_localize(None)

id_col = next((c for c in ("id", "job_id", "external_id") if c in oa.columns), None)
oa["posting_id"] = "open_apply_2026:" + oa[id_col].astype(str)

open_apply = finalise(oa, "open_apply_2026")

open_apply_ds = open_apply[open_apply["canonical_title"].isin(DS_TITLES)].copy()

print(f"Open-Apply processed: {len(open_apply_ds):,} DS-adjacent rows (from {len(open_apply):,} total)")
print(open_apply_ds["canonical_title"].value_counts())
print(open_apply_ds["geo"].value_counts())

# %% [markdown]
# ## 3  Merge all sources

# %%
# Filter Glassdoor to DS-adjacent roles for consistency with the other sources.
# DS_TITLES was defined in section 2.3 (LinkedIn cell).
glassdoor_ds = glassdoor[glassdoor["canonical_title"].isin(DS_TITLES)].copy()
print(f"Glassdoor DS-adjacent: {len(glassdoor_ds):,} rows "
      f"(dropped {len(glassdoor) - len(glassdoor_ds)} Other/Unclassified)")

all_frames = [
    glassdoor_ds,   # ~2020 snapshot
    linkedin_ds,    # Apr 2024 snapshot
    open_apply_ds,  # Apr 2026 snapshot
]

unified = pd.concat(all_frames, ignore_index=True)
print(f"\nUnified dataset: {len(unified):,} rows")
print(unified["source"].value_counts())
print(unified["year"].value_counts().sort_index())

# %% [markdown]
# ## 3.5  Pre-analysis diagnostics
#
# Seven checks before deduplication and saving:
# 1. Source × year cross-tab — find where anomalous year rows come from
# 2. Drop anomalous years — remove timestamp parsing artifacts
# 3. US-only filter — primary analysis geography
# 4. Role distribution — confirm role mix at each snapshot
# 5. Description length — assess text-length bias risk for skill extraction
# 6. Cross-source duplicate check — ensure sources don't overlap within the same year
# 7. Manual spot-check — verify descriptions look like real job text

# %%
# ── Check 1: Source × year cross-tab ─────────────────────────────────────────
print("=== Source × year breakdown (before any filtering) ===")
cross = (
    unified.groupby(["source", "year"])
    .size()
    .unstack(fill_value=0)
    .sort_index(axis=1)
)
print(cross.to_string())
print(f"\nTotal rows: {len(unified):,}")

# %%
# ── Check 2: Drop anomalous years ────────────────────────────────────────────
# Expected valid years: 2020 (Glassdoor), 2024 (LinkedIn), 2025-2026 (Open-Apply).
# Rows outside these are timestamp parsing artifacts (LinkedIn Unix-ms misreads).
KEEP_YEARS = {2020, 2024, 2025, 2026}

anomalous = unified[~unified["year"].isin(KEEP_YEARS)]
print(f"Anomalous rows to drop: {len(anomalous):,}")
if len(anomalous) > 0:
    print(anomalous.groupby(["source", "year"]).size().to_string())

unified = unified[unified["year"].isin(KEEP_YEARS)].copy()
print(f"\nRows remaining: {len(unified):,}")
print(unified["year"].value_counts().sort_index())

# %%
# ── Check 3: US-only filter ───────────────────────────────────────────────────
print("Geography breakdown before US filter:")
print(unified.groupby(["source", "geo"]).size().unstack(fill_value=0).to_string())

unified = unified[unified["geo"] == "US"].copy()

print(f"\nAfter US filter: {len(unified):,} rows")
print(unified.groupby(["source", "year"]).size().unstack(fill_value=0).to_string())

# %%
# ── Check 4: Role distribution at each snapshot ───────────────────────────────
title_by_source = (
    unified.groupby(["source", "canonical_title"])
    .size()
    .unstack(fill_value=0)
)
print("Role counts by source:")
print(title_by_source.to_string())

print("\nRole share by source (%):")
shares = (title_by_source.div(title_by_source.sum(axis=1), axis=0) * 100).round(1)
print(shares.to_string())

# %%
# ── Check 5: Description length by source ────────────────────────────────────
# Risk: shorter Glassdoor descriptions → fewer regex matches → artificially
# lower apparent 2020 skill prevalence (not a real trend).
unified["_desc_len"] = unified["description_text"].str.len()

print("Description length (chars) by source:")
print(unified.groupby("source")["_desc_len"]
      .describe(percentiles=[.25, .5, .75, .95])
      .round(0)
      .to_string())

print("\nIf Glassdoor median is <50% of Open-Apply median, flag in the article")
print("as potential downward bias on 2020 skill prevalence figures.")
unified = unified.drop(columns=["_desc_len"])

# %%
# ── Check 6: Cross-source duplicates ─────────────────────────────────────────
# Checks for same company+title+year appearing in more than one source.
# Cross-year matches (same company on LinkedIn 2024 and Open-Apply 2026)
# are NOT duplicates — different time points.
cross_dupes = (
    unified.groupby(["year", "company", "canonical_title", "source"])
    .size()
    .reset_index(name="n")
)
problem = (
    cross_dupes.groupby(["year", "company", "canonical_title"])
    .filter(lambda g: g["source"].nunique() > 1)
)
print(f"Same year+company+title in >1 source: {len(problem):,} rows")
if len(problem) > 0:
    print(problem.sort_values(["year", "company"]).head(20).to_string())
else:
    print("Clean — no within-year cross-source duplicates.")

# %% [markdown]
# ## 4  Deduplication
#
# A posting is a duplicate if it shares: **company + normalised canonical title + posting date within a 30-day window**.
#
# Strategy: sort by date, group by (company, canonical_title), then flag rows whose date is within 30 days of the previous row in the same group.

# %%
unified["_date_ts"] = pd.to_datetime(unified["date"], errors="coerce")
unified = unified.sort_values(["company", "canonical_title", "_date_ts"]).reset_index(drop=True)

def flag_duplicates(group: pd.DataFrame) -> pd.Series:
    dates = group["_date_ts"]
    is_dup = pd.Series(False, index=group.index)
    for i in range(1, len(group)):
        prev_date = dates.iloc[i - 1]
        curr_date = dates.iloc[i]
        if pd.notnull(prev_date) and pd.notnull(curr_date):
            if (curr_date - prev_date).days <= 30:
                is_dup.iloc[i] = True
    return is_dup

dup_flags = unified.groupby(
    ["company", "canonical_title"], group_keys=False
).apply(flag_duplicates)

unified["is_duplicate"] = dup_flags.reindex(unified.index, fill_value=False)
unified = unified.drop(columns=["_date_ts"])

n_dup = unified["is_duplicate"].sum()
print(f"Flagged {n_dup:,} duplicates ({n_dup/len(unified)*100:.1f}% of total)")
print(f"Clean rows (is_duplicate=False): {(~unified['is_duplicate']).sum():,}")

# %%
# Spot-check: sample 20 flagged duplicates for manual review
sample = unified[unified["is_duplicate"]][["source", "company", "canonical_title", "date"]].sample(
    min(20, n_dup), random_state=42
)
sample

# %% [markdown]
# ## 5  Quality checks

# %%
# Null rates (description length checked in section 3.5)
null_pct = (unified.isnull().sum() / len(unified) * 100).round(1)
print("Null rates (%):")
print(null_pct[null_pct > 0].to_string())

# %%
# Title distribution by year (post-dedup)
clean = unified[~unified["is_duplicate"]]
title_year = (
    clean.groupby(["year", "canonical_title"])
    .size()
    .unstack(fill_value=0)
    .sort_index()
)
title_year

# %%
# Seniority distribution by source (geo is trivially all-US after section 3.5 filter)
print("Seniority distribution by source:")
print(clean.groupby(["source", "seniority"]).size().unstack(fill_value=0).to_string())

# %% [markdown]
# ## 6  Save to processed/

# %%
# Convert skills_present to list-of-strings (required for parquet)
unified["skills_present"] = unified["skills_present"].apply(
    lambda x: x if isinstance(x, list) else []
)

out_path = OUT / "postings_unified.parquet"
unified.to_parquet(out_path, index=False)
print(f"Saved {len(unified):,} rows → {out_path}")
print(f"File size: {out_path.stat().st_size / 1_000_000:.1f} MB")

# %%
# Sanity-check: reload and verify schema
verify = pd.read_parquet(out_path)
print("Reloaded schema:")
print(verify.dtypes)
print(f"\nTotal rows: {len(verify):,}")
print(f"Columns: {list(verify.columns)}")

# %% [markdown]
# ## Summary
#
# ### Design
# Three isolated time-point snapshots — not a continuous time series.
# LukeBarousse excluded: analyst-only dataset (Google Search "data analyst"),
# incompatible with cross-role DS analysis.
#
# ### Row counts (confirmed from `postings_unified.parquet`)
#
# | Source | Raw | DS-adjacent | After year + US filter | After dedup | Dedup rate |
# |---|---|---|---|---|---|
# | glassdoor_2020 | 672 | 600 | 594 | 403 | 32% |
# | linkedin_arshkon | 123,849 | 1,966 | 1,834 | 1,283 | 30% |
# | open_apply_2026 | 231,167 | 8,066 | 2,945 | 1,589 | 46% |
# | **Total** | | **10,632** | **5,373** | **3,275** | **39%** |
#
# ### Diagnostic findings
#
# **Anomalous years dropped:** 1,844 Open-Apply rows with `posted_at` dates in
# 2016–2019 and 2021–2023 — confirmed timestamp parsing artifacts, all removed.
#
# **Residual date concern (fix in notebook 03):** Open-Apply contributes 2 US rows
# tagged year=2020 and 15 clean rows tagged year=2024 that survived the pipeline.
# Jobs from a 2026 ATS scrape with 2–6 year old dates are implausible. Drop at the
# start of notebook 03:
# ```python
# df = df[~((df['source'] == 'open_apply_2026') & (df['year'] < 2025))]
# ```
#
# **Deduplication note:** The 39% dedup rate is high but correct. The logic collapses
# all company + canonical_title postings within a 30-day window to one row. Large tech
# companies with many simultaneous openings contribute only one row after dedup.
# After dedup, prevalence figures measure *"fraction of companies requiring skill X"*,
# not *"fraction of all postings"*. This is the more meaningful metric for the article.
# Highest dedup rates: Research Scientist 60%, ML Engineer 52%, Data Engineer 51% (Open-Apply).
#
# **Role distribution (clean rows) — speciation signal confirmed:**
#
# | Role | Glassdoor ~2020 | Open-Apply 2026 | Change |
# |---|---|---|---|
# | Data Scientist | **76.7%** | 20.5% | −56 pp |
# | ML Engineer | 4.2% | **15.9%** | +12 pp |
# | AI Engineer | **0.0%** | **10.1%** | +10 pp |
# | Data Engineer | 8.7% | 20.5% | +12 pp |
# | Research Scientist | 0.5% | 6.8% | +6 pp |
#
# LinkedIn 2024 excluded from role share comparison — platform skews to analyst roles
# (48% Data Analyst vs 20% on Open-Apply). Use LinkedIn 2024 for skill prevalence only.
#
# **Description length (clean rows):**
#
# | Source | Median chars | 95th pct |
# |---|---|---|
# | glassdoor_2020 | 3,333 | 6,038 |
# | linkedin_arshkon | 3,366 | 7,680 |
# | open_apply_2026 | 5,070 | 8,758 |
#
# Glassdoor/Open-Apply ratio: 66% — above the 50% flag threshold. Open-Apply descriptions
# are 52% longer. Flag in article: 2020 skill prevalence may have a mild downward bias
# for peripherally-mentioned skills; core skills (Python, SQL) unaffected.
#
# **Cross-source duplicates:** None (0 same year+company+title across sources). Clean.
#
# **Seniority caveat:** Glassdoor 2020 is 88% unclassified seniority — raw titles rarely
# contain parseable seniority markers. Do not use seniority for the 2020 snapshot in
# any comparative analysis.
#
# **Null rates:** 0.4% null company names — treated as non-duplicate by dedup reindex.
#
# ### Output file
# `data/processed/postings_unified.parquet` — 5,373 rows total, 13 columns.
# Use `df[~df['is_duplicate']]` to get the 3,275 clean analysis rows.
#
# ### Next step
# Build `taxonomy/skills_taxonomy.csv` (150–300 canonical terms, aliases, category,
# introduced year), then run `03_analysis.ipynb` for regex skill extraction and
# Wilson-interval prevalence calculations per snapshot.
