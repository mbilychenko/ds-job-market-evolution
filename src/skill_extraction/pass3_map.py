"""
Pass 3 — Deterministic Skill Mapping
Applies the frozen skills_dictionary.yaml to populate skills_present in the parquet.

Usage:
    python -m src.skill_extraction.pass3_map
"""

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import yaml

from .config import PASS1_OUTPUT, PASS2_OUTPUT, PROCESSED_DIR

PARQUET_PATH = PROCESSED_DIR / "postings_unified.parquet"


def build_reverse_lookup(skill_dict: dict) -> dict[str, str]:
    reverse: dict[str, str] = {}
    for canonical, synonyms in skill_dict.items():
        if not synonyms:
            continue
        for term in synonyms:
            reverse[term.lower()] = canonical
    return reverse


def map_to_canonical(raw_skills: list[str], reverse_lookup: dict[str, str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for term in raw_skills:
        canonical = reverse_lookup.get(term.lower())
        if canonical and canonical not in seen:
            result.append(canonical)
            seen.add(canonical)
    return result


def run_pass3() -> None:
    for path, label in [(PASS2_OUTPUT, "skills_dictionary.yaml"), (PASS1_OUTPUT, "pass1_raw_extractions.json"), (PARQUET_PATH, "postings_unified.parquet")]:
        if not path.exists():
            print(f"ERROR: {label} not found at {path}")
            sys.exit(1)

    print("Loading frozen skills dictionary...")
    with open(PASS2_OUTPUT, encoding="utf-8") as f:
        content = f.read()
    yaml_body = content.split("\n\n", 1)[1] if "\n\n" in content else content
    skill_dict = yaml.safe_load(yaml_body)
    reverse_lookup = build_reverse_lookup(skill_dict)
    print(f"  {len(skill_dict):,} canonical skills, {len(reverse_lookup):,} raw term mappings")

    print("Loading Pass 1 raw extractions...")
    with open(PASS1_OUTPUT, encoding="utf-8") as f:
        raw_extractions: dict[str, list[str]] = json.load(f)
    print(f"  {len(raw_extractions):,} postings with raw skill lists")

    print("Loading parquet...")
    df = pd.read_parquet(PARQUET_PATH)
    print(f"  {len(df):,} rows")

    print("Mapping skills...")
    df["skills_present"] = df["posting_id"].map(
        lambda pid: map_to_canonical(raw_extractions.get(pid, []), reverse_lookup)
    )

    # Log unmapped terms
    all_raw = [t for skills in raw_extractions.values() for t in skills]
    unmapped = [t for t in all_raw if t.lower() not in reverse_lookup]
    unmapped_counts = Counter(unmapped)
    top_unmapped = unmapped_counts.most_common(20)
    print(f"\nUnmapped terms: {len(set(unmapped)):,} unique, {len(unmapped):,} total occurrences")
    print("Top 20 unmapped (candidates to add to YAML):")
    for term, count in top_unmapped:
        print(f"  {count:4d}x  {term}")

    # Validation
    clean = df[~df["is_duplicate"]]
    empty = (clean["skills_present"].map(len) == 0).sum()
    print(f"\nValidation:")
    print(f"  Clean (non-duplicate) postings: {len(clean):,}")
    print(f"  Postings with zero skills:       {empty} ({empty/len(clean)*100:.1f}%)")
    print(f"  Median skills per posting:       {clean['skills_present'].map(len).median():.0f}")
    print(f"  Mean skills per posting:         {clean['skills_present'].map(len).mean():.1f}")

    print("\nMedian skills per posting by source:")
    for source, grp in clean.groupby("source"):
        print(f"  {source}: {grp['skills_present'].map(len).median():.0f}")

    print("\nSaving parquet...")
    df.to_parquet(PARQUET_PATH, index=False)
    print(f"  Saved {len(df):,} rows to {PARQUET_PATH}")


if __name__ == "__main__":
    run_pass3()
