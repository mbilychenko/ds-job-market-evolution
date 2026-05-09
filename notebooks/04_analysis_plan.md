# 04 — Analysis & Visualization Plan (v2 — post external review)

**Status:** Ready to execute — `skills_present` populated, taxonomy fixed
**Reviewed by:** External editorial review (publisher perspective) + lead data scientist (technical perspective), 2026-05-09
**Depends on:** `Data/processed/postings_unified.parquet`, `taxonomy/skills_dictionary.yaml`, `taxonomy/skills_categories.csv` (to be built)
**Outputs:**
- `outputs/tables/` — all analysis CSVs (each maps to a `sources.md` entry)
- `outputs/figures/` — 4–5 publication-quality charts
- `notebooks/03_analysis.ipynb`
- `notebooks/04_visualization.ipynb`

---

## Article Focus (confirmed)

**Primary:** How the Data Scientist role has evolved from 2020 → 2026 — speciation is the thesis, not skills prevalence

**Secondary:** DS in context of the 2026 ecosystem — skill profile similarity to adjacent roles, GenAI ownership, what makes DS distinct

**Critical framing note (from editorial review):** The speciation finding — DS declining from ~77% to ~20% of DS-adjacent postings — is the only genuinely original contribution. The four-narrative skills analysis is what every industry report publishes. The article must open with speciation as the frame, with skills analysis subordinated to it. If speciation ends up in section 4 after 1,000 words of skills analysis, the article becomes mediocre.

---

## Data Shape

| Snapshot | Source | Clean DS postings | Total clean postings |
|---|---|---|---|
| 2020 | Glassdoor | ~170 | 403 |
| 2024 | LinkedIn Arshkon | ~290 | 1,283 |
| 2026 | OpenApply | ~320 | 1,589 |

**Key constraints that shape every analysis:**
- 2020 baseline n=~170 DS postings from one source. Wilson CI half-width at 10% prevalence ≈ ±4–5 pp. Strong trend claims only defensible for skills with >30% 2020 prevalence.
- 168 rows with year=2025 (OpenApply artifact) — collapse into 2026 snapshot, disclose in methods
- Glassdoor 2020 vs. OpenApply 2026 = two different convenience samples from different company populations, not a panel study. Cannot cleanly disentangle time effects from source effects.
- OpenApply descriptions are 52% longer than Glassdoor — may mechanically inflate 2026 skill prevalence independent of actual demand change
- LinkedIn median 6 skills/posting vs. 10–11 for other sources — LinkedIn used for skill prevalence confirmation only, not trend claims

---

## Pre-Analysis Steps

### Step A — Fix taxonomy & git freeze
Three bad collision merges already corrected in `taxonomy/skills_dictionary.yaml`:
- Restored `Prescriptive Analytics` (was merged into Descriptive Analytics)
- Restored `Distributed Tracing` (was merged into Distributed Training)
- Restored `Tracking` (was merged into Tracing)

```bash
git add taxonomy/skills_dictionary.yaml
git commit -m "freeze skills_dictionary v1.0 — 1723 canonical skills"
```
**The commit hash = reproducibility reference cited in article methods section.**

### Step B — Build skills_categories.csv
**Script:** `src/skill_extraction/build_categories.py`
**Output:** `taxonomy/skills_categories.csv`
**Cost:** ~$0.50 (3 Opus batches of ~550 skills)

Schema:
```
canonical_name, category, platform_family
Python, language,
PyTorch, ml_framework,
Databricks SQL, data_platform, Databricks
RAG, genai,
```

Categories (10): `language`, `ml_framework`, `genai`, `mlops`, `data_engineering`, `data_platform`, `cloud_infra`, `analytics_bi`, `statistical_method`, `role_adjacent`

**After generation — mandatory spot-checks before analysis:**
1. Pull all skills categorized as `genai` — verify no 2020-era terms (e.g., "model validation", "model evaluation") were incorrectly canonicalized into genai. This would inflate the rise narrative from below.
2. Spot-check `mlops` — verify CI/CD, model monitoring, feature stores are there and not collapsed into `data_engineering`

---

## Notebook 03 — Analysis

All outputs saved to `outputs/tables/`. Every CSV filename maps to a `sources.md` entry. Publish the full `ds_skill_prevalence_with_ci.csv` table so readers can verify chart skill selection was not cherry-picked.

### Setup
```python
df = pd.read_parquet("../Data/processed/postings_unified.parquet")
cats = pd.read_csv("../taxonomy/skills_categories.csv")
clean = df[~df['is_duplicate'] & (df['geo'] == 'US')]
clean['snapshot'] = clean['year'].map({2020: 2020, 2024: 2024, 2025: 2026, 2026: 2026})
ds = clean[clean['canonical_title'] == 'Data Scientist']
SNAPSHOTS = [2020, 2024, 2026]
```

---

### METHODOLOGICAL CHECKS — run before any analysis

#### M1. Description-length regression (new — from technical review)
Quantify how much of the apparent 2026 skill prevalence increase is description inflation:
```python
# For DS postings only
ds['desc_len'] = ds['description_text'].str.len()
ds['n_skills'] = ds['skills_present'].map(len)
# Fit: n_skills ~ log(desc_len) by source
import statsmodels.formula.api as smf
model = smf.ols('n_skills ~ np.log(desc_len) + C(source)', data=ds).fit()
```
Report the coefficient on `log(desc_len)`. If high and significant, the 52% length difference between Glassdoor and OpenApply translates to a quantifiable skill count inflation. State this number in the article's "Data and its limits" section.
Save to `outputs/tables/description_length_regression.csv`

#### M2. Denominator sensitivity check (new — from technical review)
Run all DS prevalence calculations twice:
1. Including zero-skill postings in the denominator (primary)
2. Excluding zero-skill postings

If figures agree within 2 pp, footnote and move on. If they diverge, disclose prominently.
Save both to `outputs/tables/ds_skill_prevalence_denominator_sensitivity.csv`

---

### PRIMARY ANALYSIS — Data Scientist role evolution

#### A. DS skill prevalence by snapshot
```python
ds_prev = (
    ds.explode('skills_present')
    .groupby(['snapshot', 'skills_present']).size()
    .div(ds.groupby('snapshot').size())
    .rename('prevalence').reset_index()
)
# Filter: >5% DS prevalence in at least one snapshot (raised from 2% per technical review)
working_skills = ds_prev[ds_prev['prevalence'] > 0.05]['skills_present'].unique()
```
Merge with `skills_categories.csv`.
Save to `outputs/tables/ds_skill_prevalence.csv`

#### B. Wilson 95% confidence intervals
For every (skill, snapshot): Wilson interval using `statsmodels.stats.proportion.proportion_confint`.

Flagging thresholds:
- `n_mentions_2020 < 15` → label "directional only, treat as weak signal"
- `n_mentions_2020 < 30` → note in chart footnote
- Only make confident trend claims for skills with 2020 prevalence >30% (CI half-width ≤ 7 pp)

Save to `outputs/tables/ds_skill_prevalence_with_ci.csv` — **publish this full table** in the article's supplementary data.

#### C. 2024 as directional consistency gate (new — from technical review)
**Before reporting any 2020→2026 skill trend, require the 2024 datapoint to be directionally consistent.**

For each skill, check: does 2024 prevalence fall between 2020 and 2026 (monotone), or does it reverse?
- Monotone (2020→2024→2026 all increasing or all decreasing): trend is plausible
- Non-monotone (e.g., 65%→45%→75%): likely a source artifact — flag, do not report as a trend

This is the single most important guard against reporting source effects as trends.
Save to `outputs/tables/ds_trend_consistency_check.csv`

#### D. Four narratives (DS-specific)

| Narrative | Threshold | Additional gate |
|---|---|---|
| **Rise** | Prevalence increase ≥ 8 pp (2020→2026) AND 2026 prevalence > 5% | 2024 point directionally consistent |
| **Persistent core** | <5 pp total change across all 3 snapshots AND >20% DS prevalence | Present in all 3 snapshots |
| **Decline** | Prevalence decrease ≥ 8 pp AND 2020 prevalence > 5% | 2024 point directionally consistent |
| **Surprising** | Increase 5–10 pp AND ≥15 2020 mentions AND ≥25 2026 mentions | Editorially selected — **must be labeled as such in article**, not presented as algorithmic output |

Do not force skills into categories if thresholds aren't met. "Surprising" is editorial judgment confirmed by data, not data alone.
Save to `outputs/tables/narrative_rise.csv`, `narrative_core.csv`, `narrative_decline.csv`, `narrative_surprising.csv`

#### E. Category-level skill mix shift within DS
Aggregate DS skill prevalence by category per snapshot:
- Share of DS postings mentioning ≥1 `genai` skill: 2020 vs 2024 vs 2026
- Same for `mlops`, `data_engineering`, `statistical_method`, `ml_framework`

This is the "what DS is becoming" story, expressed as category mix shift.
Save to `outputs/tables/ds_category_prevalence.csv`

#### F. Title-body evolution: is 2026 DS closer to 2026 ML Engineer than to 2020 DS? (new — from editorial review)
This is the empirical anchor for article section 5 ("Title vs. body mismatch"). Without this, that section is assertion.

```python
# Build prevalence vectors for each (role, snapshot) pair
# Cosine similarity between:
# - DS 2020 profile vs. DS 2026 profile (how much has DS changed internally?)
# - DS 2026 profile vs. ML Engineer 2026 profile (how close has DS drifted to ML Eng?)
# - DS 2026 profile vs. AI Engineer 2026 profile
from sklearn.metrics.pairwise import cosine_similarity
```

If DS 2026 is more similar to ML Engineer 2026 than to DS 2020, that is the finding: the title persists but the role has transformed.
Save to `outputs/tables/ds_profile_evolution_cosine.csv`

---

### SECONDARY ANALYSIS — DS in 2026 ecosystem context

#### G. Role composition by snapshot (the speciation thesis)
- Count postings per `canonical_title` per snapshot — share of total
- **Two views:**
  1. Raw (all 3 sources combined)
  2. Adjusted (Glassdoor 2020 vs. OpenApply 2026 only — excludes LinkedIn role bias)
- Report both and the gap between them explicitly — the divergence is itself a finding about platform self-selection
- State honestly: data is consistent with speciation but cannot rule out vocabulary drift and platform sampling differences as alternative explanations

Save to `outputs/tables/role_composition_raw.csv` and `role_composition_adjusted.csv`

#### H. Role skill similarity matrix — cosine similarity (replaces binary Jaccard)
For each pair of canonical roles in 2026 (OpenApply only — single source, no cross-source confounding):
- Build prevalence vector across ALL canonical skills (not just top-50)
- Compute cosine similarity between role pairs
- Result: 8×8 similarity matrix

**Why cosine over Jaccard:** Binary Jaccard on top-50 compresses variance because Python/SQL dominate the union and make all roles look 50–70% similar. Cosine similarity on full prevalence vectors respects skill emphasis differences — a role where SQL is 80% prevalent is treated differently from one where it's 20%.

Instead of a heatmap (which looks impressive but says little), produce: ranked list of which role is most similar to DS in 2026, with the top skills driving that similarity. One paragraph + one table.
Save to `outputs/tables/role_cosine_similarity_2026.csv`

#### I. GenAI skill ownership in 2026
Among all postings mentioning ≥1 `genai` skill in 2026 (OpenApply only):
- Share coming from each canonical role
- Which specific GenAI skills are concentrated in DS vs. ML Engineer vs. AI Engineer?

Answers: "Is DS claiming GenAI, or is that AI Engineer territory?" — directly supports or complicates the speciation thesis.
Save to `outputs/tables/genai_by_role_2026.csv`

#### J. AI Engineer emergence profile (new — from editorial review)
AI Engineer appears at 0% in 2020 and ~10% of postings in 2026. What is its skill profile?
- Is AI Engineer = DS + GenAI skills?
- Is AI Engineer = Software Engineer + GenAI skills?
- Cosine similarity: AI Engineer 2026 vs. DS 2020, DS 2026, ML Engineer 2026

This is one of the most original findings available in this dataset. No industry survey asks this question empirically.
Save to `outputs/tables/ai_engineer_profile_2026.csv`

#### K. Skills disproportionately concentrated in DS
For each skill in 2026 (OpenApply only): `DS prevalence / mean prevalence across all roles`
- Ratio > 2.0: "DS-specific" skills
- Ratio < 0.5: skills DS underrepresents vs. adjacent roles

**Note:** Do not use this as a headline article finding — sensitive to role composition of the denominator. Use as a supplementary table and for informing section 5 writing.
Save to `outputs/tables/ds_distinctiveness_2026.csv`

#### L. Skill breadth by role — 2026 OpenApply only (scoped per technical review)
Median canonical skills per posting, by role, **using OpenApply 2026 only** (single source eliminates cross-source description-length confounding).

Tests the DS-as-generalist-hub hypothesis. If DS has the highest skill breadth, it is the role that spans the most domains.
Save to `outputs/tables/skill_breadth_by_role_2026.csv`

---

## Notebook 04 — Visualization

All charts: 300 DPI PNG + SVG, consistent color palette, title + axis labels with units + data source annotation + n= per panel. Hero chart tested at 1200px wide. No word clouds.

| # | Type | Data | Key design note |
|---|---|---|---|
| 1 (hero) | Small multiples line chart | `ds_skill_prevalence_with_ci.csv` | ~12 DS skills across 3 snapshots, shaded CI bands. Skills selected by prevalence rank, not narrative fit — state this explicitly. |
| 2 | Stacked area | `role_composition_raw.csv` + adjusted | Two panels side-by-side: raw vs. adjusted. The gap between panels is the LinkedIn platform-bias finding. |
| 3 | Role similarity table | `role_cosine_similarity_2026.csv` | Ranked list: which role is most similar to DS in 2026, with skill drivers. One paragraph + table. Replaces heatmap. |
| 4 | Table with inline bars | `narrative_rise.csv` + `narrative_decline.csv` | Top 10 risers + top 10 fallers within DS, n= per cell, CIs shown |
| 5 (optional) | Quadrant scatter | `ds_skill_prevalence_with_ci.csv` | x=2020 DS prevalence, y=change 2020→2026, colored by category. Only skills passing the 2024 consistency gate. |

---

## Article Structure (revised — speciation first)

| Section | Words | Content |
|---|---|---|
| 1. Hook | ~200 | Open with the speciation number: DS from 77% to 20% of postings. Thesis upfront. |
| 2. Data and its limits | ~300 | 3 sources, 3 snapshots, not a panel study. LinkedIn bias. Description length inflation (with regression coefficient). 12.5% zero-skill rate. |
| 3. Role speciation | ~600 | The thesis. Role composition raw vs. adjusted. AI Engineer emergence profile. Who owns GenAI. |
| 4. Skills shift within DS | ~800–1000 | Four narratives (with honest CI reporting). Category mix shift. Hero chart. |
| 5. Title vs. body mismatch | ~400 | Anchored to Analysis F: is 2026 DS closer to 2026 ML Engineer than to 2020 DS? Now has empirical content. |
| 6. Where this is going | ~500 | 3–5 predictions framed as: "if someone runs this analysis on 2028 postings using the same taxonomy, they should find X." Falsifiable against this specific dataset's methodology. |
| 7. What this means | ~300 | Framework for durable vs. trend-driven skills. Not a listicle. |

**Total: ~3,100–3,300 words.**

---

## Known Risks and Mitigations

| Risk | Mitigation |
|---|---|
| 2020 n=~170 → wide CIs for most skills | Raise filter to >5% prevalence. Flag anything with <15 2020 mentions as directional. Anchor strong claims to >30% prevalence skills only. |
| Description length inflation (OpenApply 52% longer) | Run M1 regression, report coefficient. Restrict trend claims to >10% DS prevalence at both endpoints. |
| Source heterogeneity (Glassdoor vs. OpenApply) | Show 2024 LinkedIn as directional consistency gate (M2). State clearly: two convenience samples, not a panel. |
| GenAI extracted from 2020 text by 2026-trained model | Audit raw terms mapping to `genai` category — verify no 2020 skills were mis-categorized into genai. |
| "Surprising" narrative = noise at small n | Require ≥15 2020 mentions AND ≥25 2026 mentions. Label as editorial selection, not algorithmic finding. |
| Speciation thesis overstated | Use careful language: "consistent with speciation — cannot rule out vocabulary drift and platform sampling differences." |
| Jaccard / binary similarity metrics compress variance | Replaced with cosine similarity on full prevalence vectors throughout. |

---

## Key Numbers for Article Methods Section

| Claim | Value |
|---|---|
| Total postings | 5,373 |
| Clean non-duplicate US postings | 3,275 |
| Clean DS postings | ~780 |
| Postings with skills extracted | 2,865 (87.5%) |
| Canonical skills in taxonomy | 1,723 (after 3 fixes) |
| Taxonomy git commit hash | TBD — freeze before analysis starts |
| Three snapshots | 2020 (Glassdoor), 2024 (LinkedIn), 2026 (OpenApply) |
| Extraction model | Claude Sonnet 4.6 |
| Normalization model | Claude Opus 4.7 |
| VOCAB_MIN_COUNT filter | ≥2 occurrences — disproportionately excludes rare 2020-era skills (disclose in methods) |
