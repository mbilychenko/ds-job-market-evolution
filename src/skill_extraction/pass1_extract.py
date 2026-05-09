"""
Pass 1 — Skill Extraction
Sends batches of 5 job descriptions to Claude Sonnet and returns raw skill lists.

Usage:
    python -m src.skill_extraction.pass1_extract          # resume from checkpoint
    python -m src.skill_extraction.pass1_extract --fresh  # start from scratch
"""

import asyncio
import json
import logging
import sys
from collections import Counter
from pathlib import Path

import anthropic
import pandas as pd
from tqdm import tqdm

from .config import (
    PASS1_BATCH_SIZE,
    PASS1_CHECKPOINT_EVERY,
    PASS1_CONCURRENCY,
    PASS1_INPUT,
    PASS1_MAX_TOKENS,
    PASS1_MODEL,
    PASS1_OUTPUT,
    VOCAB_MIN_COUNT,
)

log = logging.getLogger(__name__)

# System prompt is constant across all 655 calls → Sonnet caches it after first request.
EXTRACTION_SYSTEM_PROMPT = """\
You are extracting technical skills from data science, machine learning, and data engineering job descriptions.

For each job description, extract ALL technical skills explicitly mentioned as required or preferred.

Focus on:
- Programming languages (Python, R, SQL, Scala, Java, Go, C++, Bash, etc.)
- ML/AI frameworks and libraries (PyTorch, TensorFlow, scikit-learn, Hugging Face, LangChain, etc.)
- Cloud platforms and infrastructure (AWS, GCP, Azure, Kubernetes, Docker, Terraform, etc.)
- Data platforms and tools (Spark, Kafka, Airflow, dbt, Snowflake, Databricks, Redshift, etc.)
- ML concepts and methods (deep learning, NLP, computer vision, reinforcement learning, RAG, fine-tuning, etc.)
- LLM-era skills (vector databases, embeddings, agents, prompt engineering, LLM evaluation, etc.)
- Statistical and analytical methods (A/B testing, causal inference, hypothesis testing, Bayesian methods, etc.)
- Visualization tools (Tableau, Power BI, Plotly, Matplotlib, Seaborn, etc.)
- MLOps and deployment (MLflow, Kubeflow, CI/CD, model monitoring, feature stores, etc.)

Rules:
- Extract ONLY skills required or preferred for the role. Skip generic business language ("communication", "teamwork").
- Do NOT extract skills mentioned in negation ("no experience in X required", "X not required").
- Do NOT extract skills from company descriptions only — focus on role requirements.
- Use the exact lowercase phrasing from the text. Do not rephrase or standardize yet.
- Include each skill once, even if it appears multiple times.

Return ONLY a valid JSON object. No commentary, no markdown fences.
Format: {"posting_id": ["skill1", "skill2", ...], ...}
"""


def load_clean_postings(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    # Fix residual Open-Apply date artifacts (documented in 02_cleaning_process.md)
    df = df[~((df["source"] == "open_apply_2026") & (df["year"] < 2025))]
    return df[~df["is_duplicate"]].reset_index(drop=True)


def make_batches(df: pd.DataFrame, batch_size: int) -> list[dict[str, str]]:
    batches = []
    for i in range(0, len(df), batch_size):
        chunk = df.iloc[i : i + batch_size]
        batch = {row["posting_id"]: row["description_text"] for _, row in chunk.iterrows()}
        batches.append(batch)
    return batches


def parse_json_response(text: str) -> dict[str, list[str]]:
    text = text.strip()
    # Strip markdown fences if model wraps response
    if text.startswith("```"):
        lines = text.splitlines()
        inner_start = 1
        inner_end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[inner_start:inner_end])
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass
    # Last resort: find first {...} block
    start, end = text.find("{"), text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            result = json.loads(text[start:end])
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass
    log.warning("Could not parse JSON from response; returning empty dict")
    return {}


async def process_batch(
    client: anthropic.AsyncAnthropic,
    semaphore: asyncio.Semaphore,
    batch: dict[str, str],
    batch_idx: int,
) -> tuple[int, dict[str, list[str]]]:
    async with semaphore:
        for attempt in range(6):
            try:
                response = await client.messages.create(
                    model=PASS1_MODEL,
                    max_tokens=PASS1_MAX_TOKENS,
                    system=[
                        {
                            "type": "text",
                            "text": EXTRACTION_SYSTEM_PROMPT,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    messages=[
                        {
                            "role": "user",
                            "content": json.dumps(batch, ensure_ascii=False),
                        }
                    ],
                )
                parsed = parse_json_response(response.content[0].text)
                return batch_idx, parsed
            except anthropic.RateLimitError:
                wait = 30 * (2**attempt)  # 30s, 60s, 120s, 240s, 480s, 960s
                log.warning(f"Rate limit on batch {batch_idx}, retrying in {wait}s")
                await asyncio.sleep(wait)
            except anthropic.APIStatusError as e:
                log.warning(f"API error on batch {batch_idx} attempt {attempt + 1}: {e}")
                if attempt < 5:
                    await asyncio.sleep(15 * (2**attempt))
            except Exception as e:
                log.error(f"Unexpected error on batch {batch_idx}: {e}")
                break
        return batch_idx, {}


async def run_pass1(resume: bool = True, limit: int | None = None) -> dict[str, list[str]]:
    output_path = PASS1_OUTPUT if not limit else PASS1_OUTPUT.parent / "pass1_dry_run.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    raw_extractions: dict[str, list[str]] = {}
    if resume and not limit and output_path.exists():
        with open(output_path) as f:
            raw_extractions = json.load(f)
        print(f"Checkpoint loaded: {len(raw_extractions):,} postings already processed")

    df = load_clean_postings(PASS1_INPUT)
    if limit:
        df = df.head(limit)
        print(f"DRY RUN — limited to {limit} postings")
    print(f"Clean postings: {len(df):,}")
    print(f"Source breakdown:\n{df['source'].value_counts().to_string()}")

    batches = make_batches(df, PASS1_BATCH_SIZE)

    already_done = set(raw_extractions.keys())
    pending = [
        (i, batch)
        for i, batch in enumerate(batches)
        if not all(pid in already_done for pid in batch)
    ]
    print(f"\nBatches pending: {len(pending):,} / {len(batches):,}")

    if not pending:
        print("All batches already processed — nothing to do.")
        return raw_extractions

    client = anthropic.AsyncAnthropic()
    semaphore = asyncio.Semaphore(PASS1_CONCURRENCY)

    tasks = [process_batch(client, semaphore, batch, idx) for idx, batch in pending]

    completed = 0
    with tqdm(total=len(tasks), desc="Pass 1 — extracting skills", unit="batch") as pbar:
        for coro in asyncio.as_completed(tasks):
            _, result = await coro
            raw_extractions.update(result)
            completed += 1
            pbar.update(1)
            pbar.set_postfix({"postings": len(raw_extractions)})

            if completed % PASS1_CHECKPOINT_EVERY == 0:
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(raw_extractions, f, indent=2)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(raw_extractions, f, indent=2)

    print(f"\nPass 1 complete — {len(raw_extractions):,} postings saved to {output_path}")
    return raw_extractions


def print_vocab_stats(raw_extractions: dict[str, list[str]]) -> None:
    all_terms = [term for skills in raw_extractions.values() for term in skills]
    vocab = Counter(all_terms)

    total = len(raw_extractions)
    empty = sum(1 for s in raw_extractions.values() if not s)

    print("\n--- Vocabulary Statistics ---")
    print(f"Postings processed:      {total:,}")
    print(f"Postings with no skills: {empty:,} ({empty / total * 100:.1f}%)")
    print(f"Total term occurrences:  {len(all_terms):,}")
    print(f"Unique terms:            {len(vocab):,}")
    print(
        f"Terms (count >= {VOCAB_MIN_COUNT}):       "
        f"{sum(1 for c in vocab.values() if c >= VOCAB_MIN_COUNT):,}"
    )
    print(f"\nTop 30 most frequent terms:")
    for term, count in vocab.most_common(30):
        pct = count / total * 100
        print(f"  {count:5d}  ({pct:4.1f}%)  {term}")

    print("\n--- Sanity check (expected ranges) ---")
    checks = {
        "python": (0.80, "should be >80%"),
        "sql": (0.60, "should be >60%"),
        "machine learning": (0.40, "should be >40%"),
    }
    # Sum counts across all case variants (e.g. "python" + "Python" → same key)
    lower: Counter = Counter()
    for k, v in vocab.items():
        lower[k.lower()] += v
    for term, (threshold, label) in checks.items():
        prevalence = lower.get(term, 0) / total
        status = "OK" if prevalence >= threshold else "LOW — check extraction"
        print(f"  {term:25s}  {prevalence:.1%}  ({label})  [{status}]")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    resume = "--fresh" not in sys.argv

    limit: int | None = None
    for arg in sys.argv[1:]:
        if arg.startswith("--limit="):
            limit = int(arg.split("=")[1])

    results = asyncio.run(run_pass1(resume=resume, limit=limit))
    print_vocab_stats(results)
