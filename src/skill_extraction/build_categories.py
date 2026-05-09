"""
Build taxonomy/skills_categories.csv
Maps each canonical skill to a two-level category hierarchy and platform family.

Level 1 — category: broad grouping (language, ml_framework, genai, etc.)
Level 2 — subcategory: named slot for the most important skills within a category;
           everything else → "Other {Category}" (e.g., "Other Languages")

Opus assigns: category + platform_family  (reliable, two fields)
Python assigns: subcategory               (deterministic, no LLM variability)

Usage:
    python -m src.skill_extraction.build_categories
"""

import csv
import io
import sys
from collections import Counter

import anthropic
import yaml

from .config import PASS2_OUTPUT, TAXONOMY_DIR

OUTPUT_PATH = TAXONOMY_DIR / "skills_categories.csv"
BATCH_SIZE = 300  # ~3,000 output tokens per batch — safely under 8,192 limit

# ── Level 2: named subcategory slots ────────────────────────────────────────
# Key insight: the most important skills within each category get their own
# named slot; everything else rolls up to "Other {Category}".
# Values are lowercase match patterns against canonical_name.lower().
# Order within each dict does not matter — first match wins.

NAMED_SLOTS: dict[str, dict[str, list[str]]] = {
    "language": {
        "Python": ["python"],
        "R":      ["r"],
        "SQL":    ["sql"],
        "Scala":  ["scala"],                # Spark/data-eng language; tracks Python displacement
        "SAS":    ["sas"],                  # legacy enterprise/pharma signal; expect 2020 decline
    },
    "ml_framework": {
        "PyTorch":      ["pytorch"],
        "TensorFlow":   ["tensorflow"],
        "scikit-learn": ["scikit-learn", "scikit learn", "sklearn"],
        "XGBoost":      ["xgboost"],        # quintessential 2020-era DS tool
        "LightGBM":     ["lightgbm"],
        "Keras":        ["keras"],          # was dominant pre-PyTorch era
        "Reinforcement Learning": ["reinforcement learning", "inverse reinforcement learning",
                                   "imitation learning"],
        "Computer Vision": ["computer vision", "3d computer vision", "object detection",
                            "image recognition", "image classification", "semantic segmentation",
                            "pose estimation", "visual classification", "object classification",
                            "object tracking"],
        "NLP": ["nlp", "natural language understanding", "named entity recognition",
                "sentiment analysis", "text classification", "entity recognition",
                "entity extraction"],
    },
    "genai": {
        "LLM":                ["llm", "llms", "large language models"],
        "RAG":                ["rag", "retrieval augmented generation",
                               "retrieval-augmented generation"],
        "Fine-tuning":        ["fine-tuning", "fine tuning", "finetuning",
                               "llm fine-tuning", "model fine-tuning"],
        "Agents":             ["agents", "ai agents", "llm agents",
                               "autonomous agents", "agentic workflows"],
        "Prompt Engineering": ["prompt engineering"],
        "Vector Databases":   ["vector databases", "vector search", "pinecone", "chroma",
                               "weaviate", "milvus", "qdrant", "faiss", "pgvector"],
        "LangChain":          ["langchain", "langgraph", "langsmith"],
        "Hugging Face":       ["hugging face", "hugging face transformers"],
    },
    "data_engineering": {
        "Apache Spark":   ["apache spark", "pyspark", "spark sql", "spark scala",
                           "spark streaming"],
        "Apache Airflow": ["apache airflow", "airflow", "amazon mwaa", "mwaa",
                           "cloud composer", "astronomer"],
        "dbt":            ["dbt", "dbt cloud"],
        "Apache Kafka":   ["apache kafka", "kafka streams", "msk"],
        "Apache Flink":   ["apache flink", "flink"],
        "ETL":            ["etl", "elt", "etl/elt", "etl pipelines", "etl processes",
                           "etl design and development", "etl development", "etl tools"],
    },
    "data_platform": {
        "Snowflake":       ["snowflake", "snowpark", "snowpipe", "snowsql"],
        "Databricks":      ["databricks", "databricks sql", "azure databricks",
                            "databricks workflows"],
        "BigQuery":        ["bigquery", "google bigquery"],
        "Amazon Redshift": ["amazon redshift", "redshift spectrum"],
        "PostgreSQL":      ["postgresql"],
        "Delta Lake":      ["delta lake", "delta tables", "delta sharing"],
    },
    "cloud_infra": {
        "AWS":        ["aws", "amazon web services"],
        "GCP":        ["gcp", "google cloud platform", "google cloud"],
        "Azure":      ["azure", "microsoft azure"],
        "Kubernetes": ["kubernetes", "gke", "amazon eks", "azure kubernetes service",
                       "openshift"],
        "Docker":     ["docker", "docker compose"],
        "Terraform":  ["terraform"],
    },
    "analytics_bi": {
        "Tableau":    ["tableau", "tableau desktop", "tableau online", "tableau server",
                       "tableau prep", "tableau prep builder"],
        "Power BI":   ["power bi", "microsoft power bi", "power bi desktop"],
        "Looker":     ["looker", "looker studio", "lookml"],
        "Excel":      ["microsoft excel", "excel"],
        "Matplotlib": ["matplotlib", "seaborn"],
        "Jupyter":    ["jupyter", "jupyter notebook", "jupyterlab"],
    },
    "statistical_method": {
        "A/B Testing":      ["a/b testing", "ab testing", "a/b test", "a/b tests"],
        "Causal Inference": ["causal inference"],
        "Bayesian Methods": ["bayesian methods", "bayesian statistics",
                             "bayesian inference", "bayesian"],
        "Statistics":       ["statistics", "statistical methods", "statistical analysis",
                             "statistical modeling", "statistical learning",
                             "statistical machine learning", "statistical significance",
                             "statistical testing", "statistical inference",
                             "statistical concepts", "statistical rigor",
                             "statistical programming", "statistical software",
                             "applied statistics", "descriptive statistics",
                             "inferential statistics", "probability and statistics",
                             "probability", "probability distributions", "advanced statistics"],
        "Regression":       ["regression", "linear regression", "logistic regression",
                             "multiple regression", "multivariate regression",
                             "regression analysis", "regression modeling",
                             "generalized linear models", "linear models"],
        "Time Series":      ["time series", "time series analysis", "time series forecasting",
                             "time series modeling", "time series data", "arima", "sarima"],
        "Experimentation":  ["experimentation", "experimental design", "design of experiments",
                             "online experimentation", "randomized controlled experiments",
                             "sequential testing", "incrementality testing",
                             "quasi-experimental design"],
    },
    "mlops": {
        "MLflow":           ["mlflow"],
        "Kubeflow":         ["kubeflow"],
        "Weights & Biases": ["weights & biases"],
        "SageMaker":        ["amazon sagemaker", "sagemaker pipelines",
                             "sagemaker feature store", "sagemaker model registry"],
    },
    "role_adjacent": {},  # no named slots — everything is "Other Role Adjacent"
}

FALLBACK_SUBCATEGORY: dict[str, str] = {
    "language":           "Other Languages",
    "ml_framework":       "Other ML Frameworks",
    "genai":              "Other GenAI",
    "data_engineering":   "Other Data Engineering",
    "data_platform":      "Other Data Platforms",
    "cloud_infra":        "Other Cloud",
    "analytics_bi":       "Other BI & Analytics",
    "statistical_method": "Other Statistical Methods",
    "mlops":              "Other MLOps",
    "role_adjacent":      "Other Role Adjacent",
    "unclassified":       "Unclassified",
}


def assign_subcategory(canonical_name: str, category: str) -> str:
    """Deterministic subcategory assignment — no LLM involved."""
    name_lower = canonical_name.lower().strip()
    for slot_name, patterns in NAMED_SLOTS.get(category, {}).items():
        if name_lower in patterns:
            return slot_name
    return FALLBACK_SUBCATEGORY.get(category, f"Other {category.replace('_', ' ').title()}")


# ── Opus prompt — assigns category + platform_family only ───────────────────

CATEGORIES_DEF = """\
language           - Programming/query languages (Python, R, SQL, Scala, Go, Julia, Bash)
ml_framework       - ML/DL libraries and frameworks (PyTorch, TensorFlow, scikit-learn, XGBoost, JAX, LightGBM)
genai              - LLM-era and generative AI (LLM, RAG, fine-tuning, prompt engineering, agents, vector databases, embeddings, LLM evaluation, diffusion models)
mlops              - ML lifecycle and deployment (MLflow, Kubeflow, model monitoring, feature stores, CI/CD for ML, model serving, experiment tracking)
data_engineering   - Data movement and transformation (ETL, ELT, dbt, Apache Spark, Kafka, Airflow, Flink, data pipelines, data quality)
data_platform      - Data warehouse/lakehouse platforms (Snowflake, Databricks, BigQuery, Redshift, Delta Lake, Apache Iceberg)
cloud_infra        - Cloud platforms and general infrastructure (AWS, GCP, Azure, Kubernetes, Docker, Terraform, CI/CD)
analytics_bi       - BI tools and analytics (Tableau, Power BI, Looker, Google Analytics, Plotly, Matplotlib, Excel)
statistical_method - Statistical and quantitative methods (A/B testing, causal inference, Bayesian methods, regression, hypothesis testing, time series, experiment design)
role_adjacent      - Domain knowledge, soft skills, processes, and non-technical tools (communication, product sense, Jira, Salesforce, agile, finance domain)
"""

SYSTEM_PROMPT = f"""\
You are categorizing data science job posting skills for a research article about how data science roles evolved from 2020 to 2026.

## Categories — use exactly these 10 strings:
{CATEGORIES_DEF}

## Platform Family Rules
Assign platform_family ONLY when the skill is a specific product within a larger vendor suite.
- "Databricks SQL" → platform_family: Databricks
- "Amazon S3" → platform_family: AWS
- "Google BigQuery" → platform_family: GCP
- "Azure DevOps" → platform_family: Azure
- "Hugging Face Transformers" → platform_family: Hugging Face
- "OpenAI API" → platform_family: OpenAI
Leave platform_family EMPTY for standalone tools, languages, methods, and open-source projects.
- Python → empty, PyTorch → empty, A/B Testing → empty, dbt → empty, Apache Spark → empty

## Output Format
Return ONLY a CSV with exactly 3 columns, NO header row:
canonical_name,category,platform_family

Rules:
- canonical_name must be copied EXACTLY as given (same casing, same spelling)
- category must be one of the 10 strings above
- platform_family is a short vendor name or empty string
- One row per skill — do not skip any
- Wrap values in double quotes only if they contain a comma
"""


def parse_csv_response(text: str) -> list[dict]:
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
                "canonical_name":  row[0].strip(),
                "category":        row[1].strip(),
                "platform_family": row[2].strip(),
            })
    return rows


def categorize_batch(client: anthropic.Anthropic, skills: list[str]) -> list[dict]:
    skills_block = "\n".join(skills)
    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=8192,
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
    return parse_csv_response(response.content[0].text)


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
    print(f"  Sending in {total_batches} batches of ~{BATCH_SIZE} skills...")

    all_rows: list[dict] = []
    for i in range(0, len(skills), BATCH_SIZE):
        batch = skills[i: i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(f"  Batch {batch_num}/{total_batches}...", end=" ", flush=True)
        rows = categorize_batch(client, batch)
        all_rows.extend(rows)
        print(f"{len(rows)} rows returned")

    # Fill in any skills Opus missed
    returned_names = {r["canonical_name"] for r in all_rows}
    missing = [s for s in skills if s not in returned_names]
    if missing:
        print(f"\nWARNING: {len(missing)} skills missing from Opus response — marked unclassified:")
        for s in missing[:20]:
            print(f"  {s}")
        for s in missing:
            all_rows.append({"canonical_name": s, "category": "unclassified", "platform_family": ""})

    # Assign subcategory deterministically
    for row in all_rows:
        row["subcategory"] = assign_subcategory(row["canonical_name"], row["category"])

    # Sort alphabetically
    all_rows.sort(key=lambda r: r["canonical_name"].lower())

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["canonical_name", "category", "subcategory", "platform_family"]
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nSaved {len(all_rows):,} rows to {OUTPUT_PATH}")

    # Summary
    cats = Counter(r["category"] for r in all_rows)
    subcats = Counter(r["subcategory"] for r in all_rows)

    print("\nCategory distribution:")
    for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {cat:<22} {count:>4}")

    print("\nNamed subcategory slots found:")
    named = {
        sub: cnt for sub, cnt in subcats.items()
        if not sub.startswith("Other ") and sub != "Unclassified"
    }
    for sub, cnt in sorted(named.items(), key=lambda x: x[0]):
        print(f"  {sub:<25} {cnt:>4} canonical skill(s)")

    if cats.get("unclassified", 0):
        print(f"\nWARNING: {cats['unclassified']} unclassified skills — review before analysis.")


if __name__ == "__main__":
    run_build_categories()
