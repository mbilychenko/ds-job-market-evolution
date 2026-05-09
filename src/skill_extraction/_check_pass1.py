import json
import statistics
import pandas as pd
from collections import Counter

with open("Data/interim/pass1_raw_extractions.json") as f:
    data = json.load(f)

df = pd.read_parquet("Data/processed/postings_unified.parquet")
df = df[~((df["source"] == "open_apply_2026") & (df["year"] < 2025))]
clean = df[~df["is_duplicate"]].reset_index(drop=True)

total_expected = len(clean)
total_extracted = len(data)
missing_ids = set(clean["posting_id"]) - set(data.keys())
empty = sum(1 for v in data.values() if not v)

print("=== Coverage ===")
print(f"Expected clean postings:  {total_expected:,}")
print(f"Postings in JSON:         {total_extracted:,}")
print(f"Missing from JSON:        {len(missing_ids):,}")
print(f"Postings with no skills:  {empty:,} ({empty/total_extracted*100:.1f}%)")

print("\n=== Coverage by source ===")
for src in clean["source"].unique():
    src_ids = set(clean[clean["source"] == src]["posting_id"])
    covered = len(src_ids & set(data.keys()))
    print(f"  {src:25s}  {covered:,} / {len(src_ids):,}  ({covered/len(src_ids)*100:.1f}%)")

print("\n=== Skills per posting (distribution) ===")
skill_counts = [len(v) for v in data.values()]
print(f"  Median:  {statistics.median(skill_counts):.0f}")
print(f"  Mean:    {statistics.mean(skill_counts):.1f}")
print(f"  Min:     {min(skill_counts)}")
print(f"  Max:     {max(skill_counts)}")
print(f"  Zero:    {skill_counts.count(0)} postings")

print("\n=== Skills per posting by source ===")
id_to_source = dict(zip(clean["posting_id"], clean["source"]))
by_source = {}
for pid, skills in data.items():
    src = id_to_source.get(pid, "unknown")
    by_source.setdefault(src, []).append(len(skills))
for src, counts in sorted(by_source.items()):
    print(f"  {src:25s}  median={statistics.median(counts):.0f}  mean={statistics.mean(counts):.1f}")

print("\n=== Top 20 skills overall ===")
all_terms = [t for skills in data.values() for t in skills]
vocab = Counter(all_terms)
for term, count in vocab.most_common(20):
    pct = count / total_extracted * 100
    print(f"  {count:5d}  ({pct:5.1f}%)  {term}")

print("\n=== Sanity checks ===")
checks = {
    "python": (0.80, ">80%"),
    "sql":    (0.60, ">60%"),
    "machine learning": (0.40, ">40%"),
    "llm":    (0.00, "present in 2026 postings"),
}
lower_vocab: Counter = Counter()
for k, v in vocab.items():
    lower_vocab[k.lower()] += v
for term, (threshold, label) in checks.items():
    pct = lower_vocab.get(term, 0) / total_extracted
    status = "OK" if pct >= threshold else "LOW"
    print(f"  {term:25s}  {pct:.1%}  (expected {label})  [{status}]")

print("\n=== 5 random spot-checks ===")
import random
random.seed(42)
sample_ids = random.sample(list(data.keys()), 5)
id_to_desc = dict(zip(clean["posting_id"], clean["description_text"]))
id_to_title = dict(zip(clean["posting_id"], clean["canonical_title"]))
for pid in sample_ids:
    title = id_to_title.get(pid, "?")
    desc_snippet = id_to_desc.get(pid, "")[:120].replace("\n", " ")
    skills = data[pid]
    print(f"\n  [{pid}] {title}")
    print(f"  Desc: {desc_snippet}...")
    print(f"  Skills ({len(skills)}): {skills[:10]}")
