# Data Sources — Raw Datasets

This file documents every dataset downloaded for the project, including source links, audit findings, and assessment of usefulness. Update this file each time a new dataset is added.

---

## Dataset 1: LinkedIn Job Postings (2023–2024)

| Field | Value |
|---|---|
| **Kaggle ref** | `arshkon/linkedin-job-postings` |
| **Kaggle URL** | https://www.kaggle.com/datasets/arshkon/linkedin-job-postings |
| **Local path** | `data/raw/linkedin_arshkon/` |
| **Downloaded** | 2026-05-04 |
| **File size** | ~158 MB |
| **Key files** | `postings.csv`, `jobs/job_skills.csv`, `mappings/skills.csv` |

### Actual Content (after audit)

| Property | Finding |
|---|---|
| **Advertised coverage** | 2023–2024 |
| **Actual date range** | April 2024 only (single-month snapshot) |
| **Total postings** | 123,849 |
| **DS-adjacent postings** | ~1,521 (1%) |
| **Description text** | Present, rich (mean 3,766 chars, <1% null) |
| **Geography** | Predominantly US |
| **Pre-extracted skills** | 35 coarse categories (too broad for our analysis) |

### Schema (key columns)
- `job_id`, `title`, `company_name`, `description`, `location`
- `listed_time` (Unix ms timestamp), `formatted_experience_level`
- `normalized_salary`, `formatted_work_type`
- Companion: `job_skills.csv` links `job_id` → `skill_abr` (maps to 35 categories in `mappings/skills.csv`)

### Assessment
- **Time coverage: poor** — single month (April 2024), not a time series despite the dataset name
- **Description quality: excellent** — full free text suitable for skill extraction
- **Role diversity: good** — covers all titles, not just one role
- **Use in project:** Single data point for April 2024 cross-section; description text usable for skill extraction

---

## Dataset 2: Data Analyst Job Postings (Google Search)

| Field | Value |
|---|---|
| **Kaggle ref** | `lukebarousse/data-analyst-job-postings-google-search` |
| **Kaggle URL** | https://www.kaggle.com/datasets/lukebarousse/data-analyst-job-postings-google-search |
| **Local path** | `data/raw/lukebarousse_analyst/` |
| **Downloaded** | 2026-05-04 |
| **File size** | ~82 MB |
| **Key files** | `gsearch_jobs.csv` |

### Actual Content (after audit)

| Property | Finding |
|---|---|
| **Advertised coverage** | Google Search scrape |
| **Actual date range** | Nov 2022 – Apr 2025 |
| **Total postings** | 61,953 |
| **DS-adjacent postings** | All (search term = "data analyst" only) |
| **Description text** | Present, 0% null |
| **Geography** | US only (`search_location = United States`) |
| **Pre-extracted skills** | 134-term taxonomy in `description_tokens` column |
| **Gap** | August 2024 missing; volume drops sharply post mid-2024 |

### Schema (key columns)
- `title`, `company_name`, `location`, `description`, `date_time`
- `search_term` (always "data analyst"), `schedule_type`, `work_from_home`
- `description_tokens` — pre-extracted list of skills (e.g. `['sql', 'python', 'tableau']`)
- `salary_standardized`, `salary_avg`, `salary_min`, `salary_max`

### Pre-extracted Skill Taxonomy (134 terms)
Top skills by prevalence in the dataset (2022–2025):

| Skill | Prevalence |
|---|---|
| sql | 50% |
| excel | 31% |
| python | 30% |
| power_bi | 28% |
| tableau | 27% |
| r | 18% |
| sas | 8% |
| azure | 6% |
| aws | 5% |
| snowflake | 5% |

Notable absences: no `llm`, `rag`, `vector_db`, `agents`, `langchain`, `openai` — taxonomy was built pre-2023 GenAI wave.

### Key Trend Findings (from audit)
Skill prevalence by year — "persistent core" confirmed flat:

| Skill | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|
| sql | 52% | 50% | 52% | 41% |
| python | 30% | 28% | 35% | 26% |
| tableau | 28% | 27% | 27% | 23% |
| excel | 36% | 33% | 29% | 27% |
| power_bi | 26% | 25% | 28% | 21% |

n per year: 2022=5,488 | 2023=33,413 | 2024=16,469 | 2025=6,583

### Assessment
- **Time coverage: good** — Nov 2022 to Apr 2025, consistent monthly volume
- **Role coverage: poor** — "data analyst" only; cannot support speciation thesis
- **Skill taxonomy: useful starting point** — 134 terms, but missing all GenAI/LLM vocabulary
- **Use in project:** "Persistent core" finding (SQL/Python flat); taxonomy seed; 2022–2025 anchor for analyst role

---

## Dataset 3: Glassdoor Data Science Job Postings (~2020)

| Field | Value |
|---|---|
| **Kaggle ref** | `rashikrahmanpritom/data-science-job-posting-on-glassdoor` |
| **Kaggle URL** | https://www.kaggle.com/datasets/rashikrahmanpritom/data-science-job-posting-on-glassdoor |
| **Local path** | `data/raw/glassdoor_2020/` |
| **Downloaded** | 2026-05-04 |
| **File size** | ~3 MB |
| **Key files** | `Uncleaned_DS_jobs.csv` (672 rows), `Cleaned_DS_Jobs.csv` (660 rows) |

### Actual Content (after audit)

| Property | Finding |
|---|---|
| **Advertised coverage** | ~2020 (no date column; inferred from vocabulary and Founded max=2019) |
| **Actual date range** | Unknown exact date — single snapshot, estimated 2020 |
| **Total postings** | 672 |
| **Description text** | Present, 0% null, full length |
| **Geography** | US only — major tech hubs (SF, NYC, DC, Boston, Chicago) |
| **Pre-extracted skills** | 7 binary flags in cleaned file: python, excel, hadoop, spark, aws, tableau, big_data |

### Schema (key columns)
- `Job Title`, `Job Description`, `Rating`, `Company Name` (has `\n{rating}` suffix — needs cleaning), `Location`
- `Size`, `Type of ownership`, `Industry`, `Sector`, `Founded`, `Revenue`
- Cleaned file adds: `min_salary`, `max_salary`, `avg_salary`, `job_simp`, `seniority`, binary skill flags

### Skill Prevalence (~2020 baseline)

| Skill | Prevalence |
|---|---|
| python | 73% |
| excel | 44% |
| spark | 28% |
| aws | 26% |
| hadoop | 21% |
| big_data | 21% |
| tableau | 19% |

### Known Data Quality Issues
- `Company Name` has Glassdoor rating appended (e.g. `"Healthfirst\n3.1"`) — strip `\n{rating}` before use
- `seniority` is 84% "na" — unusable
- Only 7 pre-extracted skills — must re-extract from description text for full taxonomy

### Assessment
- **Time coverage: single point ~2020** — our earliest anchor, critical for the 2020-vs-2026 comparison
- **Role diversity: good** — DS (67%), analyst, data engineer, MLE all present
- **Sample size: small** — n=672; all findings from this dataset must report confidence intervals
- **Use in project:** Primary 2020 baseline for skill prevalence comparison

---

## Dataset 4: Open-Apply Jobs — ATS Live Feed (April 2026)

| Field | Value |
|---|---|
| **HuggingFace repo** | `edwarddgao/open-apply-jobs` |
| **HuggingFace URL** | https://huggingface.co/datasets/edwarddgao/open-apply-jobs |
| **Source code** | https://github.com/edwarddgao/openapply |
| **License** | MIT |
| **Local path** | `data/raw/open_apply_2026/` |
| **Downloaded** | 2026-05-04 (snapshot: date=2026-04-17) |
| **File size** | ~207 MB total (greenhouse 156MB, lever 15MB, ashby 36MB) |
| **Key files** | `greenhouse.parquet`, `lever.parquet`, `ashby.parquet` |

### Actual Content (after audit)

| Property | Finding |
|---|---|
| **Data source** | Live ATS APIs — Greenhouse, Lever, Ashby (company career boards directly) |
| **Snapshot date** | April 17, 2026 |
| **Total postings** | 231,167 (146,689 greenhouse + 47,213 lever + 37,265 ashby) |
| **DS-adjacent postings** | ~8,203 (4,992 greenhouse + 1,444 lever + 1,767 ashby) |
| **Description text** | Full HTML — mean 5,503 chars (greenhouse), 4,858 (ashby), 1,735 (lever) after stripping |
| **Truncation** | None — full descriptions from source |
| **Geography** | Global; US, UK, Remote well represented |
| **Salary data** | Not available (Greenhouse API does not expose salary) |

### Schema (key columns)
- `id` (format: `{ats}:{company_slug}:{job_id}`), `source_slug`, `title`
- `description_html` — full HTML, must be stripped before use
- `posted_at` (ISO 8601 timestamp), `department`, `locations` (list), `remote`
- `apply_url` — traceable to original career board posting

### Known Data Quality Issues
- `description_html` requires HTML entity decoding + tag stripping before text analysis
- `employment_type`, `salary_*` columns are 100% null in greenhouse source
- `locations` is a list field — must explode for geography filtering
- Lever descriptions are shorter (mean 1,735 chars) — check if truncated or genuinely brief

### Skill Prevalence (top modern skills observed in descriptions)
RAG, Vector DBs, LangChain, Fine-tuning, LLM APIs, Prompt Engineering, MLOps, AutoGen — full GenAI vocabulary present in descriptions.

### Assessment
- **Time coverage: April 2026 snapshot** — our most recent data point and the 2026 endpoint
- **Description quality: best in dataset collection** — full text, real provenance, no truncation
- **Role diversity: excellent** — AI Engineer, Senior Data Scientist, MLOps Engineer, NLP Engineer, Analytics Engineer all present
- **Use in project:** Definitive 2026 cross-section for skill prevalence; enables direct 2020-vs-2026 comparison

---

## Datasets Evaluated but Excluded

| Dataset | Kaggle/HF URL | Reason excluded |
|---|---|---|
| `alitaqishah/ai-jobs-market-2025-2026-salaries` | https://www.kaggle.com/datasets/alitaqishah/ai-jobs-market-2025-2026-salaries | **Synthetic** — sequential job IDs (AIJOB0001…), fabricated demand scores, no description text |
| `atharvasoundankar/ai-job-market-global-2026` | https://www.kaggle.com/datasets/atharvasoundankar/ai-job-market-global-2026 | **Adzuna truncation** — 99% of descriptions hard-capped at 500 chars; 35% duplicate descriptions; 85% of data from 2 months |
| `nitikachandel95/global-data-science-jobs-dataset-cleaned` | https://www.kaggle.com/datasets/nitikachandel95/global-data-science-jobs-dataset-cleaned | **Adzuna truncation** — 99% capped at 500 chars; 70% empty skills field; no date column |

**Note:** Any dataset sourced from Adzuna's free API tier will have the 500-character description truncation. Avoid these.

---

## Coverage Summary

| Period | Dataset | Roles covered | Usable postings |
|---|---|---|---|
| ~2020 | `glassdoor_2020` | DS, MLE, Analyst, DE | 672 |
| Nov 2022 – Apr 2025 | `lukebarousse_analyst` | Data Analyst only | 61,953 |
| Apr 2024 | `linkedin_arshkon` | All DS roles | 123,849 (1,521 DS-adjacent) |
| Apr 2026 | `open_apply_2026` | All DS/AI roles | ~8,203 DS-adjacent |

---

## Datasets Still to Evaluate

| Gap | Priority | Candidates |
|---|---|---|
| Multi-role time series 2021–2023 | High | `asaniczka/data-scientist-linkedin-job-postings`, HuggingFace job posting repos |
| Stack Overflow Developer Survey (practitioner self-report) | Medium | Download directly from stackoverflow.com/research (2020–2024 annual CSVs) |
