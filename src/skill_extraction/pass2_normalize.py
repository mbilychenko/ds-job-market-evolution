"""
Pass 2 — Canonical Normalization
Takes the raw vocabulary from Pass 1 and produces taxonomy/skills_dictionary.yaml.

Steps:
  1. Load unique vocabulary from pass1_raw_extractions.json
  2. Send batches of 300 terms directly to Claude Opus for canonical normalization
  3. Merge batch YAMLs and resolve cross-batch collisions
  4. Save frozen skills_dictionary.yaml

Usage:
    python -m src.skill_extraction.pass2_normalize
"""

import json
import logging
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import anthropic
import yaml
from rapidfuzz import fuzz, process
from tqdm import tqdm

from .config import (
    COLLISION_THRESHOLD,
    PASS1_OUTPUT,
    PASS2_BATCH_SIZE,
    PASS2_DRAFT,
    PASS2_MAX_TOKENS,
    PASS2_MODEL,
    PASS2_OUTPUT,
    VOCAB_MIN_COUNT,
)

log = logging.getLogger(__name__)

# Constant across all Opus batches — cached after first request.
NORMALIZATION_SYSTEM_PROMPT = """\
You are building a canonical skills taxonomy for data science job posting analysis.

Your task: normalize raw skill terms extracted from job postings into a clean canonical dictionary.

For each group of synonymous terms, assign ONE canonical name and list ALL raw variants that map to it (including the canonical name itself if it appears in the list).

## Canonical Name Rules
- Title Case for proper nouns: PyTorch, Apache Spark, Amazon Web Services, Hugging Face
- UPPERCASE for acronyms: SQL, NLP, RAG, LLM, API, CI/CD, MLOps, EDA
- Prefer ESCO (European Skills/Competencies) terminology where applicable
- Use the most widely recognized professional term

## Merging Rules (merge these)
- Abbreviations + full names: "k8s" + "kubernetes" → Kubernetes
- Case/punctuation variants: "pytorch", "PyTorch", "pytorch framework" → PyTorch
- Obvious abbreviations: "nlp" + "natural language processing" → NLP
- Typos and plurals: "neural network" + "neural networks" → Neural Networks

## Splitting Rules (keep these separate — do NOT merge)
- Different frameworks: PyTorch ≠ TensorFlow ≠ JAX
- Different cloud providers: AWS ≠ GCP ≠ Azure
- Different databases: SQL ≠ PostgreSQL ≠ MySQL ≠ MongoDB ≠ Redis
- LLM-era skills must remain DISTINCT:
  LLM, RAG, Vector Databases, Embeddings, Agents, Fine-tuning, Prompt Engineering,
  LLM Evaluation — these are separate skills even though they overlap
- Different abstraction levels: NLP ≠ LLM ≠ RAG ≠ Transformers

## Output Format
Return ONLY valid YAML. No commentary, no markdown fences, no code blocks.

canonical_name_1:
  - raw term 1
  - raw term 2
canonical_name_2:
  - raw term 3
"""


def load_vocab(path: Path, min_count: int) -> tuple[list[str], Counter]:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    all_terms = [t for skills in raw.values() for t in skills]
    vocab = Counter(all_terms)
    terms = sorted(term for term, count in vocab.items() if count >= min_count)
    return terms, vocab


def parse_yaml_response(text: str) -> dict[str, list[str]]:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner_end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[1:inner_end])
    try:
        result = yaml.safe_load(text)
        if isinstance(result, dict):
            return {k: v for k, v in result.items() if isinstance(v, list)}
    except yaml.YAMLError as e:
        log.warning(f"YAML parse error: {e}")
    return {}


def normalize_batch(
    client: anthropic.Anthropic, terms: list[str]
) -> dict[str, list[str]]:
    terms_block = "\n".join(f"- {t}" for t in terms)
    response = client.messages.create(
        model=PASS2_MODEL,
        max_tokens=PASS2_MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": NORMALIZATION_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": f"Normalize these {len(terms)} terms into a canonical YAML dictionary:\n\n{terms_block}",
            }
        ],
    )
    return parse_yaml_response(response.content[0].text)


def merge_batch_yamls(batch_results: list[dict[str, list[str]]]) -> dict[str, list[str]]:
    """Merge multiple batch YAML dicts; identical canonical names have their synonym lists unioned."""
    merged: dict[str, list[str]] = {}
    for batch in batch_results:
        for canonical, synonyms in batch.items():
            if canonical in merged:
                merged[canonical] = list(set(merged[canonical]) | set(synonyms))
            else:
                merged[canonical] = list(set(synonyms))
    return merged


def resolve_collisions(
    merged: dict[str, list[str]], threshold: int = COLLISION_THRESHOLD
) -> dict[str, list[str]]:
    """
    Find near-duplicate canonical names produced by different batches and merge them.
    Winner is the canonical with the most synonyms (proxy for prevalence).
    Uses fuzzy string matching on canonical names only — safe at this stage because
    canonical names are short, clean, and professionally standardized.
    """
    names = list(merged.keys())

    # Build collision clusters via fuzzy matching on canonical names
    assigned: set[str] = set()
    name_clusters: dict[str, list[str]] = {}
    for name in names:
        if name in assigned:
            continue
        candidates = [n for n in names if n not in assigned and n != name]
        if candidates:
            matches = process.extract(
                name,
                candidates,
                scorer=fuzz.token_sort_ratio,
                score_cutoff=threshold,
                limit=None,
            )
            group = [name] + [m[0] for m in matches]
        else:
            group = [name]
        name_clusters[name] = group
        assigned.update(group)

    collision_count = sum(1 for members in name_clusters.values() if len(members) > 1)
    if collision_count == 0:
        print("No cross-batch collisions detected.")
        return merged

    print(f"Resolving {collision_count} collision cluster(s):")
    result: dict[str, list[str]] = {}
    consumed: set[str] = set()

    for rep, members in name_clusters.items():
        if len(members) == 1:
            name = members[0]
            if name not in consumed:
                result[name] = merged[name]
            continue
        winner = max(members, key=lambda m: len(merged.get(m, [])))
        combined = []
        for m in members:
            combined.extend(merged.get(m, []))
        losers = [m for m in members if m != winner]
        for loser in losers:
            consumed.add(loser)
        result[winner] = list(set(combined))
        print(f"  {losers} -> {winner}")

    return result


def save_yaml(
    final_dict: dict[str, list[str]],
    output_path: Path,
    input_term_count: int,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f"# taxonomy/skills_dictionary.yaml\n"
        f"# Generated:        {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"# Model:            {PASS2_MODEL}\n"
        f"# Source:           pass1_raw_extractions.json\n"
        f"# Input terms:      {input_term_count} (vocab_min_count >= {VOCAB_MIN_COUNT})\n"
        f"# Canonical skills: {len(final_dict)}\n"
        f"# STATUS:           DRAFT — requires human review before freezing\n\n"
    )
    sorted_dict = dict(sorted(final_dict.items(), key=lambda x: x[0].lower()))
    yaml_body = yaml.dump(sorted_dict, allow_unicode=True, default_flow_style=False, sort_keys=False)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header + yaml_body)


def run_pass2() -> None:
    if not PASS1_OUTPUT.exists():
        print(f"ERROR: {PASS1_OUTPUT} not found. Run pass1_extract.py first.")
        sys.exit(1)

    print("Loading Pass 1 vocabulary...")
    terms, vocab = load_vocab(PASS1_OUTPUT, VOCAB_MIN_COUNT)
    print(f"  All unique terms: {len(vocab):,}")
    print(f"  Terms (count >= {VOCAB_MIN_COUNT}): {len(terms):,}")

    client = anthropic.Anthropic()
    total_batches = (len(terms) + PASS2_BATCH_SIZE - 1) // PASS2_BATCH_SIZE
    print(
        f"\nPass 2: sending {len(terms):,} terms to {PASS2_MODEL} "
        f"in {total_batches} batch(es) of {PASS2_BATCH_SIZE}..."
    )

    PASS2_DRAFT.parent.mkdir(parents=True, exist_ok=True)
    batch_results: list[dict[str, list[str]]] = []

    for batch_num, i in enumerate(
        tqdm(range(0, len(terms), PASS2_BATCH_SIZE), desc="Pass 2 batches"),
        start=1,
    ):
        batch = terms[i : i + PASS2_BATCH_SIZE]
        result = normalize_batch(client, batch)
        batch_results.append(result)
        log.info(f"Batch {batch_num}/{total_batches}: {len(result)} canonical skills")

        # Incremental save so human can monitor progress
        draft_so_far = merge_batch_yamls(batch_results)
        with open(PASS2_DRAFT, "w", encoding="utf-8") as f:
            yaml.dump(draft_so_far, f, allow_unicode=True, default_flow_style=False)

    print(f"\nMerging {len(batch_results)} batch result(s)...")
    merged = merge_batch_yamls(batch_results)
    print(f"  After merge: {len(merged):,} canonical skills")

    print("\nResolving cross-batch collisions...")
    final_dict = resolve_collisions(merged)

    save_yaml(final_dict, PASS2_OUTPUT, len(terms))

    print(f"\n{'=' * 60}")
    print("Pass 2 complete")
    print(f"{'=' * 60}")
    print(f"  Input terms:       {len(terms):,}")
    print(f"  Canonical skills:  {len(final_dict):,}")
    print(f"  Output:            {PASS2_OUTPUT}")
    print(f"\nDRAFT saved — human review required before freezing:")
    print(f"  [ ] Check for over-merging (skills collapsed that should be separate)")
    print(f"  [ ] Check for under-merging (synonyms left as separate canonicals)")
    print(f"  [ ] Verify LLM-era skills are distinct:")
    print(f"      LLM, RAG, Agents, Embeddings, Vector Databases, Fine-tuning,")
    print(f"      Prompt Engineering, LLM Evaluation — must NOT be merged")
    print(f"  [ ] Verify cloud providers are separate: AWS, GCP, Azure")
    print(f"  [ ] Check that 'R' (language) is handled correctly")
    print(f"\nOnce satisfied:")
    print(f"  git add taxonomy/skills_dictionary.yaml")
    print(f"  git commit -m 'freeze skills_dictionary v1.0 — N canonical skills'")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run_pass2()
