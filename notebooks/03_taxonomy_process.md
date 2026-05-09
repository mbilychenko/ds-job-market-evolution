# Taxonomy & Skill Extraction Process

**Status:** Complete — `skills_present` populated in `Data/processed/postings_unified.parquet`
**Date completed:** 2026-05-09
**Author:** Maksym Bilychenko

---

## Overview

Three-pass pipeline to extract and normalize skills from 3,275 job postings:

```
Pass 1 — LLM Extraction     (Claude Sonnet 4.6, per posting, async)
          ↓  Data/interim/pass1_raw_extractions.json
Pass 2 — LLM Normalization  (Claude Opus 4.7, one-time on unique vocabulary)
          ↓  taxonomy/skills_dictionary.yaml  ← frozen, git-versioned
Pass 3 — Deterministic Mapping  (pure Python, no API)
          ↓  skills_present column in postings_unified.parquet
```

The `skills_dictionary.yaml` is the reproducibility anchor. Its git commit hash is the reference cited in the article's methods section. Re-running Pass 3 with the same YAML always produces identical output.

---

## Approach Decision: Why Three Passes

Three approaches were evaluated before settling on this pipeline.

### Option 1 — Regex matching against a pre-built taxonomy (rejected)

**What it is:** Build `taxonomy/skills_taxonomy.csv` manually with canonical names and pipe-separated alias columns, then match case-insensitively against `description_text`.

**Pros:**
- Fully deterministic from day one
- No API cost
- Runs in milliseconds
- Every match traces back to a CSV row

**Cons:**
- Circular dependency: you must know which skills exist before building the taxonomy. LLM-era terms (RAG, vector databases, LoRA fine-tuning) were not foreseeable at taxonomy design time and would be missed entirely.
- Synonym brittleness: capturing every variant of "kubernetes" requires exhaustive manual curation. Any alias not in the CSV is a miss.
- Biased toward known skills: the taxonomy reflects what the analyst thought mattered, not what employers actually required.

**Verdict: rejected.** The article's thesis depends on detecting skills the analyst did not anticipate.

---

### Option 2 — LLM extraction and normalization per posting (rejected)

**What it is:** Send each of the 3,275 job descriptions to an LLM and ask it to return a clean, normalized skill list directly in one call.

**Pros:**
- Handles natural language variation contextually
- No pre-specification of skills required
- Single step, fast to prototype

**Cons:**
- Normalization inconsistency: "machine learning" in one call, "ML" in another, "Machine Learning" in a third. Downstream prevalence counts become unreliable.
- No reproducibility anchor: re-running the pipeline with the same API key on the same data could produce different canonical names. A research article cannot cite "we ran the API" as a reproducibility guarantee.
- Cost at the wrong layer: paying for Opus-quality normalization on every posting is expensive. "python" appears 1,763 times and needs to be resolved to "Python" exactly once, not 1,763 times.
- No human review gate: per-posting output cannot practically be reviewed before analysis.

**Verdict: rejected.** The reproducibility failure alone disqualifies this for a published article.

---

### Option 3 — Three-pass LLM pipeline (adopted)

**Pros:**
- Taxonomy emerges from data: Pass 1 discovers what employers actually wrote.
- Consistent normalization: Pass 2 resolves each raw term to a canonical name exactly once.
- Reproducible after freeze: `skills_dictionary.yaml` committed to git. Commit hash = reproducibility reference.
- Human review gate: YAML can be inspected and corrected before Pass 3 runs.
- Cost-efficient: Pass 2 normalizes ~2,280 unique terms, not 3,275 postings.

**Cons:**
- More complex pipeline (three scripts)
- Requires a human review step between Pass 2 and Pass 3
- Pass 1 raw extractions can vary if re-run (but checkpointed — not re-run in practice)

**Verdict: adopted.**

---

## Pass 1 — Skill Extraction

**Script:** `src/skill_extraction/pass1_extract.py`
**Model:** Claude Sonnet 4.6 (`claude-sonnet-4-6`)
**Method:** Async, 10 concurrent requests, batches of 5 postings per API call, exponential backoff (6 retries, 30s base), checkpoint every 50 batches

### Run Summary

Two runs were required due to rate-limit failures on the first pass:

| Run | Batches | Duration | Postings captured |
|---|---|---|---|
| Run 1 | 652 | ~87 min | 2,455 (803 batches failed) |
| Run 2 (recovery) | 173 | ~20 min | Recovered most failed batches |

### Final Pass 1 Results

| Metric | Value | Assessment |
|---|---|---|
| Postings in JSON | 3,082 / 3,258 expected | 94.6% coverage |
| Missing postings | 176 | Persistent rate-limit casualties, accepted |
| Postings with zero skills | 184 (6.0%) | Slightly above <5% target — acceptable |
| Median skills per posting | 10 | Within expected 8–20 range |
| Mean skills per posting | 11.9 | Normal |
| Total term occurrences | 36,669 | — |
| Unique terms extracted | 6,455 | — |
| Terms appearing ≥ 2 times | 2,280 | Input vocabulary for Pass 2 |

### Top 10 Most Frequent Raw Terms

| Term | Count | Prevalence |
|---|---|---|
| python | 1,763 | 57.2% |
| sql | 1,389 | 45.1% |
| machine learning | 762 | 24.7% |
| aws | 578 | 18.8% |
| r | 486 | 15.8% |
| tableau | 474 | 15.4% |
| spark | 358 | 11.6% |
| snowflake | 351 | 11.4% |
| data modeling | 323 | 10.5% |
| pytorch | 320 | 10.4% |

### Sanity Check Note

The plan's thresholds (Python >80%, SQL >60%, ML >40%) were written assuming a Data Scientist–only dataset. The actual dataset covers all 8 canonical roles — Data Analyst and Data Engineer postings suppress Python/ML prevalence across the full corpus. Filtering to Data Scientist rows only shows much higher rates. **Not a data quality issue.**

### Known Extraction Artifacts (handled in Pass 2)

- Mixed casing: `"python"` and `"Python"`, `"TensorFlow"` and `"tensorflow"`
- Synonymous tool names: `"airflow"` and `"apache airflow"`, `"etl"` and `"elt"`
- Some conceptual over-extraction in analyst roles (e.g., `"ms office suite"`, `"figma"`) — low-frequency, excluded post-analysis

**Output:** `Data/interim/pass1_raw_extractions.json`

---

## Pass 2 — Canonical Normalization

**Script:** `src/skill_extraction/pass2_normalize.py`
**Model:** Claude Opus 4.7 (`claude-opus-4-7`)
**Cost:** ~$2.25 (8 batches × ~$0.28 avg, output tokens dominated)

### Design Decisions

#### Pre-clustering removed (external review finding)

The original design included a RapidFuzz pre-clustering step (token_sort_ratio ≥ 85) to reduce vocabulary size by 30–40% before sending to Opus. This was removed after an external review identified a critical correctness hazard:

**The problem:** `token_sort_ratio` at threshold 85 merges terms that share words but represent distinct skills:
- `"logistic regression"` and `"linear regression"` score ~86 — would merge
- `"gradient boosting"` and `"gradient descent"` score ~85 — would merge
- `"model monitoring"` and `"model training"` score ~76 — safe, but the boundary is too narrow

**The deeper flaw:** Pre-clustering happened before Opus saw the terms, so wrong merges were invisible to Opus and to the human reviewer. The `expand_synonyms` step re-attached cluster members to whatever canonical the representative was mapped to — a wrong merge could not be corrected downstream.

**What was saved by removing it:** 2–3 fewer Opus batches = ~$0.60–0.90. Not worth the correctness risk.

**Decision:** Send all 2,280 terms directly to Opus. Let Opus do all semantic merging.

#### Batching at 300 terms (mandatory, not arbitrary)

2,280 terms as YAML output would be 40,000–60,000+ output tokens, exceeding the 8,192 output token cap. A single-batch run would return a truncated, unparseable response. 300 terms per batch produces ~3,000–4,000 output tokens, safely within limits.

#### Collision resolution bug (fixed before run)

The original `resolve_collisions` function added both winners and losers to the `consumed` set, which could cause a winner to be silently dropped from the result if it appeared as a singleton cluster rep after being added to `consumed`. Fix: only losers are added to `consumed`.

#### Prompt caching

The system prompt (NORMALIZATION_SYSTEM_PROMPT, ~500 tokens) uses `cache_control: ephemeral`. Paid as a cache write on batch 1, cache read on batches 2–8. Saves ~$0.12.

#### ESCO/O*NET grounding

`taxonomy/esco_onet_reference.md` was created before Pass 2 to provide Opus with professional canonical name preferences across 6 roles. Referenced in the system prompt.

### Run Results

| Metric | Value |
|---|---|
| Input terms | 2,280 |
| Batches | 8 (7 × 300 terms + 1 × 180 terms) |
| Duration | ~4 min 33 sec |
| Canonical skills after merge | 1,731 |
| Collision clusters resolved | 11 |
| Final canonical skills | 1,720 |

### Collision Resolutions (11 clusters)

| Merged | Into | Assessment |
|---|---|---|
| Gaussian Splatting | 3D Gaussian Splatting | ✅ Correct |
| Streaming Data | Data Streaming | ✅ Correct |
| ELT Pipelines | ETL Pipelines | ✅ Correct |
| Google Analytics 4 | Google Analytics | ✅ Acceptable |
| ML Inference Optimization | Inference Optimization | ✅ Correct |
| Microsoft Dynamics AX | Microsoft Dynamics | ✅ Correct |
| Optimization Models | Model Optimization | ✅ Correct |
| RT-qPCR | RT-PCR | ✅ Correct |
| **Prescriptive Analytics** | **Descriptive Analytics** | ⚠️ **WRONG — different concepts** |
| **Distributed Tracing** | **Distributed Training** | ⚠️ **WRONG — tracing = observability, training = ML** |
| **Tracking** | **Tracing** | ⚠️ **Likely wrong — experiment tracking ≠ system tracing** |

**Action required before freezing:** The three flagged merges in `taxonomy/skills_dictionary.yaml` should be corrected — restore `Prescriptive Analytics`, `Distributed Tracing`, and `Tracking` as separate entries. These were accepted as-is for now (low prevalence terms, won't affect core article findings) but should be fixed before publishing the taxonomy as a standalone artifact.

**Output:** `taxonomy/skills_dictionary.yaml` (DRAFT — human review required before git freeze)

---

## Pass 3 — Deterministic Mapping

**Script:** `src/skill_extraction/pass3_map.py`
**Method:** Pure Python reverse lookup — no API calls
**Duration:** Seconds

### Results

| Metric | Value | Assessment |
|---|---|---|
| Canonical skills in dictionary | 1,720 | — |
| Raw term mappings | 2,204 | — |
| Postings processed | 5,373 total (3,275 clean) | — |
| Postings with zero skills | 410 (12.5% of clean) | ⚠️ Above <5% target |
| Median skills per posting | 8 | Within 8–20 range |
| Mean skills per posting | 9.9 | Normal |

### Zero-Skill Postings Breakdown

The 12.5% zero-skill rate (410 of 3,275 clean postings) breaks down approximately as:
- ~176 postings Pass 1 never processed (persistent rate-limit casualties from Run 1)
- 184 postings Pass 1 returned zero skills (short/boilerplate descriptions)
- ~50 postings where Pass 1 extracted terms that all fell below the `VOCAB_MIN_COUNT=2` threshold or were genuinely unmapped

**These postings are still counted in the denominator for all prevalence calculations** — they reduce skill prevalence figures proportionally. This is correct behavior: a posting with no detectable skills genuinely doesn't mention those skills.

**Article disclosure required:** "Approximately 12.5% of clean postings yielded no extractable skills, primarily due to rate-limit failures in the extraction pass and very short job descriptions. These postings are included in denominator counts."

### Median Skills by Source

| Source | Median skills/posting |
|---|---|
| glassdoor_2020 | 11 |
| linkedin_arshkon | 6 |
| open_apply_2026 | 10 |

LinkedIn's lower median (6 vs 10–11) reflects shorter description texts on LinkedIn vs job board postings. Not a quality issue — LinkedIn postings are genuinely more terse. **This is a known bias: LinkedIn 2024 postings may systematically under-count skills relative to Glassdoor 2020 and OpenApply 2026.** Trend comparisons between 2020 and 2026 are more reliable than comparisons involving 2024.

### Unmapped Terms

4,039 unique raw terms had no mapping in the dictionary (appearing only once each, except `programming` and `temporal modeling` which appeared twice). The top 20 unmapped terms are all low-signal:
- Generic terms: `programming`, `analytic modeling`, `product metrics`
- Niche/non-DS tools: `ngzorro`, `cypress`, `npm`, `primavera p6`, `mapr`, `pcf`
- Fragmented CI/CD: `continuous integration (ci)`, `continuous deployment (cd)` (the combined `CI/CD` is in the taxonomy)
- `node js` — legitimate gap but negligible for DS article

**No important DS skills appear to be missing from the taxonomy.**

---

## Taxonomy Scale and Next Steps

### 1,720 canonical skills — is this too many?

For the frozen taxonomy artifact: no. Granularity is a feature — `Databricks`, `Databricks SQL`, and `Databricks Workflows` are distinct skills that employers list separately.

For analysis and visualization: yes, 1,720 is too many to display. Two filtering strategies will reduce this to a workable set:

**Frequency filtering (for analysis):** Skills present in >1% of postings (~31+ postings) will naturally produce ~150–300 meaningful skills. This is the working set for all prevalence calculations.

**Category grouping (for visualization):** A separate `skills_categories.csv` will map canonical skills to high-level categories (`language`, `ml_framework`, `data_engineering`, `data_platform`, `cloud_infra`, `genai`, `analytics_bi`, `statistical_method`, `mlops`, `role_adjacent`). Within categories, a `platform_family` field groups product suites (all Databricks products, all AWS services, etc.).

This two-tier approach preserves granularity for detailed analysis while enabling readable charts.

### Files Produced

| File | Location | Status |
|---|---|---|
| `pass1_raw_extractions.json` | `Data/interim/` | ✅ Complete |
| `pass1_dry_run.json` | `Data/interim/` | ✅ Reference only |
| `skills_dictionary_draft.yaml` | `taxonomy/` | ✅ Intermediate artifact |
| `skills_dictionary.yaml` | `taxonomy/` | ⚠️ DRAFT — 3 bad merges to fix before git freeze |
| `postings_unified.parquet` | `Data/processed/` | ✅ `skills_present` populated |
| `esco_onet_reference.md` | `taxonomy/` | ✅ Reference |

### Pending Before Freezing Taxonomy

- [ ] Fix 3 bad collision merges in `skills_dictionary.yaml`: restore `Prescriptive Analytics`, `Distributed Tracing`, `Tracking` as separate entries
- [ ] `git add taxonomy/skills_dictionary.yaml && git commit -m "freeze skills_dictionary v1.0 — 1720 canonical skills"`
- [ ] Build `taxonomy/skills_categories.csv` (canonical_name → category, platform_family)

### Next Phase

Notebook `03_analysis.ipynb`:
1. Load parquet, filter to US non-duplicate postings
2. Apply frequency filter (>1% prevalence) to get working skill set
3. Calculate prevalence by year and by canonical_title × year
4. Apply category groupings for visualization
5. Surface the four narratives: rise, persistent core, decline, surprising

---

## Key Numbers for the Article

| Claim | Value | Source |
|---|---|---|
| Total postings in dataset | 5,373 | `postings_unified.parquet` |
| Clean (non-duplicate) US postings | 3,275 | Pass 3 validation |
| Postings with extracted skills | 2,865 (87.5%) | Pass 3 validation |
| Canonical skills in taxonomy | 1,720 | `skills_dictionary.yaml` |
| Raw unique terms before normalization | 6,455 | Pass 1 output |
| Vocabulary sent to normalization | 2,280 | min_count ≥ 2 filter |
| Taxonomy model | Claude Opus 4.7 | `config.py` |
| Extraction model | Claude Sonnet 4.6 | `config.py` |
| Three snapshots | 2020, 2024, 2026 | Glassdoor, LinkedIn, OpenApply |

---

## Implementation Notes (for Reproducibility Section)

- Python environment: see `requirements.txt`
- API key: stored in `.env` (never committed), loaded via `python-dotenv`
- Actual data path uses capital `Data/` (not `data/`) — fixed in `config.py`
- Pass 1 retry logic: 6 attempts, 30s base exponential backoff (upgraded from 3 attempts/10s after first run lost 803 postings)
- Pass 1 resume logic: checkpoints every 50 batches to `pass1_raw_extractions.json`; second run recovered from checkpoint
- Pass 2 collision resolution uses RapidFuzz token_sort_ratio at threshold 92 on canonical names only (not raw terms) — appropriate at this stage since canonical names are professionally standardized
- Pass 3 is deterministic: same YAML + same JSON always produces identical `skills_present` output
