from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent

load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "Data"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
TAXONOMY_DIR = ROOT / "taxonomy"

PASS1_INPUT = PROCESSED_DIR / "postings_unified.parquet"
PASS1_OUTPUT = INTERIM_DIR / "pass1_raw_extractions.json"
PASS2_OUTPUT = TAXONOMY_DIR / "skills_dictionary.yaml"
PASS2_DRAFT = TAXONOMY_DIR / "skills_dictionary_draft.yaml"

PASS1_MODEL = "claude-sonnet-4-6"
PASS2_MODEL = "claude-opus-4-7"

PASS1_BATCH_SIZE = 5        # postings per API call
PASS1_CONCURRENCY = 10      # concurrent async requests
PASS1_MAX_TOKENS = 4096
PASS1_CHECKPOINT_EVERY = 50 # save progress every N completed batches

PASS2_BATCH_SIZE = 300      # terms per Opus call
PASS2_MAX_TOKENS = 8192

VOCAB_MIN_COUNT = 2          # drop terms seen in fewer than N postings
RAPIDFUZZ_THRESHOLD = 85     # pre-clustering similarity threshold (0–100)
COLLISION_THRESHOLD = 92     # post-merge collision detection threshold
