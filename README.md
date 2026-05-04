# Data Science Job Market — Data Collection & Analysis

A dataset collection and analysis pipeline tracking how data science roles and required skills have evolved from 2020 to 2026, based on job posting data from multiple sources.

---

## What This Repository Contains

This project assembles, cleans, and analyzes job posting data for data science-adjacent roles (Data Scientist, ML Engineer, Data Analyst, AI Engineer, Analytics Engineer, and related titles) across multiple years and sources. The goal is to quantify shifts in skill demand, role definitions, and title distribution over time.

---

## Repository Structure

```
.
├── Data/
│   ├── raw/                  # Original downloaded datasets (not tracked by git — see below)
│   │   └── README.md         # Full source documentation, audit findings, download instructions
│   ├── interim/              # Partially cleaned, source-specific files
│   └── processed/            # Final merged, deduplicated, analysis-ready data
├── taxonomy/
│   └── skills_taxonomy.csv   # Canonical skill list with synonyms and categories
├── notebooks/
│   ├── 01_data_audit.ipynb   # Per-source schema inspection and quality checks
│   ├── 02_cleaning.ipynb     # Deduplication, normalization, skill extraction
│   ├── 03_analysis.ipynb     # Frequency trends, co-occurrence, role distribution
│   └── 04_visualization.ipynb
├── src/
│   ├── clean.py              # Cleaning utilities
│   ├── extract_skills.py     # Regex-based skill extraction against taxonomy
│   └── normalize_titles.py   # Job title → canonical role mapping
├── outputs/
│   ├── figures/              # Publication-quality charts
│   └── tables/               # CSV exports of key findings
├── requirements.txt
└── README.md
```

---

## Data Sources

Raw data files are not tracked in git (sizes range from 3 MB to 207 MB). See [`Data/raw/README.md`](Data/raw/README.md) for full audit notes on each source including exact date ranges, schema, known quality issues, and download instructions.

| # | Dataset | Source | Coverage | Postings | Status |
|---|---|---|---|---|---|
| 1 | Glassdoor DS Job Postings | [Kaggle](https://www.kaggle.com/datasets/rashikrahmanpritom/data-science-job-posting-on-glassdoor) | ~2020 | 672 | Used — 2020 baseline |
| 2 | Data Analyst Job Postings (Google Search) | [Kaggle](https://www.kaggle.com/datasets/lukebarousse/data-analyst-job-postings-google-search) | Nov 2022 – Apr 2025 | 61,953 | Used — analyst time series |
| 3 | LinkedIn Job Postings | [Kaggle](https://www.kaggle.com/datasets/arshkon/linkedin-job-postings) | Apr 2024 (single snapshot) | 123,849 | Used — multi-role cross-section |
| 4 | Open-Apply Jobs (ATS live feed) | [HuggingFace](https://huggingface.co/datasets/edwarddgao/open-apply-jobs) | Apr 2026 snapshot | ~231,000 (8,203 DS-adjacent) | Used — 2026 endpoint |

### Downloading the data

**Kaggle datasets** — requires a Kaggle account and API key ([setup guide](https://www.kaggle.com/docs/api)):

```bash
# Place your kaggle.json at ~/.kaggle/kaggle.json first
pip install kaggle

kaggle datasets download -d rashikrahmanpritom/data-science-job-posting-on-glassdoor -p Data/raw/glassdoor_2020 --unzip
kaggle datasets download -d lukebarousse/data-analyst-job-postings-google-search -p Data/raw/lukebarousse_analyst --unzip
kaggle datasets download -d arshkon/linkedin-job-postings -p Data/raw/linkedin_arshkon --unzip
```

**HuggingFace dataset** — downloads the April 17 2026 snapshot across all three ATS sources:

```python
from huggingface_hub import HfFileSystem
import shutil

fs = HfFileSystem()
sources = ['greenhouse', 'lever', 'ashby']

for src in sources:
    remote = f'datasets/edwarddgao/open-apply-jobs/data/date=2026-04-17/source={src}/part.parquet'
    with fs.open(remote, 'rb') as r, open(f'Data/raw/open_apply_2026/{src}.parquet', 'wb') as w:
        shutil.copyfileobj(r, w)
```

---

## Setup

```bash
git clone <repo-url>
cd <repo-name>

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

Then download the raw data using the instructions above before running any notebooks.

---

## Skills Taxonomy

The file `taxonomy/skills_taxonomy.csv` is the central reference for skill extraction across all datasets. It maps messy free-text terms to canonical skill names.

| Column | Description |
|---|---|
| `canonical_name` | The term used in all analysis and charts |
| `aliases` | Pipe-separated synonyms matched case-insensitively in job descriptions |
| `category` | One of: `language`, `framework_library`, `platform_cloud`, `concept_method`, `tool_viz`, `role_adjacent` |
| `introduced` | Approximate year the term entered mainstream usage |

Contributions and corrections to the taxonomy are welcome via pull request.

---

## Reproducibility

All analysis is intended to be fully reproducible from raw data:

1. Download raw data (instructions above)
2. Run `notebooks/01_data_audit.ipynb` — verifies source integrity
3. Run `notebooks/02_cleaning.ipynb` — produces `Data/processed/postings.parquet`
4. Run `notebooks/03_analysis.ipynb` — produces tables in `outputs/tables/`
5. Run `notebooks/04_visualization.ipynb` — produces charts in `outputs/figures/`

No hardcoded local paths. All paths are relative to the repository root.

---

## Key Design Decisions

- **Unit of analysis:** individual job postings, not monthly aggregates
- **Geography:** US postings only for primary analysis; non-US reported separately
- **Skill extraction:** regex matching against the curated taxonomy (not NER or LLM-based)
- **Deduplication:** postings flagged as duplicates if they share company + normalized title within a 30-day window
- **Role normalization:** raw titles mapped to canonical roles (Data Scientist, ML Engineer, Analytics Engineer, AI Engineer, Data Analyst, Data Engineer, Research Scientist, Other)

---

## License

Code: MIT

Data: subject to the terms of each upstream source. See [`Data/raw/README.md`](Data/raw/README.md) for per-dataset license notes.
