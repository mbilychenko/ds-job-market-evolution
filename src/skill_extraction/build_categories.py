"""
Build taxonomy/skills_categories.csv
Maps each canonical skill to a high-level category and platform family.

Usage:
    python -m src.skill_extraction.build_categories
"""

import csv
import io
import sys
from pathlib import Path

import anthropic
import yaml

from .config import PASS2_OUTPUT, TAXONOMY_DIR

OUTPUT_PATH = TAXONOMY_DIR / "skills_categories.csv"
BATCH_SIZE = 550  # ~3,300 output tokens per batch — safely under 8,192 limit

CATEGORIES = """
language           - Programming/query languages: Python, R, SQL, Scala, Go, Julia
ml_framework       - ML/DL libraries and frameworks: PyTorch, TensorFlow, scikit-learn, XGBoost, JAX
genai              - LLM-era and generative AI skills: LLM, RAG, fine-tuning, prompt engineering, agents, vector databases, embeddings, LLM evaluation
mlops              - ML lifecycle and deployment: MLflow, Kubeflow, model monitoring, feature stores, CI/CD for ML, model serving
data_engineering   - Data movement and transformation: ETL, dbt, Apache Spark, Kafka, Airflow, Flink, data pipelines
data_platform      - Data warehouse/lakehouse platforms: Snowflake, Databricks, BigQuery, Redshift, Delta Lake
cloud_infra        - Cloud platforms and infrastructure: AWS, GCP, Azure services, Kubernetes, Docker, Terraform
analytics_bi       - BI tools and analytics: Tableau, Power BI, Looker, Google Analytics, Plotly, Excel
statistical_method - Statistical and quantitative methods: A/B testing, causal inference, Bayesian methods, regression, hypothesis testing, time series
role_adjacent      - Soft skills, domain knowledge, processes: communication, product sense, stakeholder management, agile, domain-specific tools (Salesforce, Jira)
"""

SYSTEM_PROMPT = f"""You are categorizing data science job posting skills for a research article about how data science roles have evolved from 2020 to 2026.

## Categories (use exactly these strings):
{CATEGORIES}

## Platform Family Rules
- Assign a platform_family ONLY when the skill is a specific product within a larger vendor suite.
  Examples: "Databricks SQL" → Databricks, "Amazon S3" → AWS, "Google BigQuery" → GCP, "Azure DevOps" → Azure
- Leave platform_family EMPTY for standalone tools, languages, methods, and concepts.
  Examples: Python → empty, PyTorch → empty, A/B Testing → empty, dbt → empty

## Output Format
Return ONLY a CSV with exactly 3 columns and NO header row:
canonical_name,category,platform_family

Rules:
- canonical_name must be copied EXACTLY as given (same casing, same spelling)
- category must be one of the 10 strings above
- platform_family is either a short vendor name or empty
- One row per skill, no skipping
- No quotes unless the name contains a comma
"""


def parse_csv_response(text: str, expected_names: list[str]) -> list[dict]:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[1:end])

    rows = []
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        if len(row) == 2:
            row.append("")
        if len(row) >= 3:
            rows.append({
                "canonical_name": row[0].strip(),
                "category": row[1].strip(),
                "platform_family": row[2].strip(),
            })
    return rows


def categorize_batch(client: anthropic.Anthropic, skills: list[str]) -> list[dict]:
    skills_block = "\n".join(skills)
    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=4096,
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": f"Categorize these {len(skills)} skills:\n\n{skills_block}",
        }],
    )
    return parse_csv_response(response.content[0].text, skills)


def run_build_categories() -> None:
    if not PASS2_OUTPUT.exists():
        print(f"ERROR: {PASS2_OUTPUT} not found.")
        sys.exit(1)

    print("Loading skills dictionary...")
    with open(PASS2_OUTPUT, encoding="utf-8") as f:
        content = f.read()
    yaml_body = content.split("\n\n", 1)[1] if "\n\n" in content else content
    skill_dict = yaml.safe_load(yaml_body)
    skills = sorted(skill_dict.keys())
    print(f"  {len(skills):,} canonical skills to categorize")

    client = anthropic.Anthropic()
    total_batches = (len(skills) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"  Sending in {total_batches} batches of {BATCH_SIZE}...")

    all_rows: list[dict] = []
    for i in range(0, len(skills), BATCH_SIZE):
        batch = skills[i: i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(f"  Batch {batch_num}/{total_batches}...", end=" ", flush=True)
        rows = categorize_batch(client, batch)
        all_rows.extend(rows)
        print(f"{len(rows)} rows returned")

    # Fill in any skills that were missed or misnamed by Opus
    returned_names = {r["canonical_name"] for r in all_rows}
    missing = [s for s in skills if s not in returned_names]
    if missing:
        print(f"\nWARNING: {len(missing)} skills missing from response — marked as unclassified:")
        for s in missing[:20]:
            print(f"  {s}")
        for s in missing:
            all_rows.append({"canonical_name": s, "category": "unclassified", "platform_family": ""})

    # Sort by canonical name for readability
    all_rows.sort(key=lambda r: r["canonical_name"].lower())

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["canonical_name", "category", "platform_family"])
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nSaved {len(all_rows):,} rows to {OUTPUT_PATH}")

    # Category distribution summary
    from collections import Counter
    cats = Counter(r["category"] for r in all_rows)
    print("\nCategory distribution:")
    for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {cat:<22} {count:>4}")

    unclassified = cats.get("unclassified", 0)
    if unclassified > 0:
        print(f"\nWARNING: {unclassified} unclassified skills — review and fix before analysis.")


if __name__ == "__main__":
    run_build_categories()
